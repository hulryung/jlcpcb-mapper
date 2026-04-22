"""Value parsers per category. Each parser returns the appropriate Spec or None."""
from __future__ import annotations
import re
from ..core.types import Value
from ..categories.spec.cap import CeramicCapSpec, PolarizedCapSpec
from ..categories.spec.resistor import ResistorSpec
from ..categories.spec.inductor import InductorSpec
from ..categories.spec.led import LEDSpec
from ..categories.spec.crystal import CrystalSpec


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


_R_RE = re.compile(r"^(\d+(?:\.\d+)?)(?:([KkMm])|R)?$")
_R_MULT = {"K": 1000, "k": 1000, "M": 1_000_000, "m": 1_000_000, "": 1}


class ResistorValueParser:
    """Parse resistor value strings and return ResistorSpec or None.

    Accepted forms: "10", "10k", "10K", "4.7k", "10M", "10m" (mega compat),
    "10R", "0R", "0Ω", "10kΩ", "10k/0.1%" (slash-separated tolerance dropped).
    Returns None on junk (empty, "foobar", "10uF").
    """

    def parse(self, raw: str) -> ResistorSpec | None:
        if not raw or not raw.strip():
            return None
        # Drop slash-separated trailing tokens (tolerance, power, etc.)
        token = raw.split("/", 1)[0].strip()
        # Short-circuit zero-ohm special forms
        if token in ("0", "0R", "0Ω"):
            return ResistorSpec(value=Value(0.0, "Ω"))
        # Strip trailing Ω so "10kΩ" becomes "10k"
        if token.endswith("Ω"):
            token = token[:-1]
        m = _R_RE.match(token)
        if not m:
            return None
        num = float(m.group(1))
        mult = _R_MULT[m.group(2) or ""]
        ohms = num * mult
        return ResistorSpec(value=Value(ohms, "Ω"))


_L_RE = re.compile(r"^(\d+(?:\.\d+)?)\s*([munpµμ]?)H$", re.IGNORECASE)
_L_UNIT_CANON = {"u": "µ", "µ": "µ", "μ": "µ", "m": "m", "n": "n", "p": "p", "": ""}


class InductorValueParser:
    """Parse inductor value strings and return InductorSpec or None.

    Accepted forms: "33uH", "33µH", "33μH" (Greek mu), "4.7uH", "10nH", "1mH", "33H".
    Returns None on junk (empty, "foobar", "10uF").
    """

    def parse(self, raw: str) -> InductorSpec | None:
        if not raw or not raw.strip():
            return None
        m = _L_RE.match(raw.strip())
        if not m:
            return None
        mag = float(m.group(1))
        prefix = m.group(2).lower()  # normalize to lowercase before canonicalization
        # Canonicalize: both ASCII 'u' and micro-sign variants map to µ (U+00B5)
        canon_prefix = _L_UNIT_CANON.get(prefix, prefix)
        if canon_prefix == "":
            unit = "H"
        else:
            unit = f"{canon_prefix}H"
        return InductorSpec(value=Value(mag, unit))


class LEDValueParser:
    """Parse LED Value field. LEDs typically use descriptive tokens (color, MPN).

    Stores the raw token (trimmed, upper-cased for grouping consistency) as
    Value(0, token). Returns None on empty or whitespace-only input.
    """

    def parse(self, raw: str) -> LEDSpec | None:
        token = raw.strip().upper()
        if not token:
            return None
        return LEDSpec(value=Value(0, token))


_XTAL_WITH_PREFIX = re.compile(r"^(\d+(?:\.\d+)?)\s*([kKmM])(?:Hz|HZ|hz)?$")
_XTAL_BARE_HZ = re.compile(r"^(\d+(?:\.\d+)?)\s*(?:Hz|HZ|hz)$")


class CrystalValueParser:
    """Parse crystal frequency strings and return CrystalSpec or None.

    Accepted forms:
      "16MHz"       → Value(16, "MHz")
      "32.768kHz"   → Value(32.768, "kHz")
      "16M" / "16m" → Value(16, "MHz")
      "25MHZ"       → Value(25, "MHz")
      "400Hz"       → Value(400, "Hz")
    Returns None on bare numbers ("16"), empty input, or junk.
    """

    def parse(self, raw: str) -> CrystalSpec | None:
        if not raw or not raw.strip():
            return None
        # Handle slash-separated (uncommon): take first token only
        token = raw.split("/")[0].strip()
        m = _XTAL_WITH_PREFIX.match(token)
        if m:
            mag = float(m.group(1))
            unit_prefix = m.group(2).lower()
            unit = "kHz" if unit_prefix == "k" else "MHz"
            return CrystalSpec(value=Value(mag, unit))
        m = _XTAL_BARE_HZ.match(token)
        if m:
            return CrystalSpec(value=Value(float(m.group(1)), "Hz"))
        return None


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
