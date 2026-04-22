import pytest
from jlcpcb_mapper.core.registry import Registry
from jlcpcb_mapper.categories.base import Category

class _M:
    def __init__(self, ids): self.ids = ids
    def matches(self, lib_id): return lib_id in self.ids

def _cat(name, ids):
    return Category(
        name=name, matcher=_M(ids), value_parser=None, package_extractor=None,
        default_package="", candidate_source=None, scorer=None,
        footprint_resolver=None, prompt_hook=None,
    )

def test_lookup_hits_first_matching_category():
    r = Registry()
    r.register(_cat("resistor", ["Device:R"]))
    r.register(_cat("capacitor", ["Device:C"]))
    assert r.lookup("Device:R").name == "resistor"
    assert r.lookup("Device:C").name == "capacitor"

def test_lookup_returns_none_when_no_match():
    r = Registry()
    r.register(_cat("resistor", ["Device:R"]))
    assert r.lookup("Device:Unknown") is None

def test_register_rejects_duplicate_names():
    r = Registry()
    r.register(_cat("resistor", ["Device:R"]))
    with pytest.raises(ValueError, match="duplicate"):
        r.register(_cat("resistor", ["Device:R2"]))
