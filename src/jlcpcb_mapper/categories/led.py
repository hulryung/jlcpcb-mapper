"""LED category bundle."""
from __future__ import annotations
from pathlib import Path
from .base import Category
from ..components.matchers import LibIdAny
from ..components.value_parsers import LEDValueParser
from ..components.package_extractors import RegexFromRules
from ..components.candidate_sources import LEDSource
from ..components.scorers import GenericBasicStockScorer
from ..components.footprint_resolvers import BuiltinMap, EasyedaFallback, Composite
from ..components.prompt_hooks import GenericPromptHook


_PACKAGE_RULES = [
    (r"^LED_SMD:LED_(\d{4})_", lambda m: m.group(1)),
]

_BUILTIN = {
    "0402": "LED_SMD:LED_0402_1005Metric",
    "0603": "LED_SMD:LED_0603_1608Metric",
    "0805": "LED_SMD:LED_0805_2012Metric",
}


def make(fp_out_dir: Path) -> Category:
    return Category(
        name="led",
        matcher=LibIdAny(["Device:LED"]),
        value_parser=LEDValueParser(),
        package_extractor=RegexFromRules(_PACKAGE_RULES),
        default_package="0603",
        candidate_source=LEDSource(),
        scorer=GenericBasicStockScorer(),
        footprint_resolver=Composite([
            BuiltinMap(_BUILTIN),
            EasyedaFallback(out_dir=fp_out_dir),
        ]),
        prompt_hook=GenericPromptHook(),
    )
