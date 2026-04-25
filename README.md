# jlcpcb-mapper

> [한국어 README](./README.ko.md)

LLM-assisted part mapping from KiCad schematics to JLCPCB's LCSC catalog.
Reads symbols that don't yet have a footprint or LCSC, scores candidates
against the local `parts.db`, asks Claude Code to break ties on
ambiguous picks, then writes the LCSC and KiCad footprint back into the
schematic.

## What problem this solves

Hand-mapping every passive, IC, and connector in a KiCad project to a
JLCPCB part is tedious and easy to get wrong — same value, different
package; correct package, EOL stock; SMD label, leaded part. This tool
automates the mechanical 80% (resistors, ceramic caps, common diodes
and MOSFETs by MPN, etc.) and gives you a Markdown review document that
explains *why* it picked each part, with LCSC.com links and alternatives,
so the human review step is a quick read-through rather than a search
session.

## How it works

The pipeline runs per **group** (symbols sharing the same category +
spec + package hint):

1. **Match** — route each empty-LCSC symbol to a category by `lib_id`
   (Device:R → resistor, Device:CP → polarized_capacitor,
   Device:FerriteBead → ferrite_bead, anything else with a `:` → ic).
2. **Parse** — extract a structured spec from the Value field
   (`"4.7uH/2A"` → inductance + minimum current rating).
3. **Query** — pull candidates from `parts.db` by category, package,
   and description LIKE on the value.
4. **Decide** — three paths:
   - **single** — only one candidate after filtering.
   - **score** — `Basic-tier × stock-bucket × tier-specific dimensions`
     deterministic score; if the gap to the runner-up exceeds a
     threshold, accept it.
   - **llm** — close call → send the top-N to Claude Code for a
     tiebreak with an explicit reason.
5. **Resolve footprint** — KiCad built-in mapping for common SMD
   passives; on-the-fly EasyEDA download (via the `kicad-jlcpcb-tools`
   helper) for anything else.

Manual overrides bypass the pipeline entirely — see [Manual overrides](#manual-overrides-for-subjective-picks).

## Prerequisites

- KiCad 9 project (`*.kicad_pro`, `*.kicad_sch`).
- A JLCPCB parts SQLite catalog. The standalone `jlcpcb-mapper fetch-db`
  command builds one — see the [Quick start](#quick-start) below. If you
  already use [`kicad-jlcpcb-tools`](https://github.com/bouni/kicad-jlcpcb-tools)
  and have run its "Download parts data" step, the tool also auto-detects
  that DB.
- [Claude Code CLI](https://docs.claude.com/en/docs/claude-code) (`claude`)
  on `PATH`. Used for tiebreaks; the pipeline still runs without it
  (deterministic score path only) but quality will drop.
- Python 3.12+ and `uv` or `pipx` for installation.

## Install

```bash
pipx install jlcpcb-mapper
# or for development:
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
```

## Quick start

```bash
jlcpcb-mapper fetch-db                      # one-time: download parts.db (~1 GB → slim DB)
cd /path/to/my-kicad-project
jlcpcb-mapper init                          # scaffolds jlcpcb-mapper.yaml
jlcpcb-mapper map my-project.kicad_pro      # writes LCSC + footprint
# Review the generated report:
open .jlcpcb-mapper/run-<latest>.md
git diff                                    # eyeball schematic changes
```

`fetch-db` writes to `~/.cache/jlcpcb-mapper/parts.db` by default and the
tool auto-detects it from there.

The tool refuses to run on a dirty git tree (override with `--force`)
so you can always reach a known-good state with `git checkout .` if
the mapping is off.

## End-to-end workflow

A typical first-time mapping on a KiCad board.

### 1. Get `parts.db` ready

```bash
jlcpcb-mapper fetch-db
```

Downloads JLCPCB's parts data and builds a slim SQLite catalog at
`~/Library/Caches/jlcpcb-mapper/parts.db` (macOS) /
`~/.cache/jlcpcb-mapper/parts.db` (Linux). One-shot, ~1 GB of zip chunks
fetched once and reduced to a ~100 MB DB. Re-run periodically to refresh
stock and pricing.

If you already have the `kicad-jlcpcb-tools` plugin set up in KiCad with
its parts data downloaded, `jlcpcb-mapper` also auto-detects that DB —
no need to fetch twice. You can override the path explicitly via
`parts_db:` in the config.

### 2. Initialize the config

```bash
jlcpcb-mapper init
```

Edits a `jlcpcb-mapper.yaml` next to your `*.kicad_pro`. The defaults
are reasonable for hobby boards (0402 passives, X7R/X5R caps,
min_stock 1000); read [Configuration](#configuration) for tuning.

### 3. Run the mapper

```bash
jlcpcb-mapper map my-project.kicad_pro
```

What happens:

- Schematics are read.
- Symbols are filtered: must be on-board, must have a Value, must not
  be a `power:*` symbol, must have an empty Footprint AND empty LCSC.
- Each remaining symbol is routed to a category and grouped with its
  twins.
- Each group runs through query → score → (optional) LLM tiebreak.
- A timestamped backup of every modified `.kicad_sch` is written to
  `.jlcpcb-mapper/backups/<ts>/`.
- The schematics are atomically rewritten with new LCSC and Footprint
  values.
- A Markdown report (`.jlcpcb-mapper/run-<ts>.md`) and JSON log
  (`run-<ts>.json`) are written.

### 4. Review the report

Open `.jlcpcb-mapper/run-<latest>.md`. Each grouped pick looks like:

```markdown
### resistor 4700Ω 0402 — 20 refs (R20, R21, R22, R23, R24, R50, … +14 more)

**Selected**: [`C25744`](https://www.lcsc.com/product-detail/C25744.html) — UNI-ROYAL 0402WGF4701TCE
- **Package** `0402` · **Tier** Basic · **Stock** 4.4M · **Price** $0.0009
- 4.7kΩ 1% 1/16W 0402 Chip Resistor

**Why this part?** Score 1.00 vs runner-up 0.40 — Basic-tier (vs Extended), higher stock (4.4M vs 60k).

**Alternatives considered**:

| LCSC | Mfr Part | Tier | Package | Stock | Price | Score |
|------|----------|------|---------|-------|-------|-------|
| [`C123456`](…) | YAGEO RC0402FR-… | Extended | 0402 | 60k | $0.0007 | 0.40 |
| …
```

The "Why this part?" line distinguishes:
- **single** — only candidate after filtering.
- **score** — which dimension dominated (Basic-tier, stock, voltage match).
- **llm** — Claude's own one-sentence reasoning passed through.
- **manual** — pinned in config (no scoring).

### 5. Approve or revert

```bash
git diff                # see what changed
git checkout .          # revert if you don't like it
```

If you accept, commit the schematic changes alongside your config.

### 6. Re-check before fab

```bash
jlcpcb-mapper verify my-project.kicad_pro
```

Re-runs the lookup against the current `parts.db` and warns if any
mapped LCSC has dropped below `verify.min_stock_warning` or the price
has moved by more than `verify.price_change_pct_warning`.

## Configuration

`jlcpcb-mapper.yaml` lives next to your `*.kicad_pro`. Defaults come
from `default_config.yaml` shipped with the package; the user file
overrides keys you set, deep-merged.

### Selection rules

```yaml
selection:
  prefer_order: [basic, preferred, extended]
  min_stock: 1000
  defaults:
    resistor:
      package: "0402"
      tolerance: "1%"
      power: "1/16W"
    capacitor:
      package: "0402"
      voltage_min: 10
      dielectric_prefer: [X7R, X5R]
    led:
      package: "0603"
```

`prefer_order` only affects scoring weights. `min_stock` is a hard SQL
filter — anything below it never even reaches the scoring path.

### LLM hints

```yaml
hints: |
  - Prefer Basic parts with high stock.
  - Avoid parts with stock < 10000 (EOL risk).
```

Free-form text appended verbatim to the LLM prompt. Useful for
project-specific rules ("avoid Y5V dielectric", "prefer AEC-Q200 for
the automotive section", …).

### Tiebreak thresholds

```yaml
score_tiebreak_threshold: 0.1   # accept score-path pick if top - second >= this
llm_tiebreak_top_n: 5           # otherwise send this many top rows to the LLM
```

### Manual overrides for subjective picks

```yaml
manual_lcsc:
  by_reference:
    J2: C16214      # 2.0mm DC barrel jack (DC-005 2.0)
    J3: C165948     # USB-C 16P SMD (TYPE-C-31-M-12)
    J1: C492421     # 2.54mm 2x4 pin header (PZ254V-12-8P)
  by_value:
    "POGO (1PI)": C5221287   # all 12 pogo-pin symbols at once
    "SW_SPST":    C7470157   # 6×6 tactile switch
```

`by_reference` (exact ref designator) wins over `by_value` (matches
the symbol's Value field, useful when many symbols share the same
choice). The LCSC is written without scoring; if it isn't in
`parts.db` it surfaces as a `manual_unknown_lcsc` failure and the auto
pipeline retains the ref. Existing footprints are preserved — manual
mode only writes the LCSC.

### Footprint overrides

```yaml
kicad_footprint_map_overrides:
  resistor:
    "0402": "MyLib:R_0402_HouseStyle"
```

Per-(category, package) → footprint identifier. Useful when your
in-house library has stricter pad geometry than KiCad's stock
footprint.

## Output artifacts

Each `map` run creates, under `.jlcpcb-mapper/`:

| File | Purpose |
|---|---|
| `run-<ts>.json` | Machine-readable summary: schematics, eligibility counts, per-source counts (`single`, `score`, `llm`, `manual`, `failed`), per-group outcomes, failure list. |
| `run-<ts>.md` | Human review document — what this README's report example shows. |
| `traces/<ts>/groups.jsonl` | One JSON line per group with the full per-stage trace (match → parse → extract → query → post_filter → score breakdown → decide → resolve). Stable list order; `timestamp_ms` is monotonic. |
| `traces/<ts>/index.json` | `reference → line offset` map for fast `explain <ref>` lookups. |
| `backups/<ts>/` | A copy of every modified `.kicad_sch` taken before the atomic write. |

## Flags

**`map`** — `--config PATH`, `--non-interactive`, `--force`,
`--allow-stale-db`, `--fill-lcsc-only`, `--include-dnp`,
`--apply-2nd-pass-suggestions`

**`verify`** — `--config PATH`, `--non-interactive`, `--force`,
`--allow-stale-db`

`--fill-lcsc-only` widens target selection to "any symbol missing an
LCSC" regardless of footprint state. Useful when KiCad's symbol
library already provided a footprint and you only need the LCSC to
finish the BOM.

## Categories supported

`resistor`, `ceramic_capacitor`, `polarized_capacitor`, `inductor`,
`ferrite_bead`, `led`, `crystal`, `connector`, `ic` (catch-all by MPN).
Anything outside these — mounting holes, custom pogo pins, USB-C
receptacles, mechanical switches — is best handled via
`manual_lcsc` overrides.

## Status

v0.1 — used and validated against real KiCad projects (≈150 eligible
symbols, ~75% exact-match rate against hand-picked parts). See `docs/`
for design notes.

## Future work

- **Schematic-context-aware part selection.** Today the tool picks
  parts from the symbol Value + footprint package alone. The richer
  decision — "this 100nF cap sits on a 3.3 V LDO output, so 16 V X7R
  is fine but 6.3 V Y5V isn't"; "this 4.7 µH inductor carries the
  switcher's output current, so it needs ≥ 2× the load rating" — is
  still on the human reviewer. Net topology, voltage-domain
  inference, and per-net current estimates would let the LLM tiebreak
  with full context instead of just the symbol's local fields.

## Acknowledgments

The parts.db schema and the upstream JLCPCB parts feed both come from
[`kicad-jlcpcb-tools`](https://github.com/bouni/kicad-jlcpcb-tools) and
[`yaqwsx/jlcparts`](https://github.com/yaqwsx/jlcparts). This project
is a separate front-end that consumes the same data; it doesn't replace
those tools.
