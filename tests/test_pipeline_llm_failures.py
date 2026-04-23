"""Regression tests: LLM failure modes produce explicit trace methods.

Covers three paths in _decide:
- llm_reject (LLM returns null)
- llm_hallucination (LLM returns LCSC not in candidates)
- llm_error_fallback (LLM raises)

All three fall back to rows[0] and Decision.source="llm".
The distinguishing signal is the trace event's method field.
"""
from __future__ import annotations
import sqlite3
from pathlib import Path
import pytest

from jlcpcb_mapper.core.pipeline import run_pipeline, Instance
from jlcpcb_mapper.parts_db import PartsDB


class _RaisingLLM:
    def call(self, prompt, schema_keys):
        raise RuntimeError("boom")


class _NullLLM:
    class _Resp:
        data = {"lcsc": None, "reason": "no good match"}
    def call(self, prompt, schema_keys):
        return self._Resp()


class _HallucLLM:
    class _Resp:
        data = {"lcsc": "C_NOT_IN_ROWS", "reason": "made it up"}
    def call(self, prompt, schema_keys):
        return self._Resp()


def _populate(conn):
    # Two candidates with SCORES THAT ARE EQUAL — forces LLM tiebreak path.
    # Both basic=0, both stock=10k → same _stock_bucket(0.7) → same W_STOCK (0.28).
    # With scorer=None (IC category), LLM is the decider unconditionally.
    # We use IC to bypass scorer entirely.
    conn.executescript("""
        CREATE TABLE parts (
            lcsc TEXT PRIMARY KEY, category TEXT, mfr TEXT, mfr_part TEXT,
            package TEXT, description TEXT, basic INTEGER, preferred INTEGER,
            stock INTEGER, price REAL
        );
        INSERT INTO parts VALUES ('C1','MCU','STM','STM32F031K6T6',
            'LQFP-32','STM32F031K6T6 ARM Cortex-M0',1,0,20000,0.50);
        INSERT INTO parts VALUES ('C2','MCU','STM','STM32F031K6T6TR',
            'LQFP-32','STM32F031K6T6TR tape-reel variant',0,0,10000,0.48);
    """)


@pytest.fixture
def db(tmp_path: Path) -> PartsDB:
    p = tmp_path / "parts.db"
    conn = sqlite3.connect(str(p))
    _populate(conn); conn.commit(); conn.close()
    return PartsDB(p)


@pytest.fixture(autouse=True)
def _stub_easyeda(monkeypatch, tmp_path):
    def _fake_download(lcsc, out_dir):
        path = Path(out_dir) / f"{lcsc}_fake.kicad_mod"
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        path.write_text("(module fake)")
        return path
    import jlcpcb_mapper.downloader as dl
    monkeypatch.setattr(dl, "download_footprint", _fake_download)


def _run_ic(db, tmp_path, llm):
    """Run the pipeline with a single IC instance that matches both C1 and C2,
    so _decide must go through the LLM path (scorer=None for IC)."""
    inst = Instance(
        sch_path=tmp_path / "x.kicad_sch",
        reference="U1",
        lib_id="MCU_ST_STM32F0:STM32F031K6Tx",
        value="STM32F031K6T6",
        footprint="Package_QFP:LQFP-32_7x7mm_P0.8mm",  # pre-existing, skips resolver
        dnp=False, on_board=True, in_bom=True,
    )
    return run_pipeline(
        instances=[inst], db=db, llm=llm, hints="",
        score_tiebreak_threshold=0.01, llm_tiebreak_top_n=5,
        min_stock=1000, fp_out_dir=tmp_path / "fp",
    )


def _get_decide_event(decision):
    """Return the last 'decide' trace event, or raise if missing."""
    for e in reversed(decision.group.trace.events):
        if e.stage == "decide":
            return e
    raise AssertionError("no 'decide' trace event found")


def test_llm_raising_falls_back_with_explicit_method(db, tmp_path):
    """When LLM raises, decision falls back to rows[0] and trace records
    decide.method=llm_error_fallback."""
    decisions = _run_ic(db, tmp_path, _RaisingLLM())
    assert len(decisions) == 1
    d = decisions[0]
    assert d.chosen_lcsc == "C1"   # first row
    assert d.source == "llm"
    event = _get_decide_event(d)
    assert event.data.get("method") == "llm_error_fallback"
    assert "boom" in event.data.get("error", "")


def test_llm_null_falls_back_with_explicit_method(db, tmp_path):
    """When LLM returns null, decision falls back to rows[0] and trace
    records decide.method=llm_reject."""
    decisions = _run_ic(db, tmp_path, _NullLLM())
    d = decisions[0]
    assert d.chosen_lcsc == "C1"
    assert d.source == "llm"
    event = _get_decide_event(d)
    assert event.data.get("method") == "llm_reject"
    assert event.data.get("fallback_lcsc") == "C1"


def test_llm_hallucination_falls_back_with_explicit_method(db, tmp_path):
    """When LLM returns an LCSC not in candidates, decision falls back to
    rows[0] and trace records decide.method=llm_hallucination."""
    decisions = _run_ic(db, tmp_path, _HallucLLM())
    d = decisions[0]
    assert d.chosen_lcsc == "C1"
    assert d.source == "llm"
    event = _get_decide_event(d)
    assert event.data.get("method") == "llm_hallucination"
    assert event.data.get("returned") == "C_NOT_IN_ROWS"


def test_llm_valid_response_is_recorded_with_method_llm(db, tmp_path):
    """Sanity check: happy-path LLM call records decide.method=llm."""
    class _GoodLLM:
        class _Resp:
            data = {"lcsc": "C2", "reason": "tape-reel preferred"}
        def call(self, prompt, schema_keys):
            return self._Resp()

    decisions = _run_ic(db, tmp_path, _GoodLLM())
    d = decisions[0]
    assert d.chosen_lcsc == "C2"
    event = _get_decide_event(d)
    assert event.data.get("method") == "llm"
    assert event.data.get("reason") == "tape-reel preferred"
