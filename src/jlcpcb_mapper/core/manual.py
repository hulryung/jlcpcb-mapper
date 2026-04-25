"""User-supplied LCSC overrides.

Some symbols are subjective (specific connector form factors, mechanical
fit) and not worth scoring. The user pins an LCSC in `manual_lcsc:` and
the pipeline writes it directly without scoring or LLM. by_reference
beats by_value when both match.
"""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable

from ..config import ManualLCSC
from ..io.parts_db import PartRow, PartsDB
from ..observability.trace import Trace
from .pipeline import Decision, Group, Instance


@dataclass
class _ManualSpec:
    """Minimal Spec stand-in so synthetic Decisions render through the
    existing report and trace plumbing."""
    value_label: str
    match_kind: str  # "by_reference" or "by_value"

    def display(self) -> str:
        return self.value_label or "manual"

    def group_key(self):
        return ("manual", self.value_label, self.match_kind)

    def llm_context(self) -> dict:
        return {}


@dataclass
class _ManualCategory:
    """Pseudo-category. Only `.name` is read by downstream code."""
    name: str = "manual"


@dataclass
class ManualAssignment:
    instance: Instance
    lcsc: str
    match_kind: str  # by_reference | by_value


@dataclass
class ManualResolution:
    decisions: list[Decision] = field(default_factory=list)
    matched_refs: set[str] = field(default_factory=set)
    unknown_lcscs: list[tuple[str, list[str]]] = field(default_factory=list)
    # ^ (lcsc, [refs]) for entries that couldn't be looked up in parts.db


def _match(instance: Instance, manual: ManualLCSC) -> tuple[str, str] | None:
    lcsc = manual.by_reference.get(instance.reference)
    if lcsc:
        return (lcsc, "by_reference")
    lcsc = manual.by_value.get(instance.value)
    if lcsc:
        return (lcsc, "by_value")
    return None


def _build_decision(lcsc: str, part: PartRow, assignments: list[ManualAssignment]) -> Decision:
    instances = [a.instance for a in assignments]
    # Use the first assignment's value+match_kind for the group label.
    sample = assignments[0]
    spec = _ManualSpec(value_label=sample.instance.value, match_kind=sample.match_kind)
    trace = Trace()
    trace.record(
        "decide",
        method="manual",
        lcsc=lcsc,
        match_kind=sample.match_kind,
        refs=[a.instance.reference for a in assignments],
    )
    group = Group(
        category=_ManualCategory(),
        spec=spec,
        package_hint="",
        instances=instances,
        trace=trace,
    )
    return Decision(
        group=group,
        chosen_lcsc=lcsc,
        candidates=[part],
        footprint="",       # keep whatever the schematic already has
        downloaded=False,
        source="manual",
    )


def resolve_manual_overrides(
    instances: Iterable[Instance],
    manual: ManualLCSC,
    db: PartsDB,
) -> ManualResolution:
    """Match instances against the user's overrides and build synthetic
    Decisions. Returns matched refs so the auto pipeline can skip them."""
    by_lcsc: dict[str, list[ManualAssignment]] = defaultdict(list)
    matched: set[str] = set()
    for inst in instances:
        m = _match(inst, manual)
        if m is None:
            continue
        lcsc, kind = m
        by_lcsc[lcsc].append(ManualAssignment(instance=inst, lcsc=lcsc, match_kind=kind))
        matched.add(inst.reference)

    decisions: list[Decision] = []
    unknown: list[tuple[str, list[str]]] = []
    for lcsc, assignments in by_lcsc.items():
        part = db.get(lcsc)
        if part is None:
            unknown.append((lcsc, [a.instance.reference for a in assignments]))
            # Don't claim these refs — the auto pipeline can still try.
            for a in assignments:
                matched.discard(a.instance.reference)
            continue
        decisions.append(_build_decision(lcsc, part, assignments))

    return ManualResolution(decisions=decisions, matched_refs=matched, unknown_lcscs=unknown)
