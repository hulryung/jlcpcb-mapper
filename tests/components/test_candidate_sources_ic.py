"""Tests for ICSource."""
import pytest
from jlcpcb_mapper.core.types import QuerySpec
from jlcpcb_mapper.categories.spec.ic import ICSpec
from jlcpcb_mapper.components.candidate_sources import ICSource
from jlcpcb_mapper.parts_db import PartRow


def _spec(mpn: str) -> ICSpec:
    return ICSpec(mpn=mpn)


def _row(lcsc: str, pkg: str, mfr_part: str = "", stock: int = 10000, basic: int = 0) -> PartRow:
    return PartRow(
        lcsc=lcsc, category="Microcontroller", mfr="ST",
        mfr_part=mfr_part or lcsc, package=pkg,
        description=f"MCU {mfr_part}",
        basic=basic, preferred=0, stock=stock, price=0.50,
    )


# --- Query tests ---

def test_query_with_package_hint():
    q = ICSource().query(_spec("STM32F031K6T6"), package_hint="LQFP-32")
    assert q.category_like == "%"
    assert q.mpn_patterns == ("%STM32F031K6T6%",)
    assert q.package is None  # substring filter in post_filter


def test_query_no_package_hint_returns_tight_query():
    """When package_hint is empty, return limit=1 to minimize wasted work."""
    q = ICSource().query(_spec("STM32F031K6T6"), package_hint="")
    assert q.limit == 1


def test_query_no_package_hint_category_like():
    q = ICSource().query(_spec("STM32F031K6T6"), package_hint="")
    assert q.category_like == "%"


def test_query_min_stock_forwarded():
    q = ICSource(min_stock=500).query(_spec("STM32F031K6T6"), package_hint="LQFP-32")
    assert q.min_stock == 500


def test_query_limit_forwarded():
    q = ICSource(limit=30).query(_spec("STM32F031K6T6"), package_hint="LQFP-32")
    assert q.limit == 30


def test_query_mpn_with_percent_escaped():
    """% in MPN is LIKE-escaped to prevent wildcard expansion."""
    q = ICSource().query(_spec("MPN%FOO"), package_hint="SOT-23")
    assert q.mpn_patterns == (r"%MPN\%FOO%",)


def test_query_mpn_with_underscore_escaped():
    """_ in MPN is LIKE-escaped."""
    q = ICSource().query(_spec("LM2596S_3V3"), package_hint="SOT-23")
    assert q.mpn_patterns == (r"%LM2596S\_3V3%",)


# --- post_filter tests ---

def test_post_filter_keeps_matching_package():
    src = ICSource()
    rows = [
        _row("C1", "LQFP-32", "STM32F031K6T6"),
        _row("C2", "LQFP-64", "STM32F031K6T6"),
    ]
    result = src.post_filter(rows, _spec("STM32F031K6T6"), package_hint="LQFP-32")
    assert [r.lcsc for r in result] == ["C1"]


def test_post_filter_case_insensitive():
    src = ICSource()
    rows = [_row("C1", "lqfp-32", "STM32F031K6T6")]
    result = src.post_filter(rows, _spec("STM32F031K6T6"), package_hint="LQFP-32")
    assert [r.lcsc for r in result] == ["C1"]


def test_post_filter_empty_hint_returns_empty():
    src = ICSource()
    rows = [_row("C1", "LQFP-32", "STM32F031K6T6")]
    result = src.post_filter(rows, _spec("STM32F031K6T6"), package_hint="")
    assert result == []


def test_post_filter_none_hint_returns_empty():
    src = ICSource()
    rows = [_row("C1", "LQFP-32", "STM32F031K6T6")]
    result = src.post_filter(rows, _spec("STM32F031K6T6"), package_hint=None)
    assert result == []


def test_post_filter_substring_match():
    """'LQFP-32' hint is in 'LQFP-32_7x7mm' package string."""
    src = ICSource()
    rows = [
        _row("C1", "LQFP-32_7x7mm", "STM32F031K6T6"),
        _row("C2", "LQFP-64", "STM32F031K6T6"),
    ]
    result = src.post_filter(rows, _spec("STM32F031K6T6"), package_hint="LQFP-32")
    assert [r.lcsc for r in result] == ["C1"]
