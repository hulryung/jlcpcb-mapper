from pathlib import Path
from unittest.mock import patch
from jlcpcb_mapper.commands.verify_cmd import run_verify
from jlcpcb_mapper.config import load_config
from tests.fixtures.make_test_db import build

FIX = Path(__file__).parent / "fixtures"

def test_verify_flags_low_stock(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    # uart.kicad_sch contains J5 already mapped to C262679; test DB gives it stock=500
    (proj / "uart.kicad_sch").write_bytes((FIX / "uart.kicad_sch").read_bytes())
    (proj / "uart.kicad_pro").write_text("{}")
    build(proj / "parts.db")
    (proj / "jlcpcb-mapper.yaml").write_text(
        f"parts_db: {proj}/parts.db\n"
        "verify:\n  min_stock_warning: 1000\n"
    )
    cfg = load_config(proj / "jlcpcb-mapper.yaml")
    with patch("jlcpcb_mapper.commands.verify_cmd.run_preflight"):
        report = run_verify(
            project_pro=proj / "uart.kicad_pro",
            config=cfg,
            non_interactive=True,
            force=True,
            allow_stale_db=True,
        )
    # C262679 has stock 500, below threshold 1000 → low_stock flagged
    assert any(f.kind == "low_stock" for f in report.failures)

def test_verify_missing_lcsc_in_db(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "uart.kicad_sch").write_bytes((FIX / "uart.kicad_sch").read_bytes())
    (proj / "uart.kicad_pro").write_text("{}")
    # Build an empty DB — J5's LCSC C262679 will not be found
    import sqlite3
    conn = sqlite3.connect(str(proj / "parts.db"))
    conn.execute("CREATE TABLE parts (lcsc TEXT PRIMARY KEY, category TEXT, mfr TEXT, mfr_part TEXT, package TEXT, description TEXT, basic INTEGER, preferred INTEGER, stock INTEGER, price REAL)")
    conn.commit(); conn.close()
    (proj / "jlcpcb-mapper.yaml").write_text(f"parts_db: {proj}/parts.db\n")
    cfg = load_config(proj / "jlcpcb-mapper.yaml")
    with patch("jlcpcb_mapper.commands.verify_cmd.run_preflight"):
        report = run_verify(
            project_pro=proj / "uart.kicad_pro",
            config=cfg,
            non_interactive=True,
            force=True,
            allow_stale_db=True,
        )
    assert any(f.kind == "missing" for f in report.failures)

def test_verify_writes_state_snapshot(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "uart.kicad_sch").write_bytes((FIX / "uart.kicad_sch").read_bytes())
    (proj / "uart.kicad_pro").write_text("{}")
    build(proj / "parts.db")
    (proj / "jlcpcb-mapper.yaml").write_text(f"parts_db: {proj}/parts.db\n")
    cfg = load_config(proj / "jlcpcb-mapper.yaml")
    with patch("jlcpcb_mapper.commands.verify_cmd.run_preflight"):
        run_verify(
            project_pro=proj / "uart.kicad_pro",
            config=cfg,
            non_interactive=True,
            force=True,
            allow_stale_db=True,
        )
    state = proj / ".jlcpcb-mapper" / "last-state.json"
    assert state.exists()
    import json
    data = json.loads(state.read_text())
    assert "parts" in data
    assert "C262679" in data["parts"]
