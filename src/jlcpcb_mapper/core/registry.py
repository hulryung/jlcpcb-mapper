"""Registry of categories. Populated at import time by categories/__init__.py."""
from __future__ import annotations
from ..categories.base import Category


class Registry:
    def __init__(self) -> None:
        self._categories: list[Category] = []

    def register(self, cat: Category) -> None:
        if any(c.name == cat.name for c in self._categories):
            raise ValueError(f"duplicate category name: {cat.name}")
        self._categories.append(cat)

    def lookup(self, lib_id: str) -> Category | None:
        for c in self._categories:
            if c.matcher.matches(lib_id):
                return c
        return None

    def all(self) -> list[Category]:
        return list(self._categories)
