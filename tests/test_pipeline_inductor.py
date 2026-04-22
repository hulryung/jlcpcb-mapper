"""Integration test for the INDUCTOR category end-to-end through the pipeline.

Scenario: Device:L, value "33uH", empty footprint (no pre-existing footprint).
- default_package = "0805" is used as package_hint.
- DB has three rows; C1 (basic) wins over C2 (non-basic) by scorer.
- C3 has wrong value and is excluded by description LIKE filter.
- BuiltinMap is empty (_BUILTIN={}) so EasyedaFallback fires → downloaded=True.

Scoring verification:
  C1 (basic=1, stock=40000): score = 0.4 + 0.4*0.7 = 0.68
  C2 (basic=0, stock=60000): score = 0   + 0.4*1.0 = 0.40
  diff = 0.28 > tau=0.01 → scorer decides C1 without LLM.
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
        -- C1: expected winner — basic, correct value (33uH), 0805, 40k stock
        INSERT INTO parts VALUES (
            'C1', 'Inductor (SMD)', 'Murata', 'LQM2HPNR33MGJ',
            '0805', '33uH 20% 0.25A 0805', 1, 0, 40000, 0.05
        );
        -- C2: non-basic, correct value (33uH), 0805, 60k stock — higher stock but no basic bonus
        INSERT INTO parts VALUES (
            'C2', 'Inductor (SMD)', 'TDK', 'MLF2012DR33K',
            '0805', '33uH 10% 0.3A 0805', 0, 0, 60000, 0.04
        );
        -- C3: basic, but wrong value (10uH) — description LIKE '%33uH%' excludes it
        INSERT INTO parts VALUES (
            'C3', 'Inductor (SMD)', 'Murata', 'LQM2HPNR10MGJ',
            '0805', '10uH 20% 0.4A 0805', 1, 0, 50000, 0.05
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
    """Stub out EasyEDA download so tests don't hit the network."""
    def _fake_download(lcsc, out_dir):
        path = Path(out_dir) / f"{lcsc}_fake.kicad_mod"
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        path.write_text("(module fake)")
        return path
    import jlcpcb_mapper.downloader as dl
    monkeypatch.setattr(dl, "download_footprint", _fake_download)


def test_33uH_empty_footprint_uses_easyeda(db, tmp_path):
    """Device:L with 33uH, empty footprint → C1 (basic+40k stock), EasyedaFallback fires."""
    instances = [
        Instance(
            sch_path=tmp_path / "x.kicad_sch",
            reference="L1",
            lib_id="Device:L",
            value="33uH",
            footprint="",  # empty — no BuiltinMap entry → EasyedaFallback fires
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
    assert d.chosen_lcsc == "C1", f"Expected C1 (basic+40k stock), got {d.chosen_lcsc}"
    assert d.source == "score"
    # BuiltinMap is empty → EasyedaFallback is used
    assert d.downloaded is True, "Expected EasyedaFallback to fire (downloaded=True)"
    assert d.footprint.startswith("LCSC:C1"), (
        f"Expected LCSC:C1_fake footprint from EasyedaFallback, got '{d.footprint}'"
    )
