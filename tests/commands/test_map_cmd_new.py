import sqlite3
from pathlib import Path
import pytest

from jlcpcb_mapper.config import load_config
from jlcpcb_mapper.commands.map_cmd import run_map
from tests.fixtures.minimal_sch import minimal_sch_one_symbol


_DB_SQL = """
CREATE TABLE parts (
    lcsc TEXT PRIMARY KEY, category TEXT, mfr TEXT, mfr_part TEXT,
    package TEXT, description TEXT, basic INTEGER, preferred INTEGER,
    stock INTEGER, price REAL
);
INSERT INTO parts VALUES ('C16133','Aluminum Electrolytic','Nichicon','X',
    'D6.3','220uF 10V',1,0,25000,0.05);
INSERT INTO parts VALUES ('C471773','Aluminum Electrolytic','Other','Y',
    'D6.3','220uF 10V',0,0,15000,0.04);
"""


def _mk_project(tmp_path: Path) -> Path:
    proj = tmp_path / "p.kicad_pro"
    proj.write_text("{}")
    (tmp_path / "p.kicad_sch").write_text(
        minimal_sch_one_symbol(
            reference="C12", lib_id="Device:CP",
            value="220uF/10V", footprint="",
        )
    )
    return proj


def _mk_db(tmp_path: Path) -> Path:
    p = tmp_path / "parts.db"
    conn = sqlite3.connect(str(p))
    conn.executescript(_DB_SQL)
    conn.commit()
    conn.close()
    return p


def test_run_map_writes_lcsc_and_footprint(tmp_path, monkeypatch):
    # Stub preflight's side-effectful checks
    monkeypatch.setattr("jlcpcb_mapper.preflight._claude_ok", lambda: True)
    monkeypatch.setattr("jlcpcb_mapper.preflight._git_is_clean", lambda paths: True)

    # Stub easyeda download to avoid any HTTP.
    # Must be patched on the module BEFORE default_registry() is called inside run_map,
    # because EasyedaFallback.__init__ does `from ..io.easyeda import download_footprint`.
    def _fake_dl(lcsc, d):
        Path(d).mkdir(parents=True, exist_ok=True)
        out = Path(d) / f"{lcsc}_fake.kicad_mod"
        out.write_text("(module fake)")
        return out

    import jlcpcb_mapper.io.easyeda as ez
    monkeypatch.setattr(ez, "download_footprint", _fake_dl)

    project = _mk_project(tmp_path)
    cfg = load_config(tmp_path / "nope.yaml")  # returns defaults-only Config
    cfg.parts_db = str(_mk_db(tmp_path))

    report = run_map(
        project_pro=project, config=cfg,
        non_interactive=True, force=True, allow_stale_db=True,
        fill_lcsc_only=False, include_dnp=True, apply_suggestions=False,
    )

    # Verify report shape
    assert report.filtered_in == 1
    assert report.total_empty_instances == 1

    # Verify schematic got LCSC + footprint written
    text = (tmp_path / "p.kicad_sch").read_text()
    assert "C16133" in text
    assert "LCSC:C16133" in text

    # Verify trace file exists
    traces_parent = tmp_path / ".jlcpcb-mapper" / "traces"
    assert traces_parent.exists()
    trace_dirs = list(traces_parent.iterdir())
    assert len(trace_dirs) == 1
    assert (trace_dirs[0] / "groups.jsonl").exists()
    assert (trace_dirs[0] / "index.json").exists()

    # Verify run-log exists
    run_logs = list((tmp_path / ".jlcpcb-mapper").glob("run-*.json"))
    assert len(run_logs) == 1
