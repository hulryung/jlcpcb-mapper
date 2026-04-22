from jlcpcb_mapper.core.types import Value
from jlcpcb_mapper.categories.spec.cap import CeramicCapSpec, PolarizedCapSpec
from jlcpcb_mapper.components.value_parsers import CapValueParser

def test_ceramic_parses_plain_value():
    p = CapValueParser(keep_voltage=False)
    assert p.parse("10uF") == CeramicCapSpec(value=Value(10, "µF"))
    assert p.parse("10µF") == CeramicCapSpec(value=Value(10, "µF"))
    assert p.parse("100nF") == CeramicCapSpec(value=Value(100, "nF"))
    assert p.parse("2u2") == CeramicCapSpec(value=Value(2.2, "µF"))

def test_ceramic_drops_extra_slash_tokens():
    p = CapValueParser(keep_voltage=False)
    assert p.parse("10uF/25V") == CeramicCapSpec(value=Value(10, "µF"))

def test_polarized_keeps_voltage():
    p = CapValueParser(keep_voltage=True)
    spec = p.parse("220uF/10V")
    assert spec == PolarizedCapSpec(value=Value(220, "µF"), voltage=Value(10, "V"))

def test_polarized_missing_voltage_is_none():
    p = CapValueParser(keep_voltage=True)
    spec = p.parse("220uF")
    assert spec == PolarizedCapSpec(value=Value(220, "µF"), voltage=None)

def test_polarized_voltage_before_value_ignored():
    p = CapValueParser(keep_voltage=True)
    # Only slash-separated trailing tokens are inspected for voltage.
    spec = p.parse("10V/220uF")
    assert spec is None  # primary token "10V" is not a capacitance

def test_parse_none_on_junk():
    p = CapValueParser(keep_voltage=False)
    assert p.parse("foobar") is None
    assert p.parse("") is None
