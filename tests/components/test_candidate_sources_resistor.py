import pytest
from jlcpcb_mapper.core.types import Value
from jlcpcb_mapper.categories.spec.resistor import ResistorSpec
from jlcpcb_mapper.components.candidate_sources import ResistorSource
from jlcpcb_mapper.parts_db import PartRow


def _spec(ohms: float) -> ResistorSpec:
    return ResistorSpec(value=Value(ohms, "Ω"))


def _row(lcsc, pkg, desc, stock=10000, basic=0, preferred=0):
    return PartRow(lcsc=lcsc, category="Chip Resistor - Surface Mount", mfr="Y",
                   mfr_part="X", package=pkg, description=desc,
                   basic=basic, preferred=preferred, stock=stock, price=0.01)


def test_query_10k_0402():
    q = ResistorSource().query(_spec(10000), package_hint="0402")
    assert "Chip Resistor" in q.category_like
    assert q.package == "0402"
    assert q.description_patterns == ("% 10kΩ%",)


def test_query_zero_ohm():
    q = ResistorSource().query(_spec(0), package_hint="0402")
    assert q.description_patterns == ("% 0Ω%",)


def test_query_4_7k_0603():
    q = ResistorSource().query(_spec(4700), package_hint="0603")
    assert q.package == "0603"
    assert q.description_patterns == ("% 4.7kΩ%",)


def test_query_1M_0603():
    q = ResistorSource().query(_spec(1_000_000), package_hint="0603")
    assert q.description_patterns == ("% 1MΩ%",)


def test_query_10M_0402():
    q = ResistorSource().query(_spec(10_000_000), package_hint="0402")
    assert q.description_patterns == ("% 10MΩ%",)


def test_query_1k_no_trailing_zero():
    """1000Ω should render as '1kΩ' not '1.0kΩ'."""
    q = ResistorSource().query(_spec(1000), package_hint="0402")
    assert q.description_patterns == ("% 1kΩ%",)


def test_query_plain_ohms_under_1k():
    """Plain ohm values under 1k stay in Ω."""
    q = ResistorSource().query(_spec(100), package_hint="0402")
    assert q.description_patterns == ("% 100Ω%",)


def test_post_filter_is_identity():
    """ResistorSource.post_filter returns rows unchanged."""
    src = ResistorSource()
    spec = _spec(10000)
    rows = [
        _row("C1", "0402", "10kΩ 1% 0.1W"),
        _row("C2", "0402", "10kΩ 5% 0.1W"),
    ]
    result = src.post_filter(rows, spec, package_hint="0402")
    assert result is rows or result == rows


def test_query_includes_min_stock():
    q = ResistorSource(min_stock=500).query(_spec(10000), package_hint="0402")
    assert q.min_stock == 500


def test_query_fractional_value():
    """4.7kΩ → pattern '% 4.7kΩ%'."""
    q = ResistorSource().query(_spec(4700), package_hint="0402")
    assert q.description_patterns == ("% 4.7kΩ%",)
