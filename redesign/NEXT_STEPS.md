# Next Steps

The 29-task plan is done. What comes after:

## Decision 1: Merge strategy

The `arch-redesign` branch is 46 commits ahead of `main` with clean tests. Three options:

### A. Fast-forward merge (simplest)

```bash
cd /Users/dkkang/dev/jlcpcb-mapper
git checkout main
git merge --ff-only arch-redesign
# then clean up the worktree:
git worktree remove ../jlcpcb-mapper-arch-redesign
git branch -d arch-redesign    # optional — can keep for history
```

**Pros**: No merge commit, linear history, tight.
**Cons**: 46 individual commits land on main. The commit graph shows every review iteration.

### B. Squash or merge commit

```bash
git checkout main
git merge --no-ff arch-redesign -m "feat: architecture redesign

29-task plan completed. See docs/superpowers/specs/2026-04-22-architecture-redesign.md
for rationale; redesign/ for handoff notes.

- 8 categories fully wired (polarized_cap, resistor, ceramic_cap, inductor,
  led, crystal, ic, connector)
- Per-category Spec + composition-based Category bundles
- Deterministic scorer + LLM tiebreak
- Structured per-stage observability (traces/<ts>/groups.jsonl)
- Golden-file regression harness
- 386 tests passing (0 regressions)
"
```

**Pros**: One merge commit on main; the redesign shows up as a discrete event. Individual commits still in history via `--first-parent` skipping or follow-arrow.
**Cons**: Explicit merge commit, which some projects avoid.

### C. Open a PR for review first

If you want a fresh pair of eyes:

```bash
git push -u origin arch-redesign
gh pr create --title "feat: architecture redesign (29-task plan, 46 commits)" \
             --body "See docs/superpowers/specs/... for spec and redesign/README.md for handoff notes."
```

Then let someone else (or a fresh Claude session with `/ultrareview`) scan before merging.

**Recommendation**: B if this is a solo project; C if anyone else maintains.

## Decision 2: What to tackle after merge

Ordered by impact/ROI:

### Most impactful

1. **Probe real parts.db for Unicode mu variants** (DEFERRED D-2)
   - One-shot SQL query against the user's actual `parts.db`
   - If Unicode µ/μ is present in descriptions, extend `QuerySpec.description_or_patterns` to emit multiple variants
   - Otherwise mark D-2 as resolved

2. **Thread-local connections** (DEFERRED D-1)
   - Replace `check_same_thread=False` with per-thread connections
   - Restores parallelism lost in Phase B
   - Estimate: one hour of careful refactoring + a concurrency test

3. **Run against a real user project**
   - End-to-end smoke on an actual KiCad project (not the minimal fixture)
   - Watch the generated `traces/<ts>/groups.jsonl`
   - Identify any categories or edge cases the test suite missed

### Useful polish

4. **Expand golden file coverage** (DEFERRED S-4)
   - Add resistor, IC, connector cases
   - Each case locks a different code path as a regression guard

5. **`explain <ref>` CLI command**
   - Spec already planned it; `index.json` is already written
   - ~20 lines of click + trace file reading
   - Users get "why was C12 mapped to this LCSC?" answer in one command

6. **LED THT / other edge cases** (DEFERRED S-5)
   - Add THT footprint extraction rules
   - Or document in source if KiCad project uses SMD exclusively

### Nice-to-have

7. **Resistor Spec tolerance/power fields** — only if config hints aren't enough.
8. **IC BuiltinMap** — populate SOIC-8/SOT-23 etc. to reduce EasyEDA dependency.

## Decision 3: Anything to rethink?

Before the merge, consider:

- **`Value(0, TOKEN)` convention for LEDs** — the tension with `ICSpec(mpn: str)` is real. If you want to standardize, picking one style across the 8 categories is a small refactor (LEDSpec is the only offender; ICSpec already uses native fields). Low urgency.

- **`Scorer.score(row, spec, trace)` takes Trace** — slight leak of observability into the business protocol. If protocol cleanliness matters, a thunk pattern (scorer returns `(score, breakdown_dict)`, pipeline records to trace) would be cleaner. Not urgent.

- **`category_like="%"` + `limit=1` sentinel for ConnectorSource/ICSource** — relies on post_filter returning `[]`. A more explicit "no-candidates" signal from source.query would be cleaner. Not urgent.

## Verification before merge

```bash
cd /Users/dkkang/dev/jlcpcb-mapper-arch-redesign

# Tests
.venv/bin/pytest -q                            # expect: 386 passed

# Schematic round-trip (should never change)
.venv/bin/pytest tests/test_schematic* -v

# Golden regression
.venv/bin/pytest tests/golden/ -v              # expect: 1 passed

# Integration smoke
.venv/bin/pytest tests/commands/test_map_cmd_new.py -v
.venv/bin/pytest tests/test_pipeline_polarized.py -v

# Commit log sanity
git log main..arch-redesign --oneline | wc -l  # expect: 46

# No uncommitted changes
git status                                      # expect: clean
```

## Rollback if needed

The worktree is separate from main — nothing on `arch-redesign` affects `main` until you merge.

If you merge and decide to revert:

```bash
git log --oneline -5                    # find the merge commit
git revert -m 1 <merge_sha>             # revert, preserving the merge structure
```

If you want to keep the branch but not merge, simply don't merge. The worktree + branch will persist.
