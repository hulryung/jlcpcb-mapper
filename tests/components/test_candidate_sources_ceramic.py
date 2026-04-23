"""Unit tests for CeramicCapSource."""
from jlcpcb_mapper.core.types import Value
from jlcpcb_mapper.categories.spec.cap import CeramicCapSpec
from jlcpcb_mapper.components.candidate_sources import CeramicCapSource
from jlcpcb_mapper.io.parts_db import PartRow


def _row(lcsc, pkg, desc, stock=10000, basic=0, preferred=0):
    return PartRow(
        lcsc=lcsc, category="Multilayer Ceramic Capacitor", mfr="Y", mfr_part="X",
        package=pkg, description=desc, basic=basic, preferred=preferred,
        stock=stock, price=0.01,
    )


def test_query_10uf_0603():
    """10µF 0603 → category_like includes Ceramic Capacitor, exact package, uF pattern."""
    spec = CeramicCapSpec(value=Value(10, "µF"))
    q = CeramicCapSource().query(spec, package_hint="0603")
    assert "%Ceramic Capacitor%" in q.category_like
    assert q.package == "0603"
    assert q.description_patterns == ("%10uF%",)


def test_query_100nf_0402():
    """100nF 0402 → nF kept as-is."""
    spec = CeramicCapSpec(value=Value(100, "nF"))
    q = CeramicCapSource().query(spec, package_hint="0402")
    assert q.package == "0402"
    assert q.description_patterns == ("%100nF%",)


def test_query_4_7uf_0805():
    """4.7µF 0805 → fractional value, µ→u."""
    spec = CeramicCapSpec(value=Value(4.7, "µF"))
    q = CeramicCapSource().query(spec, package_hint="0805")
    assert q.package == "0805"
    assert q.description_patterns == ("%4.7uF%",)


def test_query_normalizes_greek_mu():
    """Greek mu (U+03BC μ) should also be normalized to ASCII u."""
    spec = CeramicCapSpec(value=Value(10, "μF"))  # U+03BC
    q = CeramicCapSource().query(spec, package_hint="0603")
    assert q.description_patterns == ("%10uF%",)


def test_query_min_stock_propagated():
    spec = CeramicCapSpec(value=Value(100, "nF"))
    q = CeramicCapSource(min_stock=500).query(spec, package_hint="0402")
    assert q.min_stock == 500


def test_post_filter_is_identity():
    """post_filter returns rows unchanged (no client-side filtering needed)."""
    src = CeramicCapSource()
    spec = CeramicCapSpec(value=Value(10, "µF"))
    rows = [
        _row("C1", "0603", "10uF X7R 10V 0603"),
        _row("C2", "0603", "10uF Y5V 10V 0603"),
    ]
    result = src.post_filter(rows, spec, package_hint="0603")
    assert result is rows or result == rows
