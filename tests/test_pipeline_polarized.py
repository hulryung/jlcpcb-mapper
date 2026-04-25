import sqlite3
from pathlib import Path
import pytest
from jlcpcb_mapper.core.pipeline import run_pipeline, Instance
from jlcpcb_mapper.io.parts_db import PartsDB


class _FakeLLM:
    def __init__(self):
        self.calls = 0
    def call(self, prompt, schema_keys):
        self.calls += 1
        raise AssertionError("scorer should have decided without LLM")


def _populate(conn):
    conn.executescript("""
        CREATE TABLE parts (
            lcsc TEXT PRIMARY KEY, category TEXT, mfr TEXT, mfr_part TEXT,
            package TEXT, description TEXT, basic INTEGER, preferred INTEGER,
            stock INTEGER, price REAL
        );
        -- Expected winner: basic, 10V exact, high stock
        INSERT INTO parts VALUES ('C16133','Aluminum Electrolytic','Nichicon','UWT1A221MCL1GS',
            'D6.3','220uF 10V ±20% 6.3x5.4mm',1,0,25000,0.05);
        -- Loser: non-basic, 10V, lower stock
        INSERT INTO parts VALUES ('C471773','Aluminum Electrolytic','Other','ELEB',
            'D6.3','220uF 10V 20%',0,0,15000,0.04);
        -- Wrong package
        INSERT INTO parts VALUES ('C9999','Aluminum Electrolytic','X','EL9',
            'D8','220uF 10V',1,0,30000,0.06);
        -- Under-rated (6.3V) — should be filtered
        INSERT INTO parts VALUES ('C8888','Aluminum Electrolytic','X','EL8',
            'D6.3','220uF 6.3V',1,0,40000,0.05);
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
    import jlcpcb_mapper.io.easyeda as dl
    monkeypatch.setattr(dl, "download_footprint", _fake_download)


def test_220uf_10v_selects_basic_exact_voltage(db, tmp_path):
    instances = [
        Instance(sch_path=tmp_path / "x.kicad_sch",
                 reference="C12", lib_id="Device:CP",
                 value="220uF/10V", footprint="",
                 dnp=False, on_board=True, in_bom=True),
    ]
    decisions, _skipped = run_pipeline(
        instances=instances,
        db=db,
        llm=_FakeLLM(),
        hints="",
        score_tiebreak_threshold=0.01,  # force scorer decision for deterministic case
        llm_tiebreak_top_n=5,
        min_stock=1000,
        fp_out_dir=tmp_path / "fp",
    )
    assert len(decisions) == 1
    d = decisions[0]
    assert d.chosen_lcsc == "C16133"
    assert d.source == "score"
    assert d.footprint.startswith("LCSC:C16133")
    assert d.downloaded is True
