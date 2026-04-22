"""Crystal Spec dataclass."""
from __future__ import annotations
from dataclasses import dataclass
from ...core.types import Value


@dataclass(frozen=True)
class CrystalSpec:
    value: Value  # frequency, e.g. Value(16, "MHz") or Value(32.768, "kHz")

    def group_key(self):
        return ("crystal", self.value)

    def display(self) -> str:
        return self.value.display()

    def llm_context(self) -> dict:
        return {"value": self.value.display()}
