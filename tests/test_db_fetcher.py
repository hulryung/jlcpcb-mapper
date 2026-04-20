from pathlib import Path
import sqlite3
import json
from unittest.mock import patch, MagicMock
from jlcpcb_mapper.db_fetcher import (
    transform_cache_to_parts_db,
    probe_chunk_urls,
    build_parts_db_from_cache,
)


def _make_cache(tmp_path, rows) -> Path:
    """Build a tiny cache.sqlite3 mimicking yaqwsx/jlcparts schema.

    rows: list of tuples (lcsc_int, category_id, mfr, package, manuf_id,
                          basic, preferred, description, stock, price_json)
    """
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
    for r in rows:
        c.execute("INSERT INTO components VALUES (?,?,?,?,?,?,?,?,?,?)", r)
    conn.commit()
    conn.close()
    return p


def test_transform_writes_expected_row(tmp_path):
    cache = _make_cache(tmp_path, [
        (17168, 1, "0402WGF0000TCE", "0402", 1, 1, 0, "0Ω 0402", 2300000,
         '[{"qFrom":1,"qTo":9,"price":0.0008}]'),
    ])
    out = tmp_path / "parts.db"
    count = transform_cache_to_parts_db(cache, out, min_stock=100)
    assert count == 1
    conn = sqlite3.connect(str(out))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM parts WHERE lcsc='C17168'").fetchone()
    assert row is not None
    assert row["lcsc"] == "C17168"
    assert row["category"] == "Chip Resistor - Surface Mount"
    assert row["mfr"] == "UNI-ROYAL"
    assert row["mfr_part"] == "0402WGF0000TCE"
    assert row["basic"] == 1
    assert row["stock"] == 2300000
    assert abs(row["price"] - 0.0008) < 1e-9


def test_transform_applies_stock_filter(tmp_path):
    cache = _make_cache(tmp_path, [
        (1, 1, "A", "0402", 1, 1, 0, "stockful", 5000, '[{"qFrom":1,"qTo":9,"price":0.001}]'),
        (2, 1, "B", "0402", 1, 0, 0, "empty",     0,    '[{"qFrom":1,"qTo":9,"price":0.001}]'),
        (3, 1, "C", "0402", 1, 0, 0, "tiny",      50,   '[{"qFrom":1,"qTo":9,"price":0.001}]'),
    ])
    out = tmp_path / "parts.db"
    count = transform_cache_to_parts_db(cache, out, min_stock=100)
    # Only the row with stock >= 100 should be present
    assert count == 1
    conn = sqlite3.connect(str(out))
    lcscs = [r[0] for r in conn.execute("SELECT lcsc FROM parts")]
    assert lcscs == ["C1"]


def test_transform_handles_bad_price(tmp_path):
    cache = _make_cache(tmp_path, [
        (17168, 1, "X", "0402", 1, 1, 0, "x", 1000, 'not json'),
    ])
    out = tmp_path / "parts.db"
    transform_cache_to_parts_db(cache, out, min_stock=100)
    conn = sqlite3.connect(str(out))
    row = conn.execute("SELECT price FROM parts LIMIT 1").fetchone()
    assert row[0] == 0.0  # graceful fallback via COALESCE


def test_transform_creates_indexes(tmp_path):
    cache = _make_cache(tmp_path, [
        (1, 1, "A", "0402", 1, 1, 0, "t", 1000, '[{"price":0.001}]'),
    ])
    out = tmp_path / "parts.db"
    transform_cache_to_parts_db(cache, out, min_stock=100)
    conn = sqlite3.connect(str(out))
    idxs = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='parts'"
    )]
    # At least one named index we create (not the implicit PK one)
    named = [i for i in idxs if i.startswith("idx_")]
    assert len(named) >= 1


def test_probe_chunk_urls_stops_at_404():
    def fake_head(url, **kw):
        resp = MagicMock()
        resp.status_code = 200 if ("cache.zip" in url or "z01" in url or "z02" in url or "z03" in url) else 404
        return resp
    with patch("jlcpcb_mapper.db_fetcher._head", side_effect=fake_head):
        urls = probe_chunk_urls(base="https://example.com/", max_probe=10)
    assert len(urls) == 4
    assert urls[0].endswith("cache.zip")
    assert urls[-1].endswith("cache.z03")


def test_build_parts_db_end_to_end_mocked(tmp_path):
    """Full pipeline with all I/O mocked."""
    cache_dir = tmp_path / "cache"
    out_db = tmp_path / "parts.db"
    fake_cache = _make_cache(tmp_path, [
        (17168, 1, "A", "0402", 1, 1, 0, "x", 2000, '[{"price":0.001}]'),
    ])

    def fake_download(urls, dest_dir):
        dest_dir.mkdir(parents=True, exist_ok=True)
        return [dest_dir / u.rsplit("/", 1)[-1] for u in urls]

    def fake_reassemble(chunk_paths, out_dir):
        out_dir.mkdir(parents=True, exist_ok=True)
        dest = out_dir / "cache.sqlite3"
        dest.write_bytes(fake_cache.read_bytes())
        return dest

    with patch("jlcpcb_mapper.db_fetcher.probe_chunk_urls", return_value=["u1", "u2"]), \
         patch("jlcpcb_mapper.db_fetcher._download_all", side_effect=fake_download), \
         patch("jlcpcb_mapper.db_fetcher._reassemble_and_extract", side_effect=fake_reassemble):
        build_parts_db_from_cache(out_db=out_db, cache_dir=cache_dir, min_stock=100)
    assert out_db.exists()
    conn = sqlite3.connect(str(out_db))
    assert conn.execute("SELECT COUNT(*) FROM parts").fetchone()[0] == 1


def test_build_parts_db_deletes_intermediate_by_default(tmp_path):
    """Intermediate cache.sqlite3 should be auto-deleted after transform unless --keep-cache."""
    cache_dir = tmp_path / "cache"
    out_db = tmp_path / "parts.db"
    fake_cache = _make_cache(tmp_path, [
        (1, 1, "A", "0402", 1, 1, 0, "x", 2000, '[{"price":0.001}]'),
    ])

    captured: dict = {}
    def fake_reassemble(chunk_paths, out_dir):
        out_dir.mkdir(parents=True, exist_ok=True)
        dest = out_dir / "cache.sqlite3"
        dest.write_bytes(fake_cache.read_bytes())
        captured["path"] = dest
        return dest

    with patch("jlcpcb_mapper.db_fetcher.probe_chunk_urls", return_value=["u1"]), \
         patch("jlcpcb_mapper.db_fetcher._download_all", return_value=[]), \
         patch("jlcpcb_mapper.db_fetcher._reassemble_and_extract", side_effect=fake_reassemble):
        build_parts_db_from_cache(out_db=out_db, cache_dir=cache_dir, min_stock=100, keep_cache=False)
    assert not captured["path"].exists(), "intermediate cache.sqlite3 should be deleted"


def test_build_parts_db_keeps_intermediate_when_requested(tmp_path):
    cache_dir = tmp_path / "cache"
    out_db = tmp_path / "parts.db"
    fake_cache = _make_cache(tmp_path, [
        (1, 1, "A", "0402", 1, 1, 0, "x", 2000, '[{"price":0.001}]'),
    ])

    captured: dict = {}
    def fake_reassemble(chunk_paths, out_dir):
        out_dir.mkdir(parents=True, exist_ok=True)
        dest = out_dir / "cache.sqlite3"
        dest.write_bytes(fake_cache.read_bytes())
        captured["path"] = dest
        return dest

    with patch("jlcpcb_mapper.db_fetcher.probe_chunk_urls", return_value=["u1"]), \
         patch("jlcpcb_mapper.db_fetcher._download_all", return_value=[]), \
         patch("jlcpcb_mapper.db_fetcher._reassemble_and_extract", side_effect=fake_reassemble):
        build_parts_db_from_cache(out_db=out_db, cache_dir=cache_dir, min_stock=100, keep_cache=True)
    assert captured["path"].exists(), "intermediate cache.sqlite3 should be kept"
