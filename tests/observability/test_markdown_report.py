"""Tests for the human-readable Markdown run report."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path

from jlcpcb_mapper.io.parts_db import PartRow
from jlcpcb_mapper.observability.markdown_report import write_markdown_report


# ---- minimal stand-ins for Group / Decision / Trace ----

@dataclass
class _StubTraceEvent:
    stage: str
    data: dict


@dataclass
class _StubTrace:
    events: list[_StubTraceEvent] = field(default_factory=list)


@dataclass
class _StubInstance:
    reference: str


@dataclass
class _StubSpec:
    label: str
    def display(self) -> str: return self.label


@dataclass
class _StubCategory:
    name: str


@dataclass
class _StubGroup:
    category: _StubCategory
    spec: _StubSpec
    package_hint: str
    instances: list[_StubInstance]
    trace: _StubTrace


@dataclass
class _StubDecision:
    group: _StubGroup
    chosen_lcsc: str | None
    candidates: list[PartRow]
    footprint: str
    downloaded: bool
    source: str


@dataclass
class _StubReport:
    schematics: list = field(default_factory=list)
    total_empty_instances: int = 0
    filtered_in: int = 0
    sources: dict = field(default_factory=dict)
    failures: list = field(default_factory=list)


def _row(lcsc: str, mfr: str, mfr_part: str, package: str, basic: int, preferred: int,
         stock: int, price: float, description: str = "") -> PartRow:
    return PartRow(
        lcsc=lcsc, category="Chip Resistor",
        mfr=mfr, mfr_part=mfr_part, package=package, description=description,
        basic=basic, preferred=preferred, stock=stock, price=price,
    )


def _decision_score_path() -> _StubDecision:
    chosen = _row("C25744", "UNI-ROYAL", "0402WGF1002TCE", "0402", 1, 1, 4_400_000, 0.0009,
                  "10kΩ 1% 1/16W 0402")
    runner = _row("C123456", "YAGEO", "RC0402FR-0710KL", "0402", 0, 0, 60_000, 0.0007,
                  "10kΩ 1% 1/16W 0402")
    trace = _StubTrace(events=[
        _StubTraceEvent("score_breakdown", {"lcsc": "C25744", "basic": 0.4, "preferred": 0.2, "stock": 0.4, "total": 1.0}),
        _StubTraceEvent("score_breakdown", {"lcsc": "C123456", "basic": 0.0, "preferred": 0.0, "stock": 0.28, "total": 0.28}),
        _StubTraceEvent("decide", {"method": "score", "lcsc": "C25744", "diff": 0.72}),
    ])
    g = _StubGroup(_StubCategory("resistor"), _StubSpec("10kΩ"), "0402",
                   [_StubInstance("R1"), _StubInstance("R2")], trace)
    return _StubDecision(g, "C25744", [chosen, runner], "Resistor_SMD:R_0402_1005Metric", False, "score")


def _decision_llm_path() -> _StubDecision:
    chosen = _row("C58277", "Honor Elec", "RVT1A331M0607", "SMD,D6.3xL7.7mm", 0, 0, 25_000, 0.035,
                  "330uF 10V SMD")
    runner = _row("C432338", "Lelon", "10ZLH330MEFC6.3X11", "插件,D6.3xL11mm", 0, 0, 5_000, 0.030,
                  "330uF 10V THT")
    trace = _StubTrace(events=[
        _StubTraceEvent("decide", {"method": "llm", "lcsc": "C58277", "reason": "Closest SMD form factor matching the existing footprint"}),
    ])
    g = _StubGroup(_StubCategory("polarized_capacitor"), _StubSpec("330µF/10V"), "D6.3",
                   [_StubInstance("C2")], trace)
    return _StubDecision(g, "C58277", [chosen, runner], "", False, "llm")


def _decision_single_path() -> _StubDecision:
    only = _row("C9400", "SXN", "SMDRI127-330MT", "SMD,12.3x12.3mm", 0, 0, 100_000, 0.21,
                "33uH 3A 65mΩ")
    g = _StubGroup(_StubCategory("inductor"), _StubSpec("33µH/3A"), "0805",
                   [_StubInstance("L2")], _StubTrace())
    return _StubDecision(g, "C9400", [only], "", False, "single")


def test_score_path_renders_chosen_url_and_rationale(tmp_path: Path):
    decision = _decision_score_path()
    out = tmp_path / "run.md"
    write_markdown_report(
        decisions=[decision], skipped=[], report=_StubReport(filtered_in=2),
        out_path=out, project_name="demo.kicad_pro",
    )
    text = out.read_text()
    assert "https://www.lcsc.com/product-detail/C25744.html" in text
    assert "**Selected**: [`C25744`]" in text
    # Tier shown
    assert "**Tier** Basic" in text
    # Rationale references the score delta and the basic-tier dimension
    assert "Score 1.00 vs runner-up 0.28" in text
    assert "Basic-tier" in text
    # Alternatives table includes the runner-up
    assert "C123456" in text
    # Refs summary includes both refs
    assert "R1, R2" in text
    # Tier legend present
    assert "Basic" in text and "Extended" in text


def test_llm_path_passes_through_reason(tmp_path: Path):
    decision = _decision_llm_path()
    out = tmp_path / "run.md"
    write_markdown_report(
        decisions=[decision], skipped=[], report=_StubReport(filtered_in=1),
        out_path=out, project_name=None,
    )
    text = out.read_text()
    assert "LLM tiebreak: Closest SMD form factor" in text
    assert "[`C58277`]" in text


def test_single_path_states_no_tiebreak(tmp_path: Path):
    decision = _decision_single_path()
    out = tmp_path / "run.md"
    write_markdown_report(
        decisions=[decision], skipped=[], report=_StubReport(filtered_in=1),
        out_path=out, project_name=None,
    )
    text = out.read_text()
    assert "Only candidate after package + value filter" in text
    assert "_No alternatives" in text


def test_failures_section_lists_unmapped(tmp_path: Path):
    @dataclass
    class _Failure:
        kind: str
        detail: str

    out = tmp_path / "run.md"
    rpt = _StubReport(filtered_in=0, failures=[_Failure("no_candidates", "ic FOO refs=['U1']")])
    write_markdown_report(
        decisions=[], skipped=[], report=rpt, out_path=out, project_name=None,
    )
    text = out.read_text()
    assert "## Unmapped components" in text
    assert "[no_candidates]" in text
    assert "ic FOO refs=['U1']" in text
