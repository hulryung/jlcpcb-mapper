# Annotated Commit Log

46 commits on `arch-redesign`, branched from `13e8f57` on `main`. Listed in chronological order (oldest first).

## Phase A — Core scaffolding (4 commits)

| # | SHA | Commit | Notes |
|---|---|---|---|
| 1 | `472dd35` | feat(core): add Value dataclass for magnitude/unit pairs | Task 1. Frozen dataclass, `display()` handles integer vs fractional. |
| 2 | `cd05a40` | feat(core): add QuerySpec and Spec protocol | Task 2. Plan heading "PartRow re-export" was stale — removed post-review. |
| 3 | `de3b96b` | feat(observability): add Trace and TraceEvent | Task 3. Reviewer flagged monotonic-timestamp ordering; carried into Task 21 constraint. |
| 4 | `262948b` | feat(categories,core): Category bundle + Registry with protocols | Task 4. 7 protocols + frozen `Category`. Skipped the plan's try/except PartRow shim — direct import. |

## Phase B — Polarized cap end-to-end (9 + 2 follow-ups)

| # | SHA | Commit | Notes |
|---|---|---|---|
| 5 | `901dafd` | feat(components): LibIdAny and LibIdPrefix matchers | Task 5. |
| 6 | `2566954` | feat(components,spec): CapValueParser + Ceramic/Polarized cap specs | Task 6. |
| 7 | `ecf1094` | fix(components): canonicalize Greek mu (U+03BC) to micro sign in CapValueParser | **Task 6 follow-up R-1**. Prevents silent group_key splits. |
| 8 | `103961f` | feat(components): RegexFromRules package extractor | Task 7. |
| 9 | `00236c8` | feat(parts_db): add PartsDB.execute(QuerySpec) alongside legacy method | Task 8. Coexistence during migration; `query_candidates` removed in `f4645f7`. |
| 10 | `29547f8` | feat(components): PolarizedCapSource with voltage post-filter | Task 9. |
| 11 | `a18e52c` | test(components): cover Greek mu branch in PolarizedCapSource._normalize_micro | **Task 9 follow-up R-2**. Coverage for the Greek-mu fix in source. |
| 12 | `2a3e862` | feat(components): PolarizedCapScorer with voltage-aware weighting | Task 10. |
| 13 | `37e1d63` | fix(components): accept concatenated VDC/VAC voltage forms | **Task 10 follow-up R-3**. Regex was missing `VDC`/`VAC` forms. |
| 14 | `6b7054a` | feat(components): BuiltinMap + EasyedaFallback + Composite resolvers | Task 11. |
| 15 | `06d09b6` | chore(components): document Composite last-wins + type EasyedaFallback.downloader | **Task 11 follow-up R-4**. Docstring + type annotation from code review. |
| 16 | `ccf92fb` | feat(components): CapPromptHook with voltage-aware criteria | Task 12. |
| 17 | `c99634d` | feat(pipeline): wire POLARIZED_CAP end-to-end; 220µF/10V integration passes | **Task 13 — Phase B acceptance gate**. Added `check_same_thread=False` (tracked as D-1); introduced deferred registry import. |
| 18 | `fe3ffd0` | chore(pipeline,categories): reviewer polish from Task 13 | **Task 13 follow-up R-5**. `dataclasses.replace`, guarded `next()`, deferred-import comment. |

## Phase C — Remaining categories (7 + 1 follow-up)

| # | SHA | Commit | Notes |
|---|---|---|---|
| 19 | `f1f0a1a` | feat(spec): add ResistorSpec dataclass with group_key/display/llm_context | Task 14 start. |
| 20 | `0dee052` | feat(value-parsers): add ResistorValueParser; handle kΩ/MΩ/0Ω/slash-split forms | Task 14 continued. Preserves legacy `m = mega` quirk. |
| 21 | `d428952` | feat(candidate-sources): add ResistorSource with SI-pattern query and identity post_filter | Task 14 continued. Leading-space invariant in patterns. |
| 22 | `3e57b4c` | feat(components): add GenericBasicStockScorer and GenericPromptHook; extract _common_candidate_payload helper | Task 14 continued. Shared payload helper across prompt hooks. |
| 23 | `f3bed0d` | feat(categories): wire RESISTOR category end-to-end; register in default_registry; add integration tests proving all_have_fp and BuiltinMap paths | Task 14 complete. First test to exercise the `all_have_fp=True` branch. |
| 24 | `06a3ddd` | feat(candidate-sources): add CeramicCapSource with µ/μ→u normalization and identity post_filter | Task 15. |
| 25 | `e271221` | feat(categories): add CERAMIC_CAP category bundle; register with ordering guard against Device:C_Polarized collision | Task 15 complete. First registry-ordering regression test. |
| 26 | `d5b2e2c` | chore(candidate-sources): align CeramicCapSource limit default to 50 | **Task 15 follow-up R-6**. |
| 27 | `ab123b9` | feat(inductor): add InductorSpec, InductorValueParser, InductorSource with TDD | Task 16 components. |
| 28 | `5f7899d` | feat(categories): wire INDUCTOR category end-to-end; register in default_registry | Task 16 complete. Empty BuiltinMap; proves EasyedaFallback path. |
| 29 | `2acbd12` | feat(led): add LEDSpec, LEDValueParser, LEDSource with TDD | Task 17 components. Introduces `Value(0, TOKEN)` convention. |
| 30 | `f170983` | feat(categories): wire LED category end-to-end; register in default_registry | Task 17 complete. BuiltinMap hit path. |
| 31 | `0e61db1` | feat(categories): wire Crystal category end-to-end; register in default_registry | Task 18. Single commit for all components. `scorer=None` for lib_ids without SMD package rules. |
| 32 | `6f99c63` | feat(task19): IC category — catch-all with LLM path and MPN-based matching | Task 19. Introduces `_ICMatcher` with exclusion list. |
| 33 | `ffc51ab` | fix(parts_db): add ESCAPE clause for mpn_patterns LIKE queries | **Task 19 follow-up R-7**. SQL injection / LIKE wildcard escaping. |
| 34 | `2d7ef63` | feat(protocol): extend ValueParser.parse with optional lib_id kwarg | **Task 20 — protocol extension**. All 6 existing parsers updated to accept/ignore `lib_id=`. 6 regression tests. |
| 35 | `56993e9` | feat(connector): add ConnectorSpec, ConnectorValueParser, ConnectorSource | Task 20 components. |
| 36 | `3d10f3c` | feat(connector): wire Connector category into registry; add integration tests | Task 20 complete. 3 integration cases: 1xN-LLM, 2xN-no-hint-fails, generic-fails. |
| 37 | `bf2644b` | fix(connector): escape SQL LIKE wildcards in ConnectorSource.query | **Task 20 follow-up R-8**. |

## Phase D — Observability (4 commits)

| # | SHA | Commit | Notes |
|---|---|---|---|
| 38 | `94cfc77` | feat(observability): JSONL trace writer with ref-to-line index | Task 21. Preserves list order not timestamp. |
| 39 | `ac3eb56` | feat(report): per-source decision counters surfaced in to_text/to_dict | Task 22. `asdict` picks up the new `sources` field automatically. |
| 40 | `605a9ba` | feat(preflight): add lib_id_coverage_report for unmatched-symbol detection | Task 23. |
| 41 | `1f18a9c` | test(pipeline): regression tests for LLM failure modes | Task 24. Pins `decide.method` trace values for 4 branches. |

## Phase E — Migration (5 commits)

| # | SHA | Commit | Notes |
|---|---|---|---|
| 42 | `675f869` | refactor: relocate parts_db/schematic/easyeda/llm under io/ | Task 25. `downloader.py` renamed to `easyeda.py`. 48 import updates. |
| 43 | `77c6957` | refactor(map_cmd): drive new pipeline end-to-end | Task 26. **Critical switchover**. Introduces `tests/fixtures/minimal_sch.py` + CLI-level integration test. |
| 44 | `39d26e4` | test(golden): regression harness + polarized_cap 220µF/10V baseline | Task 27. Locks the motivating case. |
| 45 | `f4645f7` | refactor: remove legacy category-specific modules and tests | Task 28. 8 sources + 8 tests + `query_candidates` removed. Test count 486 → 383. `project.py` lost `category_from_lib_id` import (inlined). |
| 46 | `26a25fe` | chore: surface pipeline thresholds in config; document traces in README | Task 29. Final task. Config fields replace `getattr` placeholders. README Observability section. |

## Commit-count evolution

```
Phase A:   0 →   4   (+4,   16 tests:   154 → 170)
Phase B:   4 →  18   (+14, +39 tests:   170 → 209)   — 220µF/10V gate met
Phase C:  18 →  37   (+19,+255 tests:   209 → 464)
Phase D:  37 →  41   (+4,  +19 tests:   464 → 483)
Phase E:  41 →  46   (+5,  −97 tests:   483 → 386)   — net negative from legacy-test deletion
```
