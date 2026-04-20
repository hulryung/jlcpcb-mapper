from tests.fixtures.make_test_db import build
from jlcpcb_mapper.parts_db import PartsDB
from jlcpcb_mapper.candidates import candidates_for
from jlcpcb_mapper.grouper import GroupKey

def mk_db(tmp_path):
    p = tmp_path / "parts.db"
    build(p)
    return PartsDB(p)

def test_resistor_candidates(tmp_path):
    db = mk_db(tmp_path)
    key = GroupKey(category="resistor", value="0Ω", package_hint="0402")
    rows = candidates_for(key, db, min_stock=1000, limit=30)
    lcsc = [r.lcsc for r in rows]
    assert "C17168" in lcsc

def test_capacitor_candidates(tmp_path):
    db = mk_db(tmp_path)
    key = GroupKey(category="capacitor", value="2.2µF", package_hint="0402")
    rows = candidates_for(key, db, min_stock=1000, limit=30)
    assert any(r.lcsc == "C440198" for r in rows)

def test_connector_candidates_looser(tmp_path):
    db = mk_db(tmp_path)
    key = GroupKey(category="connector_1x6", value="AFC24-S06FIA-00", package_hint="")
    rows = candidates_for(key, db, min_stock=0, limit=30)
    assert any(r.lcsc == "C262679" for r in rows)
