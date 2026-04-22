"""LED Spec dataclass.

Design note: LEDs don't carry a numeric magnitude — their "value" is a
descriptive token (color name or MPN, e.g. "RED", "WS2812B").  We use
Value(magnitude=0, unit=token) to avoid introducing a separate StringSpec
hierarchy while keeping the Spec protocol interface uniform across all
categories.  ``magnitude`` is always 0 and should be ignored; ``unit``
holds the canonical (trimmed, upper-cased) token.
"""
from __future__ import annotations
from dataclasses import dataclass
from ...core.types import Value


@dataclass(frozen=True)
class LEDSpec:
    value: Value  # Value(0, token), e.g. Value(0, "RED") or Value(0, "WS2812B")

    def group_key(self): return ("led", self.value)

    def display(self) -> str:
        # The unit field holds the descriptive token; magnitude is unused.
        return self.value.unit

    def llm_context(self) -> dict:
        return {"value": self.value.unit}
