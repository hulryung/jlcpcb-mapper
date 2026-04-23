# tests/test_map_cmd.py
from pathlib import Path
from unittest.mock import patch, MagicMock
from jlcpcb_mapper.commands.map_cmd import run_map
from jlcpcb_mapper.config import load_config
from tests.fixtures.make_test_db import build

FIX = Path(__file__).parent / "fixtures"

def test_map_end_to_end_writes_footprint_and_lcsc(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "uart.kicad_sch").write_bytes((FIX / "uart.kicad_sch").read_bytes())
    (proj / "uart.kicad_pro").write_text("{}")
    (proj / "jlcpcb-mapper.yaml").write_text(f"parts_db: {proj}/parts.db\n")
    build(proj / "parts.db")
    (proj / "fp-lib-table").write_text("(fp_lib_table\n)")

    cfg = load_config(proj / "jlcpcb-mapper.yaml")

    fake_llm = MagicMock()
    fake_llm.smoke_check.return_value = True
    def llm_call(prompt, schema_keys):
        if "lcsc" in schema_keys and "reason" in schema_keys:
            return MagicMock(data={"lcsc": "C17168", "reason": "test"})
        # 2nd-pass review
        return MagicMock(data={"flagged": [], "overall_ok": True})
    fake_llm.call.side_effect = llm_call

    with patch("jlcpcb_mapper.commands.map_cmd.ClaudeClient", return_value=fake_llm), \
         patch("jlcpcb_mapper.commands.map_cmd.run_preflight"), \
         patch("jlcpcb_mapper.io.easyeda.download_footprint", return_value=None):
        report = run_map(
            project_pro=proj / "uart.kicad_pro",
            config=cfg,
            non_interactive=True,
            force=True,
            allow_stale_db=True,
            fill_lcsc_only=False,
            include_dnp=False,
            apply_suggestions=False,
        )

    # At least one group mapped to C17168
    assert any(g.lcsc == "C17168" for g in report.groups)
    # Schematic was modified in-place
    text = (proj / "uart.kicad_sch").read_text()
    assert "C17168" in text
    # Built-in KiCad footprint applied (resistor 0402)
    assert "Resistor_SMD:R_0402_1005Metric" in text
    # Backup exists
    backups = list((proj / ".jlcpcb-mapper" / "backups").glob("*/uart.kicad_sch"))
    assert len(backups) >= 1
    # Run log written
    logs = list((proj / ".jlcpcb-mapper").glob("run-*.json"))
    assert len(logs) >= 1


def test_fill_lcsc_only_preserves_existing_footprint(tmp_path):
    """In --fill-lcsc-only mode, existing footprints must NOT be overwritten."""
    proj = tmp_path / "proj"
    proj.mkdir()
    # Start from uart fixture but pre-set an unusual footprint on R31
    import re
    src_text = (FIX / "uart.kicad_sch").read_text()
    # Find R31 block, set a custom Footprint
    new_text = re.sub(
        r'(\(property "Footprint" )""(\s+\(at 106.68 129.54 0\))',
        r'\1"Custom:Very_Specific_Footprint"\2',
        src_text, count=1,
    )
    assert "Custom:Very_Specific_Footprint" in new_text
    (proj / "uart.kicad_sch").write_text(new_text)
    (proj / "uart.kicad_pro").write_text("{}")
    (proj / "jlcpcb-mapper.yaml").write_text(f"parts_db: {proj}/parts.db\n")
    build(proj / "parts.db")
    (proj / "fp-lib-table").write_text("(fp_lib_table\n)")

    cfg = load_config(proj / "jlcpcb-mapper.yaml")

    fake_llm = MagicMock()
    fake_llm.smoke_check.return_value = True
    def llm_call(prompt, schema_keys):
        if "lcsc" in schema_keys and "reason" in schema_keys:
            return MagicMock(data={"lcsc": "C17168", "reason": "test"})
        return MagicMock(data={"flagged": [], "overall_ok": True})
    fake_llm.call.side_effect = llm_call

    with patch("jlcpcb_mapper.commands.map_cmd.ClaudeClient", return_value=fake_llm), \
         patch("jlcpcb_mapper.commands.map_cmd.run_preflight"), \
         patch("jlcpcb_mapper.io.easyeda.download_footprint", return_value=None):
        run_map(
            project_pro=proj / "uart.kicad_pro",
            config=cfg,
            non_interactive=True,
            force=True,
            allow_stale_db=True,
            fill_lcsc_only=True,   # key flag
            include_dnp=False,
            apply_suggestions=False,
        )
    final = (proj / "uart.kicad_sch").read_text()
    # Existing custom footprint must survive
    assert "Custom:Very_Specific_Footprint" in final, "existing footprint was clobbered"
    # LCSC got added
    assert "C17168" in final
