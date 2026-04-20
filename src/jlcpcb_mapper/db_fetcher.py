from __future__ import annotations
from pathlib import Path
import json
import sqlite3
import urllib.request

_DEFAULT_BASE = "https://yaqwsx.github.io/jlcparts/data/"

_CREATE_PARTS_SQL = """
CREATE TABLE IF NOT EXISTS parts (
    lcsc TEXT PRIMARY KEY,
    category TEXT,
    mfr TEXT,
    mfr_part TEXT,
    package TEXT,
    description TEXT,
    basic INTEGER,
    preferred INTEGER,
    stock INTEGER,
    price REAL
)
"""

def _head(url: str, timeout: int = 20):
    """Return an object with .status_code. Uses urllib for HEAD."""
    req = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            class _R:
                status_code = r.status
            return _R()
    except urllib.error.HTTPError as e:
        class _R:
            status_code = e.code
        return _R()
    except Exception:
        class _R:
            status_code = 0
        return _R()


def probe_chunk_urls(base: str = _DEFAULT_BASE, max_probe: int = 20) -> list[str]:
    urls = [base + "cache.zip"]
    for i in range(1, max_probe + 1):
        url = f"{base}cache.z{i:02d}"
        r = _head(url)
        if r.status_code != 200:
            break
        urls.append(url)
    return urls


def _download_all(urls: list[str], dest_dir: Path) -> list[Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for url in urls:
        name = url.rsplit("/", 1)[-1]
        path = dest_dir / name
        # Skip if already present (simple resume-by-existence)
        if not path.exists() or path.stat().st_size == 0:
            print(f"downloading {url}")
            with urllib.request.urlopen(url) as r, open(path, "wb") as f:
                while True:
                    chunk = r.read(1024 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
        paths.append(path)
    return paths


def _reassemble_and_extract(chunk_paths: list[Path], out_dir: Path) -> Path:
    """Reassemble the split zip and extract cache.sqlite3 into out_dir.
    Returns the path to the extracted cache.sqlite3.
    """
    import zipfile
    try:
        from split_file_reader.split_file_reader import SplitFileReader
    except Exception as e:
        raise RuntimeError(
            "split-file-reader is required to reassemble split zip. Install via "
            "`pip install split-file-reader`."
        ) from e

    # SplitFileReader expects the chunks in correct order: cache.zip first, then z01, z02, ...
    # But our probe returns them in that order; ensure so explicitly.
    def _sort_key(p: Path) -> tuple[int, str]:
        name = p.name
        if name.endswith(".zip"):
            return (0, name)
        # cache.zNN
        suffix = name.rsplit(".z", 1)[-1]
        try:
            return (int(suffix), name)
        except ValueError:
            return (9999, name)
    ordered = sorted(chunk_paths, key=_sort_key)

    out_dir.mkdir(parents=True, exist_ok=True)
    with SplitFileReader([str(p) for p in ordered]) as sfr:
        with zipfile.ZipFile(sfr, "r") as zf:
            target = None
            for info in zf.namelist():
                if info.endswith("cache.sqlite3"):
                    target = info
                    break
            if target is None:
                raise RuntimeError("cache.sqlite3 not found in archive")
            zf.extract(target, str(out_dir))
            return out_dir / target


def _parse_first_price(price_json: str) -> float:
    try:
        arr = json.loads(price_json)
        if isinstance(arr, list) and arr:
            v = arr[0].get("price", 0.0)
            return float(v)
    except Exception:
        pass
    return 0.0


def transform_cache_to_parts_db(cache_sqlite: Path, out_db: Path) -> int:
    """Convert a yaqwsx/jlcparts cache.sqlite3 into our schema at out_db.
    Returns the number of rows written.
    """
    if out_db.exists():
        out_db.unlink()
    src = sqlite3.connect(str(cache_sqlite))
    src.row_factory = sqlite3.Row
    dst = sqlite3.connect(str(out_db))
    dst.execute(_CREATE_PARTS_SQL)

    query = """
    SELECT
        c.lcsc               AS lcsc_int,
        cat.subcategory      AS category,
        m.name               AS mfr,
        c.mfr                AS mfr_part,
        c.package            AS package,
        c.description        AS description,
        c.basic              AS basic,
        c.preferred          AS preferred,
        c.stock              AS stock,
        c.price              AS price_json
    FROM components c
    LEFT JOIN manufacturers m ON m.id = c.manufacturer_id
    LEFT JOIN categories    cat ON cat.id = c.category_id
    """
    cur = src.execute(query)
    BATCH = 1000
    batch: list = []
    count = 0
    for r in cur:
        batch.append((
            f"C{r['lcsc_int']}",
            r["category"] or "",
            r["mfr"] or "",
            r["mfr_part"] or "",
            r["package"] or "",
            r["description"] or "",
            int(r["basic"] or 0),
            int(r["preferred"] or 0),
            int(r["stock"] or 0),
            _parse_first_price(r["price_json"] or ""),
        ))
        if len(batch) >= BATCH:
            dst.executemany(
                "INSERT OR REPLACE INTO parts (lcsc,category,mfr,mfr_part,package,description,basic,preferred,stock,price) VALUES (?,?,?,?,?,?,?,?,?,?)",
                batch,
            )
            count += len(batch)
            batch.clear()
    if batch:
        dst.executemany(
            "INSERT OR REPLACE INTO parts (lcsc,category,mfr,mfr_part,package,description,basic,preferred,stock,price) VALUES (?,?,?,?,?,?,?,?,?,?)",
            batch,
        )
        count += len(batch)
    dst.commit()
    dst.close()
    src.close()
    return count


def build_parts_db_from_cache(
    *,
    out_db: Path,
    cache_dir: Path,
    base_url: str = _DEFAULT_BASE,
) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    urls = probe_chunk_urls(base=base_url)
    if len(urls) < 1:
        raise RuntimeError("Could not enumerate cache chunk URLs (no cache.zip found).")
    chunks = _download_all(urls, cache_dir)
    extract_dir = cache_dir / "extracted"
    extract_dir.mkdir(parents=True, exist_ok=True)
    cache_sqlite = _reassemble_and_extract(chunks, extract_dir)
    transform_cache_to_parts_db(cache_sqlite, out_db)
    return out_db
