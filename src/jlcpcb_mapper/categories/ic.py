"""IC category bundle.

ICs are the catch-all category: any lib_id that contains ':' and is NOT
claimed by an earlier category (Device:, power:, Connector) routes here.
Register IC LAST in the registry so earlier categories get first pick.
"""
from __future__ import annotations
from pathlib import Path
from .base import Category
from ..components.value_parsers import ICValueParser
from ..components.package_extractors import RegexFromRules
from ..components.candidate_sources import ICSource
from ..components.footprint_resolvers import BuiltinMap, EasyedaFallback, Composite
from ..components.prompt_hooks import ICPromptHook


class _ICMatcher:
    """Catch-all for IC lib_ids.

    Matches any lib_id containing ':' EXCEPT those starting with prefixes
    that are claimed by earlier categories. Register IC LAST in the registry.
    """
    _NON_IC_PREFIXES = ("Device:", "power:", "Connector")

    def matches(self, lib_id: str) -> bool:
        if ":" not in lib_id:
            return False
        return not lib_id.startswith(self._NON_IC_PREFIXES)


_PACKAGE_RULES = [
    (r"^Package_TO_SOT_SMD:(SOT-\d+)", lambda m: m.group(1)),
    (r"^Package_TO_SOT_SMD:(TO-\d+(?:-\d+)?)(?:_|$)", lambda m: m.group(1)),
    (r"^Package_QFN:[^:]*?(QFN-\d+)", lambda m: m.group(1)),
    (r"^Package_SON:[^:]*?(QFN-\d+)", lambda m: m.group(1)),
    (r"^Package_QFP:LQFP-(\d+)", lambda m: f"LQFP-{m.group(1)}"),
    (r"^Package_SO:SOIC-(\d+)", lambda m: f"SOIC-{m.group(1)}"),
    (r"^Package_SO:((?:SOP|TSSOP|SSOP)-\d+)", lambda m: m.group(1)),
    (r"^Diode_SMD:D_(SMA|SMB|SMC)$", lambda m: m.group(1)),
    (r"^Diode_SMD:D_MELF$", lambda m: "MELF"),
    (r"^Diode_SMD:D_(SOD-\d+)", lambda m: m.group(1)),
]


def make(fp_out_dir: Path) -> Category:
    return Category(
        name="ic",
        matcher=_ICMatcher(),
        value_parser=ICValueParser(),
        package_extractor=RegexFromRules(_PACKAGE_RULES),
        default_package="",   # No fallback — require explicit footprint
        candidate_source=ICSource(),
        scorer=None,           # LLM decides; no deterministic ranking for ICs
        footprint_resolver=Composite([
            BuiltinMap({}),    # No built-in IC mappings
            EasyedaFallback(out_dir=fp_out_dir),
        ]),
        prompt_hook=ICPromptHook(),
    )
