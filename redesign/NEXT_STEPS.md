# Next Steps

The 29-task plan is merged to `main`. What to consider next.

## What's already done

- ✅ **All 29 tasks implemented** — 386 tests passing
- ✅ **Merge to `main`** — fast-forward (after rebase onto the 3 in-flight plan annotations)
- ✅ **`arch-redesign` branch deleted** — linear history preserved
- ✅ **Sibling worktree cleaned up** — only the main worktree remains
- ✅ **Handoff docs committed** to `redesign/`

## What to tackle (ordered by ROI)

### Most impactful

1. **Probe real parts.db for Unicode mu variants** (DEFERRED `D-2`)
   - One-shot SQL query against the user's actual `parts.db`
   - If Unicode µ/μ is present in descriptions, extend `QuerySpec.description_or_patterns` to emit multiple variants
   - Otherwise mark D-2 as resolved
   - **Time**: ~15 min to probe, 1–2 hours if a fix is needed

2. **Thread-local connections** (DEFERRED `D-1`)
   - Replace `check_same_thread=False` with per-thread connections in `io/parts_db.py`
   - Restores parallelism lost in Phase B
   - **Time**: ~1 hour of careful refactoring + a concurrency test

3. **Run against a real user project**
   - End-to-end smoke on an actual KiCad project (not the minimal fixture)
   - Watch the generated `.jlcpcb-mapper/traces/<ts>/groups.jsonl`
   - Identify any categories or edge cases the test suite missed
   - **Time**: depends on the project, but 15–30 min for a first pass

### Useful polish

4. **Expand golden file coverage** (DEFERRED `S-4`)
   - Add resistor, IC, connector cases to `tests/golden/cases/`
   - Each case locks a different code path as a regression guard
   - **Time**: ~30 min per case

5. **`explain <ref>` CLI command**
   - Spec already planned it; `index.json` is already written
   - ~20 lines of click + trace file reading
   - Users get "why was C12 mapped to this LCSC?" answer in one command
   - **Time**: ~1 hour including tests

6. **LED THT / other edge cases** (DEFERRED `S-5`)
   - Add THT footprint extraction rules in `categories/led.py`
   - Or document the limitation in source if KiCad project uses SMD exclusively
   - **Time**: ~30 min

### Nice-to-have

7. **Resistor Spec tolerance/power fields** — only if config hints aren't enough.
8. **IC BuiltinMap** — populate SOIC-8/SOT-23 etc. to reduce EasyEDA dependency.
9. **Greek mu `hZ` edge case** (`S-7`) — one-char regex tweak.

## Anything worth rethinking

- **`Value(0, TOKEN)` convention for LEDs** — tension with `ICSpec(mpn: str)`. Unification is a small refactor (LEDSpec is the only offender). Low urgency; skip unless touching LED anyway.

- **`Scorer.score(row, spec, trace)` takes Trace** — slight leak of observability into the business protocol. If protocol cleanliness matters, a thunk pattern (scorer returns `(score, breakdown_dict)`, pipeline records to trace) would be cleaner. Not urgent.

- **`category_like="%"` + `limit=1` sentinel for `ConnectorSource`/`ICSource`** — relies on post_filter returning `[]`. A more explicit "no-candidates" signal from source.query would be cleaner. Not urgent.

## Health check (run anytime)

```bash
cd /Users/dkkang/dev/jlcpcb-mapper

# Tests
.venv/bin/pytest -q                            # expect: 386 passed

# Schematic round-trip (should never change)
.venv/bin/pytest tests/test_schematic* -v

# Golden regression
.venv/bin/pytest tests/golden/ -v              # expect: 1 passed

# Integration smoke
.venv/bin/pytest tests/commands/test_map_cmd_new.py -v
.venv/bin/pytest tests/test_pipeline_polarized.py -v

# No uncommitted changes
git status                                      # expect: clean
```

## Rollback (if ever needed)

The redesign was fast-forwarded, so there's no merge commit to revert. To roll back the whole redesign:

```bash
# find the plan-doc commit (the branch point before redesign)
git log --oneline docs/superpowers/plans/
# then hard-reset (DESTRUCTIVE; only after confirming no new commits on top)
git reset --hard 13e8f57   # the original plan commit
```

Practically, you'd revert individual follow-up commits instead of the entire redesign. The 47 redesign commits are all in history with clear messages; cherry-pick-revert is feasible if a specific change needs to go.

For additions on top of the redesign (new work), normal `git revert <sha>` works fine.
