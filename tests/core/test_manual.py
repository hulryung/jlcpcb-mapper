"""Tests for manual LCSC override resolution."""
from __future__ import annotations
import sqlite3
from pathlib import Path
import pytest

from jlcpcb_mapper.config import ManualLCSC
from jlcpcb_mapper.core.manual import resolve_manual_overrides
from jlcpcb_mapper.core.pipeline import Instance
from jlcpcb_mapper.io.parts_db import PartsDB


def _populate(conn):
    conn.executescript("""
        CREATE TABLE parts (
            lcsc TEXT PRIMARY KEY, category TEXT, mfr TEXT, mfr_part TEXT,
            package TEXT, description TEXT, basic INTEGER, preferred INTEGER,
            stock INTEGER, price REAL
        );
        INSERT INTO parts VALUES ('C16214', 'DC Power Connectors', 'XKB', 'DC-005 2.0', '插件',
                                  '12V 1A 2mm DC Power Jack', 0, 0, 97256, 0.05);
        INSERT INTO parts VALUES ('C5221287', 'Pogo Pin', 'Pomagtic', 'YTC1P-2010-01', 'SMD,D=2mm',
                                  '12V 2.5A 2mm Pogo Pin', 0, 0, 677, 0.12);
    """)


@pytest.fixture
def db(tmp_path: Path) -> PartsDB:
    p = tmp_path / "parts.db"
    conn = sqlite3.connect(str(p))
    _populate(conn)
    conn.commit()
    conn.close()
    return PartsDB(p)


def _inst(ref: str, value: str = "", lib_id: str = "Connector:X", footprint: str = "") -> Instance:
    return Instance(
        sch_path=Path("/x.kicad_sch"), reference=ref, lib_id=lib_id,
        value=value, footprint=footprint,
        dnp=False, on_board=True, in_bom=True,
    )


def test_by_reference_match_returns_synthetic_decision(db):
    manual = ManualLCSC(by_reference={"J2": "C16214"}, by_value={})
    res = resolve_manual_overrides([_inst("J2", value="Barrel_Jack")], manual, db)
    assert "J2" in res.matched_refs
    assert len(res.decisions) == 1
    d = res.decisions[0]
    assert d.chosen_lcsc == "C16214"
    assert d.source == "manual"
    assert d.candidates[0].mfr_part == "DC-005 2.0"


def test_by_value_groups_multiple_refs_into_one_decision(db):
    """All POGO refs share the same LCSC → one synthetic Decision with N instances."""
    manual = ManualLCSC(by_reference={}, by_value={"POGO": "C5221287"})
    insts = [_inst(f"J{i}", value="POGO") for i in (6, 7, 8, 9)]
    res = resolve_manual_overrides(insts, manual, db)
    assert res.matched_refs == {"J6", "J7", "J8", "J9"}
    assert len(res.decisions) == 1
    d = res.decisions[0]
    assert {i.reference for i in d.group.instances} == {"J6", "J7", "J8", "J9"}
    assert d.chosen_lcsc == "C5221287"


def test_by_reference_wins_over_by_value(db):
    manual = ManualLCSC(
        by_reference={"J2": "C16214"},
        by_value={"Barrel_Jack": "C5221287"},  # would otherwise also match J2
    )
    res = resolve_manual_overrides([_inst("J2", value="Barrel_Jack")], manual, db)
    assert res.decisions[0].chosen_lcsc == "C16214"


def test_unknown_lcsc_reported_and_ref_unclaimed(db):
    """If the user pins an LCSC that isn't in parts.db, surface it as a
    failure and don't claim the ref (the auto pipeline can still try)."""
    manual = ManualLCSC(by_reference={"J9": "C99999999"}, by_value={})
    res = resolve_manual_overrides([_inst("J9", value="x")], manual, db)
    assert res.matched_refs == set()
    assert res.unknown_lcscs == [("C99999999", ["J9"])]
    assert res.decisions == []


def test_no_match_leaves_instance_for_pipeline(db):
    manual = ManualLCSC(by_reference={"J2": "C16214"}, by_value={})
    res = resolve_manual_overrides([_inst("R1", value="10k")], manual, db)
    assert res.matched_refs == set()
    assert res.decisions == []


def test_decision_traces_match_kind_for_report(db):
    """The synthetic Decision must carry enough trace data for the
    Markdown report's _manual_rationale to render the right by_reference
    vs by_value sentence."""
    manual = ManualLCSC(by_reference={"J2": "C16214"}, by_value={})
    res = resolve_manual_overrides([_inst("J2", value="x")], manual, db)
    d = res.decisions[0]
    decide_events = [e for e in d.group.trace.events if e.stage == "decide"]
    assert decide_events, "expected a decide event"
    assert decide_events[0].data.get("match_kind") == "by_reference"
