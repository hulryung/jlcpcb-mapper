"""Human-readable Markdown report companion to run-<ts>.json.

Renders one entry per decision with the chosen LCSC, its short spec, an
LCSC product link, the rationale that drove the pick (score breakdown or
LLM reasoning), and the top alternatives that were considered. Designed
for the user to scan before committing the schematic edits.
"""
from __future__ import annotations
from pathlib import Path
from typing import Iterable, Sequence

from ..io.parts_db import PartRow


_LCSC_URL_TEMPLATE = "https://www.lcsc.com/product-detail/{lcsc}.html"
_MAX_ALTERNATIVES = 3
_MAX_REFS_INLINE = 6
_MAX_DESC_CHARS = 90


def _lcsc_url(lcsc: str) -> str:
    return _LCSC_URL_TEMPLATE.format(lcsc=lcsc)


def _tier(row: PartRow) -> str:
    if row.basic:
        return "Basic"
    if row.preferred:
        return "Preferred"
    return "Extended"


def _fmt_stock(stock: int) -> str:
    if stock >= 1_000_000:
        return f"{stock / 1_000_000:.1f}M"
    if stock >= 1_000:
        return f"{stock / 1_000:.0f}k"
    return str(stock)


def _fmt_price(price: float) -> str:
    if price >= 1.0:
        return f"${price:.2f}"
    if price >= 0.01:
        return f"${price:.3f}"
    return f"${price:.4f}"


def _short_desc(desc: str | None) -> str:
    s = (desc or "").strip()
    if len(s) <= _MAX_DESC_CHARS:
        return s
    return s[:_MAX_DESC_CHARS - 1].rstrip() + "…"


def _refs_summary(refs: Sequence[str]) -> str:
    n = len(refs)
    if n <= _MAX_REFS_INLINE:
        return ", ".join(refs)
    head = ", ".join(refs[:_MAX_REFS_INLINE])
    return f"{head}, … +{n - _MAX_REFS_INLINE} more"


def _row_line(row: PartRow) -> str:
    return (
        f"- **Package** `{row.package}` · **Tier** {_tier(row)} · "
        f"**Stock** {_fmt_stock(row.stock)} · **Price** {_fmt_price(row.price)}"
    )


def _trace_events(decision, stage: str) -> list[dict]:
    events = getattr(decision.group.trace, "events", [])
    return [e.data for e in events if e.stage == stage]


def _decide_event(decision) -> dict | None:
    events = _trace_events(decision, "decide")
    return events[0] if events else None


def _score_breakdowns(decision) -> dict[str, dict]:
    """Returns {lcsc: breakdown_dict} from score_breakdown trace events."""
    out: dict[str, dict] = {}
    for data in _trace_events(decision, "score_breakdown"):
        lcsc = data.get("lcsc")
        if lcsc:
            out[lcsc] = data
    return out


def _candidates_by_score(decision) -> list[tuple[float, PartRow]]:
    breakdowns = _score_breakdowns(decision)
    out: list[tuple[float, PartRow]] = []
    for r in decision.candidates:
        score = breakdowns.get(r.lcsc, {}).get("total")
        out.append((score if score is not None else float("-inf"), r))
    out.sort(key=lambda t: -t[0])
    return out


def _score_rationale(decision) -> str:
    """Build a human sentence from the score_breakdown deltas between chosen
    and runner-up. Falls back to a generic note if breakdowns are missing.
    """
    breakdowns = _score_breakdowns(decision)
    chosen = breakdowns.get(decision.chosen_lcsc or "")
    if not chosen:
        return "Selected by deterministic scorer (breakdown unavailable)."
    ranked = _candidates_by_score(decision)
    runner_up = next(
        ((s, r) for s, r in ranked if r.lcsc != decision.chosen_lcsc),
        None,
    )
    chosen_score = chosen.get("total", 0.0)
    if runner_up is None:
        return f"Only one candidate scored (total {chosen_score:.2f}); no runner-up to break against."
    runner_score, runner_row = runner_up
    runner_break = breakdowns.get(runner_row.lcsc, {})
    deltas: list[tuple[str, float]] = []
    for dim in ("basic", "preferred", "voltage_exact", "stock"):
        if dim not in chosen or dim not in runner_break:
            continue
        d = chosen[dim] - runner_break[dim]
        if abs(d) > 1e-6:
            deltas.append((dim, d))
    parts = []
    if any(dim == "basic" and d > 0 for dim, d in deltas):
        parts.append(f"Basic-tier (vs {_tier(runner_row)})")
    if any(dim == "preferred" and d > 0 for dim, d in deltas):
        parts.append("Preferred-tier")
    if any(dim == "voltage_exact" and d > 0 for dim, d in deltas):
        parts.append("voltage matches spec exactly")
    chosen_part = next((r for r in decision.candidates if r.lcsc == decision.chosen_lcsc), None)
    if chosen_part and any(dim == "stock" and d > 0 for dim, d in deltas):
        parts.append(
            f"higher stock ({_fmt_stock(chosen_part.stock)} vs {_fmt_stock(runner_row.stock)})"
        )
    reason_body = ", ".join(parts) if parts else "marginal score lead"
    return (
        f"Score {chosen_score:.2f} vs runner-up {runner_score:.2f} — "
        f"{reason_body}."
    )


def _llm_rationale(decision) -> str:
    decide = _decide_event(decision) or {}
    method = decide.get("method", "llm")
    reason = decide.get("reason")
    if method == "llm" and reason:
        return f"LLM tiebreak: {reason}"
    if method == "llm_reject":
        return "LLM rejected all candidates; fell back to top-ranked."
    if method == "llm_hallucination":
        return "LLM returned an LCSC outside the candidate set; fell back to top-ranked."
    if method == "llm_error_fallback":
        return f"LLM call failed ({decide.get('error', 'unknown error')}); fell back to top-ranked."
    return "Selected by LLM tiebreak (no reason recorded)."


def _rationale(decision) -> str:
    if decision.source == "single":
        return f"Only candidate after package + value filter ({len(decision.candidates)} remaining)."
    if decision.source == "score":
        return _score_rationale(decision)
    if decision.source == "llm":
        return _llm_rationale(decision)
    return f"Source: {decision.source}."


def _alternatives_table(decision) -> str:
    """Render up to N alternative candidates, ranked by score where available."""
    ranked = _candidates_by_score(decision)
    rows = [
        (score, row)
        for score, row in ranked
        if row.lcsc != decision.chosen_lcsc
    ][:_MAX_ALTERNATIVES]
    if not rows:
        return "_No alternatives — only one candidate after filtering._"
    out = ["| LCSC | Mfr Part | Tier | Package | Stock | Price | Score |",
           "|------|----------|------|---------|-------|-------|-------|"]
    for score, r in rows:
        score_cell = f"{score:.2f}" if score != float("-inf") else "—"
        url = _lcsc_url(r.lcsc)
        out.append(
            f"| [`{r.lcsc}`]({url}) | {r.mfr_part or '—'} | {_tier(r)} | "
            f"`{r.package}` | {_fmt_stock(r.stock)} | {_fmt_price(r.price)} | {score_cell} |"
        )
    return "\n".join(out)


def _decision_section(decision) -> str:
    g = decision.group
    refs = [i.reference for i in g.instances]
    label = f"{g.category.name} {g.spec.display()} {g.package_hint}".strip()
    chosen_lcsc = decision.chosen_lcsc
    chosen_row = next((r for r in decision.candidates if r.lcsc == chosen_lcsc), None)

    header = f"### {label} — {len(refs)} ref{'s' if len(refs) != 1 else ''} ({_refs_summary(refs)})"
    if chosen_row is None:
        return f"{header}\n\n_No part chosen._\n"

    chosen_block = (
        f"**Selected**: [`{chosen_lcsc}`]({_lcsc_url(chosen_lcsc)}) — "
        f"{chosen_row.mfr or ''} {chosen_row.mfr_part or ''}".strip()
    )
    spec_line = _row_line(chosen_row)
    desc_line = f"- {_short_desc(chosen_row.description)}" if chosen_row.description else ""
    rationale = f"**Why this part?** {_rationale(decision)}"
    alts_header = "**Alternatives considered**:"
    alts = _alternatives_table(decision)

    parts = [header, "", chosen_block, spec_line]
    if desc_line:
        parts.append(desc_line)
    parts.extend(["", rationale, "", alts_header, "", alts, ""])
    return "\n".join(parts)


def _failures_section(failures: list, skipped: list) -> str:
    if not failures and not skipped:
        return ""
    out = ["## Unmapped components", ""]
    if failures:
        out.append("These groups had no JLCPCB candidates after filtering. Source manually:")
        out.append("")
        for f in failures:
            kind = getattr(f, "kind", None) or f.get("kind", "?")
            detail = getattr(f, "detail", None) or f.get("detail", "")
            out.append(f"- **[{kind}]** {detail}")
        out.append("")
    if skipped:
        out.append("Eligible symbols dropped before grouping:")
        out.append("")
        for s in skipped:
            out.append(
                f"- **{s.instance.reference}** `{s.instance.lib_id}` value=`{s.instance.value}` — {s.kind}"
            )
        out.append("")
    return "\n".join(out)


def _summary_header(report, project_name: str | None) -> str:
    title = "# JLCPCB Mapping Run"
    lines = [title, ""]
    if project_name:
        lines.append(f"**Project**: `{project_name}`")
    lines.append(f"**Schematics**: {len(report.schematics)} files")
    lines.append(
        f"**Eligible symbols**: {report.filtered_in} "
        f"(of {report.total_empty_instances} candidates)"
    )
    src = report.sources or {}
    src_str = " · ".join(f"{k}: {v}" for k, v in sorted(src.items())) or "—"
    lines.append(f"**Outcomes**: {src_str}")
    lines.append("")
    lines.append(
        "> **Tier legend** — _Basic_ = pre-loaded on JLCPCB feeders (no setup fee); "
        "_Preferred_ = stocked, no setup fee; _Extended_ = $3 setup fee per unique part per order."
    )
    lines.append("")
    return "\n".join(lines)


def write_markdown_report(
    *,
    decisions: Iterable,
    skipped: Iterable,
    report,
    out_path: Path,
    project_name: str | None = None,
) -> None:
    """Render the human-readable Markdown report and write to out_path."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    decisions = list(decisions)
    skipped = list(skipped)

    body: list[str] = []
    body.append(_summary_header(report, project_name))

    mapped = [d for d in decisions if d.chosen_lcsc]
    body.append(f"## Mapped components ({len(mapped)})")
    body.append("")
    for d in sorted(mapped, key=lambda d: d.group.instances[0].reference):
        body.append(_decision_section(d))
        body.append("---")
        body.append("")

    failed_decisions = [d for d in decisions if not d.chosen_lcsc]
    failures_text = _failures_section(report.failures, skipped) if hasattr(report, "failures") else ""
    if failed_decisions or failures_text:
        # Combine failed Decisions with the report.failures list (which already
        # includes them as `add_failure` entries from map_cmd).
        if failures_text:
            body.append(failures_text)

    out_path.write_text("\n".join(body))
