from __future__ import annotations
from pathlib import Path
from collections import defaultdict
from datetime import datetime

from ..config import Config
from ..project import load_project, select_targets, Target
from ..io.parts_db import PartsDB
from ..grouper import group_instances, Group, GroupKey
from ..candidates import candidates_for
from ..io.llm import ClaudeClient
from ..select import select_for_groups, SelectionResult
from ..review import review_mapping, ReviewFlag
from ..resolver import resolve_footprint, ResolveResult
from ..io.easyeda import ensure_fp_lib_table_entry
from ..io.schematic import atomic_update
from ..preflight import run_preflight
from ..report import RunReport


def _autodetect_parts_db() -> Path:
    return Path.home() / "Library/Application Support/kicad/9.0/3rdparty/plugins/com_github_bouni_kicad-jlcpcb-tools/jlcpcb_parts.db"


def _build_mutator(edits_by_ref: list[tuple[str, str, str]]):
    """Produce a mutate_fn that re-looks-up instances by reference in the fresh Schematic."""
    def mutate(sch):
        by_ref = {i.reference: i for i in sch.instances()}
        for ref, lcsc, fp in edits_by_ref:
            inst = by_ref.get(ref)
            if inst is None:
                continue
            if lcsc:
                sch.set_lcsc(inst, lcsc)
            if fp:
                sch.set_footprint(inst, fp)
    return mutate


def _interactive_resolve_flags(
    sels: list[SelectionResult],
    flags: list[ReviewFlag],
    apply_all: bool,
) -> list[SelectionResult]:
    import click
    for f in flags:
        s = sels[f.group_index]
        click.echo(f"\n  Group {f.group_index} ({s.group.key}): currently {s.chosen_lcsc}")
        click.echo(f"   Issue: {f.issue}")
        if f.suggested_lcsc:
            click.echo(f"   Suggested: {f.suggested_lcsc}")
            if apply_all or click.confirm("   Replace?", default=False):
                s.chosen_lcsc = f.suggested_lcsc
                s.reason = f"2nd-pass: {f.issue}"
    return sels


def _apply_all_flags(sels: list[SelectionResult], flags: list[ReviewFlag]) -> list[SelectionResult]:
    for f in flags:
        if f.suggested_lcsc:
            sels[f.group_index].chosen_lcsc = f.suggested_lcsc
    return sels


def run_map(
    *,
    project_pro: Path,
    config: Config,
    non_interactive: bool,
    force: bool,
    allow_stale_db: bool,
    fill_lcsc_only: bool,
    include_dnp: bool,
    apply_suggestions: bool,
) -> RunReport:
    proj = load_project(project_pro)
    parts_db_path = Path(config.parts_db).expanduser() if config.parts_db else _autodetect_parts_db()

    run_preflight(
        schematics=proj.schematics,
        parts_db=parts_db_path,
        force=force,
        allow_stale_db=allow_stale_db,
        skip_claude_check=False,
    )

    report = RunReport()
    report.schematics = [str(p) for p in proj.schematics]

    # Count empty-footprint across the project
    all_insts: list = []
    for p in proj.schematics:
        all_insts.extend(proj.loaded[p].instances())
    report.total_empty_instances = sum(1 for i in all_insts if i.footprint == "")

    targets: list[Target] = select_targets(
        proj, fill_lcsc_only=fill_lcsc_only, include_dnp=include_dnp
    )
    report.filtered_in = len(targets)

    if not targets:
        return report

    # Group by category/value/package
    insts_only = [t.inst for t in targets]
    groups: list[Group] = group_instances(insts_only, config.selection.defaults)

    # For downstream mutation, we need ref -> sch_path.
    ref_to_sch: dict[str, Path] = {t.inst.reference: t.sch_path for t in targets}

    # Candidate pre-filter per group
    db = PartsDB(parts_db_path)
    cand_map: dict[GroupKey, list] = {
        g.key: candidates_for(g.key, db, min_stock=config.selection.min_stock)
        for g in groups
    }

    # 1st-pass selection
    llm = ClaudeClient(
        model=config.llm.model,
        timeout=config.llm.timeout_seconds,
        retry=config.llm.retry_on_parse_fail,
    )
    sels: list[SelectionResult] = select_for_groups(
        groups, cand_map, llm,
        hints=config.hints,
        min_stock=config.selection.min_stock,
        concurrency=config.llm.concurrency,
    )

    # 2nd-pass review (best-effort)
    flags = review_mapping(sels, llm)
    if flags:
        if non_interactive and not apply_suggestions:
            # Warnings only
            pass
        elif apply_suggestions:
            sels = _apply_all_flags(sels, flags)
        else:
            sels = _interactive_resolve_flags(sels, flags, apply_all=False)

    # Footprint resolution and edit plan per schematic
    fp_out_dir = proj.root / config.download.output_dir / "footprints.pretty"
    downloaded_any = False
    edits_by_sch: dict[Path, list[tuple[str, str, str]]] = defaultdict(list)

    for sel in sels:
        if not sel.chosen_lcsc:
            report.add_failure(
                kind="no_candidates",
                detail=f"{sel.group.key} refs={[i.reference for i in sel.group.instances]}",
            )
            continue
        part = next((c for c in sel.candidates if c.lcsc == sel.chosen_lcsc), None)
        if part is None:
            # Shouldn't happen for 1st-pass; possible if 2nd-pass injected an LCSC not in candidates
            report.add_failure(
                kind="unknown_lcsc",
                detail=f"chosen LCSC {sel.chosen_lcsc} not in candidate list",
            )
            continue
        # Skip resolver if all instances already have footprints — no need to download
        all_have_fp = all(i.footprint for i in sel.group.instances)
        if all_have_fp:
            # No need to resolve — existing footprints are preserved.
            resolution = ResolveResult(footprint="", downloaded=False, download_failed=False)
        else:
            resolution = resolve_footprint(
                category=sel.group.key.category,
                part=part,
                out_dir=fp_out_dir,
                overrides=config.kicad_footprint_map_overrides,
            )
            if resolution.downloaded:
                downloaded_any = True
            if resolution.download_failed:
                report.add_failure(
                    kind="footprint_download",
                    detail=f"{sel.chosen_lcsc}: EasyEDA fetch failed",
                )

        report.add_group_result(
            group_label=f"{sel.group.key.category} {sel.group.key.value} {sel.group.key.package_hint}".strip(),
            refs=[i.reference for i in sel.group.instances],
            lcsc=sel.chosen_lcsc,
            footprint=resolution.footprint,
            downloaded=resolution.downloaded,
            source="llm" if sel.llm_called else "single-candidate",
        )

        for inst in sel.group.instances:
            sch_path = ref_to_sch.get(inst.reference)
            if sch_path is None:
                continue
            fp_to_write = "" if inst.footprint else resolution.footprint
            edits_by_sch[sch_path].append(
                (inst.reference, sel.chosen_lcsc, fp_to_write)
            )

    # Register LCSC fp-lib if we downloaded at least one footprint
    if downloaded_any and config.download.auto_register_fp_lib_table:
        ensure_fp_lib_table_entry(
            proj.root / "fp-lib-table",
            lib_name="LCSC",
            uri="${KIPRJMOD}/libs/lcsc/footprints.pretty",
        )

    # Atomic write per schematic
    ts = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    backup_root = proj.root / ".jlcpcb-mapper" / "backups" / ts
    for sch_path, edits in edits_by_sch.items():
        atomic_update(sch_path, _build_mutator(edits), backup_dir=backup_root)

    # Write run log
    log_path = proj.root / ".jlcpcb-mapper" / f"run-{ts}.json"
    report.write_json(log_path)
    return report
