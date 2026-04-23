"""Connector Spec dataclass."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class ConnectorSpec:
    """Parsed connector identity.

    structure: "1xN" | "2xN" | "generic"
    pins: int (0 for generic/unknown)
    value: raw Value field string (usually MPN or blank)
    """
    structure: str
    pins: int
    value: str  # raw value text, may be empty

    def group_key(self): return ("connector", self.structure, self.pins, self.value)
    def display(self) -> str:
        if self.structure in ("1xN", "2xN"):
            s = self.structure.replace("N", str(self.pins))
            return f"{s} {self.value}".strip()
        return self.value or "connector"
    def llm_context(self) -> dict:
        return {"structure": self.structure, "pins": self.pins, "value": self.value}
