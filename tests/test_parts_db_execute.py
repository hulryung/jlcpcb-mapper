import sqlite3
from pathlib import Path
import pytest
from jlcpcb_mapper.core.types import QuerySpec
from jlcpcb_mapper.parts_db import PartsDB


@pytest.fixture
def db(tmp_path: Path) -> PartsDB:
    p = tmp_path / "parts.db"
    conn = sqlite3.connect(str(p))
    conn.executescript("""
        CREATE TABLE parts (
            lcsc TEXT PRIMARY KEY, category TEXT, mfr TEXT, mfr_part TEXT,
            package TEXT, description TEXT, basic INTEGER, preferred INTEGER,
            stock INTEGER, price REAL
        );
        INSERT INTO parts VALUES ('C1','Chip Resistor','X','R1','0402','10kΩ 1%',1,0,50000,0.001);
        INSERT INTO parts VALUES ('C2','Chip Resistor','X','R2','0603','10kΩ 1%',0,1,25000,0.0015);
        INSERT INTO parts VALUES ('C3','Aluminum Electrolytic','Y','EL1','D6.3','220uF 10V',1,0,15000,0.05);
        INSERT INTO parts VALUES ('C4','Aluminum Electrolytic','Y','EL2','D6.3','220uF 25V',0,0,5000,0.04);
        INSERT INTO parts VALUES ('C5','Chip Resistor','X','R3','0402','10kΩ 1%',0,0,500,0.001);
    """)
    conn.commit(); conn.close()
    return PartsDB(p)


def test_execute_filters_category_package_and_stock(db):
    q = QuerySpec(category_like="Chip Resistor%", package="0402", min_stock=1000)
    rows = db.execute(q)
    assert [r.lcsc for r in rows] == ["C1"]  # C5 excluded by stock


def test_execute_description_pattern(db):
    q = QuerySpec(category_like="%Aluminum%", description_patterns=("%220uF%",))
    rows = db.execute(q)
    assert {r.lcsc for r in rows} == {"C3", "C4"}


def test_execute_orderby_basic_preferred_stock(db):
    q = QuerySpec(category_like="Chip Resistor%")
    rows = db.execute(q)
    # C1 basic=1, C2 preferred=1 stock=25k, C5 stock=500
    assert [r.lcsc for r in rows] == ["C1", "C2", "C5"]


def test_execute_respects_limit(db):
    q = QuerySpec(category_like="%", limit=2)
    assert len(db.execute(q)) == 2
