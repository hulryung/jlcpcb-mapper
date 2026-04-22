"""Inductor Spec dataclass."""
from __future__ import annotations
from dataclasses import dataclass
from ...core.types import Value


@dataclass(frozen=True)
class InductorSpec:
    value: Value  # e.g. Value(33, "µH")

    def group_key(self): return ("inductor", self.value)
    def display(self) -> str: return self.value.display()
    def llm_context(self) -> dict: return {"value": self.value.display()}
