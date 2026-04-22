# Architecture Redesign — jlcpcb-mapper

**Date:** 2026-04-22
**Status:** Proposed
**Motivation:** Mapping accuracy. Current pipeline spreads each category's logic across five files (`values.py`, `candidates.py`, `footprint.py`, `kicad_fp.py`, `default_config.yaml`), so adding or fixing a category requires coordinated edits across all of them. Concrete failing case: polarized electrolytic capacitors such as `Device:CP` with value `"220uF/10V"` fail at 4 of 5 pipeline stages simultaneously — `lib_id` not matched, voltage dropped in value parsing, no package extraction rule for `CP_Elec_*`, no default package, no built-in footprint mapping, and no `polarized_capacitor` candidate path unless a package hint is already set.

## Goal

Redesign the mapping pipeline so that each category owns its own logic end-to-end (match rules, value parsing, candidate query, scoring, footprint resolution, LLM prompt). Add per-stage observability so accuracy failures are diagnosable without reading source.

Out of scope:
- Schematic text round-trip (`schematic.py`) — keep as-is, validated asset.
- CLI surface (`map`, `verify`, `init`, `fetch-db`) — keep.
- Config file location and preflight behaviors that already exist (git clean, DB freshness, claude smoke check) — keep.

## Design decisions

| Axis | Choice | Rationale |
|---|---|---|
| Category representation | Python code (not YAML) | Value parsing and candidate logic need Python expressiveness; users of this tool are developers. |
| Category internal shape | Composition of components (not monolithic) | Enables reuse across similar categories (resistor/ceramic-cap/LED differ only in value parser) and per-component unit testing. |
| Value model | Per-category `Spec` dataclass | Avoids ad-hoc optional fields; richer information (voltage, tolerance) preserved only where meaningful. |
| PartsDB contract | `QuerySpec` record + category `post_filter` | Layer separation preserved; category-specific post-processing is explicit. |
| LLM usage | Shared skeleton + per-category prompt hook + optional scorer | Deterministic scoring wherever objective; LLM used as tiebreaker on ambiguous cases or where scoring is infeasible (IC/connector). |
| Observability | Per-stage structured trace, JSONL | Accuracy cycle requires knowing which stage rejected what. |

Options considered and rejected:
- YAML-declarative categories — primitive catalog would bloat; escape-hatch to Python eval would combine both systems' downsides.
- Monolithic `Category` class with all methods — inheritance tree becomes deep as base classes accumulate for each shared axis.
- Unified `Value` with all optional fields — type system allows invalid combinations (resistor with dielectric); LLM prompt code fills with optional checks.
- PartsDB method per category — reverses layering; PartsDB ends up knowing about category names.
- LLM owning the full selection — observed failure cases show most errors are pre-LLM (candidate pool wrong); objective categories deserve deterministic ranking.
- Keeping the 2nd-pass review step — with richer `Spec` group keys, most "same value/package, different LCSC" inconsistencies are prevented at grouping.

## Architecture — module map

```
jlcpcb_mapper/
├── core/
│   ├── types.py          # Value, QuerySpec, Trace event types, Spec protocol
│   ├── registry.py       # Category registry (lib_id → Category lookup)
│   └── pipeline.py       # Pipeline orchestration + trace recording
│
├── categories/
│   ├── base.py           # Category dataclass + component protocols
│   ├── resistor.py
│   ├── ceramic_cap.py
│   ├── polarized_cap.py
│   ├── inductor.py
│   ├── led.py
│   ├── crystal.py
│   ├── ic.py
│   ├── connector.py
│   └── spec/
│       ├── cap.py        # CeramicCapSpec, PolarizedCapSpec
│       ├── resistor.py   # ResistorSpec
│       ├── ...
│
├── components/
│   ├── matchers.py            # LibIdAny, LibIdPrefix, LibIdRegex
│   ├── value_parsers.py       # ResistorValueParser, CapValueParser(keep_voltage=...)
│   ├── package_extractors.py  # RegexFromRules (replaces footprint.py)
│   ├── candidate_sources.py   # QuerySpec builders + post_filter implementations
│   ├── scorers.py             # Per-category deterministic scorers
│   ├── footprint_resolvers.py # BuiltinMap, EasyedaFallback, Composite
│   └── prompt_hooks.py        # selection_criteria, candidate_payload
│
├── io/
│   ├── schematic.py      # UNCHANGED — text round-trip
│   ├── parts_db.py       # Thin: db.execute(QuerySpec) -> [PartRow]
│   ├── easyeda.py        # Was downloader.py
│   └── llm.py            # Claude CLI transport (schema/transport shared)
│
├── commands/
│   ├── map_cmd.py        # Runs pipeline, writes traces
│   ├── verify_cmd.py
│   └── fetch_db_cmd.py
│
├── observability/
│   ├── trace.py          # Trace, TraceEvent, GroupTrace
│   └── report.py         # RunReport summary + trace emission
│
└── cli.py                # UNCHANGED click entrypoints
```

Dependency direction: `cli → commands → core.pipeline → {categories, io, observability}`. Categories reference only `components/` and `core/types.py`. Categories do not know about the pipeline.

## Category composition

```python
# core/types.py
@dataclass(frozen=True)
class Value:
    magnitude: float
    unit: str  # "Ω" | "µF" | "µH" | "V" | ...
    def display(self) -> str: ...

@dataclass(frozen=True)
class QuerySpec:
    category_like: str
    package: str | None = None
    description_patterns: tuple[str, ...] = ()
    mpn_patterns: tuple[str, ...] = ()
    min_stock: int = 0
    order_by: str = "basic DESC, preferred DESC, stock DESC"
    limit: int = 50

class Spec(Protocol):
    def group_key(self) -> Hashable: ...
    def display(self) -> str: ...
    def llm_context(self) -> dict: ...
```

```python
# categories/base.py
class Matcher(Protocol):
    def matches(self, lib_id: str) -> bool: ...

class ValueParser(Protocol):
    def parse(self, raw: str) -> Spec | None: ...

class PackageExtractor(Protocol):
    def extract(self, kicad_footprint: str) -> str | None: ...

class CandidateSource(Protocol):
    def query(self, spec: Spec, package_hint: str) -> QuerySpec: ...
    def post_filter(self, rows: list[PartRow], spec: Spec, package_hint: str) -> list[PartRow]: ...

class Scorer(Protocol):
    def score(self, row: PartRow, spec: Spec, trace: Trace) -> float: ...

class FootprintResolver(Protocol):
    def resolve(self, part: PartRow, package_hint: str) -> ResolveResult: ...

class PromptHook(Protocol):
    def selection_criteria(self) -> str: ...
    def candidate_payload(self, row: PartRow) -> dict: ...

@dataclass(frozen=True)
class Category:
    name: str
    matcher: Matcher
    value_parser: ValueParser
    package_extractor: PackageExtractor
    default_package: str
    candidate_source: CandidateSource
    scorer: Scorer | None  # None = pipeline always uses LLM
    footprint_resolver: FootprintResolver
    prompt_hook: PromptHook
```

Canonical example — the `220uF/10V` case that motivates the redesign:

```python
# categories/polarized_cap.py
POLARIZED_CAP = Category(
    name="polarized_capacitor",
    matcher=matchers.LibIdAny(["Device:CP", "Device:CP_Small",
                                "Device:C_Polarized", "Device:C_Polarized_Small"]),
    value_parser=value_parsers.CapValueParser(keep_voltage=True),
    package_extractor=package_extractors.RegexFromRules([
        (r"^Capacitor_SMD:CP_Elec_(\d+\.?\d*x\d+\.?\d*)",
         lambda m: f"D{m.group(1).split('x')[0]}"),
        (r"^Capacitor_THT:CP_Radial_D(\d+\.?\d*)mm",
         lambda m: f"D{m.group(1)}mm"),
    ]),
    default_package="D6.3mm",
    candidate_source=candidate_sources.PolarizedCapSource(),
    scorer=scorers.PolarizedCapScorer(),  # voltage exact match weighted, basic>preferred>stock
    footprint_resolver=footprint_resolvers.Composite([
        footprint_resolvers.BuiltinMap({...}),
        footprint_resolvers.EasyedaFallback(),
    ]),
    prompt_hook=prompt_hooks.CapPromptHook(emphasize_voltage=True),
)
```

```python
# categories/spec/cap.py
@dataclass(frozen=True)
class PolarizedCapSpec:
    value: Value            # 220µF
    voltage: Value | None   # 10V — included in group_key (unlike ceramic cap)

    def group_key(self): return ("polarized_cap", self.value, self.voltage)
    def display(self):
        v = f"/{self.voltage.display()}" if self.voltage else ""
        return f"{self.value.display()}{v}"
    def llm_context(self):
        return {"value": self.value.display(),
                "voltage": self.voltage.display() if self.voltage else None}
```

Adding a new category: one `categories/<name>.py` bundle, optional `categories/spec/<name>.py`, optional new component in `components/` when existing building blocks are insufficient, one line in `registry.py`.

## Pipeline

Stages:
1. **Per-instance**: `match` → `parse` → `extract_package`. Skips the instance if match or parse fails. Falls back to `default_package` if extraction fails.
2. **Grouping**: bucket by `(category.name, spec.group_key(), package_hint)`. `Spec.group_key` is what determines whether `220µF/10V` and `220µF/25V` are separate groups.
3. **Per-group** (parallel via `ThreadPoolExecutor(max_workers=config.llm.concurrency)`):
   - **3a** `candidate_source.query(spec, package_hint)` → `QuerySpec` → `db.execute(QuerySpec)` → rows
   - **3b** `candidate_source.post_filter(rows, spec, package_hint)` → rows'
   - **3c** `_decide(category, group, rows')`:
     - If `len(rows') == 1` → `source="single"`, done.
     - Else if `category.scorer is not None`:
       - Compute scores, sort descending.
       - If `top - second ≥ score_tiebreak_threshold` → top1, `source="score"`, done.
       - Else narrow to top-`llm_tiebreak_top_n`, go to LLM.
     - Else (no scorer) → LLM on all rows.
     - LLM path: build prompt via `prompt_hook`, call, parse.
       - LLM returns a candidate LCSC present in the rows → use it, `source="llm"`.
       - LLM returns `null` → top1 fallback, `source="llm"`, trace `decide.method="llm_reject"`.
       - LLM returns an LCSC not in the rows → top1 fallback, `source="llm"`, trace `decide.method="llm_hallucination"`.
       - LLM raises — top1 fallback, `source="llm"`, trace `decide.method="llm_error_fallback"`.
   - **3d** `footprint_resolver.resolve(chosen_part, package_hint)`. If every instance in the group already has a non-empty footprint, skip the resolver entirely (no download needed). This is the same guard the current pipeline applies after the `--fill-lcsc-only` fix.
4. **Apply**: group decisions by schematic file. For each instance, write `lcsc = chosen`, and write `footprint = resolution.footprint` only if the instance's existing footprint is empty. Uses `schematic.atomic_update` with timestamped backups — unchanged.

Configuration additions:
- `score_tiebreak_threshold: float = 0.1`
- `llm_tiebreak_top_n: int = 5`

The existing 2nd-pass `review_mapping` step is removed. With `Spec.group_key` carrying full rating info (voltage for polarized cap, etc.), the "same value/package → different LCSC" inconsistency it was guarding against is prevented at grouping time.

## Observability

Each group carries a `Trace` — an ordered list of `TraceEvent(stage, data, timestamp_ms)`. Stages recorded:

| Stage | Data |
|---|---|
| `match` | `lib_id`, `category` (or `None`) |
| `parse` | `raw_value`, `spec` display (or `parse_failed`) |
| `extract` | `kicad_footprint`, `package` (or fallback reason) |
| `query` | Full `QuerySpec` fields |
| `query_result` | Row count |
| `post_filter` | `before`, `after`, `dropped: {reason: count}` |
| `score` | Top-3 `(lcsc, score, breakdown)` |
| `decide` | `method ∈ {single, score, llm, llm_reject, llm_error_fallback, llm_hallucination}`, chosen LCSC, reason |
| `resolve` | Resolver used (`builtin` | `easyeda`), footprint, downloaded flag |
| `apply` | Schematic file, fields written |

Outputs under the project root:
```
.jlcpcb-mapper/
├── backups/<ts>/...               # unchanged
├── run-<ts>.json                  # RunReport summary (unchanged shape; human-oriented)
└── traces/<ts>/
    ├── groups.jsonl               # one GroupTrace per line
    └── index.json                 # ref → group_offset (seed for future `explain` command)
```

Scorers receive the active `Trace` and record their own breakdown (`Scorer.score(row, spec, trace)`) rather than returning structured data, keeping the protocol signature small.

The `explain <ref>` CLI command is deferred. `index.json` is written now so it can be added as a thin wrapper later.

## Error handling

| Failure | Where | Behavior | Trace |
|---|---|---|---|
| parts.db missing / git dirty / claude down | preflight | abort with `PreflightError` | — |
| `registry.lookup` returns None | Stage 1 match | skip instance; counted in RunReport | `match.unknown_lib_id` |
| `parser.parse` returns None | Stage 1 parse | skip instance; counted | `parse.failed` |
| package extraction miss | Stage 1 extract | fall back to `default_package` | `extract.fallback_to_default` |
| zero candidates after post_filter | Stage 3b | `Decision.failure="no_candidates"`; continue other groups | `post_filter.empty` with drop reasons |
| scorer tie + LLM error | Stage 3c | top1 fallback | `decide.llm_error_fallback` |
| LLM returns LCSC not in candidates | Stage 3c | top1 fallback | `decide.llm_hallucination` |
| footprint resolve all paths fail | Stage 3d | Decision succeeds with empty footprint + failure | `resolve.all_failed` |
| schematic write fails | Stage 4 | rollback that file's `.tmp`; continue other files | `apply.write_failed` |

Policy shift vs. current code: **LLM failures are always explicit in traces, and the RunReport summary increments a "LLM fallback" warning counter.** Current code silently falls back to `candidates[0]`.

Preflight enhancement: after loading schematics and before running the pipeline, list every `lib_id` present, grouped by whether the registry has a match. If any `lib_id` is unmatched and the session is interactive, require user confirmation before continuing. This prevents silent mass-skips at Stage 1.

Edge cases (explicit decisions):
- **Same value/package but different existing footprint variants** → package extractor yields the same size key; grouped together. Trace retains originals.
- **Resistor symbol with capacitor value string** (`Device:R` value `"10uF"`) → `ResistorValueParser.parse` returns None → skipped with clear trace. User-error detection.
- **Composite value strings** (`"100k 0.1%"`) → first token parsed; extra tokens dropped. Tolerance fields can be added to `ResistorSpec` later without pipeline changes.
- **DNP / not-on-board** → filtered at target selection (same as current).
- **EasyEDA concurrent download of same LCSC** → last write wins; content identical. No locking needed.
- **`query_result.count == limit`** → boundary signal in trace; limit remains fixed initially.
- **Duplicate lib_id registration** → `registry.register` raises at import time.

## Testing

Layer 1 — **Component unit tests** (largest, fastest). Pure inputs/outputs.
```
tests/components/
├── test_matchers.py
├── test_value_parsers.py         # Spec-comparison upgrade from test_values.py
├── test_package_extractors.py    # ports test_footprint.py
├── test_candidate_sources.py
├── test_scorers.py
└── test_footprint_resolvers.py
```

Layer 2 — **Category bundle tests**: one or two representative cases per category, end-to-end through the bundle against an in-memory SQLite fixture.

Layer 3 — **Pipeline integration tests**: fake LLM, fake EasyEDA, fixture DB. Cover each `_decide` branch (`single`, `score`, `llm`, `llm_reject`, `llm_error_fallback`, `llm_hallucination`).

Layer 4 — **Trace golden-file regression tests**:
```
tests/golden/
├── cases/
│   ├── resistor_10k_0402.yaml
│   ├── polarized_cap_220uf_10v.yaml
│   └── ic_stm32g0.yaml
└── expected/
    ├── resistor_10k_0402.jsonl
    └── ...
```
Each test runs the pipeline on the input case, normalizes timestamps out of the produced JSONL, and compares to the golden file. `--update-golden` flag regenerates. This makes improvements visible as reviewable diffs.

Layer 5 — **Schematic round-trip**: `tests/test_schematic.py`, `test_schematic_write.py` unchanged.

Layer 6 — **Live** (`@pytest.mark.live`): real LLM, real EasyEDA, real parts.db. Opt-in.

Test fakes:
```python
class FakeLLM:
    """Scriptable. Records all call prompts."""
class FakeEasyedaResolver:
    """Returns predetermined footprint text per LCSC."""
```
PartsDB tests use `sqlite3.connect(":memory:")` with the same schema as production.

Migration of existing tests:
- `test_values.py` → `tests/components/test_value_parsers.py` (Spec comparisons)
- `test_footprint.py` → `tests/components/test_package_extractors.py` (direct)
- `test_kicad_fp.py` → `tests/components/test_footprint_resolvers.py` (`BuiltinMap`)
- `test_candidates.py` → `tests/components/test_candidate_sources.py` (`QuerySpec` assertions)
- `test_grouper.py` → `tests/test_pipeline.py` (Stage 2)
- `test_select.py` → `tests/test_pipeline.py` (`_decide` branches)
- `test_resolver.py` → `tests/components/test_footprint_resolvers.py` (`Composite`)
- `test_review.py` → **deleted** (2nd-pass review is removed)
- `test_schematic*.py`, `test_config.py`, `test_cli.py`, `test_project.py`, `test_report.py`, `test_parts_db.py`, `test_db_fetcher.py`, `test_preflight.py`, `test_map_cmd.py`, `test_verify_cmd.py` → kept with interface adjustments
- `test_downloader.py`, `test_llm.py`, `test_e2e.py` → `tests/live/` with `@pytest.mark.live`

Initial coverage targets:
- Component layer: ≥90% per component (pure functions).
- Category layer: 1–2 representative cases per category.
- Pipeline layer: every `_decide` branch hit once.
- Golden layer: 1–2 cases per category, grown opportunistically as bugs are fixed.

## Behavior preserved vs. current

- CLI surface and flags unchanged.
- `schematic.py` and `schematic.atomic_update` unchanged — byte-identical round-trip preserved.
- `preflight` git/DB/claude checks unchanged (extended with coverage report).
- Existing footprint on an instance is preserved when writing (`fp_to_write = "" if inst.footprint else resolution.footprint`).
- Skip resolver entirely when every instance in a group already has a footprint (no unnecessary EasyEDA calls).
- Backup directory layout (`.jlcpcb-mapper/backups/<ts>/`) unchanged.
- `RunReport.to_text()` and `run-<ts>.json` shape unchanged (new fields additive).

## Behavior changed vs. current

- Group keys include category-specific rating fields (e.g., voltage for polarized capacitors). Symbols that used to collapse into one group will now split when their ratings differ.
- 2nd-pass review step removed.
- LLM failures are surfaced in the RunReport summary (previously silent top1 fallback).
- EasyEDA download failure records the underlying exception type (previously swallowed by bare `except`).
- Preflight lists unmatched `lib_id`s and requires confirmation in interactive mode.
- Traces written to `.jlcpcb-mapper/traces/<ts>/groups.jsonl`.

## Open items deferred to implementation plan

- Exact scoring weights per category (`PolarizedCapScorer`, `CeramicCapScorer`, etc.) — tuned against golden cases during implementation.
- Initial contents of `BuiltinMap` for polarized capacitors, crystals, and non-resistor/ceramic categories.
- Whether to extract `components/` into its own sub-package or keep flat — to be decided once the full component list stabilizes.
- `explain <ref>` CLI command — deferred; trace index.json is written so it can be added later.
