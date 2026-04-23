from jlcpcb_mapper.preflight import lib_id_coverage_report
from jlcpcb_mapper.core.registry import Registry
from jlcpcb_mapper.categories.base import Category


class _M:
    def __init__(self, ids): self.ids = set(ids)
    def matches(self, lib_id): return lib_id in self.ids


def _cat(name, ids):
    return Category(
        name=name, matcher=_M(ids),
        value_parser=None, package_extractor=None,
        default_package="", candidate_source=None,
        scorer=None, footprint_resolver=None, prompt_hook=None,
    )


def test_reports_matched_counts_per_category():
    r = Registry()
    r.register(_cat("resistor", {"Device:R"}))
    r.register(_cat("capacitor", {"Device:C"}))
    lib_ids = ["Device:R", "Device:R", "Device:C", "Device:C", "Device:C"]
    rep = lib_id_coverage_report(lib_ids, r)
    assert rep["matched"] == {"resistor": 2, "capacitor": 3}
    assert rep["unmatched"] == []
    assert rep["unmatched_counts"] == {}


def test_reports_unmatched_lib_ids():
    r = Registry()
    r.register(_cat("resistor", {"Device:R"}))
    lib_ids = ["Device:R", "Device:Q_NPN_CBE", "Device:Fuse", "Device:Q_NPN_CBE"]
    rep = lib_id_coverage_report(lib_ids, r)
    assert rep["matched"] == {"resistor": 1}
    assert set(rep["unmatched"]) == {"Device:Q_NPN_CBE", "Device:Fuse"}
    assert rep["unmatched_counts"] == {"Device:Q_NPN_CBE": 2, "Device:Fuse": 1}


def test_unmatched_sorted_alphabetically():
    r = Registry()
    lib_ids = ["Zz:Foo", "Aa:Bar", "Mm:Baz"]
    rep = lib_id_coverage_report(lib_ids, r)
    assert rep["unmatched"] == ["Aa:Bar", "Mm:Baz", "Zz:Foo"]


def test_empty_lib_ids_produces_empty_report():
    r = Registry()
    r.register(_cat("resistor", {"Device:R"}))
    rep = lib_id_coverage_report([], r)
    assert rep == {"matched": {}, "unmatched": [], "unmatched_counts": {}}


def test_all_unmatched_registry_returns_only_unmatched():
    r = Registry()   # empty registry
    lib_ids = ["Device:R", "Device:C"]
    rep = lib_id_coverage_report(lib_ids, r)
    assert rep["matched"] == {}
    assert rep["unmatched"] == ["Device:C", "Device:R"]
    assert rep["unmatched_counts"] == {"Device:R": 1, "Device:C": 1}
