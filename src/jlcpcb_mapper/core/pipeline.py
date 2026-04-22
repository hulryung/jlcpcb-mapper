"""Pipeline orchestration: categorize → parse → extract → group → query → decide → resolve."""
from __future__ import annotations
import dataclasses
from dataclasses import dataclass, field
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

from .types import QuerySpec
from .registry import Registry
from ..categories.base import Category, ResolveResult
from ..categories import default_registry
from ..observability.trace import Trace
from ..parts_db import PartsDB, PartRow


@dataclass
class Instance:
    sch_path: Path
    reference: str
    lib_id: str
    value: str
    footprint: str
    dnp: bool = False
    on_board: bool = True
    in_bom: bool = True


@dataclass
class Targeted:
    inst: Instance
    category: Category
    spec: object          # a Spec
    package_hint: str


@dataclass
class Group:
    category: Category
    spec: object
    package_hint: str
    instances: list[Instance]
    trace: Trace = field(default_factory=Trace)


@dataclass
class Decision:
    group: Group
    chosen_lcsc: str | None
    candidates: list[PartRow]
    footprint: str
    downloaded: bool
    source: str            # "single" | "score" | "llm" | "failed"
    failure: str | None = None


def run_pipeline(
    *,
    instances: list[Instance],
    db: PartsDB,
    llm,
    hints: str,
    score_tiebreak_threshold: float,
    llm_tiebreak_top_n: int,
    min_stock: int,
    fp_out_dir: Path,
    registry: Registry | None = None,
    concurrency: int = 4,
) -> list[Decision]:
    reg = registry or default_registry(fp_out_dir=fp_out_dir)

    # Stage 1: per-instance match + parse + extract
    targeted: list[Targeted] = []
    for inst in instances:
        if not inst.on_board or not inst.value:
            continue
        cat = reg.lookup(inst.lib_id)
        if cat is None:
            continue
        spec = cat.value_parser.parse(inst.value) if cat.value_parser else None
        if spec is None:
            continue
        pkg = None
        if inst.footprint and cat.package_extractor:
            pkg = cat.package_extractor.extract(inst.footprint)
        pkg = pkg or cat.default_package
        targeted.append(Targeted(inst=inst, category=cat, spec=spec, package_hint=pkg))

    # Stage 2: bucket by (category.name, spec.group_key, package_hint)
    buckets: dict[tuple, Group] = {}
    for t in targeted:
        k = (t.category.name, t.spec.group_key(), t.package_hint)
        g = buckets.get(k)
        if g is None:
            g = Group(category=t.category, spec=t.spec,
                      package_hint=t.package_hint, instances=[])
            buckets[k] = g
        g.instances.append(t.inst)
    groups = list(buckets.values())

    # Stage 3: parallel per-group decide + resolve
    decisions: list[Decision] = []
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as ex:
        futs = [
            ex.submit(_process_group, g, db, llm, hints,
                      score_tiebreak_threshold, llm_tiebreak_top_n, min_stock)
            for g in groups
        ]
        for f in as_completed(futs):
            decisions.append(f.result())
    decisions.sort(key=lambda d: d.group.instances[0].reference)
    return decisions


def _process_group(g: Group, db, llm, hints, tau, top_n, min_stock) -> Decision:
    cat = g.category
    qspec: QuerySpec = cat.candidate_source.query(g.spec, g.package_hint)
    # Override min_stock if caller specified one and qspec didn't
    if min_stock and qspec.min_stock == 0:
        qspec = dataclasses.replace(qspec, min_stock=min_stock)
    g.trace.record("query", **{k: v for k, v in qspec.__dict__.items()})
    rows = db.execute(qspec)
    g.trace.record("query_result", count=len(rows))

    rows = cat.candidate_source.post_filter(rows, g.spec, g.package_hint)
    g.trace.record("post_filter", count=len(rows))
    if not rows:
        return Decision(g, None, [], "", False, "failed", "no_candidates")

    chosen, source = _decide(cat, g, rows, llm, hints, tau, top_n)

    all_have_fp = all(i.footprint for i in g.instances)
    if all_have_fp:
        res = ResolveResult(footprint="", downloaded=False)
    else:
        part = next((r for r in rows if r.lcsc == chosen), None)
        if part is None:
            g.trace.record("resolve", skipped="chosen_not_in_rows", chosen=chosen)
            return Decision(g, chosen, rows, "", False, "failed", "chosen_not_in_rows")
        res = cat.footprint_resolver.resolve(part, g.package_hint)
    g.trace.record("resolve", footprint=res.footprint,
                   downloaded=res.downloaded, failed=res.download_failed)

    return Decision(g, chosen, rows, res.footprint, res.downloaded, source,
                    None if chosen else "no_selection")


def _decide(cat: Category, g: Group, rows: list[PartRow], llm, hints: str,
            tau: float, top_n: int) -> tuple[str, str]:
    if len(rows) == 1:
        g.trace.record("decide", method="single", lcsc=rows[0].lcsc)
        return rows[0].lcsc, "single"

    if cat.scorer is not None:
        scored = sorted(
            ((cat.scorer.score(r, g.spec, g.trace), r) for r in rows),
            key=lambda t: -t[0],
        )
        top_score, top_row = scored[0]
        second_score = scored[1][0] if len(scored) > 1 else 0.0
        g.trace.record("score", top=top_score, second=second_score, top_lcsc=top_row.lcsc)
        if top_score - second_score >= tau:
            g.trace.record("decide", method="score", lcsc=top_row.lcsc,
                           diff=top_score - second_score)
            return top_row.lcsc, "score"
        rows = [r for _, r in scored[:top_n]]

    # LLM path
    prompt = _build_prompt(cat, g, rows, hints)
    try:
        resp = llm.call(prompt, schema_keys=["lcsc", "reason"])
        lcsc = resp.data.get("lcsc")
        if lcsc is None:
            g.trace.record("decide", method="llm_reject", fallback_lcsc=rows[0].lcsc)
            return rows[0].lcsc, "llm"
        if not any(r.lcsc == lcsc for r in rows):
            g.trace.record("decide", method="llm_hallucination",
                           returned=lcsc, fallback_lcsc=rows[0].lcsc)
            return rows[0].lcsc, "llm"
        g.trace.record("decide", method="llm", lcsc=lcsc,
                       reason=resp.data.get("reason"))
        return lcsc, "llm"
    except Exception as e:
        g.trace.record("decide", method="llm_error_fallback", error=str(e),
                       fallback_lcsc=rows[0].lcsc)
        return rows[0].lcsc, "llm"


def _build_prompt(cat: Category, g: Group, rows: list[PartRow], hints: str) -> str:
    hook = cat.prompt_hook
    refs = ", ".join(i.reference for i in g.instances)
    cand_payload = [hook.candidate_payload(r) for r in rows]
    return (
        "You are a component selection assistant for JLCPCB PCB assembly.\n\n"
        f"Category: {cat.name}\n"
        f"Spec: {g.spec.display()}\n"
        f"Package hint: {g.package_hint}\n"
        f"Refs: {refs} (count={len(g.instances)})\n\n"
        f"User hints:\n{hints}\n\n"
        f"Selection criteria:\n{hook.selection_criteria()}\n\n"
        f"Candidates:\n{json.dumps(cand_payload, ensure_ascii=False)}\n\n"
        "Pick ONE LCSC. Return ONLY JSON: "
        '{"lcsc": "C...", "reason": "<one sentence>"}.\n'
        'If no candidate is suitable, return {"lcsc": null, "reason": "..."}.'
    )
