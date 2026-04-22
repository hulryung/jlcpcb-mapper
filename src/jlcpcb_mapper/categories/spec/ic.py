"""IC Spec dataclass.

For ICs, the 'value' is really the manufacturer part number (MPN).
Unlike other categories, we use a named string field (mpn) rather than
Value(0, token) — IC-specific fields (package variant, rev, etc.) will
grow and having a named field is cleaner.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class ICSpec:
    mpn: str  # e.g. "STM32F031K6T6"

    def group_key(self):
        return ("ic", self.mpn)

    def display(self) -> str:
        return self.mpn

    def llm_context(self) -> dict:
        return {"mpn": self.mpn}
