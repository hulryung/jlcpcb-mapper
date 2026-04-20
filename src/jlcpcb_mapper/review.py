from __future__ import annotations
from dataclasses import dataclass
import json
from .select import SelectionResult
from .llm import ClaudeClient, LLMError

@dataclass
class ReviewFlag:
    group_index: int
    issue: str
    suggested_lcsc: str | None

def _build_prompt(sels: list[SelectionResult]) -> str:
    rows = []
    for i, s in enumerate(sels):
        rows.append({
            "group_index": i,
            "category": s.group.key.category,
            "value": s.group.key.value,
            "package": s.group.key.package_hint,
            "refs": [x.reference for x in s.group.instances],
            "chosen_lcsc": s.chosen_lcsc,
            "reason": s.reason,
        })
    return (
        "Review this component mapping table for: "
        "(1) inconsistencies (same value/package → different LCSC), "
        "(2) outliers (non-basic where basic exists), "
        "(3) suspicious low stock or EOL hints.\n\n"
        f"Mapping:\n{json.dumps(rows, ensure_ascii=False)}\n\n"
        "Return ONLY JSON: "
        '{"flagged":[{"group_index":int,"issue":str,"suggested_lcsc":str|null}],'
        '"overall_ok":bool}'
    )

def review_mapping(sels: list[SelectionResult], llm: ClaudeClient) -> list[ReviewFlag]:
    if not sels:
        return []
    try:
        resp = llm.call(_build_prompt(sels), schema_keys=["flagged", "overall_ok"])
    except LLMError:
        return []
    flagged = resp.data.get("flagged", []) or []
    return [ReviewFlag(
        group_index=int(f["group_index"]),
        issue=str(f.get("issue", "")),
        suggested_lcsc=f.get("suggested_lcsc"),
    ) for f in flagged]
