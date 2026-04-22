import pytest
from jlcpcb_mapper.core.types import Value
from jlcpcb_mapper.categories.spec.inductor import InductorSpec
from jlcpcb_mapper.components.value_parsers import InductorValueParser


def _spec(mag: float, unit: str) -> InductorSpec:
    return InductorSpec(value=Value(mag, unit))


def test_33uH():
    assert InductorValueParser().parse("33uH") == _spec(33, "µH")


def test_33_micro_sign():
    """Micro sign µ (U+00B5) canonicalized to µH."""
    assert InductorValueParser().parse("33µH") == _spec(33, "µH")


def test_33_greek_mu():
    """Greek mu μ (U+03BC) canonicalized to µH."""
    assert InductorValueParser().parse("33μH") == _spec(33, "µH")


def test_fractional_4_7uH():
    assert InductorValueParser().parse("4.7uH") == _spec(4.7, "µH")


def test_100uH():
    assert InductorValueParser().parse("100uH") == _spec(100, "µH")


def test_10nH():
    assert InductorValueParser().parse("10nH") == _spec(10, "nH")


def test_1mH():
    assert InductorValueParser().parse("1mH") == _spec(1, "mH")


def test_bare_H():
    """33H without prefix → Value(33, 'H') — uncommon but valid."""
    assert InductorValueParser().parse("33H") == _spec(33, "H")


def test_empty_returns_none():
    assert InductorValueParser().parse("") is None


def test_whitespace_returns_none():
    assert InductorValueParser().parse("   ") is None


def test_junk_returns_none():
    assert InductorValueParser().parse("foobar") is None


def test_capacitance_returns_none():
    """10uF is a capacitor, not an inductor."""
    assert InductorValueParser().parse("10uF") is None


def test_case_insensitive_uH():
    """Regex is IGNORECASE — 'UH' should match."""
    assert InductorValueParser().parse("33UH") == _spec(33, "µH")
