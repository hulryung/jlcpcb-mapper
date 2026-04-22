import re
from jlcpcb_mapper.components.package_extractors import RegexFromRules


def test_resistor_smd_size():
    ex = RegexFromRules([(r"^Resistor_SMD:R_(\d{4})_", lambda m: m.group(1))])
    assert ex.extract("Resistor_SMD:R_0402_1005Metric") == "0402"
    assert ex.extract("Resistor_SMD:R_0603_1608Metric_Pad") == "0603"


def test_polarized_cap_smd_diameter():
    ex = RegexFromRules([
        (r"^Capacitor_SMD:CP_Elec_(\d+\.?\d*x\d+\.?\d*)",
         lambda m: f"D{m.group(1).split('x')[0]}"),
    ])
    assert ex.extract("Capacitor_SMD:CP_Elec_6.3x5.4") == "D6.3"
    assert ex.extract("Capacitor_SMD:CP_Elec_8x10") == "D8"


def test_returns_none_when_no_rule_matches():
    ex = RegexFromRules([(r"^Xyz", lambda m: "x")])
    assert ex.extract("Resistor_SMD:R_0402_1005Metric") is None


def test_empty_footprint_returns_none():
    ex = RegexFromRules([(r"^X", lambda m: "x")])
    assert ex.extract("") is None


def test_multiple_rules_first_wins():
    ex = RegexFromRules([
        (r"^Package_TO_SOT_SMD:(SOT-\d+)", lambda m: m.group(1)),
        (r"^Package_TO_SOT_SMD:(TO-\d+(?:-\d+)?)(?:_|$)", lambda m: m.group(1)),
    ])
    assert ex.extract("Package_TO_SOT_SMD:SOT-23") == "SOT-23"
    assert ex.extract("Package_TO_SOT_SMD:TO-263-5_TabPin3") == "TO-263-5"
