"""Resistor Spec dataclass."""
from __future__ import annotations
from dataclasses import dataclass
from ...core.types import Value


@dataclass(frozen=True)
class ResistorSpec:
    value: Value  # e.g. Value(10000, "Ω")

    def group_key(self): return ("resistor", self.value)
    def display(self) -> str: return self.value.display()
    def llm_context(self) -> dict: return {"value": self.value.display()}
