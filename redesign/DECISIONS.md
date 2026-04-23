# Key Design Decisions

Non-obvious choices made during implementation. Each entry: what was chosen, what was rejected, and why.

---

## D1. Categories are composition bundles, not classes

**Chosen**: `Category` is a frozen dataclass holding 7 component fields. Components are duck-typed instances of @runtime_checkable Protocols.

**Rejected**: Monolithic `Category` class with all logic as methods (and inheritance for shared behavior).

**Why**: Failure modes from the original code (Greek mu, voltage drop, MPN search differences) all map to one component swap, not a class restructure. Composition lets `CapValueParser(keep_voltage=True/False)` produce two different specs from one parser. Inheritance trees would have duplicated this distinction.

---

## D2. Per-category `Spec` dataclasses (not unified rich `Value`)

**Chosen**: Each category defines its own Spec (`PolarizedCapSpec`, `ICSpec`, `ConnectorSpec`, etc.). Common protocol surface: `group_key()`, `display()`, `llm_context()`.

**Rejected**: Single `Value(magnitude, unit, voltage=None, tolerance=None, ...)` with optional fields per category.

**Why**: Type system protects against invalid combinations (resistor with dielectric). Group keys naturally include only relevant fields (voltage matters for electrolytic, not ceramic). LLM prompt code stays free of optional-checks.

**Inconsistency to be aware of**: Three idioms emerged in practice:
- `CeramicCapSpec(value: Value)` — the "clean" single-Value pattern
- `LEDSpec(value: Value)` with `Value(0, TOKEN)` — Value abused as token holder
- `ICSpec(mpn: str)`, `ConnectorSpec(structure, pins, value)` — native string/int fields

The three idioms exist because the categories really are different. We could unify on the third (always native fields) in a future cleanup but the cost-benefit is poor.

---

## D3. Hybrid LLM strategy: scorer + LLM tiebreak

**Chosen**: Each Category has an optional `Scorer`. When provided, deterministic ranking decides if `top - second ≥ score_tiebreak_threshold`; otherwise LLM acts as tiebreaker on top-N. When `scorer=None` (IC, Connector), LLM decides unconditionally.

**Rejected**: LLM-only (current code), or scorer-only (no fallback for ambiguous cases).

**Why**: The original "LLM decides everything" approach makes resistor selection nondeterministic and expensive. Scoring resistors/caps/LEDs/inductors is straightforward (basic > preferred > stock); ICs and connectors genuinely need LLM judgment.

---

## D4. Strangler migration, not in-place refactor

**Chosen**: New code lives in new packages (`core/`, `categories/`, `components/`, `observability/`). Legacy modules untouched until Task 28 deletes them in one commit.

**Rejected**: Transform legacy files in place.

**Why**: Strangler pattern lets every commit pass tests. Legacy code remains as a reference during migration. Final deletion happens after every call site has been migrated and re-tested.

---

## D5. `ValueParser.parse(raw, *, lib_id=None)` protocol extension (Task 20)

**Chosen**: When connectors needed lib_id to determine 1xN/2xN/generic structure, the protocol gained a keyword-only `lib_id` parameter. All 6 existing parsers updated to accept-and-ignore it (one-line change per parser).

**Rejected alternatives**:
- (a) Wrapper layer that maps `(lib_id, value) → Spec` in pipeline Stage 1 — adds indirection.
- (b) Connector-specific Stage 1 hook — pipeline gains category awareness.
- (c) Pre-process value to embed lib_id (e.g., `parse(f"[{lib_id}]{value}")`) — fragile, encoding-sensitive.

**Why**: Backward-compatible (keyword-only with default), one-character call site change in pipeline, six trivial parser changes. Regression tests in `test_value_parsers_accept_lib_id.py` lock the behavior.

---

## D6. `check_same_thread=False` on the SQLite connection

**Chosen**: `sqlite3.connect(..., check_same_thread=False)` so the single PartsDB instance can be shared across `ThreadPoolExecutor` workers in `_process_group`.

**Rejected**: Per-thread connections (correct fix, deferred to Phase E+).

**Why**: Pragmatic Phase-B unblock. SQLite is compiled in SERIALIZED mode in CPython so concurrent reads serialize internally — correct, not corrupting. But the shared connection bottlenecks all DB work to one thread, defeating the parallelism.

**Tracked**: See `DEFERRED.md` — "thread-local connections" is the intended cleanup.

---

## D7. `Decision.source` collapses LLM subtypes; trace.method preserves them

**Chosen**: `Decision.source ∈ {"single", "score", "llm", "failed"}`. The three LLM failure modes (`llm_reject`, `llm_hallucination`, `llm_error_fallback`) all set `source="llm"` but record the distinct method in `trace.events[...].data.method`.

**Rejected**: Surface all 7 sources directly in `Decision.source`.

**Why**: `RunReport.sources` counter stays small for the human summary (`single`/`score`/`llm`/`failed`). Trace file is the authoritative source for diagnostic detail. Splitting into 7 categories at the Decision level would require updates to `RunReport.to_text` formatting and downstream callers; we already had Task 22 done with the simpler shape.

**Tradeoff**: Code that wants per-LLM-method counts must read traces. Acceptable for the diagnostic use case (you go to the trace anyway when LLM fails).

---

## D8. Greek mu canonicalization is defense-in-depth

**Chosen**: Canonicalize μ (U+03BC) → µ (U+00B5) in three places:
- `CapValueParser._parse_cap_value` — input normalization
- `InductorValueParser._L_UNIT_CANON` — input normalization
- `_normalize_micro` in candidate_sources.py — DB LIKE pattern

**Why**: Schematic Value fields and DB descriptions both come from inconsistent sources. A failure on either side silently splits groups. Canonicalizing at all three boundaries makes the full pipeline encoding-safe.

**Note**: The third (`_normalize_micro`) handles μ → ASCII `u` for DB description LIKE, since `parts.db` descriptions historically use ASCII `uF`/`uH`.

---

## D9. `ICSpec` uses native `mpn: str`, not `Value(0, MPN)`

**Chosen**: `ICSpec(mpn: str)` with native field.

**Rejected**: Same `Value(0, TOKEN)` convention as LED.

**Why**: ICs will likely grow more fields (variant, revision, package family). Named field is clearer than abusing Value's magnitude=0 as a sentinel. LED's `Value(0, TOKEN)` was a Phase-C-velocity choice that we'd rewrite if doing it again, but it's harmless and tested. Don't churn it now.

---

## D10. Connector matcher is a bare `LibIdPrefix(["Connector"])`, classification happens in the parser

**Chosen**: One broad matcher catches all `Connector*` lib_ids; `ConnectorValueParser.parse` then runs regex on lib_id to set `structure ∈ {"1xN", "2xN", "generic"}` and `pins`.

**Rejected**: Three separate matchers + three separate sources.

**Why**: One Category bundle keeps the registry small. The structure isn't a registry-routing concern; it's a parsing concern. The parser handles it cleanly via two regexes.

---

## D11. IC matcher excludes `Device:`, `power:`, `Connector` prefixes

**Chosen**: `_ICMatcher` (private to `categories/ic.py`) returns True for any lib_id with `:` UNLESS it starts with one of three excluded prefixes.

**Rejected**: Wildcard matcher — but registry order alone protects.

**Why**: Belt and suspenders. Order alone (IC last) would work, but defining the exclusion explicitly in the matcher means a future reordering doesn't silently break. Both protections tested.

---

## D12. Golden-file tests strip `timestamp_ms`

**Chosen**: `normalize_jsonl()` zeros `timestamp_ms` before comparison.

**Why**: `time.monotonic()` is non-deterministic. The semantic content (stage names, decision data, scoring) is what we lock in. Timing data is informational only.

---

## D13. `--update-golden` lives in root `tests/conftest.py`, not `tests/golden/conftest.py`

**Chosen**: Root-level pytest_addoption so the flag is recognized whether you run from the repo root or `cd tests/golden && pytest`.

**Why**: Initial implementation put it in both files → "option already added" error. Root-only is the simplest fix. `tests/golden/conftest.py` keeps `pytest_generate_tests` for case parametrization but no `pytest_addoption`.

---

## D14. Deferred Registry import in `categories/__init__.py`

**Chosen**: `from ..core.registry import Registry` lives inside `default_registry()` body, not at module top.

**Why**: Avoid circular import (`core.pipeline → core.registry → categories.base → categories/__init__ → core.registry`). Function-local import breaks the cycle without restructuring. Comment in source explains why; future contributors won't be tempted to "clean up" the placement.
