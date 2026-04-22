"""Value parsers per category. Each parser returns the appropriate Spec or None."""
from __future__ import annotations
import re
from ..core.types import Value
from ..categories.spec.cap import CeramicCapSpec, PolarizedCapSpec


_CAP_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([munpµu]?)[Ff]?\s*$", re.IGNORECASE)
_CAP_IMPLICIT_RE = re.compile(r"^\s*(\d+)u(\d+)\s*$")  # "2u2" -> 2.2µF
_VOLTAGE_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*V\s*$", re.IGNORECASE)


def _parse_cap_value(token: str) -> Value | None:
    m = _CAP_IMPLICIT_RE.match(token)
    if m:
        return Value(float(f"{m.group(1)}.{m.group(2)}"), "µF")
    m = _CAP_RE.match(token)
    if not m:
        return None
    mag = float(m.group(1))
    unit_in = m.group(2).lower()
    unit_in = "µ" if unit_in in ("u", "µ", "μ") else unit_in
    if unit_in == "":
        return Value(mag, "F")
    return Value(mag, f"{unit_in}F")


def _parse_voltage(token: str) -> Value | None:
    m = _VOLTAGE_RE.match(token)
    if not m:
        return None
    return Value(float(m.group(1)), "V")


class CapValueParser:
    """Parse capacitor-like values.

    keep_voltage=True  → returns PolarizedCapSpec(value, voltage)
    keep_voltage=False → returns CeramicCapSpec(value), trailing voltage ignored
    """
    def __init__(self, *, keep_voltage: bool):
        self.keep_voltage = keep_voltage

    def parse(self, raw: str):
        if not raw or not raw.strip():
            return None
        parts = [p.strip() for p in raw.split("/")]
        if not parts or not parts[0]:
            return None
        value = _parse_cap_value(parts[0])
        if value is None:
            return None
        if not self.keep_voltage:
            return CeramicCapSpec(value=value)
        voltage = None
        for extra in parts[1:]:
            voltage = _parse_voltage(extra)
            if voltage:
                break
        return PolarizedCapSpec(value=value, voltage=voltage)
