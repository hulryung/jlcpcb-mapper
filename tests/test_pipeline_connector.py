"""Integration tests for the Connector category end-to-end through the pipeline.

Scenario A (1xN, LLM path, pre-existing footprint):
  lib_id: Connector_Generic:Conn_01x06_Odd_Even, value: "JST-PH-6"
  footprint: "Connector_PinSocket_2.54mm:PinSocket_1x06_P2.54mm_Vertical" (pre-existing)
  → parse → ConnectorSpec("1xN", 6, "JST-PH-6")
  → package extraction: "PinSocket_1x06"
  → ConnectorSource 1xN query → broad %Connector% + %JST-PH-6% description
  → DB has C1 (basic) and C2 (non-basic), both matching
  → scorer=None → LLM path
  → FakeLLM returns C1
  → all_have_fp=True → footprint="", downloaded=False

Scenario B (2xN, no package hint → no_candidates):
  lib_id: Connector_Generic:Conn_02x05_Odd_Even, value: "2x5-IDC"
  footprint: "" (empty → no package extraction)
  → parse → ConnectorSpec("2xN", 5, "2x5-IDC")
  → default_package="" → package_hint=""
  → ConnectorSource 2xN no hint → tight query; post_filter returns []
  → Decision.failure="no_candidates"

Scenario C (generic → skip):
  lib_id: Connector_USB:USB_C_Receptacle_Palconn_UTC16-G, value: "USBC-XYZ"
  footprint: "" (empty)
  → parse → ConnectorSpec("generic", 0, "USBC-XYZ")
  → tight query + post_filter returns []
  → Decision.failure="no_candidates"
"""
import sqlite3
from pathlib import Path
import pytest
from jlcpcb_mapper.core.pipeline import run_pipeline, Instance
from jlcpcb_mapper.io.parts_db import PartsDB


class _FakeLLM:
    def __init__(self, lcsc_to_return: str = "C1"):
        self.calls = 0
        self._lcsc = lcsc_to_return

    def call(self, prompt, schema_keys):
        self.calls += 1

        class _Resp:
            pass

        r = _Resp()
        r.data = {"lcsc": self._lcsc, "reason": "basic preferred"}
        return r


def _populate(conn):
    conn.executescript("""
        CREATE TABLE parts (
            lcsc TEXT PRIMARY KEY, category TEXT, mfr TEXT, mfr_part TEXT,
            package TEXT, description TEXT, basic INTEGER, preferred INTEGER,
            stock INTEGER, price REAL
        );
        -- C1: basic, JST-PH-6 in description, PinSocket_1x06 package
        INSERT INTO parts VALUES (
            'C1', 'Connectors', 'JST', 'B6B-PH-K-S',
            'PinSocket_1x06', 'JST-PH-6 6pin 2mm connector', 1, 0, 10000, 0.15
        );
        -- C2: non-basic, JST-PH-6 in description, PinSocket_1x06 package
        INSERT INTO parts VALUES (
            'C2', 'Connectors', 'JST', 'B6B-PH-SM4-TB',
            'PinSocket_1x06', 'JST-PH-6 6pin 2mm SMD', 0, 0, 30000, 0.12
        );
        -- C3: different package — should still pass 1xN post_filter (pass-through)
        INSERT INTO parts VALUES (
            'C3', 'Connectors', 'JST', 'B6B-ZR-SM4-TF',
            'ZH_1x06', 'JST ZH 6pin 1.5mm connector', 0, 0, 5000, 0.10
        );
    """)


@pytest.fixture
def db(tmp_path: Path) -> PartsDB:
    p = tmp_path / "parts.db"
    conn = sqlite3.connect(str(p))
    _populate(conn)
    conn.commit()
    conn.close()
    return PartsDB(p)


@pytest.fixture(autouse=True)
def _stub_easyeda(monkeypatch, tmp_path):
    def _fake_download(lcsc, out_dir):
        path = Path(out_dir) / f"{lcsc}_fake.kicad_mod"
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        path.write_text("(module fake)")
        return path

    import jlcpcb_mapper.io.easyeda as dl
    monkeypatch.setattr(dl, "download_footprint", _fake_download)


# --- Scenario A: 1xN with pre-existing footprint, LLM picks C1 ---

def test_1xn_llm_selects_c1(db, tmp_path):
    """1xN JST-PH-6 with pre-existing footprint → LLM picks C1 (basic)."""
    llm = _FakeLLM(lcsc_to_return="C1")
    instances = [
        Instance(
            sch_path=tmp_path / "x.kicad_sch",
            reference="J1",
            lib_id="Connector_Generic:Conn_01x06_Odd_Even",
            value="JST-PH-6",
            footprint="Connector_PinSocket_2.54mm:PinSocket_1x06_P2.54mm_Vertical",
            dnp=False, on_board=True, in_bom=True,
        ),
    ]
    decisions = run_pipeline(
        instances=instances,
        db=db,
        llm=llm,
        hints="",
        score_tiebreak_threshold=0.01,
        llm_tiebreak_top_n=5,
        min_stock=0,
        fp_out_dir=tmp_path / "fp",
    )

    assert len(decisions) == 1
    d = decisions[0]
    assert d.chosen_lcsc == "C1", f"Expected C1, got {d.chosen_lcsc}"
    assert d.source == "llm"
    assert d.failure is None
    # Pre-existing footprint → resolver skipped
    assert d.footprint == ""
    assert d.downloaded is False
    # scorer=None → LLM must have been called
    assert llm.calls == 1


def test_1xn_category_is_connector(db, tmp_path):
    """lib_id Connector_Generic:Conn_01x06_Odd_Even must route to connector category."""
    llm = _FakeLLM()
    instances = [
        Instance(
            sch_path=tmp_path / "x.kicad_sch",
            reference="J1",
            lib_id="Connector_Generic:Conn_01x06_Odd_Even",
            value="JST-PH-6",
            footprint="Connector_PinSocket_2.54mm:PinSocket_1x06_P2.54mm_Vertical",
            dnp=False, on_board=True, in_bom=True,
        ),
    ]
    decisions = run_pipeline(
        instances=instances,
        db=db,
        llm=llm,
        hints="",
        score_tiebreak_threshold=0.01,
        llm_tiebreak_top_n=5,
        min_stock=0,
        fp_out_dir=tmp_path / "fp",
    )
    assert len(decisions) == 1
    assert decisions[0].group.category.name == "connector"


# --- Scenario B: 2xN without package hint → no_candidates ---

def test_2xn_without_package_hint_fails_no_candidates(db, tmp_path):
    """2xN with empty footprint → no package hint → ConnectorSource bails → no_candidates."""
    instances = [
        Instance(
            sch_path=tmp_path / "x.kicad_sch",
            reference="J2",
            lib_id="Connector_Generic:Conn_02x05_Odd_Even",
            value="2x5-IDC",   # non-empty value so pipeline doesn't drop the instance
            footprint="",       # no footprint → package_hint=""
            dnp=False, on_board=True, in_bom=True,
        ),
    ]
    decisions = run_pipeline(
        instances=instances,
        db=db,
        llm=_FakeLLM(),
        hints="",
        score_tiebreak_threshold=0.01,
        llm_tiebreak_top_n=5,
        min_stock=0,
        fp_out_dir=tmp_path / "fp",
    )

    assert len(decisions) == 1
    d = decisions[0]
    assert d.chosen_lcsc is None
    assert d.source == "failed"
    assert d.failure == "no_candidates"


# --- Scenario C: generic connector → skip ---

def test_generic_connector_fails_no_candidates(db, tmp_path):
    """Generic (non-Conn_01x/02x) connector → post_filter returns [] → no_candidates."""
    instances = [
        Instance(
            sch_path=tmp_path / "x.kicad_sch",
            reference="J3",
            lib_id="Connector_USB:USB_C_Receptacle_Palconn_UTC16-G",
            value="USBC-XYZ",
            footprint="",
            dnp=False, on_board=True, in_bom=True,
        ),
    ]
    decisions = run_pipeline(
        instances=instances,
        db=db,
        llm=_FakeLLM(),
        hints="",
        score_tiebreak_threshold=0.01,
        llm_tiebreak_top_n=5,
        min_stock=0,
        fp_out_dir=tmp_path / "fp",
    )

    assert len(decisions) == 1
    d = decisions[0]
    assert d.chosen_lcsc is None
    assert d.source == "failed"
