"""Ferrite Bead Spec dataclass."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class FerriteBeadSpec:
    impedance_ohms: float       # e.g. 100 (for "100Ω@100MHz")
    test_freq_mhz: float        # e.g. 100

    def group_key(self):
        return ("ferrite_bead", self.impedance_ohms, self.test_freq_mhz)

    def display(self) -> str:
        i = f"{self.impedance_ohms:g}"
        f = f"{self.test_freq_mhz:g}"
        return f"{i}Ω@{f}MHz"

    def llm_context(self) -> dict:
        return {"impedance_ohms": self.impedance_ohms, "test_freq_mhz": self.test_freq_mhz}
