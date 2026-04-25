"""map_cmd: pipeline-driven implementation.

Drives run_pipeline end-to-end: load project → preflight → coverage report
→ build Instance list → run_pipeline → apply decisions → write traces + log.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from ..config import Config
from ..project import load_project, select_targets
from ..io.parts_db import PartsDB
from ..io.schematic import atomic_update
from ..io.llm import ClaudeClient
from ..preflight import run_preflight, lib_id_coverage_report
from ..report import RunReport
from ..core.pipeline import run_pipeline, Instance
from ..categories import default_registry
from ..observability.writer import write_group_traces


def _autodetect_parts_db() -> Path:
    return Path.home() / "Library/Application Support/kicad/9.0/3rdparty/plugins/com_github_bouni_kicad-jlcpcb-tools/jlcpcb_parts.db"


def _build_mutator(edits):
    """Produce a mutate_fn that re-looks-up instances by reference in the fresh Schematic."""
    def mutate(sch):
        by_ref = {i.reference: i for i in sch.instances()}
        for ref, lcsc, fp in edits:
            inst = by_ref.get(ref)
            if inst is None:
                continue
            if lcsc:
                sch.set_lcsc(inst, lcsc)
            if fp:
                sch.set_footprint(inst, fp)
    return mutate


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
    all_insts = []
    for p in proj.schematics:
        all_insts.extend(proj.loaded[p].instances())
    report.total_empty_instances = sum(1 for i in all_insts if i.footprint == "")

    # Build registry for coverage check + pipeline
    fp_out_dir = proj.root / config.download.output_dir / "footprints.pretty"
    registry = default_registry(fp_out_dir=fp_out_dir)

    # Coverage report — list unmatched lib_ids; in interactive mode, confirm before proceeding
    coverage = lib_id_coverage_report([i.lib_id for i in all_insts], registry)
    if coverage["unmatched"] and not non_interactive:
        import click
        click.echo("Unmatched lib_ids (these symbols will be skipped):")
        for lid in coverage["unmatched"]:
            click.echo(f"  {lid}: {coverage['unmatched_counts'][lid]}")
        if not click.confirm("Continue?", default=False):
            raise click.Abort()

    # Select targets (honors fill_lcsc_only, include_dnp, skips power/DNP/no-footprint logic)
    targets = select_targets(proj, fill_lcsc_only=fill_lcsc_only, include_dnp=include_dnp)
    report.filtered_in = len(targets)
    if not targets:
        return report

    # Build pipeline Instances from targets
    instances = [
        Instance(
            sch_path=t.sch_path,
            reference=t.inst.reference,
            lib_id=t.inst.lib_id,
            value=t.inst.value,
            footprint=t.inst.footprint,
            dnp=t.inst.dnp,
            on_board=t.inst.on_board,
            in_bom=t.inst.in_bom,
        )
        for t in targets
    ]

    # LLM client
    llm = ClaudeClient(
        model=config.llm.model,
        timeout=config.llm.timeout_seconds,
        retry=config.llm.retry_on_parse_fail,
    )

    # Run pipeline
    decisions, skipped = run_pipeline(
        instances=instances,
        db=PartsDB(parts_db_path),
        llm=llm,
        hints=config.hints,
        score_tiebreak_threshold=config.score_tiebreak_threshold,
        llm_tiebreak_top_n=config.llm_tiebreak_top_n,
        min_stock=config.selection.min_stock,
        fp_out_dir=fp_out_dir,
        registry=registry,
        concurrency=config.llm.concurrency,
    )

    # Record skipped (unmatched lib_id or value-parse failed) as failures so
    # users can see what the tool didn't even attempt.
    from collections import defaultdict as _dd
    skipped_by_reason: dict[tuple[str, str], list[str]] = _dd(list)
    for s in skipped:
        key = (s.kind, s.category_name or s.instance.lib_id)
        skipped_by_reason[key].append(s.instance.reference)
    for (kind, bucket), refs in skipped_by_reason.items():
        report.add_failure(
            kind=kind,
            detail=f"{bucket} refs={sorted(refs)}",
        )
        for _ in refs:
            report.record_source("failed")

    # Build edits from decisions
    ref_to_sch = {t.inst.reference: t.sch_path for t in targets}
    edits_by_sch: dict[Path, list] = defaultdict(list)
    for d in decisions:
        # Record source in RunReport
        report.record_source(d.source if d.chosen_lcsc else "failed")

        if not d.chosen_lcsc:
            report.add_failure(
                kind="no_candidates",
                detail=(
                    f"{d.group.category.name} {d.group.spec.display()} "
                    f"refs={[i.reference for i in d.group.instances]}"
                ),
            )
            continue

        report.add_group_result(
            group_label=(
                f"{d.group.category.name} {d.group.spec.display()} {d.group.package_hint}".strip()
            ),
            refs=[i.reference for i in d.group.instances],
            lcsc=d.chosen_lcsc,
            footprint=d.footprint,
            downloaded=d.downloaded,
            source=d.source,
        )

        for inst in d.group.instances:
            sch_path = ref_to_sch.get(inst.reference)
            if sch_path is None:
                continue
            fp_to_write = "" if inst.footprint else d.footprint
            edits_by_sch[sch_path].append(
                (inst.reference, d.chosen_lcsc, fp_to_write)
            )

    # Atomic write per schematic
    ts = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    backup_root = proj.root / ".jlcpcb-mapper" / "backups" / ts
    for sch_path, edits in edits_by_sch.items():
        atomic_update(sch_path, _build_mutator(edits), backup_dir=backup_root)

    # Write traces and run log
    traces_dir = proj.root / ".jlcpcb-mapper" / "traces" / ts
    write_group_traces(decisions, traces_dir)
    log_path = proj.root / ".jlcpcb-mapper" / f"run-{ts}.json"
    report.write_json(log_path)
    return report
