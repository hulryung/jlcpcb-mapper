from unittest.mock import patch
from jlcpcb_mapper.preflight import run_preflight, PreflightError

def test_missing_parts_db_raises(tmp_path):
    raised = False
    try:
        with patch("jlcpcb_mapper.preflight._git_is_clean", return_value=True), \
             patch("jlcpcb_mapper.preflight._claude_ok", return_value=True):
            run_preflight(
                schematics=[tmp_path / "x.kicad_sch"],
                parts_db=tmp_path / "nope.db",
                force=False, allow_stale_db=False,
            )
    except PreflightError:
        raised = True
    assert raised

def test_dirty_schematic_raises_without_force(tmp_path):
    sch = tmp_path / "uart.kicad_sch"; sch.write_text("x")
    db = tmp_path / "parts.db"; db.write_bytes(b"\x00")
    raised = False
    try:
        with patch("jlcpcb_mapper.preflight._git_is_clean", return_value=False), \
             patch("jlcpcb_mapper.preflight._claude_ok", return_value=True), \
             patch("jlcpcb_mapper.preflight._db_age_days", return_value=1):
            run_preflight([sch], db, force=False, allow_stale_db=False)
    except PreflightError:
        raised = True
    assert raised

def test_force_bypasses_git_check(tmp_path):
    sch = tmp_path / "uart.kicad_sch"; sch.write_text("x")
    db = tmp_path / "parts.db"; db.write_bytes(b"\x00")
    with patch("jlcpcb_mapper.preflight._git_is_clean", return_value=False), \
         patch("jlcpcb_mapper.preflight._claude_ok", return_value=True), \
         patch("jlcpcb_mapper.preflight._db_age_days", return_value=1):
        run_preflight([sch], db, force=True, allow_stale_db=False)  # should not raise

def test_allow_stale_db_bypasses_age_check(tmp_path):
    sch = tmp_path / "uart.kicad_sch"; sch.write_text("x")
    db = tmp_path / "parts.db"; db.write_bytes(b"\x00")
    with patch("jlcpcb_mapper.preflight._git_is_clean", return_value=True), \
         patch("jlcpcb_mapper.preflight._claude_ok", return_value=True), \
         patch("jlcpcb_mapper.preflight._db_age_days", return_value=365):
        run_preflight([sch], db, force=False, allow_stale_db=True)  # should not raise

def test_claude_check_can_be_skipped(tmp_path):
    sch = tmp_path / "uart.kicad_sch"; sch.write_text("x")
    db = tmp_path / "parts.db"; db.write_bytes(b"\x00")
    with patch("jlcpcb_mapper.preflight._git_is_clean", return_value=True), \
         patch("jlcpcb_mapper.preflight._claude_ok", return_value=False), \
         patch("jlcpcb_mapper.preflight._db_age_days", return_value=1):
        run_preflight([sch], db, force=False, allow_stale_db=False, skip_claude_check=True)
