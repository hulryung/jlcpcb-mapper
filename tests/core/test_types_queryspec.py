from jlcpcb_mapper.core.types import QuerySpec

def test_queryspec_defaults():
    q = QuerySpec(category_like="%")
    assert q.category_like == "%"
    assert q.package is None
    assert q.description_patterns == ()
    assert q.mpn_patterns == ()
    assert q.min_stock == 0
    assert q.order_by == "basic DESC, preferred DESC, stock DESC"
    assert q.limit == 50

def test_queryspec_frozen_and_hashable():
    q = QuerySpec(category_like="Chip Resistor%", package="0402",
                  description_patterns=("% 10kΩ%",), min_stock=1000)
    {q: "ok"}

def test_queryspec_tuple_patterns():
    q = QuerySpec(category_like="%", description_patterns=("a", "b"))
    assert q.description_patterns == ("a", "b")
