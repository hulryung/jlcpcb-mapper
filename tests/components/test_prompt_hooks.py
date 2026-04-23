from jlcpcb_mapper.components.prompt_hooks import CapPromptHook
from jlcpcb_mapper.io.parts_db import PartRow


def _row():
    return PartRow(lcsc="C1", category="Aluminum Electrolytic", mfr="Y",
                   mfr_part="EL1", package="D6.3", description="220uF 10V 20%",
                   basic=1, preferred=0, stock=15000, price=0.05)


def test_cap_prompt_hook_mentions_voltage_when_emphasized():
    h = CapPromptHook(emphasize_voltage=True)
    assert "voltage" in h.selection_criteria().lower()


def test_cap_prompt_hook_does_not_mention_voltage_when_not_emphasized():
    h = CapPromptHook(emphasize_voltage=False)
    assert "voltage" not in h.selection_criteria().lower()


def test_candidate_payload_structure():
    h = CapPromptHook(emphasize_voltage=True)
    p = h.candidate_payload(_row())
    assert p["lcsc"] == "C1"
    assert p["basic"] is True
    assert p["preferred"] is False
    assert p["stock"] == 15000
    assert "220uF 10V" in p["description"]
