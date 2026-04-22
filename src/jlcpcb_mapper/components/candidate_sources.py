"""CandidateSource implementations per category."""
from __future__ import annotations
import re
from ..core.types import QuerySpec
from ..parts_db import PartRow


_VOLTAGE_TOKEN = re.compile(r"(\d+(?:\.\d+)?)\s*V\b", re.IGNORECASE)


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
