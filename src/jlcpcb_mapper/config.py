from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import yaml
import importlib.resources as resources

def _deep_merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out

@dataclass
class LLMSettings:
    model: str
    concurrency: int
    timeout_seconds: int
    retry_on_parse_fail: int

@dataclass
class SelectionSettings:
    prefer_order: list
    min_stock: int
    defaults: dict

@dataclass
class VerifySettings:
    min_stock_warning: int
    price_change_pct_warning: int

@dataclass
class DownloadSettings:
    output_dir: str
    download_3d_models: bool
    auto_register_fp_lib_table: bool

@dataclass
class ManualLCSC:
    by_reference: dict
    by_value: dict


@dataclass
class Config:
    parts_db: str | None
    llm: LLMSettings
    selection: SelectionSettings
    verify: VerifySettings
    download: DownloadSettings
    kicad_footprint_map_overrides: dict
    hints: str
    manual_lcsc: ManualLCSC
    score_tiebreak_threshold: float = 0.1
    llm_tiebreak_top_n: int = 5
    _used_defaults_only: bool = False

def _load_default_dict() -> dict:
    text = resources.files("jlcpcb_mapper").joinpath("default_config.yaml").read_text()
    return yaml.safe_load(text) or {}

def load_config(path: str | Path) -> Config:
    defaults = _load_default_dict()
    user: dict[str, Any] = {}
    path = Path(path)
    used_defaults = False
    if path.exists():
        user = yaml.safe_load(path.read_text()) or {}
    else:
        used_defaults = True
    merged = _deep_merge(defaults, user)
    manual_raw = merged.get("manual_lcsc") or {}
    return Config(
        parts_db=merged.get("parts_db"),
        llm=LLMSettings(**merged["llm"]),
        selection=SelectionSettings(**merged["selection"]),
        verify=VerifySettings(**merged["verify"]),
        download=DownloadSettings(**merged["download"]),
        kicad_footprint_map_overrides=merged["kicad_footprint_map_overrides"],
        hints=merged["hints"],
        manual_lcsc=ManualLCSC(
            by_reference=dict(manual_raw.get("by_reference") or {}),
            by_value=dict(manual_raw.get("by_value") or {}),
        ),
        score_tiebreak_threshold=merged.get("score_tiebreak_threshold", 0.1),
        llm_tiebreak_top_n=merged.get("llm_tiebreak_top_n", 5),
        _used_defaults_only=used_defaults,
    )
