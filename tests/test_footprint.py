import pytest
from jlcpcb_mapper.footprint import package_from_kicad_footprint as pkg

@pytest.mark.parametrize("fp,expected", [
    ("Resistor_SMD:R_0402_1005Metric",    "0402"),
    ("Resistor_SMD:R_0603_1608Metric",    "0603"),
    ("Capacitor_SMD:C_0603_1608Metric",   "0603"),
    ("Capacitor_SMD:C_1206_3216Metric",   "1206"),
    ("LED_SMD:LED_0805_2012Metric",       "0805"),
    ("Package_TO_SOT_SMD:SOT-23",         "SOT-23"),
    ("Package_TO_SOT_SMD:SOT-223",        "SOT-223"),
    ("Package_TO_SOT_SMD:TO-263-5_TabPin3", "TO-263-5"),
    ("Package_TO_SOT_SMD:TO-252-3_TabPin2", "TO-252-3"),
    ("Diode_SMD:D_SMA",                   "SMA"),
    ("Diode_SMD:D_SMB",                   "SMB"),
    ("Diode_SMD:D_MELF",                  "MELF"),
    ("Diode_SMD:D_SOD-323",               "SOD-323"),
    ("Package_QFN:QFN-24_4x4mm_P0.5mm",   "QFN-24"),
    ("Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", "SOIC-8"),
    ("Package_SO:TSSOP-14_4.4x5mm_P0.65mm", "TSSOP-14"),
    ("", None),
    ("MountingHole:MountingHole_3.2mm_M3_Pad_Via", None),
    ("Connector_USB:USB_C_Receptacle_HCTL_HC-TYPE-C-16P-01A", None),
    ("Connector_PCBEdge:BUS_PCI_Express_Mini_Full", None),
])
def test_package_from_kicad_footprint(fp, expected):
    assert pkg(fp) == expected
