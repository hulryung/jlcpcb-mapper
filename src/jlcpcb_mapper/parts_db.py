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
        self._conn = sqlite3.connect(str(self.path))
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
    ) -> list[PartRow]:
        clauses = ["category LIKE ?"]
        args: list = [category_sql_like]
        if package:
            clauses.append("package = ?"); args.append(package)
        if value_pattern:
            clauses.append("description LIKE ?"); args.append(value_pattern)
        clauses.append("stock >= ?"); args.append(min_stock)
        sql = (
            f"SELECT {COLS} FROM parts WHERE {' AND '.join(clauses)} "
            f"ORDER BY basic DESC, preferred DESC, stock DESC LIMIT ?"
        )
        args.append(limit)
        cur = self._conn.execute(sql, args)
        return [PartRow(**dict(r)) for r in cur.fetchall()]
