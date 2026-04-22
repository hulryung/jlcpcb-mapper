"""Capacitor Spec dataclasses."""
from __future__ import annotations
from dataclasses import dataclass
from ...core.types import Value


@dataclass(frozen=True)
class CeramicCapSpec:
    value: Value

    def group_key(self): return ("ceramic_cap", self.value)
    def display(self) -> str: return self.value.display()
    def llm_context(self) -> dict: return {"value": self.value.display()}


@dataclass(frozen=True)
class PolarizedCapSpec:
    value: Value
    voltage: Value | None

    def group_key(self): return ("polarized_cap", self.value, self.voltage)
    def display(self) -> str:
        v = f"/{self.voltage.display()}" if self.voltage else ""
        return f"{self.value.display()}{v}"
    def llm_context(self) -> dict:
        return {"value": self.value.display(),
                "voltage": self.voltage.display() if self.voltage else None}
