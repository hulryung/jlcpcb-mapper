"""Lib-id matchers for Category.matcher."""
from __future__ import annotations


class LibIdAny:
    """Matches if lib_id equals any base exactly, or starts with `base + '_'`."""
    def __init__(self, bases: list[str]):
        self._bases = tuple(bases)

    def matches(self, lib_id: str) -> bool:
        for b in self._bases:
            if lib_id == b or lib_id.startswith(b + "_"):
                return True
        return False


class LibIdPrefix:
    """Matches if lib_id starts with any given prefix (no boundary assumed)."""
    def __init__(self, prefixes: list[str]):
        self._prefixes = tuple(prefixes)

    def matches(self, lib_id: str) -> bool:
        return any(lib_id.startswith(p) for p in self._prefixes)
