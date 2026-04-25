"""Inductor Spec dataclass."""
from __future__ import annotations
from dataclasses import dataclass
from ...core.types import Value


@dataclass(frozen=True)
class InductorSpec:
    value: Value  # e.g. Value(33, "µH")
    current_a: float | None = None  # minimum required current rating in amps

    def group_key(self): return ("inductor", self.value, self.current_a)

    def display(self) -> str:
        base = self.value.display()
        if self.current_a is None:
            return base
        if self.current_a < 1:
            return f"{base}/{self.current_a * 1000:g}mA"
        return f"{base}/{self.current_a:g}A"

    def llm_context(self) -> dict:
        d: dict = {"value": self.value.display()}
        if self.current_a is not None:
            d["current_a_min"] = self.current_a
        return d
