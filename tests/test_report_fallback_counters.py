import json
from pathlib import Path
from jlcpcb_mapper.report import RunReport


def test_run_report_tracks_source_counts():
    r = RunReport()
    r.record_source("score")
    r.record_source("score")
    r.record_source("llm")
    r.record_source("llm_error_fallback")
    # Internal accounting visible via to_dict
    d = r.to_dict()
    assert d["sources"] == {"score": 2, "llm": 1, "llm_error_fallback": 1}


def test_to_text_surfaces_sources():
    r = RunReport()
    r.record_source("score")
    r.record_source("llm_error_fallback")
    r.record_source("llm_error_fallback")
    txt = r.to_text()
    assert "Sources:" in txt
    assert "llm_error_fallback: 2" in txt
    assert "score: 1" in txt


def test_to_text_no_sources_line_when_empty():
    r = RunReport()
    txt = r.to_text()
    assert "Sources:" not in txt


def test_write_json_includes_sources(tmp_path: Path):
    r = RunReport()
    r.record_source("single")
    r.record_source("llm_hallucination")
    p = tmp_path / "run.json"
    r.write_json(p)
    loaded = json.loads(p.read_text())
    assert loaded["sources"] == {"single": 1, "llm_hallucination": 1}


def test_record_source_multiple_calls_same_key():
    r = RunReport()
    for _ in range(5):
        r.record_source("score")
    assert r.to_dict()["sources"] == {"score": 5}
