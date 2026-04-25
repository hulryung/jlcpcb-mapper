"""POLARIZED_CAP category bundle."""
from __future__ import annotations
from pathlib import Path
from .base import Category
from ..components.matchers import LibIdAny
from ..components.value_parsers import CapValueParser
from ..components.package_extractors import RegexFromRules
from ..components.candidate_sources import PolarizedCapSource
from ..components.scorers import PolarizedCapScorer
from ..components.footprint_resolvers import BuiltinMap, EasyedaFallback, Composite
from ..components.prompt_hooks import CapPromptHook


_PACKAGE_RULES = [
    # SMD: KiCad libs use both `CP_Elec_` and `C_Elec_` for polarized SMD caps.
    (r"^Capacitor_SMD:(?:CP_Elec_|C_Elec_)(\d+\.?\d*x\d+\.?\d*)",
     lambda m: f"D{m.group(1).split('x')[0]}"),
    # THT: keep the `mm` suffix as a sentinel so the source can force THT.
    (r"^Capacitor_THT:CP_Radial_D(\d+\.?\d*)mm",
     lambda m: f"D{m.group(1)}mm"),
]


def make(fp_out_dir: Path) -> Category:
    return Category(
        name="polarized_capacitor",
        matcher=LibIdAny(["Device:CP", "Device:CP_Small",
                          "Device:C_Polarized", "Device:C_Polarized_Small"]),
        value_parser=CapValueParser(keep_voltage=True),
        package_extractor=RegexFromRules(_PACKAGE_RULES),
        default_package="D6.3",
        candidate_source=PolarizedCapSource(),
        scorer=PolarizedCapScorer(),
        footprint_resolver=Composite([
            BuiltinMap({}),                 # polarized caps: no good built-ins yet
            EasyedaFallback(out_dir=fp_out_dir),
        ]),
        prompt_hook=CapPromptHook(emphasize_voltage=True),
    )
