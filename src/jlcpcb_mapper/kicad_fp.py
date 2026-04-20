from __future__ import annotations

_BUILTIN: dict[tuple[str, str], str] = {
    ("resistor", "0201"):  "Resistor_SMD:R_0201_0603Metric",
    ("resistor", "0402"):  "Resistor_SMD:R_0402_1005Metric",
    ("resistor", "0603"):  "Resistor_SMD:R_0603_1608Metric",
    ("resistor", "0805"):  "Resistor_SMD:R_0805_2012Metric",
    ("resistor", "1206"):  "Resistor_SMD:R_1206_3216Metric",
    ("capacitor", "0201"): "Capacitor_SMD:C_0201_0603Metric",
    ("capacitor", "0402"): "Capacitor_SMD:C_0402_1005Metric",
    ("capacitor", "0603"): "Capacitor_SMD:C_0603_1608Metric",
    ("capacitor", "0805"): "Capacitor_SMD:C_0805_2012Metric",
    ("capacitor", "1206"): "Capacitor_SMD:C_1206_3216Metric",
    ("led", "0402"):       "LED_SMD:LED_0402_1005Metric",
    ("led", "0603"):       "LED_SMD:LED_0603_1608Metric",
    ("led", "0805"):       "LED_SMD:LED_0805_2012Metric",
}


def match_kicad_footprint(category: str, package: str, overrides: dict[str, str]) -> str | None:
    key_str = f"{category},{package}"
    if key_str in overrides:
        return overrides[key_str]
    return _BUILTIN.get((category, package))
