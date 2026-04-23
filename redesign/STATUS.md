# Status Snapshot

**Last updated:** post-merge to `main`. Tip commit `61f164d` (handoff docs). Task 29 (last plan task) is `ce1ebdc`.

## Overall

| Metric | Value |
|---|---|
| Branch | `main` (redesign merged via fast-forward after rebase) |
| Prior base | `13e8f57` — the original plan commit |
| Redesign commits on main | **47** (see `COMMITS.md`) |
| Test suite | **386 passed** (from 154 baseline; new coverage replaced the deleted legacy tests) |
| Test collection time | ~0.3s (all unit + small-fixture integration) |
| Regressions | 0 across all 47 commits |
| Uncommitted changes | None (clean working tree) |
| Plan completeness | **29 / 29 tasks** |
| Working directory | `/Users/dkkang/dev/jlcpcb-mapper` |
| `arch-redesign` branch | deleted (merged cleanly) |

## Phase completion

### Phase A — Core scaffolding (4/4)

- Task 1: `Value` dataclass (`core/types.py`)
- Task 2: `QuerySpec` + `Spec` protocol (`core/types.py`)
- Task 3: `Trace` + `TraceEvent` (`observability/trace.py`)
- Task 4: `Category` bundle + component protocols + `Registry` (`categories/base.py`, `core/registry.py`)

**End state**: 170 tests, 4 commits.

### Phase B — Polarized cap end-to-end (9/9, plus 2 follow-ups)

- Tasks 5–12: Individual components (matchers, parsers, package extractors, candidate sources, scorers, footprint resolvers, prompt hooks)
- Task 13: `POLARIZED_CAP` Category bundle + pipeline skeleton + 220µF/10V integration test (acceptance gate)
- Follow-ups: Greek mu canonicalization (Task 6), VDC/VAC voltage forms (Task 10), reviewer polish (Task 13)

**Acceptance case verified**: `Device:CP` + `"220uF/10V"` → LCSC `C16133` (basic, exact 10V) via scorer, EasyEDA fallback, downloaded footprint.

**End state**: 209 tests, 11 commits total (9 + 2 follow-ups).

### Phase C — Remaining categories (7/7, plus 1 follow-up)

- Task 14: Resistor (BuiltinMap + `all_have_fp` branch proven)
- Task 15: Ceramic cap (Device:C_Polarized collision test)
- Task 16: Inductor (EasyedaFallback path proven)
- Task 17: LED (`Value(0, token)` convention)
- Task 18: Crystal (package_hint required; no-hint failure path)
- Task 19: IC (MPN match, `scorer=None`, catch-all matcher, ESCAPE fix)
- Task 20: Connector (**protocol extension** — `ValueParser.parse` now accepts `lib_id=`; 6 backward-compat regression tests)
- Follow-up: SQL LIKE escape in `ConnectorSource`

**End state**: 464 tests, 37 commits total.

### Phase D — Observability (4/4)

- Task 21: `write_group_traces` → `groups.jsonl` + `index.json`
- Task 22: `RunReport.record_source` + per-source counters
- Task 23: `lib_id_coverage_report` for preflight
- Task 24: LLM failure mode regression tests

**End state**: 483 tests, 41 commits total.

### Phase E — Migration (5/5)

- Task 25: `git mv` I/O modules to `io/` subpackage
- Task 26: Rewrite `map_cmd.py` to drive `run_pipeline`; add minimal schematic fixture and CLI integration test
- Task 27: Golden-file regression harness (`tests/golden/`) + first case (`polarized_cap_220uf_10v`)
- Task 28: Delete 8 legacy source modules + 8 legacy test files + `PartsDB.query_candidates`
- Task 29: Config fields (`score_tiebreak_threshold`, `llm_tiebreak_top_n`) + README Observability section

**End state**: 386 tests (383 after deletions + 3 new config tests), 46 commits total.

## What's been deleted

Legacy source (replaced by `components/` + `categories/`):
- `src/jlcpcb_mapper/values.py`
- `src/jlcpcb_mapper/candidates.py`
- `src/jlcpcb_mapper/footprint.py`
- `src/jlcpcb_mapper/kicad_fp.py`
- `src/jlcpcb_mapper/grouper.py`
- `src/jlcpcb_mapper/select.py`
- `src/jlcpcb_mapper/review.py`
- `src/jlcpcb_mapper/resolver.py`

Legacy tests (replaced by new component + integration coverage):
- `tests/test_values.py`, `test_candidates.py`, `test_footprint.py`, `test_kicad_fp.py`, `test_grouper.py`, `test_select.py`, `test_review.py`, `test_resolver.py`

Removed method: `PartsDB.query_candidates` (superseded by `PartsDB.execute(QuerySpec)`).

## What's new

Top-level source layout on `main`:

```
src/jlcpcb_mapper/
├── categories/            # NEW — per-category Category bundles
│   ├── base.py            # Category dataclass + 7 component protocols + ResolveResult
│   ├── spec/              # Category-specific Spec dataclasses
│   │   ├── cap.py         # CeramicCapSpec, PolarizedCapSpec
│   │   ├── resistor.py    # ResistorSpec
│   │   ├── inductor.py
│   │   ├── led.py
│   │   ├── crystal.py
│   │   ├── ic.py
│   │   └── connector.py
│   ├── polarized_cap.py
│   ├── resistor.py
│   ├── ceramic_cap.py
│   ├── inductor.py
│   ├── led.py
│   ├── crystal.py
│   ├── ic.py              # catch-all — registered LAST
│   ├── connector.py
│   └── __init__.py        # default_registry(fp_out_dir) — deferred imports to avoid cycle
│
├── components/            # NEW — reusable composition parts
│   ├── matchers.py        # LibIdAny, LibIdPrefix
│   ├── value_parsers.py   # Cap/Resistor/Inductor/LED/Crystal/IC/Connector
│   ├── package_extractors.py  # RegexFromRules
│   ├── candidate_sources.py   # 7 per-category sources
│   ├── scorers.py         # PolarizedCapScorer, GenericBasicStockScorer
│   ├── footprint_resolvers.py # BuiltinMap, EasyedaFallback, Composite
│   └── prompt_hooks.py    # CapPromptHook, ICPromptHook, GenericPromptHook
│
├── core/                  # NEW — framework
│   ├── types.py           # Value, QuerySpec, Spec protocol
│   ├── registry.py        # Registry (lib_id → Category)
│   └── pipeline.py        # run_pipeline, Instance, Group, Decision, _decide, _build_prompt
│
├── io/                    # NEW — external boundary
│   ├── parts_db.py        # PartsDB.execute(QuerySpec) — query_candidates removed
│   ├── schematic.py       # text-based round-trip parser (unchanged logic)
│   ├── easyeda.py         # was downloader.py
│   └── llm.py             # ClaudeClient subprocess wrapper
│
├── observability/         # NEW
│   ├── trace.py           # Trace, TraceEvent
│   └── writer.py          # write_group_traces (JSONL + index.json)
│
├── commands/              # EXISTING, rewritten
│   ├── map_cmd.py         # now drives run_pipeline
│   └── verify_cmd.py      # mostly unchanged
│
├── cli.py                 # UNCHANGED public surface
├── config.py              # +score_tiebreak_threshold, +llm_tiebreak_top_n
├── project.py             # category_from_lib_id replaced with inline startswith("power:")
├── preflight.py           # +lib_id_coverage_report
├── report.py              # +record_source, +sources field
├── db_fetcher.py          # unchanged
└── default_config.yaml    # +score_tiebreak_threshold, +llm_tiebreak_top_n
```

Tests on `main`:

```
tests/
├── conftest.py                   # NEW — registers --update-golden
├── fixtures/
│   └── minimal_sch.py            # NEW — minimal KiCad-9 schematic factory
├── commands/
│   └── test_map_cmd_new.py       # NEW — CLI-level integration
├── categories/
│   ├── test_base.py              # NEW
│   ├── test_spec_cap.py
│   ├── test_spec_resistor.py
│   ├── test_spec_inductor.py
│   ├── test_spec_led.py
│   ├── test_spec_crystal.py
│   ├── test_spec_ic.py
│   └── test_spec_connector.py
├── components/
│   ├── test_matchers.py
│   ├── test_value_parsers_{cap,resistor,inductor,led,crystal,ic,connector}.py
│   ├── test_value_parsers_accept_lib_id.py  # protocol extension regression
│   ├── test_package_extractors.py
│   ├── test_candidate_sources_{polarized,ceramic,resistor,inductor,led,crystal,ic,connector}.py
│   ├── test_scorers_polarized.py
│   ├── test_scorers_generic.py
│   ├── test_footprint_resolvers.py
│   ├── test_prompt_hooks.py
│   ├── test_prompt_hooks_generic.py
│   └── test_prompt_hooks_ic.py
├── core/
│   ├── test_types_value.py
│   ├── test_types_queryspec.py
│   ├── test_registry.py
│   └── test_registry_ordering.py # new — Device:C_Polarized / Connector / IC catch-all
├── observability/
│   ├── test_trace.py
│   └── test_writer.py
├── golden/
│   ├── conftest.py
│   ├── test_golden.py
│   ├── cases/
│   │   └── polarized_cap_220uf_10v.yaml
│   └── expected/
│       └── polarized_cap_220uf_10v.jsonl
├── test_pipeline_polarized.py
├── test_pipeline_resistor.py
├── test_pipeline_ceramic.py
├── test_pipeline_inductor.py
├── test_pipeline_led.py
├── test_pipeline_crystal.py
├── test_pipeline_ic.py
├── test_pipeline_connector.py
├── test_pipeline_llm_failures.py
├── test_parts_db_execute.py
├── test_report_fallback_counters.py
├── test_preflight_coverage.py
├── test_config_thresholds.py
└── (+ kept legacy: test_parts_db.py, test_project.py, test_config.py,
        test_cli.py, test_schematic*.py, test_preflight.py,
        test_report.py, test_map_cmd.py, test_e2e.py,
        test_db_fetcher.py, test_verify_cmd.py, test_downloader.py,
        test_llm.py)
```
