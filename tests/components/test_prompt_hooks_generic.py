from jlcpcb_mapper.components.prompt_hooks import GenericPromptHook
from jlcpcb_mapper.parts_db import PartRow


def _row():
    return PartRow(lcsc="C1", category="Chip Resistor - Surface Mount",
                   mfr="Yageo", mfr_part="RC0402FR-0710KL",
                   package="0402", description="10kΩ 1% 0.1W 0402",
                   basic=1, preferred=0, stock=50000, price=0.005)


def test_selection_criteria_mentions_basic_and_stock():
    h = GenericPromptHook()
    crit = h.selection_criteria()
    assert "basic" in crit.lower()
    assert "stock" in crit.lower()


def test_selection_criteria_does_not_mention_voltage():
    h = GenericPromptHook()
    assert "voltage" not in h.selection_criteria().lower()


def test_candidate_payload_has_nine_keys():
    h = GenericPromptHook()
    p = h.candidate_payload(_row())
    expected_keys = {"lcsc", "mfr", "mfr_part", "package", "basic",
                     "preferred", "stock", "price", "description"}
    assert set(p.keys()) == expected_keys


def test_candidate_payload_values():
    h = GenericPromptHook()
    p = h.candidate_payload(_row())
    assert p["lcsc"] == "C1"
    assert p["basic"] is True
    assert p["preferred"] is False
    assert p["stock"] == 50000
    assert "10kΩ" in p["description"]


def test_candidate_payload_description_truncated_at_200():
    h = GenericPromptHook()
    long_desc = "x" * 300
    row = PartRow(lcsc="C2", category="Chip Resistor", mfr="X", mfr_part="Y",
                  package="0402", description=long_desc,
                  basic=0, preferred=0, stock=100, price=0.01)
    p = h.candidate_payload(row)
    assert len(p["description"]) == 200
