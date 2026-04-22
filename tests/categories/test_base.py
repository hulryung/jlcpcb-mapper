from jlcpcb_mapper.categories.base import (
    Category, Matcher, ValueParser, PackageExtractor,
    CandidateSource, Scorer, FootprintResolver, PromptHook,
    ResolveResult,
)

def test_category_is_frozen():
    import dataclasses
    class _M:
        def matches(self, lib_id): return False
    cat = Category(
        name="x", matcher=_M(), value_parser=None, package_extractor=None,
        default_package="", candidate_source=None, scorer=None,
        footprint_resolver=None, prompt_hook=None,
    )
    try:
        cat.name = "y"  # type: ignore
    except dataclasses.FrozenInstanceError:
        return
    raise AssertionError("Category should be frozen")

def test_resolve_result_defaults():
    r = ResolveResult(footprint="X:Y", downloaded=False)
    assert r.footprint == "X:Y"
    assert r.downloaded is False
    assert r.download_failed is False
