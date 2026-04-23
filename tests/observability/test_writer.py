import json
from pathlib import Path
from jlcpcb_mapper.observability.trace import Trace
from jlcpcb_mapper.observability.writer import write_group_traces


class _FakeSpec:
    def display(self): return "220µF/10V"


class _FakeCat:
    name = "polarized_capacitor"


class _FakeInstance:
    def __init__(self, reference: str):
        self.reference = reference


class _FakeGroup:
    def __init__(self):
        self.category = _FakeCat()
        self.spec = _FakeSpec()
        self.package_hint = "D6.3"
        self.instances = [_FakeInstance("C12"), _FakeInstance("C15")]
        self.trace = Trace()
        self.trace.record("match", lib_id="Device:CP", category="polarized_capacitor")


class _FakeDecision:
    def __init__(self):
        self.group = _FakeGroup()
        self.chosen_lcsc = "C16133"
        self.footprint = "LCSC:X"
        self.source = "score"
        self.failure = None


def test_writes_jsonl_one_line_per_group(tmp_path: Path):
    out = tmp_path / "traces" / "run"
    write_group_traces([_FakeDecision()], out)
    lines = (out / "groups.jsonl").read_text().splitlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["category"] == "polarized_capacitor"
    assert data["spec_display"] == "220µF/10V"
    assert data["refs"] == ["C12", "C15"]
    assert data["outcome"]["lcsc"] == "C16133"
    assert data["outcome"]["footprint"] == "LCSC:X"
    assert data["outcome"]["source"] == "score"
    assert data["outcome"]["failure"] is None


def test_writes_ref_index(tmp_path: Path):
    out = tmp_path / "traces" / "run"
    write_group_traces([_FakeDecision()], out)
    idx = json.loads((out / "index.json").read_text())
    assert idx["C12"] == 0
    assert idx["C15"] == 0


def test_preserves_event_order_not_timestamp_order(tmp_path: Path):
    """Events must be written in list order, not sorted by timestamp."""
    d = _FakeDecision()
    # Manually craft events where timestamp order differs from list order
    d.group.trace.events.clear()
    d.group.trace.events.append(type("E", (), {
        "stage": "first", "data": {}, "timestamp_ms": 100,
    })())
    d.group.trace.events.append(type("E", (), {
        "stage": "second", "data": {}, "timestamp_ms": 50,  # earlier, but listed later
    })())

    out = tmp_path / "traces" / "run"
    write_group_traces([d], out)
    data = json.loads((out / "groups.jsonl").read_text())
    stages = [e["stage"] for e in data["events"]]
    assert stages == ["first", "second"]  # list order preserved


def test_empty_decisions_writes_empty_jsonl_and_empty_index(tmp_path: Path):
    out = tmp_path / "traces" / "run"
    write_group_traces([], out)
    assert (out / "groups.jsonl").read_text() == ""
    assert json.loads((out / "index.json").read_text()) == {}


def test_multiple_groups_get_distinct_line_numbers(tmp_path: Path):
    d1 = _FakeDecision()
    d1.group.instances = [_FakeInstance("C1")]
    d2 = _FakeDecision()
    d2.group.instances = [_FakeInstance("R1"), _FakeInstance("R2")]
    out = tmp_path / "traces" / "run"
    write_group_traces([d1, d2], out)
    idx = json.loads((out / "index.json").read_text())
    assert idx["C1"] == 0
    assert idx["R1"] == 1
    assert idx["R2"] == 1
