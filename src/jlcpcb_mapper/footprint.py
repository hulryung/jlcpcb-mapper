"""Extract JLCPCB-style package codes from KiCad footprint identifiers."""
from __future__ import annotations
import re

# Ordered list of (pattern, extractor) pairs.
# Each pattern matches the full footprint string; the extractor returns the package string.
# Falls through to None if nothing matches.

_RULES: list[tuple[re.Pattern, callable]] = []


def _rule(pattern: str):
    """Decorator: register a compiled pattern + handler."""
    def decorator(fn):
        _RULES.append((re.compile(pattern), fn))
        return fn
    return decorator


# Resistor_SMD:R_<size>_*
@_rule(r"^Resistor_SMD:R_(\d{4})_")
def _resistor(m: re.Match) -> str:
    return m.group(1)


# Capacitor_SMD:C_<size>_*
@_rule(r"^Capacitor_SMD:C_(\d{4})_")
def _capacitor(m: re.Match) -> str:
    return m.group(1)


# LED_SMD:LED_<size>_*
@_rule(r"^LED_SMD:LED_(\d{4})_")
def _led(m: re.Match) -> str:
    return m.group(1)


# Inductor_SMD:L_<size>_*
@_rule(r"^Inductor_SMD:L_(\d{4})_")
def _inductor(m: re.Match) -> str:
    return m.group(1)


# Package_TO_SOT_SMD:SOT-<n>[...] — e.g. SOT-23, SOT-223
@_rule(r"^Package_TO_SOT_SMD:(SOT-\d+)")
def _sot(m: re.Match) -> str:
    return m.group(1)


# Package_TO_SOT_SMD:TO-<n>[-<pins>][_...] — e.g. TO-263-5_TabPin3 → TO-263-5
# First suffix component: TO-<n> or TO-<n>-<pins>
@_rule(r"^Package_TO_SOT_SMD:(TO-\d+(?:-\d+)?)(?:_|$)")
def _to(m: re.Match) -> str:
    return m.group(1)


# Diode_SMD:D_SMA / D_SMB / D_SMC
@_rule(r"^Diode_SMD:D_(SMA|SMB|SMC)$")
def _diode_sm(m: re.Match) -> str:
    return m.group(1)


# Diode_SMD:D_MELF
@_rule(r"^Diode_SMD:D_MELF$")
def _diode_melf(_: re.Match) -> str:
    return "MELF"


# Diode_SMD:D_SOD-<n>[...]
@_rule(r"^Diode_SMD:D_(SOD-\d+)")
def _diode_sod(m: re.Match) -> str:
    return m.group(1)


# Package_QFN:QFN-<n>[...] or Package_SON:*QFN-<n>[...]
@_rule(r"^Package_(?:QFN|SON):[^:]*?(QFN-\d+)")
def _qfn(m: re.Match) -> str:
    return m.group(1)


# Package_SO:SOIC-<n>[...]
@_rule(r"^Package_SO:SOIC-(\d+)")
def _soic(m: re.Match) -> str:
    return f"SOIC-{m.group(1)}"


# Package_SO:SOP-<n>[...], TSSOP-<n>[...], SSOP-<n>[...]
@_rule(r"^Package_SO:((?:SOP|TSSOP|SSOP)-\d+)")
def _sop(m: re.Match) -> str:
    return m.group(1)


def package_from_kicad_footprint(fp: str) -> str | None:
    """Return the JLCPCB-style package code for a KiCad footprint identifier, or None."""
    if not fp:
        return None
    for pattern, handler in _RULES:
        m = pattern.match(fp)
        if m:
            return handler(m)
    return None
