"""Package-extraction rules: map KiCad footprint id -> JLCPCB-style package code."""
from __future__ import annotations
import re
from typing import Callable


class RegexFromRules:
    def __init__(self, rules: list[tuple[str, Callable[[re.Match], str]]]):
        self._rules = [(re.compile(p), fn) for p, fn in rules]

    def extract(self, kicad_footprint: str) -> str | None:
        if not kicad_footprint:
            return None
        for pat, fn in self._rules:
            m = pat.match(kicad_footprint)
            if m:
                return fn(m)
        return None
