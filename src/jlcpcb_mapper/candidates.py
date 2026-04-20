from __future__ import annotations
import re
from .parts_db import PartsDB, PartRow
from .grouper import GroupKey

def _value_to_sql_pattern(category: str, value: str) -> str | None:
    if category == "resistor":
        if value == "0Ω":
            return "%0Ω%"
        m = re.match(r"(\d+(?:\.\d+)?)Ω", value)
        if m:
            return f"%{m.group(1)}%"
        return None
    if category == "capacitor":
        m = re.match(r"(\d+(?:\.\d+)?)(µ|n|p)F", value)
        if m:
            return f"%{m.group(1)}{m.group(2)}F%"
        return None
    return None

CATEGORY_SQL = {
    "resistor":  "Chip Resistor%",
    "capacitor": "%Ceramic Capacitor%",
    "led":       "Light Emitting Diode%",
}

def candidates_for(
    key: GroupKey,
    db: PartsDB,
    min_stock: int,
    limit: int = 30,
) -> list[PartRow]:
    if key.category.startswith("connector"):
        return db.query_candidates(
            category_sql_like="%Connector%",
            package=None,
            value_pattern=None,
            min_stock=0,
            limit=max(limit, 50),
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
