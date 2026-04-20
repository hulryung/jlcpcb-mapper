from unittest.mock import MagicMock
from jlcpcb_mapper.review import review_mapping, ReviewFlag
from jlcpcb_mapper.select import SelectionResult
from jlcpcb_mapper.grouper import Group, GroupKey
from jlcpcb_mapper.parts_db import PartRow
from jlcpcb_mapper.schematic import SymbolInstance

def mk_sel(category, value, lcsc):
    inst = SymbolInstance("R1", "0", "Device:R_Small_US", "", "", False)
    g = Group(GroupKey(category, value, "0402"), [inst])
    return SelectionResult(g, [PartRow(lcsc,"c","","","0402","d",1,0,1,0.0)], lcsc, "ok", True)

def test_review_flags_inconsistency():
    llm = MagicMock()
    llm.call.return_value = MagicMock(data={
        "flagged": [{"group_index": 1, "issue": "different LCSC for same value", "suggested_lcsc": "C17168"}],
        "overall_ok": False,
    })
    sels = [mk_sel("resistor", "0Ω", "C17168"), mk_sel("resistor", "0Ω", "C21189")]
    flags = review_mapping(sels, llm)
    assert len(flags) == 1
    assert flags[0].suggested_lcsc == "C17168"

def test_review_no_flags():
    llm = MagicMock()
    llm.call.return_value = MagicMock(data={"flagged": [], "overall_ok": True})
    sels = [mk_sel("resistor", "0Ω", "C17168")]
    assert review_mapping(sels, llm) == []

def test_review_empty_sels_returns_empty():
    llm = MagicMock()
    assert review_mapping([], llm) == []
    llm.call.assert_not_called()
