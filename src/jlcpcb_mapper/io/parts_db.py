from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import sqlite3
import threading

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
    """Thread-safe parts.db reader.

    The pipeline fans out per-group queries across a ThreadPoolExecutor.
    sqlite3 connections opened with `check_same_thread=False` permit
    cross-thread *use* but the connection's internal state is NOT safe
    against concurrent execute() calls — Python 3.14 hardened this and
    raises `sqlite3.InterfaceError: bad parameter or other API misuse`
    when threads collide. We hold a one-connection-per-thread cache so
    each worker gets its own sqlite handle.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._local = threading.local()

    def _conn(self) -> sqlite3.Connection:
        c = getattr(self._local, "conn", None)
        if c is None:
            c = sqlite3.connect(str(self.path))
            c.row_factory = sqlite3.Row
            self._local.conn = c
        return c

    def get(self, lcsc: str) -> PartRow | None:
        cur = self._conn().execute(f"SELECT {COLS} FROM parts WHERE lcsc = ?", (lcsc,))
        r = cur.fetchone()
        return PartRow(**dict(r)) if r else None

    def execute(self, q) -> list["PartRow"]:
        """Run a QuerySpec against parts.db. Added during architecture migration."""
        from ..core.types import QuerySpec  # local import to avoid cycles
        assert isinstance(q, QuerySpec), f"expected QuerySpec, got {type(q).__name__}"
        clauses: list[str] = ["category LIKE ?"]
        args: list = [q.category_like]
        if q.package is not None:
            clauses.append("package = ?"); args.append(q.package)
        for pat in q.description_patterns:
            clauses.append("description LIKE ?"); args.append(pat)
        for pat in q.mpn_patterns:
            clauses.append("mfr_part LIKE ? ESCAPE '\\'"); args.append(pat)
        clauses.append("stock >= ?"); args.append(q.min_stock)
        sql = (
            f"SELECT {COLS} FROM parts WHERE {' AND '.join(clauses)} "
            f"ORDER BY {q.order_by} LIMIT ?"
        )
        args.append(q.limit)
        cur = self._conn().execute(sql, args)
        return [PartRow(**dict(r)) for r in cur.fetchall()]
