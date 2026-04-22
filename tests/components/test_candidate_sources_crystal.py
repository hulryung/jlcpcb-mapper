import pytest
from jlcpcb_mapper.core.types import Value, QuerySpec
from jlcpcb_mapper.categories.spec.crystal import CrystalSpec
from jlcpcb_mapper.components.candidate_sources import CrystalSource
from jlcpcb_mapper.parts_db import PartRow


def _spec(mag, unit) -> CrystalSpec:
    return CrystalSpec(value=Value(mag, unit))


def _row(lcsc, pkg, desc, stock=10000, basic=0):
    return PartRow(
        lcsc=lcsc, category="Crystal", mfr="Y",
        mfr_part="X", package=pkg, description=desc,
        basic=basic, preferred=0, stock=stock, price=0.01,
    )


# --- Query tests ---

def test_query_16mhz_with_package():
    q = CrystalSource().query(_spec(16, "MHz"), package_hint="SMD-3225")
    assert q.category_like == "%Crystal%"
    assert q.package is None  # package filter happens in post_filter
    assert q.description_patterns == ("%16MHz%",)


def test_query_32khz_with_package():
    q = CrystalSource().query(_spec(32.768, "kHz"), package_hint="SMD-3215")
    assert q.description_patterns == ("%32.768kHz%",)


def test_query_package_is_none_always():
    """CrystalSource never passes package to SQL; post_filter handles it."""
    q = CrystalSource().query(_spec(16, "MHz"), package_hint="SMD-3225")
    assert q.package is None


def test_query_min_stock_forwarded():
    q = CrystalSource(min_stock=500).query(_spec(16, "MHz"), package_hint="SMD-3225")
    assert q.min_stock == 500


def test_query_category_like_contains_crystal():
    q = CrystalSource().query(_spec(16, "MHz"), package_hint="")
    assert "Crystal" in q.category_like


# --- post_filter tests ---

def test_post_filter_keeps_matching_package():
    src = CrystalSource()
    rows = [
        _row("C1", "SMD-3225", "16MHz crystal SMD-3225"),
        _row("C2", "SMD-2016", "16MHz crystal SMD-2016"),
    ]
    result = src.post_filter(rows, _spec(16, "MHz"), package_hint="SMD-3225")
    assert [r.lcsc for r in result] == ["C1"]


def test_post_filter_case_insensitive():
    src = CrystalSource()
    rows = [
        _row("C1", "smd-3225", "16MHz crystal"),
    ]
    result = src.post_filter(rows, _spec(16, "MHz"), package_hint="SMD-3225")
    assert [r.lcsc for r in result] == ["C1"]


def test_post_filter_empty_hint_returns_empty():
    src = CrystalSource()
    rows = [
        _row("C1", "SMD-3225", "16MHz crystal SMD-3225"),
    ]
    result = src.post_filter(rows, _spec(16, "MHz"), package_hint="")
    assert result == []


def test_post_filter_none_hint_returns_empty():
    src = CrystalSource()
    rows = [_row("C1", "SMD-3225", "16MHz crystal")]
    result = src.post_filter(rows, _spec(16, "MHz"), package_hint=None)
    assert result == []


def test_post_filter_substring_match():
    """Hint substring match: 'SMD-3225' is in 'SMD-3225-4Pin'."""
    src = CrystalSource()
    rows = [
        _row("C1", "SMD-3225-4Pin", "16MHz crystal"),
        _row("C2", "HC-49", "16MHz crystal"),
    ]
    result = src.post_filter(rows, _spec(16, "MHz"), package_hint="SMD-3225")
    assert [r.lcsc for r in result] == ["C1"]


def test_post_filter_no_match_returns_empty():
    src = CrystalSource()
    rows = [_row("C1", "HC-49", "16MHz crystal")]
    result = src.post_filter(rows, _spec(16, "MHz"), package_hint="SMD-3225")
    assert result == []
