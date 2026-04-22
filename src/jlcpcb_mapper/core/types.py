"""Core types for the jlcpcb-mapper pipeline."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol, Hashable, runtime_checkable

@dataclass(frozen=True)
class Value:
    magnitude: float
    unit: str  # e.g. "Ω", "kΩ", "µF", "µH", "V"

    def display(self) -> str:
        m = self.magnitude
        if float(m).is_integer():
            return f"{int(m)}{self.unit}"
        return f"{m:g}{self.unit}"


@dataclass(frozen=True)
class QuerySpec:
    category_like: str
    package: str | None = None
    description_patterns: tuple[str, ...] = ()
    mpn_patterns: tuple[str, ...] = ()
    min_stock: int = 0
    order_by: str = "basic DESC, preferred DESC, stock DESC"
    limit: int = 50


@runtime_checkable
class Spec(Protocol):
    """Per-category parsed value. Implemented by each category's dataclass."""
    def group_key(self) -> Hashable: ...
    def display(self) -> str: ...
    def llm_context(self) -> dict: ...
