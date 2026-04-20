from click.testing import CliRunner
from jlcpcb_mapper.cli import main


def test_cli_help_lists_subcommands():
    result = CliRunner().invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "map" in result.output
    assert "verify" in result.output
    assert "init" in result.output


def test_map_requires_project_arg():
    result = CliRunner().invoke(main, ["map"])
    assert result.exit_code != 0
    assert "Missing argument" in result.output or "PROJECT" in result.output
