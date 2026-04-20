from __future__ import annotations
import re
from .parts_db import PartsDB, PartRow
from .grouper import GroupKey

# Categories that are safer to skip entirely than to mismap.
# Callers will see failure_reason="no candidates" and can assign manually.
_UNSUPPORTED = {"crystal", "polarized_capacitor"}


def _resistor_si_pattern(value: str) -> str | None:
    """Turn '0Ω' / '1000Ω' / '4700Ω' / '1000000Ω' into ' 0Ω' / ' 1kΩ' etc."""
    if value == "0Ω":
        return " 0Ω"
    m = re.match(r"(\d+(?:\.\d+)?)Ω$", value)
    if not m:
        return None
    n = float(m.group(1))
    if n >= 1_000_000:
        q = n / 1_000_000
        unit = "MΩ"
    elif n >= 1000:
        q = n / 1000
        unit = "kΩ"
    else:
        q = n
        unit = "Ω"
    if q == int(q):
        token = f"{int(q)}{unit}"
    else:
        # Drop trailing zeros: 4.70 -> 4.7
        token = f"{q:g}{unit}"
    return f" {token}"


def _inductor_pattern(value: str) -> str | None:
    """'33µH' or '4.7µH' or '100uH' -> SQL LIKE pattern '%33uH%' (ASCII u)."""
    m = re.match(r"(\d+(?:\.\d+)?)([µumnp])H$", value)
    if not m:
        return None
    num = m.group(1)
    unit = m.group(2).replace("µ", "u")
    return f"%{num}{unit}H%"


def _value_to_sql_pattern(category: str, value: str) -> str | None:
    if category == "resistor":
        si = _resistor_si_pattern(value)
        if si is None:
            return None
        return f"%{si}%"
    if category == "capacitor":
        m = re.match(r"(\d+(?:\.\d+)?)(µ|n|p)F$", value)
        if not m:
            return None
        unit_in = m.group(2)
        unit_out = "u" if unit_in == "µ" else unit_in
        return f"%{m.group(1)}{unit_out}F%"
    return None

CATEGORY_SQL = {
    "resistor":  "Chip Resistor%",
    "capacitor": "%Ceramic Capacitor%",
    "led":       "Light Emitting Diode%",
    "inductor":  "%Inductor%",
}

def candidates_for(
    key: GroupKey,
    db: PartsDB,
    min_stock: int,
    limit: int = 30,
) -> list[PartRow]:
    if key.category in _UNSUPPORTED:
        return []
    if key.category.startswith("connector_2x"):
        return []  # 2xN connectors are diverse; safer to skip than mismap
    if key.category.startswith("connector"):
        return db.query_candidates(
            category_sql_like="%Connector%",
            package=None,
            value_pattern=None,
            min_stock=0,
            limit=max(limit, 50),
        )
    if key.category == "inductor":
        pattern = _inductor_pattern(key.value)
        return db.query_candidates(
            category_sql_like="%Inductor%",
            package=key.package_hint or None,
            value_pattern=pattern,
            min_stock=min_stock,
            limit=limit,
        )
    cat_sql = CATEGORY_SQL.get(key.category, "%")
    pkg = key.package_hint or None
    value_pattern = _value_to_sql_pattern(key.category, key.value)
    return db.query_candidates(
        category_sql_like=cat_sql,
        package=pkg,
        value_pattern=value_pattern,
        min_stock=min_stock,
        limit=limit,
    )
