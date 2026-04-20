import pytest
from tests.fixtures.make_test_db import build
from jlcpcb_mapper.parts_db import PartsDB
from jlcpcb_mapper.candidates import candidates_for, _value_to_sql_pattern
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


@pytest.mark.parametrize("value,expected", [
    ("0Ω",       "% 0Ω%"),
    ("100Ω",     "% 100Ω%"),
    ("4.7Ω",     "% 4.7Ω%"),
    ("1000Ω",    "% 1kΩ%"),
    ("4700Ω",    "% 4.7kΩ%"),
    ("5100Ω",    "% 5.1kΩ%"),
    ("51000Ω",   "% 51kΩ%"),
    ("1000000Ω", "% 1MΩ%"),
    ("2200000Ω", "% 2.2MΩ%"),
])
def test_resistor_value_pattern_uses_si_prefix(value, expected):
    assert _value_to_sql_pattern("resistor", value) == expected


@pytest.mark.parametrize("value,expected", [
    ("2.2µF", "%2.2uF%"),
    ("1µF",   "%1uF%"),
    ("100nF", "%100nF%"),
    ("22pF",  "%22pF%"),
])
def test_capacitor_value_pattern_uses_ascii_u(value, expected):
    assert _value_to_sql_pattern("capacitor", value) == expected


def test_resistor_0ohm_does_not_match_100ohm():
    """The " 0Ω" pattern must not falsely match " 100Ω" as a substring."""
    pat = _value_to_sql_pattern("resistor", "0Ω")
    # Simulate SQLite LIKE matching: % is anything
    import re
    re_pat = re.compile("^" + pat.replace("%", ".*").replace(" ", r"\ ") + "$")
    assert re_pat.search(" 0Ω 50V")
    assert not re_pat.fullmatch(" 100Ω 50V ")


def test_candidates_match_real_description_formats(tmp_path):
    import sqlite3
    p = tmp_path / "parts.db"
    conn = sqlite3.connect(str(p))
    conn.execute("""CREATE TABLE parts (
        lcsc TEXT PRIMARY KEY, category TEXT, mfr TEXT, mfr_part TEXT,
        package TEXT, description TEXT, basic INTEGER, preferred INTEGER,
        stock INTEGER, price REAL
    )""")
    rows = [
        ("C17168","Chip Resistor - Surface Mount","UNI-ROYAL","0402WGF0000TCE","0402",
         "-55℃~+155℃ 0Ω 50V 62.5mW Thick Film Resistor ±1% ±800ppm/℃ 0402",1,0,13_791_840,0.0007),
        ("C25091","Chip Resistor - Surface Mount","UNI-ROYAL","0402WGF2200TCE","0402",
         "-55℃~+155℃ 220Ω 50V 62.5mW Thick Film Resistor ±1% ±100ppm/℃ 0402",1,0,7_000_000,0.0008),
        ("C11702","Chip Resistor - Surface Mount","UNI-ROYAL","0402WGF1001TCE","0402",
         "-55℃~+155℃ 1kΩ 50V 62.5mW Thick Film Resistor ±1% ±100ppm/℃ 0402",1,0,1_500_000,0.0008),
        ("C12530","Multilayer Ceramic Capacitors MLCC - SMD/SMT","Samsung","CL05A225MP5NSNC","0402",
         "2.2uF 6.3V X5R ±20% 0402 Multilayer Ceramic Capacitors MLCC - SMD/SMT ROHS",1,0,950_000,0.0015),
    ]
    conn.executemany("INSERT INTO parts VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()

    from jlcpcb_mapper.parts_db import PartsDB
    from jlcpcb_mapper.candidates import candidates_for
    from jlcpcb_mapper.grouper import GroupKey
    db = PartsDB(p)

    # 0Ω should pick up ONLY C17168, not C25091 (220Ω)
    r = candidates_for(GroupKey("resistor","0Ω","0402"), db, min_stock=1000, limit=10)
    lcsc_set = {x.lcsc for x in r}
    assert "C17168" in lcsc_set
    assert "C25091" not in lcsc_set, "pattern falsely matched 220Ω as 0Ω"

    # 1000Ω (normalized from 1K) should match the 1kΩ description
    r = candidates_for(GroupKey("resistor","1000Ω","0402"), db, min_stock=1000, limit=10)
    assert any(x.lcsc == "C11702" for x in r), "1kΩ not found for 1000Ω query"

    # 2.2µF should match "2.2uF" in description
    r = candidates_for(GroupKey("capacitor","2.2µF","0402"), db, min_stock=1000, limit=10)
    assert any(x.lcsc == "C12530" for x in r), "2.2uF not found for 2.2µF query"


def test_unsupported_categories_return_empty(tmp_path):
    """crystal, polarized_capacitor, connector_2xN should yield [] (safer than bad mapping)."""
    import sqlite3
    p = tmp_path / "parts.db"
    conn = sqlite3.connect(str(p))
    conn.execute("""CREATE TABLE parts (
        lcsc TEXT PRIMARY KEY, category TEXT, mfr TEXT, mfr_part TEXT,
        package TEXT, description TEXT, basic INTEGER, preferred INTEGER,
        stock INTEGER, price REAL
    )""")
    conn.execute(
        "INSERT INTO parts VALUES ('C1','x','m','mp','0402','desc',1,0,100000,0.001)"
    )
    conn.commit(); conn.close()

    from jlcpcb_mapper.parts_db import PartsDB
    from jlcpcb_mapper.candidates import candidates_for
    from jlcpcb_mapper.grouper import GroupKey
    db = PartsDB(p)
    for cat in ["crystal", "polarized_capacitor", "connector_2x4", "connector_2x10"]:
        key = GroupKey(cat, "any", "")
        assert candidates_for(key, db, min_stock=0, limit=30) == [], f"{cat} should return empty"

def test_inductor_candidate_pattern(tmp_path):
    import sqlite3
    p = tmp_path / "parts.db"
    conn = sqlite3.connect(str(p))
    conn.execute("""CREATE TABLE parts (
        lcsc TEXT PRIMARY KEY, category TEXT, mfr TEXT, mfr_part TEXT,
        package TEXT, description TEXT, basic INTEGER, preferred INTEGER,
        stock INTEGER, price REAL
    )""")
    conn.executemany("INSERT INTO parts VALUES (?,?,?,?,?,?,?,?,?,?)", [
        ("C1234","Inductors","Sunlord","MPN1","0603","33uH 20% 0603 Inductor",1,0,10000,0.01),
        ("C9999","Capacitors (MLCC)","X","Y","0402","22uF 25V X5R 0402",1,0,10000,0.01),
    ])
    conn.commit(); conn.close()

    from jlcpcb_mapper.parts_db import PartsDB
    from jlcpcb_mapper.candidates import candidates_for
    from jlcpcb_mapper.grouper import GroupKey
    db = PartsDB(p)
    rows = candidates_for(GroupKey("inductor","33µH",""), db, min_stock=0, limit=30)
    lcscs = [r.lcsc for r in rows]
    assert "C1234" in lcscs
    assert "C9999" not in lcscs
