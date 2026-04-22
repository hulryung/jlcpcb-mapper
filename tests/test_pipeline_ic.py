"""Integration tests for the IC category end-to-end through the pipeline.

Scenario A (pre-existing footprint, LLM path):
  lib_id: MCU_ST_STM32F0:STM32F031K6Tx
  value: "STM32F031K6T6"
  footprint: "Package_QFP:LQFP-32_7x7mm_P0.8mm"
  → package extraction: LQFP-32
  → ICSource uses mpn_patterns=("%STM32F031K6T6%",)
  → DB has C1 (basic, exact MPN, LQFP-32) and C2 (variant MPN, LQFP-32)
  → post_filter keeps both (both have LQFP-32 in package)
  → scorer=None → LLM path
  → FakeLLM returns C1
  → all_have_fp=True → footprint="", downloaded=False

Scenario B (no footprint → no_candidates failure):
  Same lib_id+value but footprint=""
  → default_package="" → package_hint=""
  → ICSource.post_filter returns []
  → Decision.failure="no_candidates"

Package extraction test:
  "Package_QFP:LQFP-32_7x7mm_P0.8mm" → "LQFP-32"
"""
import sqlite3
from pathlib import Path
import pytest
from jlcpcb_mapper.core.pipeline import run_pipeline, Instance
from jlcpcb_mapper.parts_db import PartsDB


class _FakeLLM:
    """Returns a predetermined LCSC selection without calling the real LLM."""

    def __init__(self, lcsc_to_return: str = "C1"):
        self.calls = 0
        self._lcsc = lcsc_to_return

    def call(self, prompt, schema_keys):
        self.calls += 1

        class _Resp:
            pass

        r = _Resp()
        r.data = {"lcsc": self._lcsc, "reason": "exact MPN match, basic part"}
        return r


def _populate(conn):
    conn.executescript("""
        CREATE TABLE parts (
            lcsc TEXT PRIMARY KEY, category TEXT, mfr TEXT, mfr_part TEXT,
            package TEXT, description TEXT, basic INTEGER, preferred INTEGER,
            stock INTEGER, price REAL
        );
        -- C1: basic, exact MPN match, LQFP-32
        INSERT INTO parts VALUES (
            'C1', 'Microcontroller Unit', 'STMicroelectronics', 'STM32F031K6T6',
            'LQFP-32', 'ARM Cortex-M0 32KB Flash 4KB RAM', 1, 0, 10000, 1.20
        );
        -- C2: non-basic variant (reel), LQFP-32
        INSERT INTO parts VALUES (
            'C2', 'Microcontroller Unit', 'STMicroelectronics', 'STM32F031K6T6TR',
            'LQFP-32', 'ARM Cortex-M0 32KB Flash 4KB RAM Reel', 0, 0, 20000, 1.10
        );
        -- C3: different package (LQFP-48) — excluded by post_filter
        INSERT INTO parts VALUES (
            'C3', 'Microcontroller Unit', 'STMicroelectronics', 'STM32F031K6U6',
            'LQFP-48', 'ARM Cortex-M0 32KB Flash 4KB RAM UFQFPN48', 1, 0, 5000, 1.30
        );
        -- C4: completely different MPN — should not be matched by mpn_patterns
        INSERT INTO parts VALUES (
            'C4', 'Microcontroller Unit', 'Microchip', 'PIC16F877A',
            'LQFP-32', 'PIC 8-bit MCU', 0, 0, 8000, 0.90
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

    import jlcpcb_mapper.downloader as dl
    monkeypatch.setattr(dl, "download_footprint", _fake_download)


def test_stm32_lqfp32_llm_selects_c1(db, tmp_path):
    """STM32F031K6T6 with LQFP-32 footprint → LLM picks C1 (basic, exact MPN)."""
    llm = _FakeLLM(lcsc_to_return="C1")
    instances = [
        Instance(
            sch_path=tmp_path / "x.kicad_sch",
            reference="U1",
            lib_id="MCU_ST_STM32F0:STM32F031K6Tx",
            value="STM32F031K6T6",
            footprint="Package_QFP:LQFP-32_7x7mm_P0.8mm",
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
    assert d.chosen_lcsc == "C1", f"Expected C1 (basic, exact MPN), got {d.chosen_lcsc}"
    assert d.source == "llm"
    assert d.failure is None
    # Pre-existing footprint → resolver skipped
    assert d.footprint == ""
    assert d.downloaded is False
    # LLM must have been called (scorer=None)
    assert llm.calls == 1


def test_ic_no_footprint_returns_failed(db, tmp_path):
    """IC with empty footprint → default_package='' → post_filter returns [] → failed."""
    instances = [
        Instance(
            sch_path=tmp_path / "x.kicad_sch",
            reference="U2",
            lib_id="MCU_ST_STM32F0:STM32F031K6Tx",
            value="STM32F031K6T6",
            footprint="",  # no footprint → package_hint="" → post_filter returns []
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
    assert d.source == "failed"
    assert d.failure == "no_candidates"
    assert d.chosen_lcsc is None


def test_ic_package_extraction_lqfp32():
    """Package_QFP:LQFP-32_7x7mm_P0.8mm → 'LQFP-32'."""
    from jlcpcb_mapper.categories.ic import _PACKAGE_RULES
    from jlcpcb_mapper.components.package_extractors import RegexFromRules

    extractor = RegexFromRules(_PACKAGE_RULES)
    result = extractor.extract("Package_QFP:LQFP-32_7x7mm_P0.8mm")
    assert result == "LQFP-32"


def test_ic_package_extraction_sot23():
    """Package_TO_SOT_SMD:SOT-23 → 'SOT-23'."""
    from jlcpcb_mapper.categories.ic import _PACKAGE_RULES
    from jlcpcb_mapper.components.package_extractors import RegexFromRules

    extractor = RegexFromRules(_PACKAGE_RULES)
    assert extractor.extract("Package_TO_SOT_SMD:SOT-23") == "SOT-23"


def test_ic_package_extraction_soic8():
    """Package_SO:SOIC-8_3.9x4.9mm_P1.27mm → 'SOIC-8'."""
    from jlcpcb_mapper.categories.ic import _PACKAGE_RULES
    from jlcpcb_mapper.components.package_extractors import RegexFromRules

    extractor = RegexFromRules(_PACKAGE_RULES)
    assert extractor.extract("Package_SO:SOIC-8_3.9x4.9mm_P1.27mm") == "SOIC-8"


def test_ic_package_extraction_tssop():
    """Package_SO:TSSOP-20_4.4x6.5mm_P0.65mm → 'TSSOP-20'."""
    from jlcpcb_mapper.categories.ic import _PACKAGE_RULES
    from jlcpcb_mapper.components.package_extractors import RegexFromRules

    extractor = RegexFromRules(_PACKAGE_RULES)
    assert extractor.extract("Package_SO:TSSOP-20_4.4x6.5mm_P0.65mm") == "TSSOP-20"


def test_ic_package_extraction_qfn():
    """Package_QFN:QFN-32-1EP_5x5mm_P0.5mm → 'QFN-32'."""
    from jlcpcb_mapper.categories.ic import _PACKAGE_RULES
    from jlcpcb_mapper.components.package_extractors import RegexFromRules

    extractor = RegexFromRules(_PACKAGE_RULES)
    assert extractor.extract("Package_QFN:QFN-32-1EP_5x5mm_P0.5mm") == "QFN-32"


def test_ic_package_extraction_unknown_returns_none():
    """Unknown footprint returns None."""
    from jlcpcb_mapper.categories.ic import _PACKAGE_RULES
    from jlcpcb_mapper.components.package_extractors import RegexFromRules

    extractor = RegexFromRules(_PACKAGE_RULES)
    assert extractor.extract("SomeUnknown:CUSTOM-PKG") is None
