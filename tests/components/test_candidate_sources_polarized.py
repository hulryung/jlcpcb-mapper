from jlcpcb_mapper.core.types import Value
from jlcpcb_mapper.categories.spec.cap import PolarizedCapSpec
from jlcpcb_mapper.components.candidate_sources import PolarizedCapSource
from jlcpcb_mapper.io.parts_db import PartRow


def _row(lcsc, pkg, desc, stock=10000, basic=0, preferred=0):
    return PartRow(lcsc=lcsc, category="Aluminum Electrolytic", mfr="Y", mfr_part="X",
                   package=pkg, description=desc, basic=basic, preferred=preferred,
                   stock=stock, price=0.01)


def test_query_includes_value_and_min_stock():
    spec = PolarizedCapSpec(value=Value(220, "µF"), voltage=Value(10, "V"))
    q = PolarizedCapSource(min_stock=1000).query(spec, package_hint="D6.3")
    assert "Aluminum Electrolytic" in q.category_like
    assert q.min_stock == 1000
    # µ converted to ASCII u in description search
    assert ("%220uF%",) == q.description_patterns


def test_post_filter_keeps_package_substring():
    src = PolarizedCapSource()
    spec = PolarizedCapSpec(value=Value(220, "µF"), voltage=Value(10, "V"))
    rows = [
        _row("C1", "D6.3", "220uF 10V"),
        _row("C2", "D8",   "220uF 10V"),
        _row("C3", "D6.3", "220uF 10V"),
    ]
    kept = src.post_filter(rows, spec, package_hint="D6.3")
    assert {r.lcsc for r in kept} == {"C1", "C3"}


def test_post_filter_voltage_ge_required():
    src = PolarizedCapSource()
    spec = PolarizedCapSpec(value=Value(220, "µF"), voltage=Value(10, "V"))
    rows = [
        _row("C1", "D6.3", "220uF 6.3V"),
        _row("C2", "D6.3", "220uF 10V"),
        _row("C3", "D6.3", "220uF 25V"),
        _row("C4", "D6.3", "220uF"),     # no voltage → kept as candidate
    ]
    kept = src.post_filter(rows, spec, package_hint="D6.3")
    assert {r.lcsc for r in kept} == {"C2", "C3", "C4"}


def test_post_filter_no_voltage_spec_keeps_all():
    src = PolarizedCapSource()
    spec = PolarizedCapSpec(value=Value(220, "µF"), voltage=None)
    rows = [
        _row("C1", "D6.3", "220uF 6.3V"),
        _row("C2", "D6.3", "220uF 25V"),
    ]
    kept = src.post_filter(rows, spec, package_hint="D6.3")
    assert {r.lcsc for r in kept} == {"C1", "C2"}


def test_query_normalizes_greek_mu():
    """Greek mu (U+03BC) is also normalized to ASCII u in description pattern."""
    spec = PolarizedCapSpec(value=Value(220, "μF"), voltage=None)
    q = PolarizedCapSource().query(spec, package_hint="")
    assert q.description_patterns == ("%220uF%",)


def test_post_filter_accepts_concatenated_vdc_form():
    """JLCPCB descriptions sometimes concatenate V with DC/AC (e.g., '10VDC')."""
    src = PolarizedCapSource()
    spec = PolarizedCapSpec(value=Value(220, "µF"), voltage=Value(10, "V"))
    rows = [
        _row("C1", "D6.3", "220uF 10VDC"),   # exact, concatenated
        _row("C2", "D6.3", "220uF 6.3VDC"),  # under-rated, concatenated — should drop
    ]
    kept = src.post_filter(rows, spec, package_hint="D6.3")
    assert {r.lcsc for r in kept} == {"C1"}
