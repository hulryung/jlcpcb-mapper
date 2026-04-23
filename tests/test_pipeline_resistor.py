"""Integration tests for the RESISTOR category end-to-end through the new pipeline.

Covers:
1. Instance with pre-existing footprint → all_have_fp=True branch → footprint="" in Decision.
2. Instance with empty footprint → BuiltinMap hit → footprint set, downloaded=False.
"""
import sqlite3
from pathlib import Path
import pytest
from jlcpcb_mapper.core.pipeline import run_pipeline, Instance
from jlcpcb_mapper.io.parts_db import PartsDB


class _FakeLLM:
    def __init__(self):
        self.calls = 0

    def call(self, prompt, schema_keys):
        self.calls += 1
        raise AssertionError("scorer should have decided without LLM")


def _populate(conn):
    # Descriptions mirror real JLCPCB format: "Chip Resistor 10kΩ 1% ..."
    # The leading space before the SI token (e.g. " 10kΩ") is load-bearing —
    # it prevents "110kΩ" from matching a "10kΩ" query.
    conn.executescript("""
        CREATE TABLE parts (
            lcsc TEXT PRIMARY KEY, category TEXT, mfr TEXT, mfr_part TEXT,
            package TEXT, description TEXT, basic INTEGER, preferred INTEGER,
            stock INTEGER, price REAL
        );
        -- C1: expected winner — basic, high stock, correct package + value
        INSERT INTO parts VALUES (
            'C1', 'Chip Resistor - Surface Mount', 'Yageo', 'RC0402FR-0710KL',
            '0402', 'Chip Resistor 10kΩ 1% 0.1W 0402', 1, 0, 50000, 0.005
        );
        -- C2: non-basic, correct package + value, lower stock
        INSERT INTO parts VALUES (
            'C2', 'Chip Resistor - Surface Mount', 'Other', 'RC0402-10K',
            '0402', 'Chip Resistor 10kΩ 5% 0.1W 0402', 0, 0, 30000, 0.004
        );
        -- C3: basic, but wrong package (0603) — SQL exact-match excludes it
        INSERT INTO parts VALUES (
            'C3', 'Chip Resistor - Surface Mount', 'Yageo', 'RC0603FR-0710KL',
            '0603', 'Chip Resistor 10kΩ 1% 0.1W 0603', 1, 0, 100000, 0.007
        );
        -- C4: basic, correct package, wrong value (10Ω not 10kΩ) — description won't match
        INSERT INTO parts VALUES (
            'C4', 'Chip Resistor - Surface Mount', 'Yageo', 'RC0402JR-0710RL',
            '0402', 'Chip Resistor 10Ω 5% 0.1W 0402', 1, 0, 80000, 0.003
        );
    """)


@pytest.fixture
def db(tmp_path: Path) -> PartsDB:
    p = tmp_path / "parts.db"
    conn = sqlite3.connect(str(p))
    _populate(conn)
    conn.commit()
    conn.close()
    return PartsDB(p)


@pytest.fixture(autouse=True)
def _stub_easyeda(monkeypatch, tmp_path):
    """Stub out easyeda download so tests don't hit the network."""
    def _fake_download(lcsc, out_dir):
        path = Path(out_dir) / f"{lcsc}_fake.kicad_mod"
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        path.write_text("(module fake)")
        return path
    import jlcpcb_mapper.io.easyeda as dl
    monkeypatch.setattr(dl, "download_footprint", _fake_download)


def test_10k_with_existing_footprint_skips_resolver(db, tmp_path):
    """Instance has a pre-existing footprint → all_have_fp=True → footprint='' in Decision."""
    instances = [
        Instance(
            sch_path=tmp_path / "x.kicad_sch",
            reference="R1",
            lib_id="Device:R",
            value="10k",
            footprint="Resistor_SMD:R_0402_1005Metric",  # already set
            dnp=False, on_board=True, in_bom=True,
        ),
    ]
    decisions = run_pipeline(
        instances=instances,
        db=db,
        llm=_FakeLLM(),
        hints="",
        score_tiebreak_threshold=0.01,
        llm_tiebreak_top_n=5,
        min_stock=1000,
        fp_out_dir=tmp_path / "fp",
    )

    assert len(decisions) == 1
    d = decisions[0]
    assert d.chosen_lcsc == "C1", f"Expected C1 (basic+50k stock), got {d.chosen_lcsc}"
    assert d.source == "score"
    # all_have_fp=True branch: resolver is skipped, footprint stays empty
    assert d.footprint == "", f"Expected empty footprint (resolver skipped), got '{d.footprint}'"
    assert d.downloaded is False


def test_10k_empty_footprint_uses_builtin_map(db, tmp_path):
    """Instance with empty footprint → package_hint='0402' → BuiltinMap hit."""
    instances = [
        Instance(
            sch_path=tmp_path / "x.kicad_sch",
            reference="R2",
            lib_id="Device:R",
            value="10k",
            footprint="",  # empty — resolver must supply one
            dnp=False, on_board=True, in_bom=True,
        ),
    ]
    decisions = run_pipeline(
        instances=instances,
        db=db,
        llm=_FakeLLM(),
        hints="",
        score_tiebreak_threshold=0.01,
        llm_tiebreak_top_n=5,
        min_stock=1000,
        fp_out_dir=tmp_path / "fp",
    )

    assert len(decisions) == 1
    d = decisions[0]
    assert d.chosen_lcsc == "C1"
    assert d.source == "score"
    # BuiltinMap has "0402" → "Resistor_SMD:R_0402_1005Metric"
    assert d.footprint == "Resistor_SMD:R_0402_1005Metric", (
        f"Expected BuiltinMap footprint, got '{d.footprint}'"
    )
    assert d.downloaded is False  # BuiltinMap, not EasyEDA
