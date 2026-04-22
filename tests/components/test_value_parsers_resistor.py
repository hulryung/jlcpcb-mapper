import pytest
from jlcpcb_mapper.core.types import Value
from jlcpcb_mapper.categories.spec.resistor import ResistorSpec
from jlcpcb_mapper.components.value_parsers import ResistorValueParser


def _spec(ohms: float) -> ResistorSpec:
    return ResistorSpec(value=Value(ohms, "Ω"))


def test_plain_integer():
    assert ResistorValueParser().parse("10") == _spec(10)


def test_kilo_uppercase():
    assert ResistorValueParser().parse("10K") == _spec(10000)


def test_kilo_lowercase():
    assert ResistorValueParser().parse("10k") == _spec(10000)


def test_fractional_kilo():
    assert ResistorValueParser().parse("4.7k") == _spec(4700)


def test_mega_uppercase():
    assert ResistorValueParser().parse("10M") == _spec(10_000_000)


def test_mega_lowercase_treated_as_mega():
    """Original code treats lowercase m as Mega too (migration compat)."""
    assert ResistorValueParser().parse("10m") == _spec(10_000_000)


def test_zero_plain():
    assert ResistorValueParser().parse("0") == _spec(0)


def test_zero_R_suffix():
    assert ResistorValueParser().parse("0R") == _spec(0)


def test_zero_ohm_symbol():
    assert ResistorValueParser().parse("0Ω") == _spec(0)


def test_kilo_with_ohm_symbol():
    assert ResistorValueParser().parse("10kΩ") == _spec(10000)


def test_tolerance_suffix_dropped():
    """Slash-separated tokens after the value are ignored."""
    assert ResistorValueParser().parse("10k/0.1%") == _spec(10000)


def test_empty_returns_none():
    assert ResistorValueParser().parse("") is None


def test_junk_returns_none():
    assert ResistorValueParser().parse("foobar") is None


def test_capacitance_returns_none():
    assert ResistorValueParser().parse("10uF") is None


def test_plain_1_ohm():
    assert ResistorValueParser().parse("1") == _spec(1)


def test_R_suffix_nonzero():
    """'10R' -> 10 Ω (R suffix means plain ohms for EIA notation)."""
    assert ResistorValueParser().parse("10R") == _spec(10)
