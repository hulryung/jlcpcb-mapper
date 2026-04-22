from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import sqlite3

@dataclass
class PartRow:
    lcsc: str
    category: str
    mfr: str
    mfr_part: str
    package: str
    description: str
    basic: int
    preferred: int
    stock: int
    price: float

COLS = "lcsc, category, mfr, mfr_part, package, description, basic, preferred, stock, price"

class PartsDB:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

    def get(self, lcsc: str) -> PartRow | None:
        cur = self._conn.execute(f"SELECT {COLS} FROM parts WHERE lcsc = ?", (lcsc,))
        r = cur.fetchone()
        return PartRow(**dict(r)) if r else None

    def query_candidates(
        self,
        category_sql_like: str,
        package: str | None,
        value_pattern: str | None,
        min_stock: int,
        limit: int = 30,
        mpn_pattern: str | None = None,
    ) -> list[PartRow]:
        clauses = ["category LIKE ?"]
        args: list = [category_sql_like]
        if package:
            clauses.append("package = ?"); args.append(package)
        if value_pattern:
            clauses.append("description LIKE ?"); args.append(value_pattern)
        if mpn_pattern:
            clauses.append("mfr_part LIKE ?"); args.append(mpn_pattern)
        clauses.append("stock >= ?"); args.append(min_stock)
        sql = (
            f"SELECT {COLS} FROM parts WHERE {' AND '.join(clauses)} "
            f"ORDER BY basic DESC, preferred DESC, stock DESC LIMIT ?"
        )
        args.append(limit)
        cur = self._conn.execute(sql, args)
        return [PartRow(**dict(r)) for r in cur.fetchall()]

    def execute(self, q) -> list["PartRow"]:
        """Run a QuerySpec against parts.db. Added during architecture migration."""
        from .core.types import QuerySpec  # local import to avoid cycles
        assert isinstance(q, QuerySpec), f"expected QuerySpec, got {type(q).__name__}"
        clauses: list[str] = ["category LIKE ?"]
        args: list = [q.category_like]
        if q.package is not None:
            clauses.append("package = ?"); args.append(q.package)
        for pat in q.description_patterns:
            clauses.append("description LIKE ?"); args.append(pat)
        for pat in q.mpn_patterns:
            clauses.append("mfr_part LIKE ?"); args.append(pat)
        clauses.append("stock >= ?"); args.append(q.min_stock)
        sql = (
            f"SELECT {COLS} FROM parts WHERE {' AND '.join(clauses)} "
            f"ORDER BY {q.order_by} LIMIT ?"
        )
        args.append(q.limit)
        cur = self._conn.execute(sql, args)
        return [PartRow(**dict(r)) for r in cur.fetchall()]
