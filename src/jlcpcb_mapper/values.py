from __future__ import annotations
import re

_R_RE = re.compile(r"^(\d+(?:\.\d+)?)(?:([KkMm])|R)?$")
_C_RE = re.compile(r"^(\d+(?:\.\d+)?)\s*([munpµ]?)[Ff]?$", re.IGNORECASE)
_C_IMPLICIT = re.compile(r"^(\d+)u(\d+)$")  # e.g. 2u2 -> 2.2uF

def _r_mult(suffix: str) -> int:
    return {"K": 1000, "k": 1000, "M": 1_000_000, "m": 1_000_000, "": 1}[suffix or ""]

def normalize_value(raw: str, category: str) -> str:
    raw = raw.strip()
    if category == "resistor":
        if raw in ("0", "0R", "0Ω"):
            return "0Ω"
        m = _R_RE.match(raw)
        if m:
            num = float(m.group(1))
            mult = _r_mult(m.group(2) or "")
            v = num * mult
            return f"{int(v) if v.is_integer() else v}Ω"
        return raw
    if category == "capacitor":
        m_impl = _C_IMPLICIT.match(raw)
        if m_impl:
            return f"{m_impl.group(1)}.{m_impl.group(2)}µF"
        m = _C_RE.match(raw)
        if m:
            num = m.group(1)
            unit = m.group(2).lower().replace("u", "µ")
            return f"{num}{unit}F" if unit else f"{num}F"
        return raw
    return raw

def category_from_lib_id(lib_id: str) -> str:
    if lib_id.startswith("power:"):
        return "power"
    if lib_id.startswith("Device:R"):
        return "resistor"
    if lib_id.startswith("Device:C"):
        return "capacitor"
    if lib_id.startswith("Device:LED"):
        return "led"
    if lib_id.startswith("Connector_Generic:Conn_01x"):
        try:
            pins = int(lib_id.rsplit("Conn_01x", 1)[1])
            return f"connector_1x{pins}"
        except Exception:
            return "connector"
    if lib_id.startswith("Connector"):
        return "connector"
    return "ic"
