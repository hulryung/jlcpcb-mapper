import pytest
from jlcpcb_mapper.core.types import Value
from jlcpcb_mapper.categories.spec.crystal import CrystalSpec
from jlcpcb_mapper.components.value_parsers import CrystalValueParser


def _spec(mag, unit) -> CrystalSpec:
    return CrystalSpec(value=Value(mag, unit))


def test_mhz_integer():
    assert CrystalValueParser().parse("16MHz") == _spec(16, "MHz")


def test_mhz_8():
    assert CrystalValueParser().parse("8MHz") == _spec(8, "MHz")


def test_khz_fractional():
    assert CrystalValueParser().parse("32.768kHz") == _spec(32.768, "kHz")


def test_uppercase_M_no_hz():
    assert CrystalValueParser().parse("16M") == _spec(16, "MHz")


def test_lowercase_m_no_hz():
    assert CrystalValueParser().parse("16m") == _spec(16, "MHz")


def test_uppercase_MHZ():
    assert CrystalValueParser().parse("8MHZ") == _spec(8, "MHz")


def test_lowercase_mhz():
    assert CrystalValueParser().parse("25mhz") == _spec(25, "MHz")


def test_bare_hz():
    assert CrystalValueParser().parse("400Hz") == _spec(400, "Hz")


def test_bare_HZ():
    assert CrystalValueParser().parse("400HZ") == _spec(400, "Hz")


def test_slash_takes_first_token():
    assert CrystalValueParser().parse("16MHz/10ppm") == _spec(16, "MHz")


def test_empty_returns_none():
    assert CrystalValueParser().parse("") is None


def test_whitespace_only_returns_none():
    assert CrystalValueParser().parse("   ") is None


def test_bare_number_returns_none():
    assert CrystalValueParser().parse("16") is None


def test_foobar_returns_none():
    assert CrystalValueParser().parse("foobar") is None


def test_uF_returns_none():
    assert CrystalValueParser().parse("10uF") is None


def test_khz_uppercase_K():
    assert CrystalValueParser().parse("32.768KHz") == _spec(32.768, "kHz")


def test_khz_K_no_hz():
    assert CrystalValueParser().parse("32K") == _spec(32, "kHz")
