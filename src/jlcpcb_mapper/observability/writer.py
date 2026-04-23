"""Write per-group traces to JSONL + ref→line index.

IMPORTANT ORDERING CONTRACT:
- `Trace.events` list order is authoritative. Do NOT sort by `timestamp_ms`
  — timestamps are process-relative `time.monotonic()` and may collide at
  the millisecond boundary.
- See Task 3 review notes in the plan for rationale.
"""
from __future__ import annotations
from dataclasses import asdict, is_dataclass
from pathlib import Path
import json


def _event_to_dict(event) -> dict:
    """Convert a TraceEvent to a dict, whether it's a dataclass or a duck."""
    if is_dataclass(event):
        return asdict(event)
    # Fallback for duck-typed test stubs
    return {
        "stage": event.stage,
        "data": event.data,
        "timestamp_ms": event.timestamp_ms,
    }


def write_group_traces(decisions, out_dir: Path) -> None:
    """Write one JSONL line per Decision, plus a ref→line-offset index.

    Args:
        decisions: iterable of Decision objects with .group, .chosen_lcsc,
                   .footprint, .source, .failure fields.
        out_dir: directory to create (if missing) and write into.

    Produces:
        out_dir/groups.jsonl  — one line per group
        out_dir/index.json    — {ref: line_offset, ...}
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_dir / "groups.jsonl"
    index: dict[str, int] = {}
    with jsonl_path.open("w") as f:
        for line_no, d in enumerate(decisions):
            g = d.group
            line = {
                "category": g.category.name,
                "spec_display": g.spec.display(),
                "package_hint": g.package_hint,
                "refs": [i.reference for i in g.instances],
                "events": [_event_to_dict(e) for e in g.trace.events],
                "outcome": {
                    "lcsc": d.chosen_lcsc,
                    "footprint": d.footprint,
                    "source": d.source,
                    "failure": d.failure,
                },
            }
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
            for inst in g.instances:
                index[inst.reference] = line_no
    (out_dir / "index.json").write_text(json.dumps(index, indent=2))
