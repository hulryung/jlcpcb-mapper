# Deferred Work

Known issues and reviewer suggestions that landed in the backlog. Each entry notes severity, origin, and the specific fix if known.

## Important — should address before heavy production use

### D-1. Thread-local SQLite connections (retire `check_same_thread=False`)

- **Origin**: Task 13 code review
- **Location**: `src/jlcpcb_mapper/io/parts_db.py:24` (the `sqlite3.connect(..., check_same_thread=False)` line)
- **Severity**: Important. Correctness-safe (SQLite SERIALIZED mode) but destroys the `ThreadPoolExecutor` parallelism — all DB work serializes to one connection. Symptom: `concurrency=4` in config but pipeline runs at ~1× speed.
- **Fix**: Use `threading.local()` in `PartsDB.__init__` and open a connection lazily per-thread in a `_conn` property. Remove `check_same_thread=False`. Close connections on interpreter shutdown (optional).
- **Test**: Would need a benchmark or a concurrency-timing regression test. Otherwise unit tests won't catch.

### D-2. IC source / DB description Unicode micro-encoding mismatch

- **Origin**: Task 9 code review (applied to cap sources)
- **Location**: `src/jlcpcb_mapper/components/candidate_sources.py` — `_normalize_micro` emits ASCII `u`; actual JLCPCB `parts.db` descriptions may use U+00B5 or U+03BC.
- **Severity**: Important if production DB uses Unicode in descriptions. Spec annotated this at Task 13.
- **Probe** (run against real parts.db):
  ```sql
  SELECT count(*) FROM parts WHERE description LIKE '%µF%';   -- U+00B5
  SELECT count(*) FROM parts WHERE description LIKE '%μF%';   -- U+03BC
  SELECT count(*) FROM parts WHERE description LIKE '%uF%';   -- ASCII
  ```
- **Fix** (if needed): Extend `QuerySpec` with `description_or_patterns: tuple[str, ...]` (OR'd); emit all three variants from `_normalize_micro`. Only implement once evidence shows it's needed.

---

## Suggestion — code quality

### S-1. `Decision.source` vs trace-subtype distinction

- **Origin**: Task 13 code review
- **Detail**: `Decision.source` is {"single","score","llm","failed"}; LLM subtypes (`llm_reject`, `llm_hallucination`, `llm_error_fallback`) live only in the trace. `RunReport.record_source(d.source)` rolls all three into "llm".
- **Impact**: Users wanting per-LLM-mode counts in the run summary must read the trace JSONL. That's the intended use case, but someone may expect the summary to show it.
- **If addressed**: Either (a) extend `Decision.source` to carry the subtype (breaking existing code), or (b) have map_cmd inspect traces and add detailed counts to RunReport before writing. Both are feasible; neither urgent.

### S-2. LEDSpec value convention unguarded

- **Origin**: Task 17 code review
- **Detail**: `LEDSpec(value=Value(0, "RED"))` relies on `magnitude=0` sentinel. `Value.display()` on this returns `"0RED"`. The Spec's own `display()` reads `.unit` directly — correct, but silent if someone adds code that calls `value.display()` accidentally.
- **Fix**: Add `__post_init__` guard in `LEDSpec`:
  ```python
  def __post_init__(self):
      if self.value.magnitude != 0:
          raise ValueError(f"LEDSpec magnitude must be 0, got {self.value.magnitude!r}")
  ```

### S-3. `all_have_fp=True` branch test coverage for categories other than resistor

- **Origin**: Task 14 added this test path; other category pipeline tests don't exercise it.
- **Detail**: Most integration tests use empty footprint → goes through resolver. Only `test_pipeline_resistor.py::test_10k_with_existing_footprint_skips_resolver` covers the bypass path.
- **Fix**: Extend one or two other category pipeline tests (e.g. ceramic cap) to include an instance with a pre-existing footprint.

### S-4. Golden file coverage is 1 case

- **Origin**: Task 27 implementation
- **Detail**: `tests/golden/` has only `polarized_cap_220uf_10v.yaml`. Future regressions in resistor/ceramic/IC/connector paths won't surface as golden-file diffs.
- **Fix**: Add 3–5 more cases. Suggested: one resistor (proves all_have_fp path), one IC (proves LLM path with deterministic stub), one connector 1xN, one 2xN-without-hint (proves failure path).

### S-5. LED THT footprints silently fall back to default_package="0603"

- **Origin**: Task 17 code review
- **Detail**: Regex `^LED_SMD:LED_(\d{4})_` only covers SMD. LED_THT variants produce no hint → default kicks in → almost certainly wrong package suggested.
- **Fix**: Add THT rules, OR document the limitation in `led.py` with a TODO comment.

### S-6. `InductorSpec.value is not None` guard is dead code

- **Origin**: Task 16 code review
- **Detail**: `InductorSpec.value` is typed `Value` (non-Optional). The `if spec.value is not None:` guard in `InductorSource.query` is unreachable. Same pattern in `CeramicCapSource`.
- **Fix**: Remove the guard, or make `value` genuinely Optional if there's a use case.

### S-7. `_XTAL_WITH_PREFIX` doesn't handle mixed-case `hZ`

- **Origin**: Task 18 code review
- **Detail**: Regex alternation `(?:Hz|HZ|hz)?` misses `hZ`. Not seen in real data.
- **Fix** (one-char): `re.IGNORECASE` on the whole regex, or alternation `(?:Hz|HZ|hz|hZ)?`.

### S-8. IC BuiltinMap is empty

- **Origin**: Task 19 design
- **Detail**: Every IC footprint comes from EasyEDA — network required. Some very common IC packages (SOIC-8, SOT-23-3/5/6, QFN-32) could be mapped to KiCad built-ins.
- **Fix**: Populate `_BUILTIN` in `categories/ic.py` with common mappings. Lower priority since EasyEDA works.

### S-9. `Composite.resolve` last-wins ordering docstring
- **Origin**: Task 11 code review, ADDRESSED in `06d09b6`. Kept here for completeness.

### S-10. `EasyedaFallback.downloader` type annotation
- **Origin**: Task 11 code review, ADDRESSED in `06d09b6`. Kept here for completeness.

---

## Note / Informational — no action needed

### N-1. Pipeline Stage 1 drops empty-Value instances

- **Location**: `core/pipeline.py` ~line 75: `if not inst.on_board or not inst.value: continue`
- **Detail**: Connector instances with empty Value fields silently drop. `ConnectorValueParser` is designed to work without value (lib_id is identity), but Stage 1 gate runs first.
- **Recommendation**: Document this at the gate. Change only if real schematics ship connectors with empty values.

### N-2. `QuerySpec.__dict__` usage replaced with `dataclasses.replace` (addressed in `fe3ffd0`)

Already fixed.

### N-3. `Registry.all()` defensive copy untested

- **Origin**: Task 4 review
- **Detail**: `Registry.all()` returns `list(self._categories)` (copy); an untested contract that callers can't mutate the internal list.
- **Fix**: One-line test. Low priority.

### N-4. `test_post_filter_identity` assertion pattern

- **Origin**: Multiple reviews (Task 15, 16, 17)
- **Detail**: Tests use `assert result is rows or result == rows` — tolerant of either identity or equality return. Tightening to `is` only would pin the zero-copy contract.
- **Fix**: Mechanical cleanup.

### N-5. Pyright cross-worktree false positives

- **Detail**: Throughout the execution session, every file edit triggered Pyright "import not resolved" diagnostics. Root cause: the main repo's Pyright language server has the main worktree as root; new files on the `arch-redesign` branch live in the sibling worktree it can't see.
- **Not a bug**. Resolved once the branch is merged or the IDE reopens on the worktree directly. Documented here to save a future debugging session.

### N-6. Existing `tests/test_map_cmd.py` and `tests/test_e2e.py`

- **Detail**: These are pre-redesign tests that still pass after Task 25's import updates. They exercise old patching patterns (`monkeypatch.setattr("jlcpcb_mapper.resolver.download_footprint", ...)` updated to `io.easyeda`). They're kept because they still run green — Task 28 only deleted tests for modules that were deleted.
- **Recommendation**: Keep as long as they pass. They provide additional coverage "for free".

---

## Reviewer suggestions that WERE applied (for auditability)

These were flagged in-session and fixed on the spot — no action needed, but listed here for completeness if someone wants to trace the evolution.

| # | Origin task | Fix commit | What |
|---|---|---|---|
| R-1 | Task 6 | `ecf1094` | Greek mu → micro sign canonicalization in CapValueParser |
| R-2 | Task 9 | `a18e52c` | Test coverage for Greek mu branch in PolarizedCapSource |
| R-3 | Task 10 | `37e1d63` | `VDC`/`VAC` voltage form accepted in regex |
| R-4 | Task 11 | `06d09b6` | Composite last-wins docstring + downloader type annotation |
| R-5 | Task 13 | `fe3ffd0` | `dataclasses.replace` / guarded `next()` / deferred-import comment |
| R-6 | Task 15 | `d5b2e2c` | `CeramicCapSource.limit` aligned to 50 |
| R-7 | Task 19 | `ffc51ab` | `PartsDB.execute` adds `ESCAPE '\\'` for mpn LIKE |
| R-8 | Task 20 | `bf2644b` | `ConnectorSource` SQL LIKE escape |
