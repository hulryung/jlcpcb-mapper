import pytest
from tests.fixtures.make_test_db import build
from jlcpcb_mapper.parts_db import PartsDB

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
    rows = db.query_candidates(
        category_sql_like="Chip Resistor%",
        package="0402",
        value_pattern="%0Ω%",
        min_stock=1000,
        limit=30,
    )
    assert len(rows) >= 1
    assert rows[0].lcsc == "C17168"

def test_missing_lcsc_returns_none(db):
    assert db.get("C99999999") is None
