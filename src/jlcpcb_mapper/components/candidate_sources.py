"""CandidateSource implementations per category."""
from __future__ import annotations
import re
from ..core.types import QuerySpec
from ..parts_db import PartRow


def _resistor_si_pattern(ohms: float) -> str:
    """Convert an ohm value to a JLCPCB description LIKE pattern.

    Examples: 0 → ' 0Ω', 10000 → ' 10kΩ', 4700 → ' 4.7kΩ', 1_000_000 → ' 1MΩ'.
    The leading space prevents '110kΩ' from matching '10kΩ'.
    """
    if ohms == 0:
        return " 0Ω"
    if ohms >= 1_000_000:
        q = ohms / 1_000_000
        unit = "MΩ"
    elif ohms >= 1000:
        q = ohms / 1000
        unit = "kΩ"
    else:
        q = ohms
        unit = "Ω"
    # Drop trailing zeros in fractional form
    token = f"{q:g}{unit}"
    return f" {token}"


_VOLTAGE_TOKEN = re.compile(r"(\d+(?:\.\d+)?)\s*V(?:DC|AC)?\b", re.IGNORECASE)


def _extract_voltage_numbers(description: str) -> list[float]:
    return [float(m.group(1)) for m in _VOLTAGE_TOKEN.finditer(description or "")]


def _normalize_micro(unit_or_value: str) -> str:
    """µ → u (ASCII) for DB description matching."""
    return unit_or_value.replace("µ", "u").replace("μ", "u")


class PolarizedCapSource:
    """Aluminum electrolytic capacitors. Broad category fetch + post_filter by
    package substring and voltage-rating."""

    def __init__(self, min_stock: int = 0, limit: int = 50):
        self.min_stock = min_stock
        self.limit = limit

    def query(self, spec, package_hint: str) -> QuerySpec:
        patterns = ()
        if spec.value is not None:
            token = f"%{_normalize_micro(spec.value.display())}%"
            patterns = (token,)
        return QuerySpec(
            category_like="%Aluminum Electrolytic%",
            package=None,  # use substring filter in post_filter
            description_patterns=patterns,
            min_stock=self.min_stock,
            limit=self.limit,
        )

    def post_filter(self, rows: list[PartRow], spec, package_hint: str) -> list[PartRow]:
        hint = (package_hint or "").lower()
        out: list[PartRow] = []
        required_v = spec.voltage.magnitude if spec.voltage is not None else None
        for r in rows:
            if hint and hint not in (r.package or "").lower():
                continue
            if required_v is not None:
                voltages = _extract_voltage_numbers(r.description or "")
                if voltages and max(voltages) < required_v:
                    continue
            out.append(r)
        return out


class ResistorSource:
    """Chip resistors. Exact package match + description LIKE on the SI-form value."""

    def __init__(self, min_stock: int = 0, limit: int = 50):
        self.min_stock = min_stock
        self.limit = limit

    def query(self, spec, package_hint: str) -> QuerySpec:
        si = _resistor_si_pattern(spec.value.magnitude)
        pattern = f"%{si}%"
        return QuerySpec(
            category_like="Chip Resistor%",
            package=package_hint or None,
            description_patterns=(pattern,),
            min_stock=self.min_stock,
            limit=self.limit,
        )

    def post_filter(self, rows: list[PartRow], spec, package_hint: str) -> list[PartRow]:
        # SQL already narrow — no additional client-side filtering needed.
        return rows


class CeramicCapSource:
    """Multilayer ceramic capacitors. Exact package match + description LIKE on value."""

    def __init__(self, min_stock: int = 0, limit: int = 50):
        self.min_stock = min_stock
        self.limit = limit

    def query(self, spec, package_hint: str) -> QuerySpec:
        patterns: tuple[str, ...] = ()
        if spec.value is not None:
            token = f"%{_normalize_micro(spec.value.display())}%"
            patterns = (token,)
        return QuerySpec(
            category_like="%Ceramic Capacitor%",
            package=package_hint or None,
            description_patterns=patterns,
            min_stock=self.min_stock,
            limit=self.limit,
        )

    def post_filter(self, rows: list[PartRow], spec, package_hint: str) -> list[PartRow]:
        return rows


class InductorSource:
    """Inductors. Exact package match when hint provided + description LIKE on value."""

    def __init__(self, min_stock: int = 0, limit: int = 50):
        self.min_stock = min_stock
        self.limit = limit

    def query(self, spec, package_hint: str) -> QuerySpec:
        patterns: tuple[str, ...] = ()
        if spec.value is not None:
            # Normalize µ/μ → u for DB description matching
            normalized = _normalize_micro(spec.value.display())
            patterns = (f"%{normalized}%",)
        return QuerySpec(
            category_like="%Inductor%",
            package=package_hint or None,  # exact package match when hint provided
            description_patterns=patterns,
            min_stock=self.min_stock,
            limit=self.limit,
        )

    def post_filter(self, rows: list[PartRow], spec, package_hint: str) -> list[PartRow]:
        return rows


class CrystalSource:
    """Crystals. Broad %Crystal% fetch + package substring post_filter.

    Requires package_hint; if empty, returns no candidates.
    """

    def __init__(self, min_stock: int = 0, limit: int = 50):
        self.min_stock = min_stock
        self.limit = limit

    def query(self, spec, package_hint: str) -> QuerySpec:
        patterns: tuple[str, ...] = ()
        if spec.value is not None:
            token = spec.value.display()   # e.g. "16MHz"
            patterns = (f"%{token}%",)
        return QuerySpec(
            category_like="%Crystal%",
            package=None,   # substring filter applied in post_filter
            description_patterns=patterns,
            min_stock=self.min_stock,
            limit=self.limit,
        )

    def post_filter(self, rows: list[PartRow], spec, package_hint: str) -> list[PartRow]:
        if not package_hint:
            return []   # safer to return empty than mismap
        hint = package_hint.lower()
        return [r for r in rows if hint in (r.package or "").lower()]


class LEDSource:
    """LED candidate source. Broad category + token substring in description.

    LEDs have no SI magnitude; match by the raw token against descriptions.
    """

    def __init__(self, min_stock: int = 0, limit: int = 50):
        self.min_stock = min_stock
        self.limit = limit

    def query(self, spec, package_hint: str) -> QuerySpec:
        patterns: tuple[str, ...] = ()
        token = spec.value.unit if spec.value else ""
        if token:
            # Case-insensitive SQL LIKE. Use exact token wrapped in %.
            patterns = (f"%{token}%",)
        return QuerySpec(
            category_like="Light Emitting Diode%",
            package=package_hint or None,
            description_patterns=patterns,
            min_stock=self.min_stock,
            limit=self.limit,
        )

    def post_filter(self, rows: list[PartRow], spec, package_hint: str) -> list[PartRow]:
        return rows


class ICSource:
    """IC candidate source. Matches MPN against mfr_part column.

    Requires package_hint — IC variants with different pinouts are dangerous
    to mismap. Returns empty if no package hint (post_filter catches it).
    Uses category_like="%" (broad fetch) since JLCPCB subcategorizes ICs heavily.
    """

    def __init__(self, min_stock: int = 0, limit: int = 50):
        self.min_stock = min_stock
        self.limit = limit

    def query(self, spec, package_hint: str) -> QuerySpec:
        if not package_hint or not spec.mpn:
            # post_filter will catch this and return []; issue a tight query meanwhile
            return QuerySpec(
                category_like="%",
                min_stock=self.min_stock,
                limit=1,  # minimize wasted work
            )
        # Escape % and _ for SQL LIKE
        escaped = spec.mpn.replace("%", r"\%").replace("_", r"\_")
        return QuerySpec(
            category_like="%",
            package=None,  # substring filter applied in post_filter
            mpn_patterns=(f"%{escaped}%",),
            min_stock=self.min_stock,
            limit=self.limit,
        )

    def post_filter(self, rows: list[PartRow], spec, package_hint: str) -> list[PartRow]:
        if not package_hint or not spec.mpn:
            return []
        hint = package_hint.lower()
        return [r for r in rows if hint in (r.package or "").lower()]


class ConnectorSource:
    """Connector candidate source.

    - 1xN: broad fetch by %Connector%, optionally filtered by value in description;
      post_filter passes all rows through (scorer/LLM decides).
    - 2xN with hint: broad fetch + post_filter keeps rows with package_hint substring.
    - 2xN without hint: tight no-match query (limit=1, %); post_filter returns [].
    - generic: tight no-match query; post_filter returns [].
    """

    def __init__(self, min_stock: int = 0, limit: int = 50):
        self.min_stock = min_stock
        self.limit = limit

    def query(self, spec, package_hint: str) -> QuerySpec:
        if spec.structure == "generic":
            # Force no candidates for plain connectors — safer to skip
            return QuerySpec(category_like="%", limit=1)
        if spec.structure == "2xN" and not package_hint:
            # 2xN is diverse; without hint, also bail
            return QuerySpec(category_like="%", limit=1)
        # 1xN and 2xN-with-hint both fetch broadly
        patterns: tuple[str, ...] = ()
        if spec.value:
            patterns = (f"%{spec.value}%",)
        return QuerySpec(
            category_like="%Connector%",
            package=None,   # post_filter handles 2xN package substring
            description_patterns=patterns,
            min_stock=self.min_stock,
            limit=self.limit,
        )

    def post_filter(self, rows: list[PartRow], spec, package_hint: str) -> list[PartRow]:
        if spec.structure == "generic":
            return []
        if spec.structure == "2xN":
            if not package_hint:
                return []
            hint = package_hint.lower()
            return [r for r in rows if hint in (r.package or "").lower()]
        # 1xN — pass through
        return rows
