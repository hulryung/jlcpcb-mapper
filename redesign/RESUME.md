# Resume — Instructions for the Next Claude Code Session

Use this doc to brief a future Claude Code session. Copy the "Kickoff prompt" below verbatim into the new session.

---

## Kickoff prompt (paste this)

```
I'm resuming work on a jlcpcb-mapper architecture redesign that was
completed and merged in a previous session. All 29 planned tasks are
done and landed on `main`.

Working directory: /Users/dkkang/dev/jlcpcb-mapper

Start by reading these files in order:
1. redesign/README.md
2. redesign/STATUS.md
3. redesign/NEXT_STEPS.md

The comprehensive handoff is in `redesign/`. The spec and plan are
under `docs/superpowers/`.

Before doing anything else, run a health check:
- cd /Users/dkkang/dev/jlcpcb-mapper
- .venv/bin/pytest -q   (expect 386 passed)
- git branch            (only `main` should exist)
- git status            (expect clean)

Then ask me which of the next-step options I want to pursue. Don't
start any implementation work until I confirm.
```

---

## What a future session should NOT assume

- **Don't re-read the whole spec/plan from scratch** — the handoff docs in `redesign/` are condensed on purpose. Use them.
- **Don't start implementation without confirmation** — the plan is complete; anything further is new work that needs explicit agreement.
- **Don't try to run against the real parts.db without the user** — the `_autodetect_parts_db()` path in `commands/map_cmd.py` points at `~/Library/Application Support/kicad/9.0/...` on the user's Mac. Tests use fixtures.
- **Don't rewrite or amend existing redesign commits on `main`** — the merge is done; new work goes on top.

---

## What a future session SHOULD do first (in order)

1. **Run the health check** from the kickoff prompt. If anything fails, debug before moving on.
2. **Read the handoff docs** — they are short by design.
3. **Ask the user** which of the options in `NEXT_STEPS.md` to pursue.
4. If the user says "tackle a deferred item" — look up the specific entry in `DEFERRED.md` and ask for scope confirmation before implementing.
5. If the user says "run against my real project" — ask for the `.kicad_pro` path and walk through `run_map` with careful logging, NOT autonomously.

---

## How to understand the codebase quickly

Recommended reading order (skip anything already clear from context):

1. `redesign/ARCHITECTURE.md` — two-screen overview.
2. `src/jlcpcb_mapper/categories/base.py` — 50 lines, defines all 7 component protocols + `Category` dataclass + `ResolveResult`. Everything else composes these.
3. `src/jlcpcb_mapper/core/pipeline.py` — ~200 lines. Three stages; `_decide` is the key branch point.
4. `src/jlcpcb_mapper/categories/polarized_cap.py` — the motivating example; easiest to read.
5. `docs/superpowers/specs/2026-04-22-architecture-redesign.md` — full spec if the above isn't enough.

---

## Common pitfalls for a fresh session

- **Pyright errors on worktree files from the main repo**: a known IDE artifact (see `DEFERRED.md` N-5). Not a real bug. Just run `pytest` to verify.
- **Registry ordering matters**: see `ARCHITECTURE.md`. If you add a new category, think about collisions.
- **`Trace` list order is authoritative**: don't sort events by timestamp. Addressed by the writer; if extending, preserve.
- **`check_same_thread=False` on `PartsDB`**: concurrency bottleneck documented in `DEFERRED.md` D-1. Don't remove the flag without replacing with thread-local connections, or `ThreadPoolExecutor` in the pipeline will crash on the first worker.
- **Legacy tests that were NOT deleted** (`test_map_cmd.py`, `test_e2e.py`, `test_parts_db.py`, `test_downloader.py`, `test_llm.py`, etc.) still pass and provide free coverage. Don't assume they're dead.

---

## Useful commands for any session

```bash
# Where am I?
cd /Users/dkkang/dev/jlcpcb-mapper
git branch --show-current         # main
git worktree list

# Full test suite
.venv/bin/pytest -q

# Only integration tests
.venv/bin/pytest tests/test_pipeline_*.py -v

# Golden regression
.venv/bin/pytest tests/golden/ -v

# Regenerate goldens (use when intentional behavior change)
.venv/bin/pytest tests/golden/ --update-golden

# Full category coverage in one view
ls src/jlcpcb_mapper/categories/
ls src/jlcpcb_mapper/components/
ls src/jlcpcb_mapper/core/

# Inspect a specific trace from a recent run
ls .jlcpcb-mapper/traces/   # empty in worktree; populated after running map_cmd against a project
```

---

## Escape hatches if the handoff doesn't contain something

- **Original spec/plan** (most complete): `docs/superpowers/specs/2026-04-22-architecture-redesign.md` and `docs/superpowers/plans/2026-04-22-architecture-redesign.md`
- **Commit-by-commit history**: `redesign/COMMITS.md` (annotated)
- **Git log itself**: `git log 13e8f57..HEAD --stat -p -- src tests` — enormous but complete (shows everything since the plan commit)
- **Reviewer notes**: scattered in the plan file (annotated in-place after some tasks)
