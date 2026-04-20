"""End-to-end: invoke the CLI `map` command against a copy of the real
KiCad project fixture, with LLM and download mocked. Verifies that
Footprint + LCSC get written into the real uart.kicad_sch."""
from pathlib import Path
import shutil
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from jlcpcb_mapper.cli import main
from tests.fixtures.make_test_db import build

FIX = Path(__file__).parent / "fixtures"

def test_e2e_on_uart_fixture(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    shutil.copy(FIX / "uart.kicad_sch", proj / "uart.kicad_sch")
    (proj / "uart.kicad_pro").write_text("{}")
    (proj / "fp-lib-table").write_text("(fp_lib_table\n)")
    build(proj / "parts.db")
    (proj / "jlcpcb-mapper.yaml").write_text(f"parts_db: {proj}/parts.db\n")

    fake_llm = MagicMock()
    fake_llm.smoke_check.return_value = True
    def llm_call(prompt, schema_keys):
        if "lcsc" in schema_keys and "reason" in schema_keys:
            return MagicMock(data={"lcsc": "C17168", "reason": "test"})
        return MagicMock(data={"flagged": [], "overall_ok": True})
    fake_llm.call.side_effect = llm_call

    with patch("jlcpcb_mapper.commands.map_cmd.ClaudeClient", return_value=fake_llm), \
         patch("jlcpcb_mapper.commands.map_cmd.run_preflight"), \
         patch("jlcpcb_mapper.resolver.download_footprint", return_value=None):
        result = CliRunner().invoke(main, [
            "map", str(proj / "uart.kicad_pro"),
            "--non-interactive", "--force", "--allow-stale-db",
        ])

    assert result.exit_code == 0, f"CLI failed: {result.output}\n{result.exception}"
    text = (proj / "uart.kicad_sch").read_text()
    assert "C17168" in text
    assert "R_0402_1005Metric" in text
