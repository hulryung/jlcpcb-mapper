# Architecture Quick Reference

Full detail in `docs/superpowers/specs/2026-04-22-architecture-redesign.md`. This is a condensed overview for someone picking up the work.

## Core idea

Each category owns its complete pipeline logic via composition — a `Category` bundle holding seven pluggable components. The pipeline is generic over categories; adding a new category is one file plus one registration line.

```
lib_id ──► Registry.lookup ──► Category
                                  │
                                  ▼
           ┌──────────────────────┼──────────────────────────┐
           │                      │                          │
      Matcher              ValueParser                PackageExtractor
 (is this my cat?)   (raw text → Spec)              (kicad fp → hint)
           │                      │                          │
           └──────────────────────┴──────────────────────────┘
                                  │
                                  ▼
                           (Spec, hint, refs)
                                  │
                         ┌────────┴─────────┐
                         ▼                  ▼
                  CandidateSource      FootprintResolver
            query + post_filter   (BuiltinMap → EasyEDA)
                         │
                         ▼
                   PartsDB.execute
                         │
                         ▼
                      [rows]
                         │
                         ├── Scorer? ──► if clear winner → done
                         │    (None OK;
                         │     LLM decides)
                         │
                         └── PromptHook ──► LLM tiebreak
                                                │
                                                ▼
                                           Decision
                                        (trace recorded)
```

## Component protocols

Defined in `categories/base.py` as `@runtime_checkable` Protocols. Categories are structural-typed; no explicit base class required.

| Protocol | Signature | Duck-typed by |
|---|---|---|
| `Matcher` | `matches(lib_id: str) -> bool` | `LibIdAny`, `LibIdPrefix`, `_ICMatcher` (private) |
| `ValueParser` | `parse(raw: str, *, lib_id: str \| None = None) -> Spec \| None` | 7 parsers (one per category) |
| `PackageExtractor` | `extract(kicad_footprint: str) -> str \| None` | `RegexFromRules` |
| `CandidateSource` | `query(spec, hint) -> QuerySpec` + `post_filter(rows, spec, hint) -> [PartRow]` | 7 sources (one per category) |
| `Scorer` | `score(row, spec, trace) -> float` (or `None`) | `PolarizedCapScorer`, `GenericBasicStockScorer`, or `None` for LLM-only |
| `FootprintResolver` | `resolve(part, hint) -> ResolveResult` | `BuiltinMap`, `EasyedaFallback`, `Composite` |
| `PromptHook` | `selection_criteria() -> str` + `candidate_payload(row) -> dict` | `CapPromptHook`, `ICPromptHook`, `GenericPromptHook` |

## Per-category `Spec` types

Each category defines its own frozen dataclass in `categories/spec/`. The `Spec` protocol requires `group_key() -> Hashable`, `display() -> str`, `llm_context() -> dict`.

| Category | Spec | Notable fields |
|---|---|---|
| `polarized_capacitor` | `PolarizedCapSpec` | `value`, `voltage` (voltage in group_key!) |
| `ceramic_capacitor` | `CeramicCapSpec` | `value` only |
| `resistor` | `ResistorSpec` | `value` (always in base ohms) |
| `inductor` | `InductorSpec` | `value` with unit H/mH/µH/nH |
| `led` | `LEDSpec` | `Value(0, TOKEN)` — token in unit field |
| `crystal` | `CrystalSpec` | `value` (frequency) |
| `ic` | `ICSpec` | `mpn: str` — no Value wrapper |
| `connector` | `ConnectorSpec` | `structure`, `pins`, `value` — native fields |

## Pipeline stages (`core/pipeline.py`)

```
Stage 1: per-instance
    match → parse → extract_package
    (skips on any failure)

Stage 2: group
    bucket by (category.name, spec.group_key(), package_hint)

Stage 3: per-group (parallel)
    3a. source.query → QuerySpec → db.execute → rows
    3b. source.post_filter → rows'
    3c. _decide:
        - single candidate?       → source="single"
        - scorer available?       → deterministic ranking
            - top−second ≥ τ?     → source="score"
            - else ambiguous      → LLM tiebreak on top-N
        - no scorer?              → LLM on all
            - valid LCSC?         → source="llm"
            - null?               → source="llm", method="llm_reject"
            - not in rows?        → source="llm", method="llm_hallucination"
            - raised?             → source="llm", method="llm_error_fallback"
    3d. resolver.resolve (unless all_have_fp → skip)

Stage 4: apply (sequential)
    schematic.atomic_update with backup
    write_group_traces
    report.write_json
```

## LLM failure modes

All three explicitly recorded in `trace.events[...].data.method`:

- `llm_reject` — LLM returned `{"lcsc": null}` → fallback to `rows[0]`
- `llm_hallucination` — LLM returned an LCSC not in candidates → fallback to `rows[0]`
- `llm_error_fallback` — LLM raised → fallback to `rows[0]`

All three set `Decision.source = "llm"`; the subtype is trace-only. `RunReport.record_source("llm")` rolls them together. The trace file is the authoritative source for per-method counts.

## Registry ordering

Registration order matters because `LibIdAny` and `LibIdPrefix` can overlap:

1. `polarized_capacitor` (claims `Device:CP`, `Device:C_Polarized*` before ceramic_cap grabs `Device:C`)
2. `resistor` (`Device:R`)
3. `ceramic_capacitor` (`Device:C`)
4. `inductor` (`Device:L` — `Device:LED` correctly excluded by underscore boundary)
5. `led` (`Device:LED`)
6. `crystal` (`Device:Crystal`)
7. `connector` (`Connector*` prefix — before IC catch-all)
8. `ic` (catch-all: any `<prefix>:<name>` not claimed above; excludes `Device:`, `power:`, `Connector` via its custom `_ICMatcher`)

Tests: `tests/core/test_registry_ordering.py`.

## Observability outputs

Per map run, under `.jlcpcb-mapper/`:

- `backups/<ts>/` — copies of original schematics (existing)
- `run-<ts>.json` — summary; now includes `sources: {source: count, ...}`
- `traces/<ts>/groups.jsonl` — one line per group with full event trace
- `traces/<ts>/index.json` — ref → line-offset (seed for future `explain <ref>`)

Preflight now calls `lib_id_coverage_report` and, in interactive mode, prompts before continuing if unmatched lib_ids are present.

## Key invariants / gotchas

1. **Trace event order is list order**, not timestamp order. `timestamp_ms` is `time.monotonic()` — monotonic, process-relative, collisions possible at ms boundary. Writer must preserve list order.
2. **Category registration order matters** (see table above). Tests exist at boundaries.
3. **Greek mu (U+03BC) vs micro sign (U+00B5)**: canonicalized to U+00B5 in `CapValueParser`, `InductorValueParser`, `_normalize_micro` (for DB LIKE patterns).
4. **SQL LIKE wildcards** (`%`, `_`): escaped in `ICSource` (via `ESCAPE '\\'`) and `ConnectorSource` (via Python-side replace).
5. **`check_same_thread=False`** on the SQLite connection is a Phase-B concession; see `DEFERRED.md`.
6. **Pipeline Stage 1 gate**: `if not inst.on_board or not inst.value: continue`. Connector instances with empty Value silently drop — see `DEFERRED.md`.
7. **`ConnectorValueParser.parse` never returns None** — lib_id is the identity signal, not value.
8. **`all_have_fp=True` branch**: when all instances in a group already carry a footprint, the resolver is skipped entirely (no download). Tested in resistor pipeline test.
