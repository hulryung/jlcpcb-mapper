from __future__ import annotations
from pathlib import Path
import shutil
import sqlite3
import subprocess
import urllib.error
import urllib.request

_DEFAULT_BASE = "https://yaqwsx.github.io/jlcparts/data/"


class _HeadResult:
    __slots__ = ("status_code",)
    def __init__(self, status_code: int):
        self.status_code = status_code


def _head(url: str, timeout: int = 20) -> "_HeadResult":
    req = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return _HeadResult(r.status)
    except urllib.error.HTTPError as e:
        return _HeadResult(e.code)
    except Exception:
        return _HeadResult(0)


def probe_chunk_urls(base: str = _DEFAULT_BASE, max_probe: int = 30) -> list[str]:
    """Probe cache.zip + cache.z01..zNN sequentially, stop at first 404."""
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


def _chunk_sort_key(p: Path) -> tuple[int, str]:
    name = p.name
    if name.endswith(".zip"):
        return (0, name)
    try:
        return (int(name.rsplit(".z", 1)[-1]), name)
    except ValueError:
        return (9999, name)


def _extract_with_7z(chunk_paths: list[Path], out_dir: Path) -> Path | None:
    """Try extracting the split zip with `7z`. Returns cache.sqlite3 path on
    success, None if 7z is unavailable or failed."""
    tool = shutil.which("7z") or shutil.which("7zz")
    if tool is None:
        return None
    ordered = sorted(chunk_paths, key=_chunk_sort_key)
    if not ordered:
        return None
    zip_path = ordered[0]  # 7z auto-discovers z01..zNN when pointed at cache.zip
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            [tool, "x", str(zip_path), f"-o{out_dir}", "-y"],
            check=True, capture_output=True,
        )
    except subprocess.CalledProcessError:
        return None
    target = out_dir / "cache.sqlite3"
    return target if target.exists() else None


def _extract_with_split_file_reader(chunk_paths: list[Path], out_dir: Path) -> Path:
    """Fallback: use split-file-reader + zipfile stdlib."""
    import zipfile
    try:
        from split_file_reader.split_file_reader import SplitFileReader
    except Exception as e:
        raise RuntimeError(
            "Neither `7z` nor `split-file-reader` is available. "
            "Install 7-Zip (`brew install p7zip`) or "
            "`pip install split-file-reader`."
        ) from e
    ordered = sorted(chunk_paths, key=_chunk_sort_key)
    out_dir.mkdir(parents=True, exist_ok=True)
    with SplitFileReader([str(p) for p in ordered]) as sfr:
        with zipfile.ZipFile(sfr, "r") as zf:
            target = next((n for n in zf.namelist() if n.endswith("cache.sqlite3")), None)
            if target is None:
                raise RuntimeError("cache.sqlite3 not found in archive")
            zf.extract(target, str(out_dir))
            return out_dir / target


def _reassemble_and_extract(chunk_paths: list[Path], out_dir: Path) -> Path:
    """Extract cache.sqlite3 from split zip. Prefer 7z, fall back to Python."""
    p = _extract_with_7z(chunk_paths, out_dir)
    if p is not None:
        return p
    return _extract_with_split_file_reader(chunk_paths, out_dir)


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

_TRANSFORM_SQL = """
INSERT OR REPLACE INTO parts
    (lcsc, category, mfr, mfr_part, package, description, basic, preferred, stock, price)
SELECT
    'C' || c.lcsc,
    COALESCE(cat.subcategory, ''),
    COALESCE(m.name, ''),
    COALESCE(c.mfr, ''),
    COALESCE(c.package, ''),
    COALESCE(c.description, ''),
    COALESCE(c.basic, 0),
    COALESCE(c.preferred, 0),
    COALESCE(c.stock, 0),
    COALESCE(CASE WHEN json_valid(c.price) THEN CAST(json_extract(c.price, '$[0].price') AS REAL) ELSE 0.0 END, 0.0)
FROM src.components c
LEFT JOIN src.manufacturers m ON m.id = c.manufacturer_id
LEFT JOIN src.categories cat ON cat.id = c.category_id
WHERE c.stock >= :min_stock
"""

_INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_parts_cat_pkg ON parts(category, package)",
    "CREATE INDEX IF NOT EXISTS idx_parts_basic_stock ON parts(basic DESC, preferred DESC, stock DESC)",
]


def transform_cache_to_parts_db(cache_sqlite: Path, out_db: Path, min_stock: int = 100) -> int:
    """Transform yaqwsx/jlcparts cache.sqlite3 to our slim parts.db.
    Filters by stock >= min_stock; returns row count.
    """
    if out_db.exists():
        out_db.unlink()
    dst = sqlite3.connect(str(out_db))
    dst.execute(_CREATE_PARTS_SQL)
    dst.execute(f"ATTACH DATABASE '{cache_sqlite}' AS src")
    dst.execute("BEGIN")
    dst.execute(_TRANSFORM_SQL, {"min_stock": min_stock})
    count = dst.execute("SELECT COUNT(*) FROM parts").fetchone()[0]
    for idx in _INDEX_SQL:
        dst.execute(idx)
    dst.commit()
    dst.execute("DETACH DATABASE src")
    dst.execute("VACUUM")
    dst.close()
    return count


def build_parts_db_from_cache(
    *,
    out_db: Path,
    cache_dir: Path,
    min_stock: int = 100,
    keep_cache: bool = False,
    base_url: str = _DEFAULT_BASE,
) -> Path:
    urls = probe_chunk_urls(base=base_url)
    if len(urls) < 1:
        raise RuntimeError("Could not enumerate cache chunk URLs (no cache.zip found).")
    cache_dir.mkdir(parents=True, exist_ok=True)
    chunks = _download_all(urls, cache_dir)
    extract_dir = cache_dir / "extracted"
    cache_sqlite = _reassemble_and_extract(chunks, extract_dir)
    transform_cache_to_parts_db(cache_sqlite, out_db, min_stock=min_stock)
    if not keep_cache:
        try:
            cache_sqlite.unlink()
        except Exception:
            pass
    return out_db
