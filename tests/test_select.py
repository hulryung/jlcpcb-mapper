from unittest.mock import MagicMock
from jlcpcb_mapper.select import select_for_groups
from jlcpcb_mapper.grouper import Group, GroupKey
from jlcpcb_mapper.parts_db import PartRow
from jlcpcb_mapper.schematic import SymbolInstance

def mk_inst(ref):
    return SymbolInstance(ref, "0", "Device:R_Small_US", "", "", False, 0, 0)

def test_single_candidate_skips_llm():
    llm = MagicMock()
    g = Group(GroupKey("resistor", "0Ω", "0402"), [mk_inst("R1")])
    candidates_map = {g.key: [PartRow("C17168","r","m","p","0402","d",1,0,1,0.1)]}
    results = select_for_groups([g], candidates_map, llm, hints="")
    assert results[0].chosen_lcsc == "C17168"
    assert results[0].llm_called is False
    llm.call.assert_not_called()

def test_multiple_candidates_invokes_llm():
    rows = [
        PartRow("C1","r","","","0402","d",1,0,1000,0.1),
        PartRow("C2","r","","","0402","d",0,0,500,0.1),
    ]
    llm = MagicMock()
    llm.call.return_value = MagicMock(data={"lcsc":"C1","reason":"basic"})
    g = Group(GroupKey("resistor","0Ω","0402"), [mk_inst("R1")])
    results = select_for_groups([g], {g.key: rows}, llm, hints="hints")
    assert results[0].chosen_lcsc == "C1"
    assert results[0].reason == "basic"
    assert results[0].llm_called is True

def test_no_candidates_marks_failed():
    llm = MagicMock()
    g = Group(GroupKey("resistor","0Ω","0402"), [mk_inst("R1")])
    results = select_for_groups([g], {g.key: []}, llm, hints="")
    assert results[0].chosen_lcsc is None
    assert results[0].failure_reason == "no candidates"
