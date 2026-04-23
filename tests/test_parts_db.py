import pytest
import sqlite3
from tests.fixtures.make_test_db import build
from jlcpcb_mapper.io.parts_db import PartsDB
from jlcpcb_mapper.core.types import QuerySpec

@pytest.fixture
def db(tmp_path):
    p = tmp_path / "parts.db"
    build(p)
    return PartsDB(p)

def test_lookup_by_lcsc(db):
    row = db.get("C17168")
    assert row is not None
    assert row.mfr == "UNI-ROYAL"
    assert row.basic == 1

def test_query_resistors_basic_first(db):
    q = QuerySpec(
        category_like="Chip Resistor%",
        package="0402",
        description_patterns=("%0Ω%",),
        min_stock=1000,
        limit=30,
    )
    rows = db.execute(q)
    assert len(rows) >= 1
    assert rows[0].lcsc == "C17168"

def test_missing_lcsc_returns_none(db):
    assert db.get("C99999999") is None


def test_query_candidates_mpn_pattern(tmp_path):
    """mpn_pattern filters by mfr_part LIKE — used for IC/MPN-based searches."""
    p = tmp_path / "parts.db"
    conn = sqlite3.connect(str(p))
    conn.execute("""CREATE TABLE parts (
        lcsc TEXT PRIMARY KEY, category TEXT, mfr TEXT, mfr_part TEXT,
        package TEXT, description TEXT, basic INTEGER, preferred INTEGER,
        stock INTEGER, price REAL
    )""")
    conn.executemany("INSERT INTO parts VALUES (?,?,?,?,?,?,?,?,?,?)", [
        ("C20917","MOSFET","Alpha Omega","AO3400A","SOT-23","electrical specs",1,0,500000,0.03),
        ("C99999","MOSFET","Other","BC817","SOT-23","other specs",0,0,10000,0.05),
    ])
    conn.commit(); conn.close()

    db = PartsDB(p)
    q = QuerySpec(
        category_like="%",
        package=None,
        min_stock=0,
        limit=30,
        mpn_patterns=("%AO3400A%",),
    )
    rows = db.execute(q)
    assert len(rows) == 1
    assert rows[0].lcsc == "C20917"
