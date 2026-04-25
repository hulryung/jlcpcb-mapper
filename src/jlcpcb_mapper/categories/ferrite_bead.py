"""FERRITE_BEAD category bundle."""
from __future__ import annotations
from pathlib import Path
from .base import Category
from ..components.matchers import LibIdAny
from ..components.value_parsers import FerriteBeadValueParser
from ..components.package_extractors import RegexFromRules
from ..components.candidate_sources import FerriteBeadSource
from ..components.scorers import GenericBasicStockScorer
from ..components.footprint_resolvers import BuiltinMap, EasyedaFallback, Composite
from ..components.prompt_hooks import GenericPromptHook


_PACKAGE_RULES = [
    # KiCad schematic symbols typically pair FerriteBead with a resistor footprint.
    (r"^Resistor_SMD:R_(\d{4})_", lambda m: m.group(1)),
    (r"^Inductor_SMD:L_(\d{4})_", lambda m: m.group(1)),
]

# Built-in footprint map: ferrite beads use the standard resistor SMD footprints.
_BUILTIN: dict[str, str] = {
    "0402": "Resistor_SMD:R_0402_1005Metric",
    "0603": "Resistor_SMD:R_0603_1608Metric",
    "0805": "Resistor_SMD:R_0805_2012Metric",
    "1206": "Resistor_SMD:R_1206_3216Metric",
}


def make(fp_out_dir: Path) -> Category:
    return Category(
        name="ferrite_bead",
        matcher=LibIdAny(["Device:FerriteBead"]),
        value_parser=FerriteBeadValueParser(),
        package_extractor=RegexFromRules(_PACKAGE_RULES),
        default_package="0603",
        candidate_source=FerriteBeadSource(),
        scorer=GenericBasicStockScorer(),
        footprint_resolver=Composite([
            BuiltinMap(_BUILTIN),
            EasyedaFallback(out_dir=fp_out_dir),
        ]),
        prompt_hook=GenericPromptHook(),
    )
