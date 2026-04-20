import pytest
from jlcpcb_mapper.values import normalize_value, category_from_lib_id

@pytest.mark.parametrize("raw,expected", [
    ("1K",      "1000Ω"),
    ("1k",      "1000Ω"),
    ("1000",    "1000Ω"),
    ("4.7K",    "4700Ω"),
    ("0",       "0Ω"),
    ("0R",      "0Ω"),
    ("3.6K",    "3600Ω"),
    ("1M",      "1000000Ω"),
])
def test_normalize_resistor(raw, expected):
    assert normalize_value(raw, "resistor") == expected

@pytest.mark.parametrize("raw,expected", [
    ("2.2uF",   "2.2µF"),
    ("2u2",     "2.2µF"),
    ("4.7uF",   "4.7µF"),
    ("100nF",   "100nF"),
    ("1uF",     "1µF"),
])
def test_normalize_capacitor(raw, expected):
    assert normalize_value(raw, "capacitor") == expected

@pytest.mark.parametrize("lib_id,expected", [
    ("Device:R_Small_US",          "resistor"),
    ("Device:R",                    "resistor"),
    ("Device:C_Small",              "capacitor"),
    ("Device:LED",                  "led"),
    ("Connector_Generic:Conn_01x06","connector_1x6"),
    ("power:GND",                   "power"),
    ("power:+3.3V",                 "power"),
    ("MCU_Microchip:ATmega328",     "ic"),
])
def test_category_from_lib_id(lib_id, expected):
    assert category_from_lib_id(lib_id) == expected
