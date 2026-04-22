"""Core types for the jlcpcb-mapper pipeline."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class Value:
    magnitude: float
    unit: str  # e.g. "Ω", "kΩ", "µF", "µH", "V"

    def display(self) -> str:
        m = self.magnitude
        if float(m).is_integer():
            return f"{int(m)}{self.unit}"
        return f"{m:g}{self.unit}"
