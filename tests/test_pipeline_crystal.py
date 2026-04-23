"""Integration test for the Crystal category end-to-end through the pipeline.

Two test scenarios:

Scenario A (pre-existing footprint): Device:Crystal, value "16MHz",
    footprint "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm".
  Package extraction: _PACKAGE_RULES regex → "SMD-3225" as package_hint.
  Since instance already has a footprint, pipeline sets all_have_fp=True
  and skips the resolver (downloaded=False, footprint="").

  DB rows after SQL LIKE '%16MHz%': C1, C2, C4.
  post_filter hint="SMD-3225" keeps: C1 and C2.
  Scorer:
    C1: basic=1, stock=10k → bucket=0.7 → score = 0.4 + 0.4*0.7 = 0.68
    C2: basic=0, stock=40k → bucket=1.0 → score = 0 + 0.4*1.0 = 0.40
    diff = 0.28 > tau=0.01 → scorer picks C1, source="score".
  downloaded=False (resolver skipped).

Scenario B (no footprint): Instance with empty footprint →
    default_package="" → post_filter returns [] → source="failed".
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
    conn.executescript("""
        CREATE TABLE parts (
            lcsc TEXT PRIMARY KEY, category TEXT, mfr TEXT, mfr_part TEXT,
            package TEXT, description TEXT, basic INTEGER, preferred INTEGER,
            stock INTEGER, price REAL
        );
        -- C1: expected winner — basic, 16MHz description, SMD-3225, 10k stock
        INSERT INTO parts VALUES (
            'C1', 'Crystal Resonator', 'Abracon', 'ABM3-16.000MHZ-D2Y-T',
            'SMD-3225', '16MHz crystal SMD-3225', 1, 0, 10000, 0.10
        );
        -- C2: non-basic, 16MHz, SMD-3225, 40k stock — higher stock but no basic bonus
        INSERT INTO parts VALUES (
            'C2', 'Crystal Resonator', 'Epson', 'FA-238',
            'SMD-3225', '16MHz crystal SMD-3225', 0, 0, 40000, 0.08
        );
        -- C3: basic, 32.768kHz — excluded by SQL %16MHz% LIKE filter
        INSERT INTO parts VALUES (
            'C3', 'Crystal Resonator', 'Epson', 'FC-135',
            'SMD-3225', '32.768kHz crystal', 1, 0, 30000, 0.05
        );
        -- C4: basic, 16MHz, HC-49 — excluded by post_filter package check
        INSERT INTO parts VALUES (
            'C4', 'Crystal Resonator', 'NDK', 'NX5032GA',
            'HC-49', '16MHz crystal HC-49', 1, 0, 20000, 0.09
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
    def _fake_download(lcsc, out_dir):
        path = Path(out_dir) / f"{lcsc}_fake.kicad_mod"
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        path.write_text("(module fake)")
        return path
    import jlcpcb_mapper.io.easyeda as dl
    monkeypatch.setattr(dl, "download_footprint", _fake_download)


def test_16mhz_smd3225_selects_basic(db, tmp_path):
    """Device:Crystal, 16MHz, SMD-3225 footprint → C1 wins (basic+10k stock)."""
    instances = [
        Instance(
            sch_path=tmp_path / "x.kicad_sch",
            reference="Y1",
            lib_id="Device:Crystal",
            value="16MHz",
            footprint="Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm",
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
        min_stock=0,
        fp_out_dir=tmp_path / "fp",
    )

    assert len(decisions) == 1
    d = decisions[0]
    assert d.chosen_lcsc == "C1", f"Expected C1 (basic+10k stock), got {d.chosen_lcsc}"
    assert d.source == "score"
    # Instance already has a footprint → pipeline skips resolver (fill-lcsc-only mode)
    assert d.downloaded is False
    assert d.footprint == ""


def test_crystal_variant_lib_id_matched(db, tmp_path):
    """Device:Crystal_GND24 (variant) should also be matched by the crystal category."""
    instances = [
        Instance(
            sch_path=tmp_path / "x.kicad_sch",
            reference="Y2",
            lib_id="Device:Crystal_GND24",
            value="16MHz",
            footprint="Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm",
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
        min_stock=0,
        fp_out_dir=tmp_path / "fp",
    )

    assert len(decisions) == 1
    d = decisions[0]
    assert d.chosen_lcsc == "C1"


def test_crystal_no_footprint_returns_failed(db, tmp_path):
    """Crystal with no footprint (empty) uses default_package='', post_filter returns []."""
    instances = [
        Instance(
            sch_path=tmp_path / "x.kicad_sch",
            reference="Y3",
            lib_id="Device:Crystal",
            value="16MHz",
            footprint="",  # empty: default_package="" → post_filter returns []
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
        min_stock=0,
        fp_out_dir=tmp_path / "fp",
    )

    assert len(decisions) == 1
    d = decisions[0]
    assert d.source == "failed"
    assert d.chosen_lcsc is None
