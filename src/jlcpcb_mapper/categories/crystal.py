"""Crystal category bundle."""
from __future__ import annotations
from pathlib import Path
from .base import Category
from ..components.matchers import LibIdAny
from ..components.value_parsers import CrystalValueParser
from ..components.package_extractors import RegexFromRules
from ..components.candidate_sources import CrystalSource
from ..components.scorers import GenericBasicStockScorer
from ..components.footprint_resolvers import BuiltinMap, EasyedaFallback, Composite
from ..components.prompt_hooks import GenericPromptHook


_PACKAGE_RULES = [
    # Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm → "SMD-3225"
    (r"^Crystal:Crystal_SMD_(\d+)-\d+Pin_", lambda m: f"SMD-{m.group(1)}"),
    # Crystal:Crystal_SMD_3225_3.2x2.5mm (no pin count) → "SMD-3225"
    (r"^Crystal:Crystal_SMD_(\d+)_", lambda m: f"SMD-{m.group(1)}"),
]

# No built-in footprint mapping — EasyEDA handles all.
_BUILTIN: dict[str, str] = {}


def make(fp_out_dir: Path) -> Category:
    return Category(
        name="crystal",
        matcher=LibIdAny(["Device:Crystal"]),
        value_parser=CrystalValueParser(),
        package_extractor=RegexFromRules(_PACKAGE_RULES),
        default_package="",  # No sensible default; user must set footprint
        candidate_source=CrystalSource(),
        scorer=GenericBasicStockScorer(),
        footprint_resolver=Composite([
            BuiltinMap(_BUILTIN),
            EasyedaFallback(out_dir=fp_out_dir),
        ]),
        prompt_hook=GenericPromptHook(),
    )
