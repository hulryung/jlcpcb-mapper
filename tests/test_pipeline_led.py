"""Integration test for the LED category end-to-end through the pipeline.

Scenario: Device:LED, value "RED", empty footprint (no pre-existing footprint).
- default_package = "0603" used as package_hint (no footprint to extract from).
- DB has three rows:
    C1 (basic, "RED LED 0603 620nm", 0603, 100k stock) — expected winner
    C2 (non-basic, "RED LED 0603 625nm", 0603, 200k stock) — higher stock but no basic bonus
    C3 (basic, "GREEN LED 0603 525nm", 0603, 50k stock) — excluded by %RED% LIKE filter
- Scorer picks C1 (basic bonus outweighs C2's extra stock).
- BuiltinMap has "0603" → "LED_SMD:LED_0603_1608Metric" → downloaded=False.

Scoring verification:
  max_stock = 200000 (C2's stock is highest among candidates, but C3 is filtered out in DB)
  C1 (basic=1, stock=100000): score = 0.4 + 0.4*(100000/200000) = 0.4 + 0.2 = 0.60
  C2 (basic=0, stock=200000): score = 0   + 0.4*(200000/200000) = 0.0 + 0.4 = 0.40
  diff = 0.20 > tau=0.01 → scorer decides without LLM.
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
        -- C1: expected winner — basic, RED description, 0603, 100k stock
        INSERT INTO parts VALUES (
            'C1', 'Light Emitting Diode (SMD)', 'Hubei', 'XL-0603URC-04',
            '0603', 'RED LED 0603 620nm', 1, 0, 100000, 0.01
        );
        -- C2: non-basic, RED description, 0603, 200k stock — higher stock but no basic bonus
        INSERT INTO parts VALUES (
            'C2', 'Light Emitting Diode (SMD)', 'Everlight', '19-21SURSYGC-S',
            '0603', 'RED LED 0603 625nm', 0, 0, 200000, 0.01
        );
        -- C3: basic, GREEN description — excluded by %RED% LIKE filter
        INSERT INTO parts VALUES (
            'C3', 'Light Emitting Diode (SMD)', 'Hubei', 'XL-0603UGC-04',
            '0603', 'GREEN LED 0603 525nm', 1, 0, 50000, 0.01
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


def test_red_led_empty_footprint_builtin_map_hit(db, tmp_path):
    """Device:LED with value 'RED', empty footprint → C1 wins, BuiltinMap returns 0603 fp."""
    instances = [
        Instance(
            sch_path=tmp_path / "x.kicad_sch",
            reference="D1",
            lib_id="Device:LED",
            value="RED",
            footprint="",  # empty — default_package="0603" used
            dnp=False, on_board=True, in_bom=True,
        ),
    ]
    decisions, _skipped = run_pipeline(
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
    assert d.chosen_lcsc == "C1", f"Expected C1 (basic+100k stock), got {d.chosen_lcsc}"
    assert d.source == "score"
    assert d.footprint == "LED_SMD:LED_0603_1608Metric", (
        f"Expected BuiltinMap hit for 0603, got '{d.footprint}'"
    )
    assert d.downloaded is False, "BuiltinMap hit should not download"
