import pytest
from jlcpcb_mapper.core.types import Value, QuerySpec
from jlcpcb_mapper.categories.spec.inductor import InductorSpec
from jlcpcb_mapper.components.candidate_sources import InductorSource
from jlcpcb_mapper.parts_db import PartRow


def _spec(mag: float, unit: str) -> InductorSpec:
    return InductorSpec(value=Value(mag, unit))


def _row(lcsc, pkg, desc, stock=10000, basic=0, preferred=0):
    return PartRow(lcsc=lcsc, category="Inductor (SMD)", mfr="Y",
                   mfr_part="X", package=pkg, description=desc,
                   basic=basic, preferred=preferred, stock=stock, price=0.01)


def test_query_33uH_0805():
    q = InductorSource().query(_spec(33, "µH"), package_hint="0805")
    assert "%Inductor%" in q.category_like
    assert q.package == "0805"
    assert q.description_patterns == ("%33uH%",)


def test_query_4_7uH_0805():
    q = InductorSource().query(_spec(4.7, "µH"), package_hint="0805")
    assert q.description_patterns == ("%4.7uH%",)


def test_query_10nH_0603():
    q = InductorSource().query(_spec(10, "nH"), package_hint="0603")
    assert q.package == "0603"
    assert q.description_patterns == ("%10nH%",)


def test_query_1mH():
    q = InductorSource().query(_spec(1, "mH"), package_hint="0805")
    assert q.description_patterns == ("%1mH%",)


def test_query_micro_sign_normalized():
    """Value stored with µ (U+00B5) → display gives '33µH' → normalized to '33uH'."""
    q = InductorSource().query(_spec(33, "µH"), package_hint="0805")
    # µ should become u in the DB pattern
    assert q.description_patterns == ("%33uH%",)
    assert "µ" not in q.description_patterns[0]


def test_query_no_package_hint():
    """No package hint → package=None in QuerySpec."""
    q = InductorSource().query(_spec(33, "µH"), package_hint="")
    assert q.package is None


def test_query_min_stock_forwarded():
    q = InductorSource(min_stock=500).query(_spec(33, "µH"), package_hint="0805")
    assert q.min_stock == 500


def test_post_filter_identity():
    """post_filter returns rows unchanged."""
    src = InductorSource()
    rows = [
        _row("C1", "0805", "33uH 20% 0805"),
        _row("C2", "0805", "33uH 10% 0805"),
    ]
    result = src.post_filter(rows, _spec(33, "µH"), package_hint="0805")
    assert result is rows or result == rows
