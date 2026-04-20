from __future__ import annotations
from pathlib import Path
import subprocess
import time

class PreflightError(Exception):
    pass

def _git_is_clean(paths: list[Path]) -> bool:
    if not paths:
        return True
    try:
        cp = subprocess.run(
            ["git", "status", "--porcelain", "--", *map(str, paths)],
            capture_output=True, text=True, check=True,
        )
        return cp.stdout.strip() == ""
    except subprocess.CalledProcessError:
        return True
    except FileNotFoundError:
        return True

def _db_age_days(db: Path) -> int:
    return int((time.time() - db.stat().st_mtime) / 86400)

def _claude_ok() -> bool:
    try:
        cp = subprocess.run(
            ["claude", "-p", "ok"],
            capture_output=True, text=True, timeout=20,
        )
        return cp.returncode == 0
    except Exception:
        return False

def run_preflight(
    schematics: list[Path],
    parts_db: Path,
    force: bool,
    allow_stale_db: bool,
    skip_claude_check: bool = False,
) -> None:
    parts_db = Path(parts_db)
    if not parts_db.exists():
        raise PreflightError(
            f"parts.db not found at {parts_db}. Run kicad-jlcpcb-tools to download."
        )
    if not allow_stale_db and _db_age_days(parts_db) > 30:
        raise PreflightError(
            f"parts.db is older than 30 days ({parts_db}). Refresh or use --allow-stale-db."
        )
    if not force and not _git_is_clean([Path(p) for p in schematics]):
        raise PreflightError(
            "target schematic files have uncommitted changes; commit/stash first or use --force."
        )
    if not skip_claude_check and not _claude_ok():
        raise PreflightError("claude CLI not available or failed smoke check.")
