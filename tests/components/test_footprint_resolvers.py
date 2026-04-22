from jlcpcb_mapper.components.footprint_resolvers import BuiltinMap, Composite
from jlcpcb_mapper.categories.base import ResolveResult
from jlcpcb_mapper.parts_db import PartRow


def _part(lcsc="C1", package="0402"):
    return PartRow(lcsc=lcsc, category="x", mfr="y", mfr_part="z",
                   package=package, description="", basic=0, preferred=0,
                   stock=0, price=0.0)


def test_builtin_map_hit():
    r = BuiltinMap({"0402": "Resistor_SMD:R_0402_1005Metric"})
    res = r.resolve(_part(package="0402"), package_hint="0402")
    assert res == ResolveResult(footprint="Resistor_SMD:R_0402_1005Metric", downloaded=False)


def test_builtin_map_miss_returns_empty():
    r = BuiltinMap({"0402": "Resistor_SMD:R_0402_1005Metric"})
    res = r.resolve(_part(package="0603"), package_hint="0603")
    assert res.footprint == ""
    assert res.downloaded is False


def test_composite_tries_in_order_until_nonempty():
    class _Stub:
        def __init__(self, fp, downloaded=False): self.fp, self.d = fp, downloaded
        def resolve(self, part, hint):
            return ResolveResult(footprint=self.fp, downloaded=self.d)
    c = Composite([_Stub(""), _Stub("LCSC:X_fp", downloaded=True)])
    res = c.resolve(_part(), package_hint="")
    assert res.footprint == "LCSC:X_fp"
    assert res.downloaded is True


def test_composite_all_fail_returns_failed():
    class _Stub:
        def resolve(self, part, hint):
            return ResolveResult(footprint="", downloaded=False, download_failed=True)
    c = Composite([_Stub()])
    res = c.resolve(_part(), package_hint="")
    assert res.download_failed is True
