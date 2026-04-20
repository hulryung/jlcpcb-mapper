from jlcpcb_mapper.config import load_config

def test_load_config_applies_defaults(tmp_path):
    (tmp_path / "jlcpcb-mapper.yaml").write_text("")  # empty
    cfg = load_config(tmp_path / "jlcpcb-mapper.yaml")
    assert cfg.selection.min_stock == 1000
    assert cfg.selection.defaults["resistor"]["package"] == "0402"
    assert cfg.llm.model == "claude-haiku-4-5"
    assert cfg.llm.concurrency == 4

def test_load_config_user_overrides(tmp_path):
    (tmp_path / "cfg.yaml").write_text(
        "llm:\n  model: claude-sonnet-4-6\n"
        "selection:\n  min_stock: 500\n"
    )
    cfg = load_config(tmp_path / "cfg.yaml")
    assert cfg.llm.model == "claude-sonnet-4-6"
    assert cfg.selection.min_stock == 500
    assert cfg.selection.defaults["resistor"]["package"] == "0402"  # default preserved

def test_load_config_missing_file_uses_defaults(tmp_path):
    cfg = load_config(tmp_path / "nonexistent.yaml")
    assert cfg.selection.min_stock == 1000
    assert cfg._used_defaults_only is True
