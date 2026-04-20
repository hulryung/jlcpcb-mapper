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
    ("Device:Rotary_Encoder",       "ic"),
    ("Device:Crystal",              "crystal"),
    ("Device:C_Polarized_Small_US", "polarized_capacitor"),
])
def test_category_from_lib_id(lib_id, expected):
    assert category_from_lib_id(lib_id) == expected


@pytest.mark.parametrize("raw,category,expected", [
    ("0/F/1005",       "resistor",  "0Ω"),
    ("22/F/1005",      "resistor",  "22Ω"),
    ("330uF/10V",      "capacitor", "330µF"),
    ("220uF/25V",      "capacitor", "220µF"),
    ("33uH/3A",        "inductor",  "33µH"),
    ("4.7uH/2A",       "inductor",  "4.7µH"),
    ("25MHz/12pF/3225","crystal",   "25MHz"),
])
def test_normalize_strips_slash_suffixes(raw, category, expected):
    # Just verify the first-token stripping path; the actual normalization
    # depends on category support. For categories we don't fully normalize,
    # we at least expect the slash-suffix to be gone.
    val = normalize_value(raw, category)
    assert "/" not in val

def test_normalize_resistor_with_slash_suffix_is_ohms():
    assert normalize_value("0/F/1005", "resistor") == "0Ω"
    assert normalize_value("22/F/1005", "resistor") == "22Ω"

def test_normalize_capacitor_with_slash_suffix():
    # 330uF/10V -> first token "330uF" -> µF form
    assert normalize_value("330uF/10V", "capacitor") == "330µF"

def test_normalize_inductor():
    assert normalize_value("33uH/3A", "inductor") == "33µH"
    assert normalize_value("4.7uH/2A", "inductor") == "4.7µH"

@pytest.mark.parametrize("lib_id,expected", [
    ("Device:Crystal",                  "crystal"),
    ("Device:Crystal_GND24",            "crystal"),
    ("Device:L",                        "inductor"),
    ("Device:L_Small",                  "inductor"),
    ("Device:C_Polarized",              "polarized_capacitor"),
    ("Device:C_Polarized_Small_US",     "polarized_capacitor"),
    ("Connector_Generic:Conn_02x04_Odd_Even", "connector_2x4"),
    ("Connector_Generic:Conn_02x10",    "connector_2x10"),
])
def test_new_categories(lib_id, expected):
    assert category_from_lib_id(lib_id) == expected
