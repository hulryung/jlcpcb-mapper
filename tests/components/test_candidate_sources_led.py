import pytest
from jlcpcb_mapper.core.types import Value, QuerySpec
from jlcpcb_mapper.categories.spec.led import LEDSpec
from jlcpcb_mapper.components.candidate_sources import LEDSource
from jlcpcb_mapper.io.parts_db import PartRow


def _spec(token: str) -> LEDSpec:
    return LEDSpec(value=Value(0, token))


def _row(lcsc, pkg, desc, stock=10000, basic=0, preferred=0):
    return PartRow(
        lcsc=lcsc, category="Light Emitting Diode (SMD)", mfr="Y",
        mfr_part="X", package=pkg, description=desc,
        basic=basic, preferred=preferred, stock=stock, price=0.01,
    )


def test_query_red_0603():
    q = LEDSource().query(_spec("RED"), package_hint="0603")
    assert q.category_like == "Light Emitting Diode%"
    assert q.package == "0603"
    assert q.description_patterns == ("%RED%",)


def test_query_ws2812b_empty_package():
    q = LEDSource().query(_spec("WS2812B"), package_hint="")
    assert q.package is None
    assert q.description_patterns == ("%WS2812B%",)


def test_query_empty_token_defensive():
    """An empty token (shouldn't normally happen) → no description patterns."""
    spec = LEDSpec(value=Value(0, ""))
    q = LEDSource().query(spec, package_hint="0603")
    assert q.description_patterns == ()


def test_query_min_stock_forwarded():
    q = LEDSource(min_stock=1000).query(_spec("RED"), package_hint="0603")
    assert q.min_stock == 1000


def test_query_category_like_no_leading_percent():
    """category_like must start with 'Light' not '%Light'."""
    q = LEDSource().query(_spec("RED"), package_hint="0603")
    assert q.category_like.startswith("Light Emitting Diode")
    assert not q.category_like.startswith("%")


def test_post_filter_identity():
    """post_filter returns rows unchanged."""
    src = LEDSource()
    rows = [
        _row("C1", "0603", "RED LED 0603 620nm"),
        _row("C2", "0603", "RED LED 0603 625nm"),
    ]
    result = src.post_filter(rows, _spec("RED"), package_hint="0603")
    assert result is rows or result == rows
