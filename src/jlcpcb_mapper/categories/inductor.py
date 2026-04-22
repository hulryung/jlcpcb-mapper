"""INDUCTOR category bundle."""
from __future__ import annotations
from pathlib import Path
from .base import Category
from ..components.matchers import LibIdAny
from ..components.value_parsers import InductorValueParser
from ..components.package_extractors import RegexFromRules
from ..components.candidate_sources import InductorSource
from ..components.scorers import GenericBasicStockScorer
from ..components.footprint_resolvers import BuiltinMap, EasyedaFallback, Composite
from ..components.prompt_hooks import GenericPromptHook


_PACKAGE_RULES = [
    (r"^Inductor_SMD:L_(\d{4})_", lambda m: m.group(1)),
]

# Legacy kicad_fp.py has NO builtin inductor entries.
# EasyedaFallback handles all footprint resolution.
_BUILTIN: dict[str, str] = {}


def make(fp_out_dir: Path) -> Category:
    return Category(
        name="inductor",
        matcher=LibIdAny(["Device:L"]),
        value_parser=InductorValueParser(),
        package_extractor=RegexFromRules(_PACKAGE_RULES),
        default_package="0805",  # common inductor SMD size
        candidate_source=InductorSource(),
        scorer=GenericBasicStockScorer(),
        footprint_resolver=Composite([
            BuiltinMap(_BUILTIN),        # empty — always misses
            EasyedaFallback(out_dir=fp_out_dir),
        ]),
        prompt_hook=GenericPromptHook(),
    )
