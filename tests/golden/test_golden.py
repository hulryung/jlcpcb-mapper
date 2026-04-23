"""Golden-file pipeline regression tests.

Each case is a YAML file describing:
- db_schema: SQL to populate an in-memory parts.db
- instances: list of dicts matching Instance fields
- llm_responses: optional dict of {prompt_substring: response_data} for deterministic LLM
- hints: optional user hints string
- tau: optional score_tiebreak_threshold override (default 0.05)
- min_stock: optional (default 1000)
"""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path
import yaml

from jlcpcb_mapper.core.pipeline import run_pipeline, Instance
from jlcpcb_mapper.io.parts_db import PartsDB
from jlcpcb_mapper.observability.writer import write_group_traces

from .conftest import EXPECTED_DIR, normalize_jsonl


class _DeterministicLLM:
    """Matches prompt substrings in a dict to canned responses."""
    def __init__(self, mapping: dict):
        self.mapping = mapping

    def call(self, prompt, schema_keys):
        class _Resp:
            pass
        r = _Resp()
        for key, val in self.mapping.items():
            if key in prompt:
                r.data = val
                return r
        r.data = {"lcsc": None, "reason": "no rule matched"}
        return r


def _stub_easyeda(monkeypatch, tmp_path):
    def _fake_dl(lcsc, d):
        Path(d).mkdir(parents=True, exist_ok=True)
        out = Path(d) / f"{lcsc}_fake.kicad_mod"
        out.write_text("(module fake)")
        return out
    import jlcpcb_mapper.io.easyeda as ez
    monkeypatch.setattr(ez, "download_footprint", _fake_dl)


def test_golden(golden_case, tmp_path, request, monkeypatch):
    _stub_easyeda(monkeypatch, tmp_path)

    case = yaml.safe_load(Path(golden_case).read_text())

    # Build in-memory DB
    dbp = tmp_path / "p.db"
    conn = sqlite3.connect(str(dbp))
    conn.executescript(case["db_schema"])
    conn.commit(); conn.close()

    # Build Instances
    instances = [
        Instance(sch_path=tmp_path / "x.kicad_sch", **inst)
        for inst in case["instances"]
    ]
    llm = _DeterministicLLM(case.get("llm_responses", {}))

    decisions = run_pipeline(
        instances=instances,
        db=PartsDB(dbp),
        llm=llm,
        hints=case.get("hints", ""),
        score_tiebreak_threshold=case.get("tau", 0.05),
        llm_tiebreak_top_n=case.get("top_n", 5),
        min_stock=case.get("min_stock", 1000),
        fp_out_dir=tmp_path / "fp",
    )
    out_dir = tmp_path / "out"
    write_group_traces(decisions, out_dir)
    produced = normalize_jsonl((out_dir / "groups.jsonl").read_text())

    expected_path = EXPECTED_DIR / (Path(golden_case).stem + ".jsonl")
    if request.config.getoption("--update-golden"):
        EXPECTED_DIR.mkdir(parents=True, exist_ok=True)
        expected_path.write_text(produced + "\n" if produced else "")
        return

    if not expected_path.exists():
        raise AssertionError(
            f"Golden file missing: {expected_path}\n"
            f"Run: pytest tests/golden/ --update-golden"
        )

    expected = expected_path.read_text().rstrip()
    assert produced == expected, (
        f"Golden file mismatch for {Path(golden_case).stem}:\n"
        f"--- expected ---\n{expected}\n"
        f"--- got ---\n{produced}"
    )
