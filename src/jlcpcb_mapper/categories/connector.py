"""Connector category bundle.

Matches any lib_id starting with "Connector" — covers:
- Connector_Generic:Conn_01xN... (1xN pin headers/sockets)
- Connector_Generic:Conn_02xN... (2xN dual-row)
- Connector_USB:...
- Connector_Molex:...
- etc.

Register BEFORE ic (ic is the catch-all for everything else).
"""
from __future__ import annotations
from pathlib import Path
from .base import Category
from ..components.matchers import LibIdPrefix
from ..components.value_parsers import ConnectorValueParser
from ..components.package_extractors import RegexFromRules
from ..components.candidate_sources import ConnectorSource
from ..components.footprint_resolvers import BuiltinMap, EasyedaFallback, Composite
from ..components.prompt_hooks import GenericPromptHook


_PACKAGE_RULES = [
    (r"^Connector_PinSocket_2\.54mm:PinSocket_2x(\d+)_", lambda m: f"PinSocket_2x{m.group(1)}"),
    (r"^Connector_PinSocket_2\.54mm:PinSocket_1x(\d+)_", lambda m: f"PinSocket_1x{m.group(1)}"),
    (r"^Connector_PinHeader_2\.54mm:PinHeader_2x(\d+)_", lambda m: f"PinHeader_2x{m.group(1)}"),
    (r"^Connector_PinHeader_2\.54mm:PinHeader_1x(\d+)_", lambda m: f"PinHeader_1x{m.group(1)}"),
]

_BUILTIN: dict = {}   # no generic built-in fallbacks — resolver uses EasyEDA


def make(fp_out_dir: Path) -> Category:
    return Category(
        name="connector",
        matcher=LibIdPrefix(["Connector"]),
        value_parser=ConnectorValueParser(),
        package_extractor=RegexFromRules(_PACKAGE_RULES),
        default_package="",
        candidate_source=ConnectorSource(),
        scorer=None,   # LLM decides
        footprint_resolver=Composite([
            BuiltinMap(_BUILTIN),
            EasyedaFallback(out_dir=fp_out_dir),
        ]),
        prompt_hook=GenericPromptHook(),
    )
