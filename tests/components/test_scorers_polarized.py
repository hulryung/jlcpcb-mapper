from jlcpcb_mapper.core.types import Value
from jlcpcb_mapper.categories.spec.cap import PolarizedCapSpec
from jlcpcb_mapper.components.scorers import PolarizedCapScorer
from jlcpcb_mapper.parts_db import PartRow
from jlcpcb_mapper.observability.trace import Trace


def _row(lcsc, basic=0, preferred=0, stock=10000, desc="220uF 10V"):
    return PartRow(lcsc=lcsc, category="Aluminum Electrolytic", mfr="X", mfr_part="Y",
                   package="D6.3", description=desc, basic=basic, preferred=preferred,
                   stock=stock, price=0.01)


def test_basic_outranks_extended_with_same_voltage():
    s = PolarizedCapScorer()
    spec = PolarizedCapSpec(value=Value(220, "µF"), voltage=Value(10, "V"))
    t = Trace()
    assert s.score(_row("C1", basic=1), spec, t) > s.score(_row("C2"), spec, t)


def test_exact_voltage_beats_higher_voltage():
    s = PolarizedCapScorer()
    spec = PolarizedCapSpec(value=Value(220, "µF"), voltage=Value(10, "V"))
    exact = _row("C1", basic=1, desc="220uF 10V")
    higher = _row("C2", basic=1, desc="220uF 25V")
    t = Trace()
    assert s.score(exact, spec, t) > s.score(higher, spec, t)


def test_scorer_records_breakdown_in_trace():
    s = PolarizedCapScorer()
    spec = PolarizedCapSpec(value=Value(220, "µF"), voltage=Value(10, "V"))
    t = Trace()
    s.score(_row("C1", basic=1), spec, t)
    assert any(e.stage == "score_breakdown" and "C1" in str(e.data.get("lcsc", ""))
               for e in t.events)


def test_concatenated_vdc_voltage_is_recognized():
    """'10VDC' in description should score same as '10V'."""
    s = PolarizedCapScorer()
    spec = PolarizedCapSpec(value=Value(220, "µF"), voltage=Value(10, "V"))
    t = Trace()
    a = s.score(_row("C1", basic=1, desc="220uF 10VDC"), spec, t)
    b = s.score(_row("C2", basic=1, desc="220uF 10V"),   spec, t)
    assert a == b  # both get full W_VOLTAGE_EXACT
