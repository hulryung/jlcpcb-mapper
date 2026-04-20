from __future__ import annotations
from pathlib import Path
import json

from ..config import Config
from ..project import load_project
from ..parts_db import PartsDB
from ..preflight import run_preflight
from ..report import RunReport

STATE_FILE = ".jlcpcb-mapper/last-state.json"


def _autodetect_parts_db() -> Path:
    return Path.home() / "Library/Application Support/kicad/9.0/3rdparty/plugins/com_github_bouni_kicad-jlcpcb-tools/jlcpcb_parts.db"


def run_verify(
    *,
    project_pro: Path,
    config: Config,
    non_interactive: bool,
    force: bool,
    allow_stale_db: bool,
) -> RunReport:
    proj = load_project(project_pro)
    parts_db_path = Path(config.parts_db) if config.parts_db else _autodetect_parts_db()
    run_preflight(
        proj.schematics, parts_db_path,
        force=force, allow_stale_db=allow_stale_db,
        skip_claude_check=True,
    )
    db = PartsDB(parts_db_path)

    state_path = proj.root / STATE_FILE
    prev: dict = {}
    if state_path.exists():
        prev = json.loads(state_path.read_text()).get("parts", {})

    report = RunReport()
    report.schematics = [str(p) for p in proj.schematics]

    new_state: dict[str, dict] = {}
    for p in proj.schematics:
        for inst in proj.loaded[p].instances():
            if not inst.lcsc:
                continue
            row = db.get(inst.lcsc)
            if row is None:
                report.add_failure(
                    kind="missing",
                    detail=f"{inst.reference} ({inst.lcsc}): not in DB (EOL?)",
                )
                continue
            new_state[inst.lcsc] = {
                "stock": row.stock, "price": row.price, "basic": row.basic,
            }
            if row.stock < config.verify.min_stock_warning:
                report.add_failure(
                    kind="low_stock",
                    detail=f"{inst.reference} ({inst.lcsc}): stock={row.stock}",
                )
            snap = prev.get(inst.lcsc)
            if snap:
                if snap.get("basic") == 1 and row.basic == 0:
                    report.add_failure(
                        kind="basic_lost",
                        detail=f"{inst.lcsc}: moved Basic → Extended",
                    )
                old_price = float(snap.get("price") or 0.0) or 0.0001
                pct = abs(row.price - old_price) / old_price * 100
                if pct >= config.verify.price_change_pct_warning:
                    report.add_failure(
                        kind="price_drift",
                        detail=f"{inst.lcsc}: {old_price:.4f} → {row.price:.4f}",
                    )

    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({"parts": new_state}, indent=2))
    return report
