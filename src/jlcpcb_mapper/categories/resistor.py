"""RESISTOR category bundle."""
from __future__ import annotations
from pathlib import Path
from .base import Category
from ..components.matchers import LibIdAny
from ..components.value_parsers import ResistorValueParser
from ..components.package_extractors import RegexFromRules
from ..components.candidate_sources import ResistorSource
from ..components.scorers import GenericBasicStockScorer
from ..components.footprint_resolvers import BuiltinMap, EasyedaFallback, Composite
from ..components.prompt_hooks import GenericPromptHook


_PACKAGE_RULES = [
    (r"^Resistor_SMD:R_(\d{4})_", lambda m: m.group(1)),
]

_BUILTIN = {
    "0201": "Resistor_SMD:R_0201_0603Metric",
    "0402": "Resistor_SMD:R_0402_1005Metric",
    "0603": "Resistor_SMD:R_0603_1608Metric",
    "0805": "Resistor_SMD:R_0805_2012Metric",
    "1206": "Resistor_SMD:R_1206_3216Metric",
}


def make(fp_out_dir: Path) -> Category:
    return Category(
        name="resistor",
        matcher=LibIdAny(["Device:R"]),
        value_parser=ResistorValueParser(),
        package_extractor=RegexFromRules(_PACKAGE_RULES),
        default_package="0402",
        candidate_source=ResistorSource(),
        scorer=GenericBasicStockScorer(),
        footprint_resolver=Composite([
            BuiltinMap(_BUILTIN),
            EasyedaFallback(out_dir=fp_out_dir),
        ]),
        prompt_hook=GenericPromptHook(),
    )
