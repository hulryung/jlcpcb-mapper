from pathlib import Path
import textwrap
from jlcpcb_mapper.config import load_config


def test_defaults_have_threshold_fields(tmp_path: Path):
    """Config defaults include both new threshold fields."""
    cfg = load_config(tmp_path / "does_not_exist.yaml")
    assert cfg.score_tiebreak_threshold == 0.1
    assert cfg.llm_tiebreak_top_n == 5


def test_user_yaml_overrides_threshold_fields(tmp_path: Path):
    user = tmp_path / "jlcpcb-mapper.yaml"
    user.write_text(textwrap.dedent("""\
        score_tiebreak_threshold: 0.25
        llm_tiebreak_top_n: 10
    """))
    cfg = load_config(user)
    assert cfg.score_tiebreak_threshold == 0.25
    assert cfg.llm_tiebreak_top_n == 10


def test_partial_override_keeps_default_for_other(tmp_path: Path):
    user = tmp_path / "jlcpcb-mapper.yaml"
    user.write_text("score_tiebreak_threshold: 0.3\n")
    cfg = load_config(user)
    assert cfg.score_tiebreak_threshold == 0.3
    assert cfg.llm_tiebreak_top_n == 5   # still default
