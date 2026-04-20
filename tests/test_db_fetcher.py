from pathlib import Path
import sqlite3
from unittest.mock import patch, MagicMock
from jlcpcb_mapper.db_fetcher import transform_cache_to_parts_db, probe_chunk_urls, build_parts_db_from_cache

def _make_minimal_cache(tmp_path) -> Path:
    """Write a tiny cache.sqlite3 mimicking yaqwsx/jlcparts schema."""
    p = tmp_path / "cache.sqlite3"
    conn = sqlite3.connect(str(p))
    c = conn.cursor()
    c.execute("""CREATE TABLE components (
        lcsc INTEGER PRIMARY KEY,
        category_id INTEGER,
        mfr TEXT,
        package TEXT,
        manufacturer_id INTEGER,
        basic INTEGER,
        preferred INTEGER,
        description TEXT,
        stock INTEGER,
        price TEXT
    )""")
    c.execute("CREATE TABLE manufacturers (id INTEGER PRIMARY KEY, name TEXT)")
    c.execute("CREATE TABLE categories (id INTEGER PRIMARY KEY, category TEXT, subcategory TEXT)")
    c.execute("INSERT INTO manufacturers VALUES (1,'UNI-ROYAL')")
    c.execute("INSERT INTO categories VALUES (1,'Resistors','Chip Resistor - Surface Mount')")
    c.execute(
        "INSERT INTO components VALUES (?,?,?,?,?,?,?,?,?,?)",
        (17168, 1, "0402WGF0000TCE", "0402", 1, 1, 0, "0Ω 0402", 2300000, '[{"qFrom":1,"qTo":9,"price":0.0008}]'),
    )
    conn.commit()
    conn.close()
    return p

def test_transform_cache_writes_expected_schema(tmp_path):
    cache = _make_minimal_cache(tmp_path)
    out = tmp_path / "parts.db"
    count = transform_cache_to_parts_db(cache, out)
    assert count == 1
    # Verify schema + row
    conn = sqlite3.connect(str(out))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM parts WHERE lcsc='C17168'").fetchone()
    assert row is not None
    assert row["lcsc"] == "C17168"
    assert row["category"] == "Chip Resistor - Surface Mount"
    assert row["mfr"] == "UNI-ROYAL"
    assert row["mfr_part"] == "0402WGF0000TCE"
    assert row["package"] == "0402"
    assert row["basic"] == 1
    assert row["stock"] == 2300000
    # price parsed to float from JSON array (first tier)
    assert abs(row["price"] - 0.0008) < 1e-9

def test_transform_handles_bad_price(tmp_path):
    cache = _make_minimal_cache(tmp_path)
    # Corrupt the price to something invalid
    conn = sqlite3.connect(str(cache))
    conn.execute("UPDATE components SET price='not json' WHERE lcsc=17168")
    conn.commit(); conn.close()
    out = tmp_path / "parts.db"
    transform_cache_to_parts_db(cache, out)
    conn = sqlite3.connect(str(out))
    row = conn.execute("SELECT price FROM parts LIMIT 1").fetchone()
    assert row[0] == 0.0  # graceful fallback

def test_probe_chunk_urls_stops_at_404():
    """Given a fake HEAD probe that returns OK for z01..z03 and 404 for z04,
    the URL list should contain exactly 4 entries: cache.zip + z01..z03."""
    def fake_head(url, **kw):
        resp = MagicMock()
        if "z04" in url or "z05" in url:
            resp.status_code = 404
        else:
            resp.status_code = 200
        return resp
    with patch("jlcpcb_mapper.db_fetcher._head", side_effect=fake_head):
        urls = probe_chunk_urls(base="https://example.com/", max_probe=10)
    assert len(urls) == 4
    assert urls[0].endswith("cache.zip")
    assert urls[-1].endswith("cache.z03")

def test_build_parts_db_end_to_end_mocked(tmp_path):
    """Full pipeline test: mock HTTP, mock reassembly, real transform."""
    cache_dir = tmp_path / "cache"
    out_db = tmp_path / "parts.db"
    fake_cache = _make_minimal_cache(tmp_path)

    def fake_download(urls, dest_dir):
        # Just pretend we downloaded; return list of dummy chunk paths
        paths = []
        for u in urls:
            p = dest_dir / u.rsplit("/", 1)[-1]
            p.write_bytes(b"dummy")
            paths.append(p)
        return paths

    def fake_reassemble_extract(chunk_paths, out_dir):
        # Write the real fake cache.sqlite3 to out_dir
        dest = out_dir / "cache.sqlite3"
        dest.write_bytes(fake_cache.read_bytes())
        return dest

    with patch("jlcpcb_mapper.db_fetcher.probe_chunk_urls", return_value=["u1", "u2"]), \
         patch("jlcpcb_mapper.db_fetcher._download_all", side_effect=fake_download), \
         patch("jlcpcb_mapper.db_fetcher._reassemble_and_extract", side_effect=fake_reassemble_extract):
        build_parts_db_from_cache(out_db=out_db, cache_dir=cache_dir)
    assert out_db.exists()
    conn = sqlite3.connect(str(out_db))
    n = conn.execute("SELECT COUNT(*) FROM parts").fetchone()[0]
    assert n == 1
