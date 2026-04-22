"""CERAMIC_CAP category bundle."""
from __future__ import annotations
from pathlib import Path
from .base import Category
from ..components.matchers import LibIdAny
from ..components.value_parsers import CapValueParser
from ..components.package_extractors import RegexFromRules
from ..components.candidate_sources import CeramicCapSource
from ..components.scorers import GenericBasicStockScorer
from ..components.footprint_resolvers import BuiltinMap, EasyedaFallback, Composite
from ..components.prompt_hooks import GenericPromptHook


_PACKAGE_RULES = [
    (r"^Capacitor_SMD:C_(\d{4})_", lambda m: m.group(1)),
]

_BUILTIN = {
    "0201": "Capacitor_SMD:C_0201_0603Metric",
    "0402": "Capacitor_SMD:C_0402_1005Metric",
    "0603": "Capacitor_SMD:C_0603_1608Metric",
    "0805": "Capacitor_SMD:C_0805_2012Metric",
    "1206": "Capacitor_SMD:C_1206_3216Metric",
}


def make(fp_out_dir: Path) -> Category:
    return Category(
        name="ceramic_capacitor",
        matcher=LibIdAny(["Device:C"]),
        value_parser=CapValueParser(keep_voltage=False),
        package_extractor=RegexFromRules(_PACKAGE_RULES),
        default_package="0402",
        candidate_source=CeramicCapSource(),
        scorer=GenericBasicStockScorer(),
        footprint_resolver=Composite([
            BuiltinMap(_BUILTIN),
            EasyedaFallback(out_dir=fp_out_dir),
        ]),
        prompt_hook=GenericPromptHook(),
    )
