from jlcpcb_mapper.kicad_fp import match_kicad_footprint


def test_resistor_0402():
    assert match_kicad_footprint("resistor", "0402", {}) == "Resistor_SMD:R_0402_1005Metric"


def test_capacitor_0603():
    assert match_kicad_footprint("capacitor", "0603", {}) == "Capacitor_SMD:C_0603_1608Metric"


def test_override_wins():
    overrides = {"resistor,0402": "Custom:MyR_0402"}
    assert match_kicad_footprint("resistor", "0402", overrides) == "Custom:MyR_0402"


def test_unknown_returns_none():
    assert match_kicad_footprint("ic", "QFN-24-EP", {}) is None
