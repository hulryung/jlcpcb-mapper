from jlcpcb_mapper.core.types import Value
from jlcpcb_mapper.categories.spec.resistor import ResistorSpec
from jlcpcb_mapper.components.scorers import GenericBasicStockScorer
from jlcpcb_mapper.parts_db import PartRow
from jlcpcb_mapper.observability.trace import Trace


def _row(lcsc, basic=0, preferred=0, stock=10000, desc="10kΩ 1% 0.1W"):
    return PartRow(lcsc=lcsc, category="Chip Resistor - Surface Mount", mfr="X",
                   mfr_part="Y", package="0402", description=desc,
                   basic=basic, preferred=preferred, stock=stock, price=0.01)


_SPEC = ResistorSpec(value=Value(10000, "Ω"))


def test_basic_beats_non_basic_same_stock():
    s = GenericBasicStockScorer()
    t = Trace()
    basic_score = s.score(_row("C1", basic=1), _SPEC, t)
    non_basic_score = s.score(_row("C2", basic=0), _SPEC, t)
    assert basic_score > non_basic_score


def test_preferred_non_basic_beats_neither():
    s = GenericBasicStockScorer()
    t = Trace()
    preferred_score = s.score(_row("C1", basic=0, preferred=1), _SPEC, t)
    neither_score = s.score(_row("C2", basic=0, preferred=0), _SPEC, t)
    assert preferred_score > neither_score


def test_trace_records_breakdown_with_lcsc():
    s = GenericBasicStockScorer()
    t = Trace()
    s.score(_row("C42", basic=1), _SPEC, t)
    assert any(
        e.stage == "score_breakdown" and e.data.get("lcsc") == "C42"
        for e in t.events
    )


def test_weights_sum_to_one():
    s = GenericBasicStockScorer()
    assert abs(s.W_BASIC + s.W_PREFERRED + s.W_STOCK - 1.0) < 1e-9


def test_high_stock_increases_score():
    s = GenericBasicStockScorer()
    t = Trace()
    low_stock = s.score(_row("C1", basic=0, stock=100), _SPEC, t)
    high_stock = s.score(_row("C2", basic=0, stock=100_000), _SPEC, t)
    assert high_stock > low_stock
