from __future__ import annotations
from dataclasses import dataclass
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from .grouper import Group, GroupKey
from .parts_db import PartRow
from .llm import ClaudeClient, LLMError

@dataclass
class SelectionResult:
    group: Group
    candidates: list[PartRow]
    chosen_lcsc: str | None
    reason: str
    llm_called: bool
    failure_reason: str | None = None

def _build_prompt(group: Group, candidates: list[PartRow], hints: str, min_stock: int) -> str:
    refs = ", ".join(i.reference for i in group.instances)
    k = group.key
    cand_payload = [
        {
            "lcsc": r.lcsc, "mfr": r.mfr, "mfr_part": r.mfr_part,
            "package": r.package, "basic": bool(r.basic), "preferred": bool(r.preferred),
            "stock": r.stock, "price": r.price,
            "description": (r.description or "")[:200],
        }
        for r in candidates
    ]
    return (
        "You are a component selection assistant for JLCPCB PCB assembly.\n\n"
        f"Component group:\n- Category: {k.category}\n- Value: {k.value}\n"
        f"- Package hint: {k.package_hint}\n- Refs: {refs}\n- Count: {len(group.instances)}\n\n"
        f"User preferences:\n{hints}\n\n"
        "Hard constraints already applied:\n"
        f"- package == \"{k.package_hint}\"\n"
        f"- stock >= {min_stock}\n"
        "- prefer basic > preferred > extended\n\n"
        f"Candidates (SQL-sorted):\n{json.dumps(cand_payload, ensure_ascii=False)}\n\n"
        "Pick ONE LCSC. Return ONLY JSON: "
        '{"lcsc": "C...", "reason": "<one sentence>"}.\n'
        'If no candidate is suitable, return {"lcsc": null, "reason": "..."}.'
    )

def _run_one(group: Group, candidates: list[PartRow], llm: ClaudeClient, hints: str, min_stock: int) -> SelectionResult:
    if not candidates:
        return SelectionResult(group, [], None, "", False, failure_reason="no candidates")
    if len(candidates) == 1:
        return SelectionResult(group, candidates, candidates[0].lcsc, "single candidate", False)
    prompt = _build_prompt(group, candidates, hints, min_stock)
    try:
        resp = llm.call(prompt, schema_keys=["lcsc", "reason"])
        lcsc = resp.data.get("lcsc")
        return SelectionResult(
            group, candidates, lcsc, resp.data.get("reason", ""), True,
            failure_reason=None if lcsc else "llm rejected all",
        )
    except LLMError as e:
        return SelectionResult(
            group, candidates, candidates[0].lcsc,
            f"fallback[0] after LLM error: {e}", True,
            failure_reason=f"llm error: {e}",
        )

def select_for_groups(
    groups: list[Group],
    candidates_map: dict[GroupKey, list[PartRow]],
    llm: ClaudeClient,
    hints: str,
    min_stock: int = 1000,
    concurrency: int = 4,
) -> list[SelectionResult]:
    results: list[SelectionResult] = []
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as ex:
        futs = {
            ex.submit(_run_one, g, candidates_map.get(g.key, []), llm, hints, min_stock): g
            for g in groups
        }
        for f in as_completed(futs):
            results.append(f.result())
    order = {id(g): i for i, g in enumerate(groups)}
    results.sort(key=lambda r: order[id(r.group)])
    return results
