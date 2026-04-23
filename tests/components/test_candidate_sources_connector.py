"""Tests for ConnectorSource."""
from jlcpcb_mapper.components.candidate_sources import ConnectorSource
from jlcpcb_mapper.categories.spec.connector import ConnectorSpec
from jlcpcb_mapper.io.parts_db import PartRow


def _spec(structure: str, pins: int, value: str = "") -> ConnectorSpec:
    return ConnectorSpec(structure=structure, pins=pins, value=value)


def _row(lcsc: str, pkg: str, description: str = "") -> PartRow:
    return PartRow(
        lcsc=lcsc, category="Connectors", mfr="Test", mfr_part=lcsc,
        package=pkg, description=description,
        basic=0, preferred=0, stock=10000, price=0.10,
    )


# --- Query tests: 1xN ---

def test_1xn_query_category_like():
    q = ConnectorSource().query(_spec("1xN", 5), package_hint="")
    assert q.category_like == "%Connector%"


def test_1xn_query_no_value_no_description_patterns():
    q = ConnectorSource().query(_spec("1xN", 5, ""), package_hint="")
    assert q.description_patterns == ()


def test_1xn_query_with_value_adds_pattern():
    q = ConnectorSource().query(_spec("1xN", 6, "JST-PH-6"), package_hint="PinSocket_1x06")
    assert q.description_patterns == ("%JST-PH-6%",)


def test_1xn_query_package_is_none():
    """package=None because post_filter handles it."""
    q = ConnectorSource().query(_spec("1xN", 5), package_hint="PinSocket_1x05")
    assert q.package is None


def test_1xn_query_respects_limit():
    q = ConnectorSource(limit=30).query(_spec("1xN", 5), package_hint="")
    assert q.limit == 30


def test_1xn_query_respects_min_stock():
    q = ConnectorSource(min_stock=100).query(_spec("1xN", 5), package_hint="")
    assert q.min_stock == 100


# --- Query tests: 2xN ---

def test_2xn_without_hint_tight_query():
    """2xN without package hint returns tight no-match query (category_like=%, limit=1)."""
    q = ConnectorSource().query(_spec("2xN", 10), package_hint="")
    assert q.category_like == "%"
    assert q.limit == 1


def test_2xn_with_hint_broad_query():
    q = ConnectorSource().query(_spec("2xN", 10), package_hint="PinSocket_2x10")
    assert q.category_like == "%Connector%"


def test_2xn_with_hint_limit_respected():
    q = ConnectorSource(limit=40).query(_spec("2xN", 10), package_hint="PinSocket_2x10")
    assert q.limit == 40


# --- Query tests: generic ---

def test_generic_tight_query():
    q = ConnectorSource().query(_spec("generic", 0), package_hint="")
    assert q.category_like == "%"
    assert q.limit == 1


def test_generic_with_hint_still_tight():
    q = ConnectorSource().query(_spec("generic", 0), package_hint="USB")
    assert q.category_like == "%"
    assert q.limit == 1


# --- post_filter tests: generic ---

def test_generic_post_filter_returns_empty():
    src = ConnectorSource()
    rows = [_row("C1", "USB-C")]
    assert src.post_filter(rows, _spec("generic", 0), package_hint="") == []


def test_generic_post_filter_with_hint_returns_empty():
    src = ConnectorSource()
    rows = [_row("C1", "USB-C")]
    assert src.post_filter(rows, _spec("generic", 0), package_hint="USB") == []


# --- post_filter tests: 2xN ---

def test_2xn_no_hint_post_filter_returns_empty():
    src = ConnectorSource()
    rows = [_row("C1", "PinSocket_2x10")]
    assert src.post_filter(rows, _spec("2xN", 10), package_hint="") == []


def test_2xn_with_hint_post_filter_keeps_matching():
    src = ConnectorSource()
    rows = [
        _row("C1", "PinSocket_2x10_P2.54mm"),
        _row("C2", "PinSocket_1x10_P2.54mm"),
        _row("C3", "PinSocket_2x10"),
    ]
    result = src.post_filter(rows, _spec("2xN", 10), package_hint="PinSocket_2x10")
    assert [r.lcsc for r in result] == ["C1", "C3"]


def test_2xn_post_filter_case_insensitive():
    src = ConnectorSource()
    rows = [_row("C1", "PINSOCKET_2X10")]
    result = src.post_filter(rows, _spec("2xN", 10), package_hint="PinSocket_2x10")
    assert [r.lcsc for r in result] == ["C1"]


# --- post_filter tests: 1xN ---

def test_1xn_post_filter_pass_through():
    """1xN post_filter returns all rows unchanged."""
    src = ConnectorSource()
    rows = [
        _row("C1", "PinSocket_1x06"),
        _row("C2", "SomeOtherPackage"),
    ]
    result = src.post_filter(rows, _spec("1xN", 6), package_hint="PinSocket_1x06")
    assert [r.lcsc for r in result] == ["C1", "C2"]


def test_1xn_post_filter_no_hint_pass_through():
    """1xN post_filter still passes through even with empty hint."""
    src = ConnectorSource()
    rows = [_row("C1", "PinSocket_1x06")]
    result = src.post_filter(rows, _spec("1xN", 6), package_hint="")
    assert [r.lcsc for r in result] == ["C1"]


def test_query_escapes_like_wildcards_in_value():
    """User value with % or _ must be escaped before SQL LIKE."""
    src = ConnectorSource()
    spec = ConnectorSpec(structure="1xN", pins=5, value="Conn_01x5")
    q = src.query(spec, package_hint="")
    # "_" in value must be escaped to "\_" so LIKE treats it literally
    assert q.description_patterns == (r"%Conn\_01x5%",)


def test_query_escapes_percent_in_value():
    src = ConnectorSource()
    spec = ConnectorSpec(structure="1xN", pins=5, value="100%pin")
    q = src.query(spec, package_hint="")
    assert q.description_patterns == (r"%100\%pin%",)
