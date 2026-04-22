"""Integration test for the CERAMIC_CAP category end-to-end through the pipeline.

Fixture: two candidates, only one basic — scorer picks the basic one without LLM.
- C1: basic, 0402, 30k stock  → score ≈ 0.4 + 0.4*0.7 = 0.68
- C2: non-basic, 0402, 50k stock → score ≈ 0 + 0.4*1.0 = 0.4
Diff = 0.28 > tau=0.01 → scorer decides C1.
Instance has empty footprint → default_package='0402' is used → BuiltinMap hits for 0402.
"""
import sqlite3
from pathlib import Path
import pytest
from jlcpcb_mapper.core.pipeline import run_pipeline, Instance
from jlcpcb_mapper.parts_db import PartsDB


class _FakeLLM:
    def __init__(self):
        self.calls = 0

    def call(self, prompt, schema_keys):
        self.calls += 1
        raise AssertionError("scorer should have decided without LLM")


def _populate(conn):
    conn.executescript("""
        CREATE TABLE parts (
            lcsc TEXT PRIMARY KEY, category TEXT, mfr TEXT, mfr_part TEXT,
            package TEXT, description TEXT, basic INTEGER, preferred INTEGER,
            stock INTEGER, price REAL
        );
        -- C1: expected winner — basic, 0402, 30k stock
        -- (empty footprint → default_package='0402' used as package_hint)
        INSERT INTO parts VALUES (
            'C1', 'Multilayer Ceramic Capacitor', 'Murata', 'GRM155R61A106KE18D',
            '0402', '10uF X7R 10V 0402', 1, 0, 30000, 0.01
        );
        -- C2: non-basic, 0402, 50k stock — higher stock but non-basic loses
        INSERT INTO parts VALUES (
            'C2', 'Multilayer Ceramic Capacitor', 'Samsung', 'CL05A106MQ5NNNC',
            '0402', '10uF X7R 10V 0402', 0, 0, 50000, 0.008
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
    import jlcpcb_mapper.downloader as dl
    monkeypatch.setattr(dl, "download_footprint", _fake_download)


def test_10uf_ceramic_selects_basic_builtin_footprint(db, tmp_path):
    """Device:C with 10uF, empty footprint → C1 (basic+30k stock), BuiltinMap for 0402."""
    instances = [
        Instance(
            sch_path=tmp_path / "x.kicad_sch",
            reference="C1",
            lib_id="Device:C",
            value="10uF",
            footprint="",  # empty — default_package='0402' used; resolver must supply footprint
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
    assert d.chosen_lcsc == "C1", f"Expected C1 (basic+30k), got {d.chosen_lcsc}"
    assert d.source == "score"
    # BuiltinMap has "0402" → "Capacitor_SMD:C_0402_1005Metric"
    assert d.footprint == "Capacitor_SMD:C_0402_1005Metric", (
        f"Expected BuiltinMap footprint, got '{d.footprint}'"
    )
    assert d.downloaded is False  # BuiltinMap, not EasyEDA
