# Architecture Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the mapping pipeline so each category owns its full logic end-to-end via composition (matcher / value parser / package extractor / candidate source / scorer / footprint resolver / prompt hook), with per-group structured traces for diagnosability. Motivating acceptance case: `Device:CP` with value `"220uF/10V"` must map successfully.

**Architecture:** Strangler pattern — build the new pipeline (`core/`, `categories/`, `components/`, `observability/`) alongside existing modules. Migrate existing I/O modules into `io/`. Switch `map_cmd.py` at the end and delete obsolete modules in one commit. Every category is a `Category` dataclass bundle; the pipeline is generic over categories.

**Tech Stack:** Python 3.11+, pytest, dataclasses, typing.Protocol, sqlite3, click (unchanged), `easyeda2kicad` (unchanged), Claude CLI via subprocess (unchanged).

**Spec:** `docs/superpowers/specs/2026-04-22-architecture-redesign.md`

**Phasing:**
- **Phase A** — Core scaffolding (types, registry, pipeline skeleton). Tasks 1–4.
- **Phase B** — First vertical slice: polarized capacitor end-to-end through new pipeline. Tasks 5–13.
- **Phase C** — Port remaining categories. Tasks 14–20.
- **Phase D** — Observability + preflight enhancement. Tasks 21–24.
- **Phase E** — Migration: move I/O modules, switch `map_cmd`, delete old modules, golden tests. Tasks 25–29.

---

## Phase A — Core scaffolding

### Task 1: `Value` dataclass in `core/types.py`

**Files:**
- Create: `src/jlcpcb_mapper/core/__init__.py` (empty)
- Create: `src/jlcpcb_mapper/core/types.py`
- Create: `tests/core/__init__.py` (empty)
- Test: `tests/core/test_types_value.py`

- [ ] **Step 1: Write failing tests**

`tests/core/test_types_value.py`:
```python
from jlcpcb_mapper.core.types import Value

def test_value_equality():
    assert Value(10.0, "kΩ") == Value(10.0, "kΩ")
    assert Value(10.0, "kΩ") != Value(10.0, "Ω")

def test_value_is_hashable():
    {Value(1, "Ω"): "ok"}

def test_value_display_integer_magnitude():
    assert Value(10, "kΩ").display() == "10kΩ"

def test_value_display_fractional_magnitude_drops_trailing_zero():
    assert Value(4.7, "µF").display() == "4.7µF"
    assert Value(4.70, "µF").display() == "4.7µF"

def test_value_frozen():
    import dataclasses
    v = Value(1, "Ω")
    try:
        v.magnitude = 2  # type: ignore
    except dataclasses.FrozenInstanceError:
        return
    raise AssertionError("Value should be frozen")
```

- [ ] **Step 2: Run test, confirm it fails**

Run: `pytest tests/core/test_types_value.py -v`
Expected: FAIL with ModuleNotFoundError.

- [ ] **Step 3: Implement `Value`**

`src/jlcpcb_mapper/core/types.py`:
```python
"""Core types for the jlcpcb-mapper pipeline."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class Value:
    magnitude: float
    unit: str  # e.g. "Ω", "kΩ", "µF", "µH", "V"

    def display(self) -> str:
        m = self.magnitude
        if float(m).is_integer():
            return f"{int(m)}{self.unit}"
        return f"{m:g}{self.unit}"
```

- [ ] **Step 4: Run test, confirm PASS**

Run: `pytest tests/core/test_types_value.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/jlcpcb_mapper/core/__init__.py src/jlcpcb_mapper/core/types.py tests/core/__init__.py tests/core/test_types_value.py
git commit -m "feat(core): add Value dataclass for magnitude/unit pairs"
```

---

### Task 2: `QuerySpec` and `Spec` protocol in `core/types.py`

**Files:**
- Modify: `src/jlcpcb_mapper/core/types.py`
- Test: `tests/core/test_types_queryspec.py`

- [ ] **Step 1: Write failing tests**

`tests/core/test_types_queryspec.py`:
```python
from jlcpcb_mapper.core.types import QuerySpec

def test_queryspec_defaults():
    q = QuerySpec(category_like="%")
    assert q.category_like == "%"
    assert q.package is None
    assert q.description_patterns == ()
    assert q.mpn_patterns == ()
    assert q.min_stock == 0
    assert q.order_by == "basic DESC, preferred DESC, stock DESC"
    assert q.limit == 50

def test_queryspec_frozen_and_hashable():
    q = QuerySpec(category_like="Chip Resistor%", package="0402",
                  description_patterns=("% 10kΩ%",), min_stock=1000)
    {q: "ok"}

def test_queryspec_tuple_patterns():
    q = QuerySpec(category_like="%", description_patterns=("a", "b"))
    assert q.description_patterns == ("a", "b")
```

- [ ] **Step 2: Run test, confirm FAIL**

Run: `pytest tests/core/test_types_queryspec.py -v`
Expected: FAIL ImportError.

- [ ] **Step 3: Extend `core/types.py`**

Append to `src/jlcpcb_mapper/core/types.py`:
```python
from typing import Protocol, Hashable, runtime_checkable

@dataclass(frozen=True)
class QuerySpec:
    category_like: str
    package: str | None = None
    description_patterns: tuple[str, ...] = ()
    mpn_patterns: tuple[str, ...] = ()
    min_stock: int = 0
    order_by: str = "basic DESC, preferred DESC, stock DESC"
    limit: int = 50

@runtime_checkable
class Spec(Protocol):
    """Per-category parsed value. Implemented by each category's dataclass."""
    def group_key(self) -> Hashable: ...
    def display(self) -> str: ...
    def llm_context(self) -> dict: ...
```

- [ ] **Step 4: Run test, confirm PASS**

Run: `pytest tests/core/test_types_queryspec.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/jlcpcb_mapper/core/types.py tests/core/test_types_queryspec.py
git commit -m "feat(core): add QuerySpec and Spec protocol"
```

---

### Task 3: `Trace` / `TraceEvent` in `observability/trace.py`

**Files:**
- Create: `src/jlcpcb_mapper/observability/__init__.py` (empty)
- Create: `src/jlcpcb_mapper/observability/trace.py`
- Create: `tests/observability/__init__.py` (empty)
- Test: `tests/observability/test_trace.py`

- [ ] **Step 1: Write failing tests**

`tests/observability/test_trace.py`:
```python
from jlcpcb_mapper.observability.trace import Trace, TraceEvent

def test_record_appends_event():
    t = Trace()
    t.record("match", lib_id="Device:CP", category="polarized_capacitor")
    assert len(t.events) == 1
    e = t.events[0]
    assert e.stage == "match"
    assert e.data == {"lib_id": "Device:CP", "category": "polarized_capacitor"}
    assert isinstance(e.timestamp_ms, int)

def test_skip_uses_skip_stage():
    t = Trace()
    t.skip("no category for lib_id", "Device:Unknown")
    assert t.events[0].stage == "skip"
    assert t.events[0].data["reason"] == "no category for lib_id"
    assert t.events[0].data["args"] == ("Device:Unknown",)

def test_events_are_ordered():
    t = Trace()
    t.record("a"); t.record("b"); t.record("c")
    assert [e.stage for e in t.events] == ["a", "b", "c"]
```

- [ ] **Step 2: Run test, confirm FAIL**

Run: `pytest tests/observability/test_trace.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `Trace`**

`src/jlcpcb_mapper/observability/trace.py`:
```python
"""Per-group structured trace recording for pipeline stages."""
from __future__ import annotations
from dataclasses import dataclass, field
import time

@dataclass
class TraceEvent:
    stage: str
    data: dict
    timestamp_ms: int

@dataclass
class Trace:
    events: list[TraceEvent] = field(default_factory=list)

    def record(self, stage: str, **data) -> None:
        self.events.append(TraceEvent(stage, data, int(time.monotonic() * 1000)))

    def skip(self, reason: str, *args) -> None:
        self.record("skip", reason=reason, args=args)
```

- [ ] **Step 4: Run test, confirm PASS**

Run: `pytest tests/observability/test_trace.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/jlcpcb_mapper/observability/__init__.py src/jlcpcb_mapper/observability/trace.py tests/observability/__init__.py tests/observability/test_trace.py
git commit -m "feat(observability): add Trace and TraceEvent"
```

---

### Task 4: `Category` dataclass + component protocols in `categories/base.py`; `Registry` in `core/registry.py`

**Files:**
- Create: `src/jlcpcb_mapper/categories/__init__.py` (empty)
- Create: `src/jlcpcb_mapper/categories/base.py`
- Create: `src/jlcpcb_mapper/core/registry.py`
- Create: `tests/categories/__init__.py` (empty)
- Test: `tests/categories/test_base.py`
- Test: `tests/core/test_registry.py`

- [ ] **Step 1: Write failing tests**

`tests/categories/test_base.py`:
```python
from jlcpcb_mapper.categories.base import (
    Category, Matcher, ValueParser, PackageExtractor,
    CandidateSource, Scorer, FootprintResolver, PromptHook,
    ResolveResult,
)

def test_category_is_frozen():
    import dataclasses
    class _M:
        def matches(self, lib_id): return False
    cat = Category(
        name="x", matcher=_M(), value_parser=None, package_extractor=None,
        default_package="", candidate_source=None, scorer=None,
        footprint_resolver=None, prompt_hook=None,
    )
    try:
        cat.name = "y"  # type: ignore
    except dataclasses.FrozenInstanceError:
        return
    raise AssertionError("Category should be frozen")

def test_resolve_result_defaults():
    r = ResolveResult(footprint="X:Y", downloaded=False)
    assert r.footprint == "X:Y"
    assert r.downloaded is False
    assert r.download_failed is False
```

`tests/core/test_registry.py`:
```python
import pytest
from jlcpcb_mapper.core.registry import Registry
from jlcpcb_mapper.categories.base import Category

class _M:
    def __init__(self, ids): self.ids = ids
    def matches(self, lib_id): return lib_id in self.ids

def _cat(name, ids):
    return Category(
        name=name, matcher=_M(ids), value_parser=None, package_extractor=None,
        default_package="", candidate_source=None, scorer=None,
        footprint_resolver=None, prompt_hook=None,
    )

def test_lookup_hits_first_matching_category():
    r = Registry()
    r.register(_cat("resistor", ["Device:R"]))
    r.register(_cat("capacitor", ["Device:C"]))
    assert r.lookup("Device:R").name == "resistor"
    assert r.lookup("Device:C").name == "capacitor"

def test_lookup_returns_none_when_no_match():
    r = Registry()
    r.register(_cat("resistor", ["Device:R"]))
    assert r.lookup("Device:Unknown") is None

def test_register_rejects_duplicate_names():
    r = Registry()
    r.register(_cat("resistor", ["Device:R"]))
    with pytest.raises(ValueError, match="duplicate"):
        r.register(_cat("resistor", ["Device:R2"]))
```

- [ ] **Step 2: Run tests, confirm FAIL**

Run: `pytest tests/categories/test_base.py tests/core/test_registry.py -v`
Expected: ImportError / ModuleNotFoundError.

- [ ] **Step 3: Implement `Category` + protocols**

`src/jlcpcb_mapper/categories/base.py`:
```python
"""Category bundle: composition of pipeline-stage components."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol, runtime_checkable
from ..core.types import QuerySpec, Spec
from ..io.parts_db import PartRow  # NOTE: PartRow will be moved to io in Task 25.
                                    # Until then it lives in jlcpcb_mapper.parts_db.
                                    # See migration note at the top of this file.

# Temporary shim — remove in Task 25 when parts_db is moved under io/.
# If the import above fails because io/ doesn't yet exist, fall back:
try:
    from ..io.parts_db import PartRow  # type: ignore
except ImportError:
    from ..parts_db import PartRow  # type: ignore

@runtime_checkable
class Matcher(Protocol):
    def matches(self, lib_id: str) -> bool: ...

@runtime_checkable
class ValueParser(Protocol):
    def parse(self, raw: str) -> Spec | None: ...

@runtime_checkable
class PackageExtractor(Protocol):
    def extract(self, kicad_footprint: str) -> str | None: ...

@runtime_checkable
class CandidateSource(Protocol):
    def query(self, spec: Spec, package_hint: str) -> QuerySpec: ...
    def post_filter(self, rows: list[PartRow], spec: Spec, package_hint: str) -> list[PartRow]: ...

# Scorer takes Trace for breakdown recording (see observability design).
# Forward import to avoid cycle.
from ..observability.trace import Trace

@runtime_checkable
class Scorer(Protocol):
    def score(self, row: PartRow, spec: Spec, trace: Trace) -> float: ...

@dataclass
class ResolveResult:
    footprint: str
    downloaded: bool
    download_failed: bool = False

@runtime_checkable
class FootprintResolver(Protocol):
    def resolve(self, part: PartRow, package_hint: str) -> ResolveResult: ...

@runtime_checkable
class PromptHook(Protocol):
    def selection_criteria(self) -> str: ...
    def candidate_payload(self, row: PartRow) -> dict: ...

@dataclass(frozen=True)
class Category:
    name: str
    matcher: Matcher
    value_parser: ValueParser | None
    package_extractor: PackageExtractor | None
    default_package: str
    candidate_source: CandidateSource | None
    scorer: Scorer | None
    footprint_resolver: FootprintResolver | None
    prompt_hook: PromptHook | None
```

`src/jlcpcb_mapper/core/registry.py`:
```python
"""Registry of categories. Populated at import time by categories/__init__.py."""
from __future__ import annotations
from ..categories.base import Category

class Registry:
    def __init__(self) -> None:
        self._categories: list[Category] = []

    def register(self, cat: Category) -> None:
        if any(c.name == cat.name for c in self._categories):
            raise ValueError(f"duplicate category name: {cat.name}")
        self._categories.append(cat)

    def lookup(self, lib_id: str) -> Category | None:
        for c in self._categories:
            if c.matcher.matches(lib_id):
                return c
        return None

    def all(self) -> list[Category]:
        return list(self._categories)
```

- [ ] **Step 4: Run tests, confirm PASS**

Run: `pytest tests/categories/test_base.py tests/core/test_registry.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/jlcpcb_mapper/categories/__init__.py src/jlcpcb_mapper/categories/base.py src/jlcpcb_mapper/core/registry.py tests/categories/__init__.py tests/categories/test_base.py tests/core/test_registry.py
git commit -m "feat(categories,core): Category bundle + Registry with protocols"
```

---

## Phase B — First vertical slice: polarized capacitor

This phase builds every component needed for `POLARIZED_CAP` and wires it through the pipeline. Finishing this phase means the acceptance case `Device:CP` + `"220uF/10V"` passes an integration test.

### Task 5: Component — `LibIdAny` matcher in `components/matchers.py`

**Files:**
- Create: `src/jlcpcb_mapper/components/__init__.py` (empty)
- Create: `src/jlcpcb_mapper/components/matchers.py`
- Create: `tests/components/__init__.py` (empty)
- Test: `tests/components/test_matchers.py`

- [ ] **Step 1: Write failing tests**

`tests/components/test_matchers.py`:
```python
from jlcpcb_mapper.components.matchers import LibIdAny, LibIdPrefix

def test_libidany_exact_and_suffixed():
    m = LibIdAny(["Device:CP", "Device:C_Polarized"])
    assert m.matches("Device:CP")
    assert m.matches("Device:CP_Small")
    assert m.matches("Device:C_Polarized")
    assert m.matches("Device:C_Polarized_Small")
    assert not m.matches("Device:C")
    assert not m.matches("Device:R")

def test_libidprefix_matches_prefix_only():
    m = LibIdPrefix(["Connector_Generic:Conn_02x"])
    assert m.matches("Connector_Generic:Conn_02x05_Odd_Even")
    assert not m.matches("Connector_Generic:Conn_01x05")
```

- [ ] **Step 2: Run test, confirm FAIL**

Run: `pytest tests/components/test_matchers.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

`src/jlcpcb_mapper/components/matchers.py`:
```python
"""Lib-id matchers for Category.matcher."""
from __future__ import annotations

class LibIdAny:
    """Matches if lib_id equals any base exactly, or starts with `base + '_'`."""
    def __init__(self, bases: list[str]):
        self._bases = tuple(bases)
    def matches(self, lib_id: str) -> bool:
        for b in self._bases:
            if lib_id == b or lib_id.startswith(b + "_"):
                return True
        return False

class LibIdPrefix:
    """Matches if lib_id starts with any given prefix (no boundary assumed)."""
    def __init__(self, prefixes: list[str]):
        self._prefixes = tuple(prefixes)
    def matches(self, lib_id: str) -> bool:
        return any(lib_id.startswith(p) for p in self._prefixes)
```

- [ ] **Step 4: Run, PASS**

Run: `pytest tests/components/test_matchers.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/jlcpcb_mapper/components/__init__.py src/jlcpcb_mapper/components/matchers.py tests/components/__init__.py tests/components/test_matchers.py
git commit -m "feat(components): LibIdAny and LibIdPrefix matchers"
```

---

### Task 6: Component — `CapValueParser` + `PolarizedCapSpec`, `CeramicCapSpec`

**Files:**
- Create: `src/jlcpcb_mapper/categories/spec/__init__.py` (empty)
- Create: `src/jlcpcb_mapper/categories/spec/cap.py`
- Create: `src/jlcpcb_mapper/components/value_parsers.py`
- Test: `tests/components/test_value_parsers_cap.py`
- Test: `tests/categories/test_spec_cap.py`

- [ ] **Step 1: Write failing tests**

`tests/categories/test_spec_cap.py`:
```python
from jlcpcb_mapper.core.types import Value
from jlcpcb_mapper.categories.spec.cap import CeramicCapSpec, PolarizedCapSpec

def test_ceramic_group_key_ignores_voltage():
    a = CeramicCapSpec(value=Value(10, "µF"))
    b = CeramicCapSpec(value=Value(10, "µF"))
    assert a.group_key() == b.group_key()
    assert a.display() == "10µF"

def test_polarized_group_key_includes_voltage():
    a = PolarizedCapSpec(value=Value(220, "µF"), voltage=Value(10, "V"))
    b = PolarizedCapSpec(value=Value(220, "µF"), voltage=Value(25, "V"))
    assert a.group_key() != b.group_key()
    assert a.display() == "220µF/10V"

def test_polarized_no_voltage_display():
    a = PolarizedCapSpec(value=Value(100, "µF"), voltage=None)
    assert a.display() == "100µF"
    assert a.llm_context() == {"value": "100µF", "voltage": None}
```

`tests/components/test_value_parsers_cap.py`:
```python
from jlcpcb_mapper.core.types import Value
from jlcpcb_mapper.categories.spec.cap import CeramicCapSpec, PolarizedCapSpec
from jlcpcb_mapper.components.value_parsers import CapValueParser

def test_ceramic_parses_plain_value():
    p = CapValueParser(keep_voltage=False)
    assert p.parse("10uF") == CeramicCapSpec(value=Value(10, "µF"))
    assert p.parse("10µF") == CeramicCapSpec(value=Value(10, "µF"))
    assert p.parse("100nF") == CeramicCapSpec(value=Value(100, "nF"))
    assert p.parse("2u2") == CeramicCapSpec(value=Value(2.2, "µF"))

def test_ceramic_drops_extra_slash_tokens():
    p = CapValueParser(keep_voltage=False)
    assert p.parse("10uF/25V") == CeramicCapSpec(value=Value(10, "µF"))

def test_polarized_keeps_voltage():
    p = CapValueParser(keep_voltage=True)
    spec = p.parse("220uF/10V")
    assert spec == PolarizedCapSpec(value=Value(220, "µF"), voltage=Value(10, "V"))

def test_polarized_missing_voltage_is_none():
    p = CapValueParser(keep_voltage=True)
    spec = p.parse("220uF")
    assert spec == PolarizedCapSpec(value=Value(220, "µF"), voltage=None)

def test_polarized_voltage_before_value_ignored():
    p = CapValueParser(keep_voltage=True)
    # Only slash-separated trailing tokens are inspected for voltage.
    spec = p.parse("10V/220uF")
    assert spec is None  # primary token "10V" is not a capacitance

def test_parse_none_on_junk():
    p = CapValueParser(keep_voltage=False)
    assert p.parse("foobar") is None
    assert p.parse("") is None
```

- [ ] **Step 2: Run, FAIL**

Run: `pytest tests/categories/test_spec_cap.py tests/components/test_value_parsers_cap.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement Specs**

`src/jlcpcb_mapper/categories/spec/cap.py`:
```python
"""Capacitor Spec dataclasses."""
from __future__ import annotations
from dataclasses import dataclass
from ...core.types import Value

@dataclass(frozen=True)
class CeramicCapSpec:
    value: Value

    def group_key(self): return ("ceramic_cap", self.value)
    def display(self) -> str: return self.value.display()
    def llm_context(self) -> dict: return {"value": self.value.display()}

@dataclass(frozen=True)
class PolarizedCapSpec:
    value: Value
    voltage: Value | None

    def group_key(self): return ("polarized_cap", self.value, self.voltage)
    def display(self) -> str:
        v = f"/{self.voltage.display()}" if self.voltage else ""
        return f"{self.value.display()}{v}"
    def llm_context(self) -> dict:
        return {"value": self.value.display(),
                "voltage": self.voltage.display() if self.voltage else None}
```

- [ ] **Step 4: Implement `CapValueParser`**

`src/jlcpcb_mapper/components/value_parsers.py`:
```python
"""Value parsers per category. Each parser returns the appropriate Spec or None."""
from __future__ import annotations
import re
from ..core.types import Value
from ..categories.spec.cap import CeramicCapSpec, PolarizedCapSpec

_CAP_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([munpµu]?)[Ff]?\s*$", re.IGNORECASE)
_CAP_IMPLICIT_RE = re.compile(r"^\s*(\d+)u(\d+)\s*$")  # "2u2" -> 2.2µF
_VOLTAGE_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*V\s*$", re.IGNORECASE)

def _parse_cap_value(token: str) -> Value | None:
    m = _CAP_IMPLICIT_RE.match(token)
    if m:
        return Value(float(f"{m.group(1)}.{m.group(2)}"), "µF")
    m = _CAP_RE.match(token)
    if not m:
        return None
    mag = float(m.group(1))
    unit_in = m.group(2).lower()
    unit_in = "µ" if unit_in in ("u", "µ") else unit_in
    if unit_in == "":
        # Bare number with optional F — treat as F only if there was an F suffix
        # Our regex accepts trailing F; check if any unit was captured
        return Value(mag, "F")
    return Value(mag, f"{unit_in}F")

def _parse_voltage(token: str) -> Value | None:
    m = _VOLTAGE_RE.match(token)
    if not m:
        return None
    return Value(float(m.group(1)), "V")

class CapValueParser:
    """Parse capacitor-like values.

    keep_voltage=True  → returns PolarizedCapSpec(value, voltage)
    keep_voltage=False → returns CeramicCapSpec(value), trailing voltage ignored
    """
    def __init__(self, *, keep_voltage: bool):
        self.keep_voltage = keep_voltage

    def parse(self, raw: str):
        if not raw or not raw.strip():
            return None
        parts = [p.strip() for p in raw.split("/")]
        if not parts or not parts[0]:
            return None
        value = _parse_cap_value(parts[0])
        if value is None:
            return None
        if not self.keep_voltage:
            return CeramicCapSpec(value=value)
        voltage = None
        for extra in parts[1:]:
            voltage = _parse_voltage(extra)
            if voltage:
                break
        return PolarizedCapSpec(value=value, voltage=voltage)
```

- [ ] **Step 5: Run, PASS**

Run: `pytest tests/categories/test_spec_cap.py tests/components/test_value_parsers_cap.py -v`
Expected: 9 passed.

- [ ] **Step 6: Commit**

```bash
git add src/jlcpcb_mapper/categories/spec/__init__.py src/jlcpcb_mapper/categories/spec/cap.py src/jlcpcb_mapper/components/value_parsers.py tests/categories/test_spec_cap.py tests/components/test_value_parsers_cap.py
git commit -m "feat(components,spec): CapValueParser + Ceramic/Polarized cap specs"
```

---

### Task 7: Component — `RegexFromRules` package extractor

**Files:**
- Create: `src/jlcpcb_mapper/components/package_extractors.py`
- Test: `tests/components/test_package_extractors.py`

- [ ] **Step 1: Write failing tests**

`tests/components/test_package_extractors.py`:
```python
import re
from jlcpcb_mapper.components.package_extractors import RegexFromRules

def test_resistor_smd_size():
    ex = RegexFromRules([(r"^Resistor_SMD:R_(\d{4})_", lambda m: m.group(1))])
    assert ex.extract("Resistor_SMD:R_0402_1005Metric") == "0402"
    assert ex.extract("Resistor_SMD:R_0603_1608Metric_Pad") == "0603"

def test_polarized_cap_smd_diameter():
    ex = RegexFromRules([
        (r"^Capacitor_SMD:CP_Elec_(\d+\.?\d*x\d+\.?\d*)",
         lambda m: f"D{m.group(1).split('x')[0]}"),
    ])
    assert ex.extract("Capacitor_SMD:CP_Elec_6.3x5.4") == "D6.3"
    assert ex.extract("Capacitor_SMD:CP_Elec_8x10") == "D8"

def test_returns_none_when_no_rule_matches():
    ex = RegexFromRules([(r"^Xyz", lambda m: "x")])
    assert ex.extract("Resistor_SMD:R_0402_1005Metric") is None

def test_empty_footprint_returns_none():
    ex = RegexFromRules([(r"^X", lambda m: "x")])
    assert ex.extract("") is None

def test_multiple_rules_first_wins():
    ex = RegexFromRules([
        (r"^Package_TO_SOT_SMD:(SOT-\d+)", lambda m: m.group(1)),
        (r"^Package_TO_SOT_SMD:(TO-\d+(?:-\d+)?)(?:_|$)", lambda m: m.group(1)),
    ])
    assert ex.extract("Package_TO_SOT_SMD:SOT-23") == "SOT-23"
    assert ex.extract("Package_TO_SOT_SMD:TO-263-5_TabPin3") == "TO-263-5"
```

- [ ] **Step 2: Run, FAIL**

Run: `pytest tests/components/test_package_extractors.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

`src/jlcpcb_mapper/components/package_extractors.py`:
```python
"""Package-extraction rules: map KiCad footprint id -> JLCPCB-style package code."""
from __future__ import annotations
import re
from typing import Callable

class RegexFromRules:
    def __init__(self, rules: list[tuple[str, Callable[[re.Match], str]]]):
        self._rules = [(re.compile(p), fn) for p, fn in rules]

    def extract(self, kicad_footprint: str) -> str | None:
        if not kicad_footprint:
            return None
        for pat, fn in self._rules:
            m = pat.match(kicad_footprint)
            if m:
                return fn(m)
        return None
```

- [ ] **Step 4: Run, PASS**

Run: `pytest tests/components/test_package_extractors.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/jlcpcb_mapper/components/package_extractors.py tests/components/test_package_extractors.py
git commit -m "feat(components): RegexFromRules package extractor"
```

---

### Task 8: Thin `PartsDB.execute(QuerySpec)` method (additive)

**Files:**
- Modify: `src/jlcpcb_mapper/parts_db.py` — add `execute(QuerySpec)` method
- Test: `tests/test_parts_db_execute.py`

Do NOT remove existing `query_candidates`; it will be deleted in Task 25 after all call-sites are migrated.

- [ ] **Step 1: Write failing tests**

`tests/test_parts_db_execute.py`:
```python
import sqlite3
from pathlib import Path
import pytest
from jlcpcb_mapper.core.types import QuerySpec
from jlcpcb_mapper.parts_db import PartsDB

@pytest.fixture
def db(tmp_path: Path) -> PartsDB:
    p = tmp_path / "parts.db"
    conn = sqlite3.connect(str(p))
    conn.executescript("""
        CREATE TABLE parts (
            lcsc TEXT PRIMARY KEY, category TEXT, mfr TEXT, mfr_part TEXT,
            package TEXT, description TEXT, basic INTEGER, preferred INTEGER,
            stock INTEGER, price REAL
        );
        INSERT INTO parts VALUES ('C1','Chip Resistor','X','R1','0402','10kΩ 1%',1,0,50000,0.001);
        INSERT INTO parts VALUES ('C2','Chip Resistor','X','R2','0603','10kΩ 1%',0,1,25000,0.0015);
        INSERT INTO parts VALUES ('C3','Aluminum Electrolytic','Y','EL1','D6.3','220uF 10V',1,0,15000,0.05);
        INSERT INTO parts VALUES ('C4','Aluminum Electrolytic','Y','EL2','D6.3','220uF 25V',0,0,5000,0.04);
        INSERT INTO parts VALUES ('C5','Chip Resistor','X','R3','0402','10kΩ 1%',0,0,500,0.001);
    """)
    conn.commit(); conn.close()
    return PartsDB(p)

def test_execute_filters_category_package_and_stock(db):
    q = QuerySpec(category_like="Chip Resistor%", package="0402", min_stock=1000)
    rows = db.execute(q)
    assert [r.lcsc for r in rows] == ["C1"]  # C5 excluded by stock

def test_execute_description_pattern(db):
    q = QuerySpec(category_like="%Aluminum%", description_patterns=("%220uF%",))
    rows = db.execute(q)
    assert {r.lcsc for r in rows} == {"C3", "C4"}

def test_execute_orderby_basic_preferred_stock(db):
    q = QuerySpec(category_like="Chip Resistor%")
    rows = db.execute(q)
    # C1 basic=1, C2 preferred=1 stock=25k, C5 stock=500
    assert [r.lcsc for r in rows] == ["C1", "C2", "C5"]

def test_execute_respects_limit(db):
    q = QuerySpec(category_like="%", limit=2)
    assert len(db.execute(q)) == 2
```

- [ ] **Step 2: Run, FAIL**

Run: `pytest tests/test_parts_db_execute.py -v`
Expected: AttributeError (no `execute` method on PartsDB).

- [ ] **Step 3: Add `execute` to `PartsDB`**

Append to `src/jlcpcb_mapper/parts_db.py` (inside class `PartsDB`):
```python
    def execute(self, q) -> list["PartRow"]:
        """Run a QuerySpec against parts.db. Added during architecture migration."""
        from .core.types import QuerySpec  # local to avoid cycle at import
        assert isinstance(q, QuerySpec), f"expected QuerySpec, got {type(q).__name__}"
        clauses: list[str] = ["category LIKE ?"]
        args: list = [q.category_like]
        if q.package is not None:
            clauses.append("package = ?"); args.append(q.package)
        for pat in q.description_patterns:
            clauses.append("description LIKE ?"); args.append(pat)
        for pat in q.mpn_patterns:
            clauses.append("mfr_part LIKE ?"); args.append(pat)
        clauses.append("stock >= ?"); args.append(q.min_stock)
        sql = (
            f"SELECT {COLS} FROM parts WHERE {' AND '.join(clauses)} "
            f"ORDER BY {q.order_by} LIMIT ?"
        )
        args.append(q.limit)
        cur = self._conn.execute(sql, args)
        return [PartRow(**dict(r)) for r in cur.fetchall()]
```

- [ ] **Step 4: Run, PASS**

Run: `pytest tests/test_parts_db_execute.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/jlcpcb_mapper/parts_db.py tests/test_parts_db_execute.py
git commit -m "feat(parts_db): add PartsDB.execute(QuerySpec) alongside legacy method"
```

---

### Task 9: Component — `PolarizedCapSource` (CandidateSource)

**Files:**
- Create: `src/jlcpcb_mapper/components/candidate_sources.py`
- Test: `tests/components/test_candidate_sources_polarized.py`

- [ ] **Step 1: Write failing tests**

`tests/components/test_candidate_sources_polarized.py`:
```python
from jlcpcb_mapper.core.types import Value
from jlcpcb_mapper.categories.spec.cap import PolarizedCapSpec
from jlcpcb_mapper.components.candidate_sources import PolarizedCapSource
from jlcpcb_mapper.parts_db import PartRow

def _row(lcsc, pkg, desc, stock=10000, basic=0, preferred=0):
    return PartRow(lcsc=lcsc, category="Aluminum Electrolytic", mfr="Y", mfr_part="X",
                   package=pkg, description=desc, basic=basic, preferred=preferred,
                   stock=stock, price=0.01)

def test_query_includes_value_and_min_stock():
    spec = PolarizedCapSpec(value=Value(220, "µF"), voltage=Value(10, "V"))
    q = PolarizedCapSource(min_stock=1000).query(spec, package_hint="D6.3")
    assert "Aluminum Electrolytic" in q.category_like
    assert q.min_stock == 1000
    # µ converted to ASCII u in description search
    assert ("%220uF%",) == q.description_patterns

def test_post_filter_keeps_package_substring():
    src = PolarizedCapSource()
    spec = PolarizedCapSpec(value=Value(220, "µF"), voltage=Value(10, "V"))
    rows = [
        _row("C1", "D6.3", "220uF 10V"),
        _row("C2", "D8",   "220uF 10V"),
        _row("C3", "D6.3", "220uF 10V"),
    ]
    kept = src.post_filter(rows, spec, package_hint="D6.3")
    assert {r.lcsc for r in kept} == {"C1", "C3"}

def test_post_filter_voltage_ge_required():
    src = PolarizedCapSource()
    spec = PolarizedCapSpec(value=Value(220, "µF"), voltage=Value(10, "V"))
    rows = [
        _row("C1", "D6.3", "220uF 6.3V"),
        _row("C2", "D6.3", "220uF 10V"),
        _row("C3", "D6.3", "220uF 25V"),
        _row("C4", "D6.3", "220uF"),     # no voltage → kept as candidate
    ]
    kept = src.post_filter(rows, spec, package_hint="D6.3")
    assert {r.lcsc for r in kept} == {"C2", "C3", "C4"}

def test_post_filter_no_voltage_spec_keeps_all():
    src = PolarizedCapSource()
    spec = PolarizedCapSpec(value=Value(220, "µF"), voltage=None)
    rows = [
        _row("C1", "D6.3", "220uF 6.3V"),
        _row("C2", "D6.3", "220uF 25V"),
    ]
    kept = src.post_filter(rows, spec, package_hint="D6.3")
    assert {r.lcsc for r in kept} == {"C1", "C2"}
```

- [ ] **Step 2: Run, FAIL**

Run: `pytest tests/components/test_candidate_sources_polarized.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

`src/jlcpcb_mapper/components/candidate_sources.py`:
```python
"""CandidateSource implementations per category."""
from __future__ import annotations
import re
from ..core.types import QuerySpec
from ..parts_db import PartRow

_VOLTAGE_TOKEN = re.compile(r"(\d+(?:\.\d+)?)\s*V\b", re.IGNORECASE)

def _extract_voltage_numbers(description: str) -> list[float]:
    return [float(m.group(1)) for m in _VOLTAGE_TOKEN.finditer(description or "")]

def _normalize_micro(unit_or_value: str) -> str:
    """µ → u (ASCII) for DB description matching."""
    return unit_or_value.replace("µ", "u")

class PolarizedCapSource:
    """Aluminum electrolytic capacitors. Broad category fetch + post_filter by
    package substring and voltage-rating."""

    def __init__(self, min_stock: int = 0, limit: int = 50):
        self.min_stock = min_stock
        self.limit = limit

    def query(self, spec, package_hint: str) -> QuerySpec:
        patterns = ()
        if spec.value is not None:
            token = f"%{_normalize_micro(spec.value.display())}%"
            patterns = (token,)
        return QuerySpec(
            category_like="%Aluminum Electrolytic%",
            package=None,  # use substring filter in post_filter
            description_patterns=patterns,
            min_stock=self.min_stock,
            limit=self.limit,
        )

    def post_filter(self, rows: list[PartRow], spec, package_hint: str) -> list[PartRow]:
        hint = (package_hint or "").lower()
        out: list[PartRow] = []
        required_v = spec.voltage.magnitude if spec.voltage is not None else None
        for r in rows:
            if hint and hint not in (r.package or "").lower():
                continue
            if required_v is not None:
                voltages = _extract_voltage_numbers(r.description or "")
                if voltages and max(voltages) < required_v:
                    continue
            out.append(r)
        return out
```

- [ ] **Step 4: Run, PASS**

Run: `pytest tests/components/test_candidate_sources_polarized.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/jlcpcb_mapper/components/candidate_sources.py tests/components/test_candidate_sources_polarized.py
git commit -m "feat(components): PolarizedCapSource with voltage post-filter"
```

---

### Task 10: Component — `PolarizedCapScorer`

**Files:**
- Create: `src/jlcpcb_mapper/components/scorers.py`
- Test: `tests/components/test_scorers_polarized.py`

- [ ] **Step 1: Write failing tests**

`tests/components/test_scorers_polarized.py`:
```python
from jlcpcb_mapper.core.types import Value
from jlcpcb_mapper.categories.spec.cap import PolarizedCapSpec
from jlcpcb_mapper.components.scorers import PolarizedCapScorer
from jlcpcb_mapper.parts_db import PartRow
from jlcpcb_mapper.observability.trace import Trace

def _row(lcsc, basic=0, preferred=0, stock=10000, desc="220uF 10V"):
    return PartRow(lcsc=lcsc, category="Aluminum Electrolytic", mfr="X", mfr_part="Y",
                   package="D6.3", description=desc, basic=basic, preferred=preferred,
                   stock=stock, price=0.01)

def test_basic_outranks_extended_with_same_voltage():
    s = PolarizedCapScorer()
    spec = PolarizedCapSpec(value=Value(220, "µF"), voltage=Value(10, "V"))
    t = Trace()
    assert s.score(_row("C1", basic=1), spec, t) > s.score(_row("C2"), spec, t)

def test_exact_voltage_beats_higher_voltage():
    s = PolarizedCapScorer()
    spec = PolarizedCapSpec(value=Value(220, "µF"), voltage=Value(10, "V"))
    exact = _row("C1", basic=1, desc="220uF 10V")
    higher = _row("C2", basic=1, desc="220uF 25V")
    t = Trace()
    assert s.score(exact, spec, t) > s.score(higher, spec, t)

def test_scorer_records_breakdown_in_trace():
    s = PolarizedCapScorer()
    spec = PolarizedCapSpec(value=Value(220, "µF"), voltage=Value(10, "V"))
    t = Trace()
    s.score(_row("C1", basic=1), spec, t)
    assert any(e.stage == "score_breakdown" and "C1" in str(e.data.get("lcsc", ""))
               for e in t.events)
```

- [ ] **Step 2: Run, FAIL**

Run: `pytest tests/components/test_scorers_polarized.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

`src/jlcpcb_mapper/components/scorers.py`:
```python
"""Deterministic scorers for categories that permit objective ranking."""
from __future__ import annotations
import re
from ..parts_db import PartRow
from ..observability.trace import Trace

_VOLTAGE_TOKEN = re.compile(r"(\d+(?:\.\d+)?)\s*V\b", re.IGNORECASE)

def _stock_bucket(stock: int) -> float:
    # Logarithmic-ish: >=50k → 1.0, 10k → 0.6, 1k → 0.3, <1k → 0.1
    if stock >= 50_000: return 1.0
    if stock >= 10_000: return 0.7
    if stock >= 5_000:  return 0.5
    if stock >= 1_000:  return 0.3
    return 0.1

class PolarizedCapScorer:
    """Weights: basic (0.3) + preferred (0.1) + voltage-exact (0.3) + stock-bucket (0.3)."""

    W_BASIC = 0.3
    W_PREFERRED = 0.1
    W_VOLTAGE_EXACT = 0.3
    W_STOCK = 0.3

    def score(self, row: PartRow, spec, trace: Trace) -> float:
        basic = self.W_BASIC if row.basic else 0.0
        preferred = self.W_PREFERRED if row.preferred else 0.0
        voltage_exact = 0.0
        if spec.voltage is not None:
            voltages = [float(m.group(1)) for m in _VOLTAGE_TOKEN.finditer(row.description or "")]
            if voltages and min(voltages) == spec.voltage.magnitude:
                voltage_exact = self.W_VOLTAGE_EXACT
            elif voltages and min(voltages) >= spec.voltage.magnitude:
                # rated above spec — acceptable but not "exact"
                voltage_exact = self.W_VOLTAGE_EXACT * 0.5
        stock = self.W_STOCK * _stock_bucket(row.stock)
        total = basic + preferred + voltage_exact + stock
        trace.record(
            "score_breakdown",
            lcsc=row.lcsc,
            basic=basic, preferred=preferred,
            voltage_exact=voltage_exact, stock=stock,
            total=total,
        )
        return total
```

- [ ] **Step 4: Run, PASS**

Run: `pytest tests/components/test_scorers_polarized.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/jlcpcb_mapper/components/scorers.py tests/components/test_scorers_polarized.py
git commit -m "feat(components): PolarizedCapScorer with voltage-aware weighting"
```

---

### Task 11: Component — `BuiltinMap`, `EasyedaFallback`, `Composite` footprint resolvers

**Files:**
- Create: `src/jlcpcb_mapper/components/footprint_resolvers.py`
- Test: `tests/components/test_footprint_resolvers.py`

- [ ] **Step 1: Write failing tests**

`tests/components/test_footprint_resolvers.py`:
```python
from jlcpcb_mapper.components.footprint_resolvers import BuiltinMap, Composite
from jlcpcb_mapper.categories.base import ResolveResult
from jlcpcb_mapper.parts_db import PartRow

def _part(lcsc="C1", package="0402"):
    return PartRow(lcsc=lcsc, category="x", mfr="y", mfr_part="z",
                   package=package, description="", basic=0, preferred=0,
                   stock=0, price=0.0)

def test_builtin_map_hit():
    r = BuiltinMap({"0402": "Resistor_SMD:R_0402_1005Metric"})
    res = r.resolve(_part(package="0402"), package_hint="0402")
    assert res == ResolveResult(footprint="Resistor_SMD:R_0402_1005Metric", downloaded=False)

def test_builtin_map_miss_returns_empty():
    r = BuiltinMap({"0402": "Resistor_SMD:R_0402_1005Metric"})
    res = r.resolve(_part(package="0603"), package_hint="0603")
    assert res.footprint == ""
    assert res.downloaded is False

def test_composite_tries_in_order_until_nonempty():
    class _Stub:
        def __init__(self, fp, downloaded=False): self.fp, self.d = fp, downloaded
        def resolve(self, part, hint):
            return ResolveResult(footprint=self.fp, downloaded=self.d)
    c = Composite([_Stub(""), _Stub("LCSC:X_fp", downloaded=True)])
    res = c.resolve(_part(), package_hint="")
    assert res.footprint == "LCSC:X_fp"
    assert res.downloaded is True

def test_composite_all_fail_returns_failed():
    class _Stub:
        def resolve(self, part, hint):
            return ResolveResult(footprint="", downloaded=False, download_failed=True)
    c = Composite([_Stub()])
    res = c.resolve(_part(), package_hint="")
    assert res.download_failed is True
```

- [ ] **Step 2: Run, FAIL**

Run: `pytest tests/components/test_footprint_resolvers.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

`src/jlcpcb_mapper/components/footprint_resolvers.py`:
```python
"""Footprint resolvers. BuiltinMap and EasyedaFallback compose via Composite."""
from __future__ import annotations
from pathlib import Path
from ..categories.base import ResolveResult
from ..parts_db import PartRow

class BuiltinMap:
    """package_hint -> KiCad library footprint id."""
    def __init__(self, mapping: dict[str, str]):
        self._map = dict(mapping)

    def resolve(self, part: PartRow, package_hint: str) -> ResolveResult:
        fp = self._map.get(package_hint, "")
        return ResolveResult(footprint=fp, downloaded=False)


class EasyedaFallback:
    """Download a KiCad footprint from EasyEDA for the given LCSC."""

    def __init__(self, out_dir: Path, downloader=None):
        self.out_dir = Path(out_dir)
        # Injectable downloader for tests; defaults to production downloader.
        if downloader is None:
            from ..downloader import download_footprint as _dl
            downloader = _dl
        self._download = downloader

    def resolve(self, part: PartRow, package_hint: str) -> ResolveResult:
        path = self._download(part.lcsc, self.out_dir)
        if path is None:
            return ResolveResult(footprint="", downloaded=False, download_failed=True)
        fp_name = Path(path).stem
        return ResolveResult(footprint=f"LCSC:{fp_name}", downloaded=True)


class Composite:
    """Try each resolver in order; return the first non-empty footprint."""
    def __init__(self, resolvers: list):
        self._resolvers = list(resolvers)

    def resolve(self, part: PartRow, package_hint: str) -> ResolveResult:
        last = ResolveResult(footprint="", downloaded=False)
        for r in self._resolvers:
            res = r.resolve(part, package_hint)
            if res.footprint:
                return res
            last = res
        return last
```

- [ ] **Step 4: Run, PASS**

Run: `pytest tests/components/test_footprint_resolvers.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/jlcpcb_mapper/components/footprint_resolvers.py tests/components/test_footprint_resolvers.py
git commit -m "feat(components): BuiltinMap + EasyedaFallback + Composite resolvers"
```

---

### Task 12: Component — `PromptHook` (`CapPromptHook`)

**Files:**
- Create: `src/jlcpcb_mapper/components/prompt_hooks.py`
- Test: `tests/components/test_prompt_hooks.py`

- [ ] **Step 1: Write failing tests**

`tests/components/test_prompt_hooks.py`:
```python
from jlcpcb_mapper.components.prompt_hooks import CapPromptHook
from jlcpcb_mapper.parts_db import PartRow

def _row():
    return PartRow(lcsc="C1", category="Aluminum Electrolytic", mfr="Y",
                   mfr_part="EL1", package="D6.3", description="220uF 10V 20%",
                   basic=1, preferred=0, stock=15000, price=0.05)

def test_cap_prompt_hook_mentions_voltage_when_emphasized():
    h = CapPromptHook(emphasize_voltage=True)
    assert "voltage" in h.selection_criteria().lower()

def test_cap_prompt_hook_does_not_mention_voltage_when_not_emphasized():
    h = CapPromptHook(emphasize_voltage=False)
    assert "voltage" not in h.selection_criteria().lower()

def test_candidate_payload_structure():
    h = CapPromptHook(emphasize_voltage=True)
    p = h.candidate_payload(_row())
    assert p["lcsc"] == "C1"
    assert p["basic"] is True
    assert p["preferred"] is False
    assert p["stock"] == 15000
    assert "220uF 10V" in p["description"]
```

- [ ] **Step 2: Run, FAIL**

Run: `pytest tests/components/test_prompt_hooks.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

`src/jlcpcb_mapper/components/prompt_hooks.py`:
```python
"""Per-category LLM prompt hooks."""
from __future__ import annotations
from ..parts_db import PartRow

class CapPromptHook:
    def __init__(self, *, emphasize_voltage: bool):
        self.emphasize_voltage = emphasize_voltage

    def selection_criteria(self) -> str:
        base = "Prefer Basic parts with higher stock."
        if self.emphasize_voltage:
            return (base + " For electrolytic caps, prefer rated voltage "
                    "equal to or just above the requested voltage; avoid "
                    "significantly over-rated parts that are larger/more expensive.")
        return base

    def candidate_payload(self, row: PartRow) -> dict:
        return {
            "lcsc": row.lcsc,
            "mfr": row.mfr,
            "mfr_part": row.mfr_part,
            "package": row.package,
            "basic": bool(row.basic),
            "preferred": bool(row.preferred),
            "stock": row.stock,
            "price": row.price,
            "description": (row.description or "")[:200],
        }
```

- [ ] **Step 4: Run, PASS**

Run: `pytest tests/components/test_prompt_hooks.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/jlcpcb_mapper/components/prompt_hooks.py tests/components/test_prompt_hooks.py
git commit -m "feat(components): CapPromptHook with voltage-aware criteria"
```

---

### Task 13: Wire `POLARIZED_CAP` Category and pipeline skeleton; integration test for 220µF/10V

**Files:**
- Create: `src/jlcpcb_mapper/categories/polarized_cap.py`
- Modify: `src/jlcpcb_mapper/categories/__init__.py` — register built-in categories
- Create: `src/jlcpcb_mapper/core/pipeline.py`
- Test: `tests/test_pipeline_polarized.py`

- [ ] **Step 1: Write failing integration test**

`tests/test_pipeline_polarized.py`:
```python
import sqlite3
from pathlib import Path
import pytest
from jlcpcb_mapper.core.pipeline import run_pipeline, Targeted, Instance
from jlcpcb_mapper.parts_db import PartsDB

class _FakeLLM:
    def __init__(self):
        self.calls = 0
    def call(self, prompt, schema_keys):
        self.calls += 1
        raise AssertionError("scorer should have decided without LLM")

def _populate(conn):
    conn.executescript("""
        CREATE TABLE parts (
            lcsc TEXT PRIMARY KEY, category TEXT, mfr TEXT, mfr_part TEXT,
            package TEXT, description TEXT, basic INTEGER, preferred INTEGER,
            stock INTEGER, price REAL
        );
        -- Expected winner: basic, 10V exact, high stock
        INSERT INTO parts VALUES ('C16133','Aluminum Electrolytic','Nichicon','UWT1A221MCL1GS',
            'D6.3','220uF 10V ±20% 6.3x5.4mm',1,0,25000,0.05);
        -- Loser: non-basic, 10V, lower stock
        INSERT INTO parts VALUES ('C471773','Aluminum Electrolytic','Other','ELEB',
            'D6.3','220uF 10V 20%',0,0,15000,0.04);
        -- Wrong package
        INSERT INTO parts VALUES ('C9999','Aluminum Electrolytic','X','EL9',
            'D8','220uF 10V',1,0,30000,0.06);
        -- Under-rated (6.3V) — should be filtered
        INSERT INTO parts VALUES ('C8888','Aluminum Electrolytic','X','EL8',
            'D6.3','220uF 6.3V',1,0,40000,0.05);
    """)

@pytest.fixture
def db(tmp_path: Path) -> PartsDB:
    p = tmp_path / "parts.db"
    conn = sqlite3.connect(str(p)); _populate(conn); conn.commit(); conn.close()
    return PartsDB(p)

def test_220uf_10v_selects_basic_exact_voltage(db, tmp_path):
    instances = [
        Instance(sch_path=tmp_path / "x.kicad_sch",
                 reference="C12", lib_id="Device:CP",
                 value="220uF/10V", footprint="",
                 dnp=False, on_board=True, in_bom=True),
    ]
    decisions = run_pipeline(
        instances=instances,
        db=db,
        llm=_FakeLLM(),
        hints="",
        score_tiebreak_threshold=0.01,  # force scorer decision for this deterministic case
        llm_tiebreak_top_n=5,
        min_stock=1000,
        fp_out_dir=tmp_path / "fp",
    )
    assert len(decisions) == 1
    d = decisions[0]
    assert d.chosen_lcsc == "C16133"
    assert d.source == "score"
    # Footprint: no BuiltinMap entry → easyeda fallback is injected in pipeline wiring (stub in this test)
```

- [ ] **Step 2: Create `Instance`/`Targeted` dataclasses and pipeline skeleton**

`src/jlcpcb_mapper/core/pipeline.py`:
```python
"""Pipeline orchestration: categorize → parse → extract → group → query → decide → resolve."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

from .types import QuerySpec
from .registry import Registry
from ..categories.base import Category, ResolveResult
from ..categories import default_registry
from ..observability.trace import Trace
from ..parts_db import PartsDB, PartRow

@dataclass
class Instance:
    sch_path: Path
    reference: str
    lib_id: str
    value: str
    footprint: str
    dnp: bool = False
    on_board: bool = True
    in_bom: bool = True

@dataclass
class Targeted:
    inst: Instance
    category: Category
    spec: object          # a Spec
    package_hint: str

@dataclass
class Group:
    category: Category
    spec: object
    package_hint: str
    instances: list[Instance]
    trace: Trace = field(default_factory=Trace)

@dataclass
class Decision:
    group: Group
    chosen_lcsc: str | None
    candidates: list[PartRow]
    footprint: str
    downloaded: bool
    source: str            # "single" | "score" | "llm" | "failed"
    failure: str | None = None


def run_pipeline(
    *,
    instances: list[Instance],
    db: PartsDB,
    llm,
    hints: str,
    score_tiebreak_threshold: float,
    llm_tiebreak_top_n: int,
    min_stock: int,
    fp_out_dir: Path,
    registry: Registry | None = None,
    concurrency: int = 4,
) -> list[Decision]:
    reg = registry or default_registry(fp_out_dir=fp_out_dir)

    # Stage 1
    targeted: list[Targeted] = []
    for inst in instances:
        if not inst.on_board or not inst.value:
            continue
        cat = reg.lookup(inst.lib_id)
        if cat is None:
            continue
        spec = cat.value_parser.parse(inst.value) if cat.value_parser else None
        if spec is None:
            continue
        pkg = None
        if inst.footprint and cat.package_extractor:
            pkg = cat.package_extractor.extract(inst.footprint)
        pkg = pkg or cat.default_package
        targeted.append(Targeted(inst=inst, category=cat, spec=spec, package_hint=pkg))

    # Stage 2 — bucket
    buckets: dict[tuple, Group] = {}
    for t in targeted:
        k = (t.category.name, t.spec.group_key(), t.package_hint)
        g = buckets.get(k)
        if g is None:
            g = Group(category=t.category, spec=t.spec, package_hint=t.package_hint, instances=[])
            buckets[k] = g
        g.instances.append(t.inst)
    groups = list(buckets.values())

    # Stage 3 (parallel per group)
    decisions: list[Decision] = []
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as ex:
        futs = [
            ex.submit(_process_group, g, db, llm, hints,
                      score_tiebreak_threshold, llm_tiebreak_top_n, min_stock)
            for g in groups
        ]
        for f in as_completed(futs):
            decisions.append(f.result())
    # Stable order by first instance reference
    decisions.sort(key=lambda d: d.group.instances[0].reference)
    return decisions


def _process_group(g: Group, db, llm, hints, tau, top_n, min_stock) -> Decision:
    cat = g.category
    qspec: QuerySpec = cat.candidate_source.query(g.spec, g.package_hint)
    # Override min_stock if caller didn't specify one on the source
    if min_stock and qspec.min_stock == 0:
        qspec = QuerySpec(**{**qspec.__dict__, "min_stock": min_stock})
    g.trace.record("query", **{k: v for k, v in qspec.__dict__.items()})
    rows = db.execute(qspec)
    g.trace.record("query_result", count=len(rows))

    rows = cat.candidate_source.post_filter(rows, g.spec, g.package_hint)
    g.trace.record("post_filter", count=len(rows))
    if not rows:
        return Decision(g, None, [], "", False, "failed", "no_candidates")

    chosen, source = _decide(cat, g, rows, llm, hints, tau, top_n)

    # Resolve footprint
    all_have_fp = all(i.footprint for i in g.instances)
    if all_have_fp:
        res = ResolveResult(footprint="", downloaded=False)
    else:
        part = next(r for r in rows if r.lcsc == chosen)
        res = cat.footprint_resolver.resolve(part, g.package_hint)
    g.trace.record("resolve", footprint=res.footprint,
                   downloaded=res.downloaded, failed=res.download_failed)

    return Decision(g, chosen, rows, res.footprint, res.downloaded, source,
                    None if chosen else "no_selection")


def _decide(cat, g, rows, llm, hints, tau, top_n) -> tuple[str, str]:
    if len(rows) == 1:
        g.trace.record("decide", method="single", lcsc=rows[0].lcsc)
        return rows[0].lcsc, "single"

    if cat.scorer is not None:
        scored = sorted(
            ((cat.scorer.score(r, g.spec, g.trace), r) for r in rows),
            key=lambda t: -t[0],
        )
        top_score, top_row = scored[0]
        second_score = scored[1][0] if len(scored) > 1 else 0.0
        g.trace.record("score", top=top_score, second=second_score, top_lcsc=top_row.lcsc)
        if top_score - second_score >= tau:
            g.trace.record("decide", method="score", lcsc=top_row.lcsc,
                           diff=top_score - second_score)
            return top_row.lcsc, "score"
        rows = [r for _, r in scored[:top_n]]

    # LLM path
    prompt = _build_prompt(cat, g, rows, hints)
    try:
        resp = llm.call(prompt, schema_keys=["lcsc", "reason"])
        lcsc = resp.data.get("lcsc")
        if lcsc is None:
            g.trace.record("decide", method="llm_reject", fallback_lcsc=rows[0].lcsc)
            return rows[0].lcsc, "llm"
        if not any(r.lcsc == lcsc for r in rows):
            g.trace.record("decide", method="llm_hallucination", returned=lcsc,
                           fallback_lcsc=rows[0].lcsc)
            return rows[0].lcsc, "llm"
        g.trace.record("decide", method="llm", lcsc=lcsc, reason=resp.data.get("reason"))
        return lcsc, "llm"
    except Exception as e:
        g.trace.record("decide", method="llm_error_fallback", error=str(e),
                       fallback_lcsc=rows[0].lcsc)
        return rows[0].lcsc, "llm"


def _build_prompt(cat: Category, g: Group, rows: list[PartRow], hints: str) -> str:
    hook = cat.prompt_hook
    refs = ", ".join(i.reference for i in g.instances)
    cand_payload = [hook.candidate_payload(r) for r in rows]
    return (
        "You are a component selection assistant for JLCPCB PCB assembly.\n\n"
        f"Category: {cat.name}\n"
        f"Spec: {g.spec.display()}\n"
        f"Package hint: {g.package_hint}\n"
        f"Refs: {refs} (count={len(g.instances)})\n\n"
        f"User hints:\n{hints}\n\n"
        f"Selection criteria:\n{hook.selection_criteria()}\n\n"
        f"Candidates:\n{json.dumps(cand_payload, ensure_ascii=False)}\n\n"
        "Pick ONE LCSC. Return ONLY JSON: "
        '{"lcsc": "C...", "reason": "<one sentence>"}.\n'
        'If no candidate is suitable, return {"lcsc": null, "reason": "..."}.'
    )
```

- [ ] **Step 3: Build `POLARIZED_CAP` + `default_registry`**

`src/jlcpcb_mapper/categories/polarized_cap.py`:
```python
"""POLARIZED_CAP category bundle."""
from __future__ import annotations
from pathlib import Path
from .base import Category
from ..components.matchers import LibIdAny
from ..components.value_parsers import CapValueParser
from ..components.package_extractors import RegexFromRules
from ..components.candidate_sources import PolarizedCapSource
from ..components.scorers import PolarizedCapScorer
from ..components.footprint_resolvers import BuiltinMap, EasyedaFallback, Composite
from ..components.prompt_hooks import CapPromptHook

_PACKAGE_RULES = [
    (r"^Capacitor_SMD:CP_Elec_(\d+\.?\d*x\d+\.?\d*)",
     lambda m: f"D{m.group(1).split('x')[0]}"),
    (r"^Capacitor_THT:CP_Radial_D(\d+\.?\d*)mm",
     lambda m: f"D{m.group(1)}mm"),
]

def make(fp_out_dir: Path) -> Category:
    return Category(
        name="polarized_capacitor",
        matcher=LibIdAny(["Device:CP", "Device:CP_Small",
                          "Device:C_Polarized", "Device:C_Polarized_Small"]),
        value_parser=CapValueParser(keep_voltage=True),
        package_extractor=RegexFromRules(_PACKAGE_RULES),
        default_package="D6.3",
        candidate_source=PolarizedCapSource(),
        scorer=PolarizedCapScorer(),
        footprint_resolver=Composite([
            BuiltinMap({}),                 # populated incrementally per task below
            EasyedaFallback(out_dir=fp_out_dir),
        ]),
        prompt_hook=CapPromptHook(emphasize_voltage=True),
    )
```

`src/jlcpcb_mapper/categories/__init__.py`:
```python
"""Built-in category registration entrypoint."""
from __future__ import annotations
from pathlib import Path
from ..core.registry import Registry

def default_registry(*, fp_out_dir: Path) -> Registry:
    from . import polarized_cap
    r = Registry()
    r.register(polarized_cap.make(fp_out_dir=fp_out_dir))
    # Additional categories registered in later tasks.
    return r
```

- [ ] **Step 4: Stub EasyedaFallback for the integration test**

The integration test uses `LCSC:C16133_*` — but the fp_out_dir is empty and no real HTTP happens. Add a test-only easyeda stub via monkeypatch in the test:

Update `tests/test_pipeline_polarized.py` — add at top:
```python
import jlcpcb_mapper.components.footprint_resolvers as fr_mod

@pytest.fixture(autouse=True)
def _stub_easyeda(monkeypatch, tmp_path):
    def _fake_download(lcsc, out_dir):
        path = Path(out_dir) / f"{lcsc}_fake.kicad_mod"
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        path.write_text("(module fake)")
        return path
    # Monkey-patch at the module level where EasyedaFallback imports lazily.
    import jlcpcb_mapper.downloader as dl
    monkeypatch.setattr(dl, "download_footprint", _fake_download)
```

Add final assertions to the existing test:
```python
    assert d.footprint.startswith("LCSC:C16133")
    assert d.downloaded is True
```

- [ ] **Step 5: Run, FAIL → implement remaining → PASS**

Run: `pytest tests/test_pipeline_polarized.py -v`
Expected: If failures remain, fix. When all green: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add src/jlcpcb_mapper/core/pipeline.py src/jlcpcb_mapper/categories/polarized_cap.py src/jlcpcb_mapper/categories/__init__.py tests/test_pipeline_polarized.py
git commit -m "feat(pipeline): wire POLARIZED_CAP end-to-end; 220µF/10V integration passes"
```

---

## Phase C — Remaining categories

Each task in this phase follows the same shape as Task 13's wiring: pick components, wire a `Category`, register in `default_registry`, add at least one integration-style test that drives the new category through `run_pipeline` with a small in-memory parts.db. Full TDD cycle per component (test → fail → impl → pass → commit) remains mandatory.

### Task 14: Resistor category

**Files:**
- Create: `src/jlcpcb_mapper/categories/spec/resistor.py` — `ResistorSpec(value: Value)`
- Extend: `src/jlcpcb_mapper/components/value_parsers.py` — `ResistorValueParser` (port `values._R_RE` logic, emit `ResistorSpec`)
- Extend: `src/jlcpcb_mapper/components/candidate_sources.py` — `ResistorSource` (category_like `Chip Resistor%`, package exact, description LIKE built from `_resistor_si_pattern` logic from existing `candidates.py`)
- Extend: `src/jlcpcb_mapper/components/scorers.py` — `GenericBasicStockScorer` (basic 0.4 + preferred 0.2 + stock-bucket 0.4)
- Extend: `src/jlcpcb_mapper/components/package_extractors.py` — add resistor size rule
- Extend: `src/jlcpcb_mapper/components/prompt_hooks.py` — `GenericPromptHook` (emphasize tolerance/power only; the current config `hints` handles project-level preferences)
- Create: `src/jlcpcb_mapper/categories/resistor.py`
- Register in `categories/__init__.py`
- Tests: one test file per component extension, one integration test for `10k 0402`

**BuiltinMap contents** (from existing `kicad_fp.py`):
```python
RESISTOR_BUILTIN = {
    "0201": "Resistor_SMD:R_0201_0603Metric",
    "0402": "Resistor_SMD:R_0402_1005Metric",
    "0603": "Resistor_SMD:R_0603_1608Metric",
    "0805": "Resistor_SMD:R_0805_2012Metric",
    "1206": "Resistor_SMD:R_1206_3216Metric",
}
```

**Integration test** (`tests/test_pipeline_resistor.py`): `Device:R`, `value="10k"`, footprint `Resistor_SMD:R_0402_1005Metric` → chosen LCSC is basic, source=`score`, footprint preserved.

### Task 15: Ceramic capacitor category

- `categories/spec/cap.py` already has `CeramicCapSpec` (Task 6).
- `CapValueParser(keep_voltage=False)` already done.
- Extend `candidate_sources.py` — `CeramicCapSource` (category `%Ceramic Capacitor%`, `value_pattern` using `_value_to_sql_pattern` logic from existing `candidates.py`, package exact-match).
- Extend `scorers.py` — `CeramicCapScorer` with optional X7R/X5R preference from hints.
- Extend `package_extractors.py` — ceramic cap size rule.
- `categories/ceramic_cap.py`. Register.
- BuiltinMap: ceramic sizes from `kicad_fp.py`.
- Integration test: `Device:C`, `10uF`, `Capacitor_SMD:C_0603_1608Metric`.

### Task 16: Inductor category

- `categories/spec/inductor.py` — `InductorSpec(value: Value)`.
- Extend `value_parsers.py` — `InductorValueParser` (port `_L_RE`).
- Extend `candidate_sources.py` — `InductorSource` (ported from `candidates._inductor_pattern`).
- Use `GenericBasicStockScorer`.
- Extend `package_extractors.py` — inductor size rule.
- BuiltinMap: none (current codebase has none).
- Integration test with a small fixture.

### Task 17: LED category

- `categories/spec/led.py` — `LEDSpec(value: Value)`.
- `value_parsers.py` — `LEDValueParser` (passthrough; LED values are usually the color name or bare).
- `candidate_sources.py` — `LEDSource` (`Light Emitting Diode%`).
- Scorer: `GenericBasicStockScorer`.
- Extend `package_extractors.py` — LED size rule.
- BuiltinMap: LED sizes from `kicad_fp.py`.

### Task 18: Crystal category

- `categories/spec/crystal.py` — `CrystalSpec(value: Value)` (frequency).
- `value_parsers.py` — `CrystalValueParser` (parse `"16MHz"`, `"32.768kHz"`).
- `candidate_sources.py` — `CrystalSource` (`%Crystal%` broad + package substring post_filter; mirror current behavior for `_UNSUPPORTED` crystal branch).
- Scorer: `GenericBasicStockScorer`.
- Requires `package_hint`; if empty → Source returns empty (current behavior).

### Task 19: IC category

- `categories/spec/ic.py` — `ICSpec(value: Value | None, mpn: str)`.  Note: for ICs the "value" is the MPN itself.
- `value_parsers.py` — `ICValueParser` (passthrough, put raw into `mpn` field; value=None).
- `candidate_sources.py` — `ICSource` (MPN LIKE on `mfr_part`, requires `package_hint`, bails if missing).
- **Scorer=None** — IC picks are LLM-only.
- `prompt_hooks.py` — `ICPromptHook` emphasizing exact MPN match.
- Package extractor: reuse RegexFromRules from existing `footprint.py` (SOT/TO/QFN/SOIC/SOP/SSOP/TSSOP).
- No BuiltinMap (all download fallback).

### Task 20: Connector category

- `categories/spec/connector.py` — `ConnectorSpec(structure: str, pins: int, value: str)`. `structure` is one of `"1xN"`, `"2xN"`, or `"generic"`.
- Matcher: `LibIdPrefix(["Connector_Generic:Conn_01x", "Connector_Generic:Conn_02x"])` + generic `"Connector"` prefix.
- **Protocol extension**: `ValueParser.parse` needs `lib_id` to distinguish 1xN/2xN/generic connectors. Update the protocol signature once, here, to `parse(self, raw: str, *, lib_id: str | None = None) -> Spec | None`. Update earlier parsers (`CapValueParser`, `ResistorValueParser`, `InductorValueParser`, `LEDValueParser`, `CrystalValueParser`, `ICValueParser`) to accept and ignore the kwarg — one-line change each. Update `core/pipeline.py` Stage 1 to pass `lib_id=inst.lib_id`. Re-run every previous component test file to confirm none break.
- `value_parsers.py` — `ConnectorValueParser` (uses `lib_id` to set `structure` and `pins`; `value` is the raw string).
- `candidate_sources.py` — `ConnectorSource` mirrors existing `candidates.py` behavior: 1xN loose, 2xN requires package_hint, plain `connector` returns empty.
- Scorer: `None` (LLM-only).
- Integration tests: 1xN common case, 2xN-with-hint case, plain-connector skip case.
- Include a regression test `tests/components/test_value_parsers_accept_lib_id.py` that asserts every existing parser accepts `lib_id=` kwarg without error.

**After Task 20**: `pytest -k pipeline -v` should green across all integration tests. All current `lib_id` groups from real projects should route.

---

## Phase D — Observability + preflight

### Task 21: `GroupTrace` writer (`groups.jsonl` + `index.json`)

**Files:**
- Create: `src/jlcpcb_mapper/observability/writer.py`
- Test: `tests/observability/test_writer.py`

- [ ] **Step 1: Test**

`tests/observability/test_writer.py`:
```python
import json
from pathlib import Path
from jlcpcb_mapper.observability.trace import Trace
from jlcpcb_mapper.observability.writer import write_group_traces

class _FakeSpec:
    def display(self): return "220µF/10V"

class _FakeCat:
    name = "polarized_capacitor"

class _FakeGroup:
    def __init__(self):
        self.category = _FakeCat()
        self.spec = _FakeSpec()
        self.package_hint = "D6.3"
        self.instances = [type("I", (), {"reference": "C12"}), type("I", (), {"reference": "C15"})]
        self.trace = Trace()
        self.trace.record("match", lib_id="Device:CP", category="polarized_capacitor")

class _FakeDecision:
    def __init__(self):
        self.group = _FakeGroup()
        self.chosen_lcsc = "C16133"
        self.footprint = "LCSC:X"
        self.source = "score"
        self.failure = None

def test_writes_jsonl_one_line_per_group(tmp_path: Path):
    out = tmp_path / "traces" / "run"
    write_group_traces([_FakeDecision()], out)
    text = (out / "groups.jsonl").read_text().splitlines()
    assert len(text) == 1
    data = json.loads(text[0])
    assert data["category"] == "polarized_capacitor"
    assert data["spec_display"] == "220µF/10V"
    assert data["refs"] == ["C12", "C15"]
    assert data["outcome"]["lcsc"] == "C16133"

def test_writes_ref_index(tmp_path: Path):
    out = tmp_path / "traces" / "run"
    write_group_traces([_FakeDecision()], out)
    idx = json.loads((out / "index.json").read_text())
    assert idx["C12"] == 0
    assert idx["C15"] == 0
```

- [ ] **Step 2: Run, FAIL → implement**

`src/jlcpcb_mapper/observability/writer.py`:
```python
"""Write per-group traces to JSONL + ref→line index."""
from __future__ import annotations
from dataclasses import asdict
from pathlib import Path
import json

def write_group_traces(decisions, out_dir: Path) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_dir / "groups.jsonl"
    index: dict[str, int] = {}
    with jsonl_path.open("w") as f:
        for line_no, d in enumerate(decisions):
            g = d.group
            line = {
                "category": g.category.name,
                "spec_display": g.spec.display(),
                "package_hint": g.package_hint,
                "refs": [i.reference for i in g.instances],
                "events": [asdict(e) for e in g.trace.events],
                "outcome": {
                    "lcsc": d.chosen_lcsc,
                    "footprint": d.footprint,
                    "source": d.source,
                    "failure": d.failure,
                },
            }
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
            for i in g.instances:
                index[i.reference] = line_no
    (out_dir / "index.json").write_text(json.dumps(index, indent=2))
```

- [ ] **Step 3: PASS + commit**

```bash
git add src/jlcpcb_mapper/observability/writer.py tests/observability/test_writer.py
git commit -m "feat(observability): JSONL trace writer with ref index"
```

---

### Task 22: `RunReport` additions (fallback counters, source breakdown)

**Files:**
- Modify: `src/jlcpcb_mapper/report.py`
- Test: `tests/test_report_fallback_counters.py`

- [ ] **Step 1: Test**

`tests/test_report_fallback_counters.py`:
```python
from jlcpcb_mapper.report import RunReport

def test_run_report_tracks_fallback_counters():
    r = RunReport()
    r.record_source("score")
    r.record_source("llm_error_fallback")
    r.record_source("llm_error_fallback")
    txt = r.to_text()
    assert "llm_error_fallback: 2" in txt
    assert "score: 1" in txt
```

- [ ] **Step 2: Extend `RunReport`**

Append to `src/jlcpcb_mapper/report.py`:
```python
    def record_source(self, source: str) -> None:
        if not hasattr(self, "_sources"):
            self._sources = {}
        self._sources[source] = self._sources.get(source, 0) + 1
```

Also update `to_text` to render `_sources`:
```python
        if getattr(self, "_sources", None):
            lines.append("Sources:")
            for k, v in sorted(self._sources.items()):
                lines.append(f"  {k}: {v}")
```

And add `_sources` to `to_dict`:
```python
    def to_dict(self) -> dict:
        d = asdict(self)
        if hasattr(self, "_sources"):
            d["sources"] = self._sources
        return d
```

- [ ] **Step 3: PASS + commit**

```bash
git add src/jlcpcb_mapper/report.py tests/test_report_fallback_counters.py
git commit -m "feat(report): per-source counters surfaced in to_text/to_dict"
```

---

### Task 23: Preflight — unmatched `lib_id` coverage report

**Files:**
- Modify: `src/jlcpcb_mapper/preflight.py`
- Test: `tests/test_preflight_coverage.py`

- [ ] **Step 1: Test**

`tests/test_preflight_coverage.py`:
```python
from jlcpcb_mapper.preflight import lib_id_coverage_report

def test_reports_unmatched_lib_ids(mocker):
    class _Cat:
        def __init__(self, name, ids):
            self.name = name; self.ids = set(ids)
        class _M:
            pass
        def _mk_matcher(self):
            ids = self.ids
            class _M:
                def matches(self, x): return x in ids
            return _M()

    # Use real Registry for fidelity
    from jlcpcb_mapper.core.registry import Registry
    from jlcpcb_mapper.categories.base import Category
    class _M:
        def __init__(self, ids): self.ids = ids
        def matches(self, x): return x in self.ids
    def _c(name, ids): return Category(name, _M(ids), None, None, "", None, None, None, None)
    reg = Registry()
    reg.register(_c("resistor", {"Device:R"}))
    reg.register(_c("capacitor", {"Device:C"}))

    lib_ids = ["Device:R", "Device:R", "Device:C", "Device:Q_NPN_CBE", "Device:Fuse"]
    rep = lib_id_coverage_report(lib_ids, reg)
    assert rep["matched"]["resistor"] == 2
    assert rep["matched"]["capacitor"] == 1
    assert set(rep["unmatched"]) == {"Device:Q_NPN_CBE", "Device:Fuse"}
    assert rep["unmatched_counts"] == {"Device:Q_NPN_CBE": 1, "Device:Fuse": 1}
```

- [ ] **Step 2: Implement**

Append to `src/jlcpcb_mapper/preflight.py`:
```python
from collections import Counter
from .core.registry import Registry

def lib_id_coverage_report(lib_ids: list[str], registry: Registry) -> dict:
    matched: Counter = Counter()
    unmatched: Counter = Counter()
    for lid in lib_ids:
        cat = registry.lookup(lid)
        if cat is None:
            unmatched[lid] += 1
        else:
            matched[cat.name] += 1
    return {
        "matched": dict(matched),
        "unmatched": sorted(unmatched.keys()),
        "unmatched_counts": dict(unmatched),
    }
```

- [ ] **Step 3: Test, PASS**

Run: `pytest tests/test_preflight_coverage.py -v`
Expected: 1 passed.

- [ ] **Step 4: Commit**

```bash
git add src/jlcpcb_mapper/preflight.py tests/test_preflight_coverage.py
git commit -m "feat(preflight): lib_id coverage report"
```

---

### Task 24: `llm_error_fallback` is explicit (surfaced from pipeline → RunReport)

**Files:**
- Modify: `src/jlcpcb_mapper/core/pipeline.py` — expose each decision's `source`
- Test: `tests/test_pipeline_llm_failures.py`

Currently pipeline already records trace events. This task ensures the `RunReport.record_source` wiring is tested end-to-end with LLM failure modes.

- [ ] **Step 1: Test**

```python
# tests/test_pipeline_llm_failures.py
from pathlib import Path
import pytest
from jlcpcb_mapper.core.pipeline import run_pipeline, Instance
# ... fixture mirrors test_pipeline_polarized but with scorer threshold raised
# to force LLM tiebreak, and FakeLLM that raises / returns hallucinated LCSC / null.

class _RaisingLLM:
    def call(self, prompt, schema_keys): raise RuntimeError("boom")

class _NullLLM:
    class _Resp: data = {"lcsc": None, "reason": "dunno"}
    def call(self, prompt, schema_keys): return self._Resp()

class _HallLLM:
    class _Resp: data = {"lcsc": "C00000", "reason": "made up"}
    def call(self, prompt, schema_keys): return self._Resp()

def _run(llm, db, tmp_path, tau=10.0):
    inst = Instance(sch_path=tmp_path/"x.kicad_sch", reference="C1",
                    lib_id="Device:CP", value="220uF/10V", footprint="",
                    dnp=False, on_board=True, in_bom=True)
    return run_pipeline(instances=[inst], db=db, llm=llm, hints="",
                        score_tiebreak_threshold=tau, llm_tiebreak_top_n=5,
                        min_stock=1000, fp_out_dir=tmp_path/"fp")

# Reuse the polarized_cap fixture shape from test_pipeline_polarized.
```

(Port fixture setup from `test_pipeline_polarized.py`; the new assertions: raising LLM → trace contains `decide.method="llm_error_fallback"`; null → `llm_reject`; hallucination → `llm_hallucination`.)

- [ ] **Step 2: Verify existing pipeline already emits these methods** (it does from Task 13). If assertions fail, patch pipeline. Otherwise just commit the test.

- [ ] **Step 3: Commit**

```bash
git add tests/test_pipeline_llm_failures.py
git commit -m "test(pipeline): LLM reject/hallucinate/raise produce explicit trace methods"
```

---

## Phase E — Migration: move I/O, switch `map_cmd`, delete old code

### Task 25: Move I/O modules under `io/`

**Files:**
- Create: `src/jlcpcb_mapper/io/__init__.py` (empty)
- Move: `src/jlcpcb_mapper/parts_db.py` → `src/jlcpcb_mapper/io/parts_db.py`
- Move: `src/jlcpcb_mapper/schematic.py` → `src/jlcpcb_mapper/io/schematic.py`
- Move: `src/jlcpcb_mapper/downloader.py` → `src/jlcpcb_mapper/io/easyeda.py`
- Move: `src/jlcpcb_mapper/llm.py` → `src/jlcpcb_mapper/io/llm.py`

- [ ] **Step 1: Move files with `git mv`**

```bash
mkdir -p src/jlcpcb_mapper/io
git mv src/jlcpcb_mapper/parts_db.py src/jlcpcb_mapper/io/parts_db.py
git mv src/jlcpcb_mapper/schematic.py src/jlcpcb_mapper/io/schematic.py
git mv src/jlcpcb_mapper/downloader.py src/jlcpcb_mapper/io/easyeda.py
git mv src/jlcpcb_mapper/llm.py src/jlcpcb_mapper/io/llm.py
touch src/jlcpcb_mapper/io/__init__.py
```

- [ ] **Step 2: Update all imports of these modules**

Replace `from .parts_db import` → `from .io.parts_db import` across the codebase.
Replace `from .schematic import` → `from .io.schematic import`.
Replace `from .downloader import` → `from .io.easyeda import`.
Replace `from .llm import` → `from .io.llm import`.

Also remove the temporary `try/except ImportError` shim at the top of `categories/base.py` and replace with a direct `from ..io.parts_db import PartRow`.

Grep:
```bash
grep -rn "from .parts_db\|from .schematic\|from .downloader\|from .llm\|from jlcpcb_mapper.parts_db\|from jlcpcb_mapper.schematic\|from jlcpcb_mapper.downloader\|from jlcpcb_mapper.llm" src tests
```
Update each hit.

- [ ] **Step 3: Run full test suite**

Run: `pytest -x`
Expected: all green.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor: relocate parts_db/schematic/easyeda/llm under io/"
```

---

### Task 26: New `map_cmd.py` driving the new pipeline

**Files:**
- Replace: `src/jlcpcb_mapper/commands/map_cmd.py`
- Modify: `src/jlcpcb_mapper/cli.py` — unchanged surface, delegates into new map_cmd
- Create: `tests/fixtures/minimal_sch.py` — KiCad-9 schematic factory
- Test: `tests/commands/test_map_cmd_new.py`

- [ ] **Step 1: Schematic fixture helper**

`tests/fixtures/minimal_sch.py`:
```python
"""Smallest valid KiCad-9 schematic bytes for round-trip tests."""
MINIMAL_SCH_TEMPLATE = '''(kicad_sch
\t(version 20231120)
\t(generator "jlcpcb-mapper-tests")
\t(uuid "00000000-0000-0000-0000-000000000001")
\t(paper "A4")
\t(lib_symbols
\t)
\t(symbol
\t\t(lib_id "{lib_id}")
\t\t(at 50 50 0)
\t\t(unit 1)
\t\t(uuid "00000000-0000-0000-0000-{ref_pad:0>12}")
\t\t(property "Reference" "{reference}"
\t\t\t(at 0 0 0)
\t\t\t(effects (font (size 1.27 1.27)))
\t\t)
\t\t(property "Value" "{value}"
\t\t\t(at 0 0 0)
\t\t\t(effects (font (size 1.27 1.27)))
\t\t)
\t\t(property "Footprint" "{footprint}"
\t\t\t(at 0 0 0)
\t\t\t(effects (font (size 1.27 1.27)))
\t\t)
\t)
)
'''

def minimal_sch_one_symbol(*, reference: str, lib_id: str, value: str, footprint: str = "") -> str:
    return MINIMAL_SCH_TEMPLATE.format(
        reference=reference, lib_id=lib_id, value=value,
        footprint=footprint, ref_pad=reference.replace("C", "").replace("R", ""),
    )
```

Add a sanity test for the fixture so it round-trips through `Schematic`:

`tests/fixtures/test_minimal_sch.py`:
```python
from pathlib import Path
from jlcpcb_mapper.io.schematic import Schematic
from .minimal_sch import minimal_sch_one_symbol

def test_minimal_sch_parses(tmp_path: Path):
    p = tmp_path / "x.kicad_sch"
    p.write_text(minimal_sch_one_symbol(reference="C12", lib_id="Device:CP",
                                         value="220uF/10V", footprint=""))
    sch = Schematic.load(p)
    insts = sch.instances()
    assert len(insts) == 1
    assert insts[0].reference == "C12"
    assert insts[0].lib_id == "Device:CP"
    assert insts[0].value == "220uF/10V"
    assert insts[0].footprint == ""
```

Run: `pytest tests/fixtures/test_minimal_sch.py -v`
Expected: PASS. If `Schematic` parses return zero instances, adjust the template to match what `_find_instance_blocks` expects. This step pins down the exact minimal text that the existing text-based parser accepts.

- [ ] **Step 2: Integration test for `run_map`**

`tests/commands/test_map_cmd_new.py`:
```python
import sqlite3
from pathlib import Path
import pytest
from jlcpcb_mapper.config import load_config
from jlcpcb_mapper.commands.map_cmd import run_map
from tests.fixtures.minimal_sch import minimal_sch_one_symbol

_DB_SQL = """
CREATE TABLE parts (
    lcsc TEXT PRIMARY KEY, category TEXT, mfr TEXT, mfr_part TEXT,
    package TEXT, description TEXT, basic INTEGER, preferred INTEGER,
    stock INTEGER, price REAL
);
INSERT INTO parts VALUES ('C16133','Aluminum Electrolytic','Nichicon','X','D6.3','220uF 10V',1,0,25000,0.05);
INSERT INTO parts VALUES ('C471773','Aluminum Electrolytic','Other','Y','D6.3','220uF 10V',0,0,15000,0.04);
"""

def _mk_project(tmp_path: Path) -> Path:
    proj = tmp_path / "p.kicad_pro"
    proj.write_text("{}")
    (tmp_path / "p.kicad_sch").write_text(
        minimal_sch_one_symbol(reference="C12", lib_id="Device:CP",
                               value="220uF/10V", footprint="")
    )
    return proj

def _mk_db(tmp_path: Path) -> Path:
    p = tmp_path / "parts.db"
    conn = sqlite3.connect(str(p))
    conn.executescript(_DB_SQL)
    conn.commit(); conn.close()
    return p

def test_run_map_writes_lcsc_and_footprint(tmp_path, monkeypatch):
    # Stub preflight's side-effectful checks
    monkeypatch.setattr("jlcpcb_mapper.preflight._claude_ok", lambda: True)
    monkeypatch.setattr("jlcpcb_mapper.preflight._git_is_clean", lambda paths: True)
    # Stub easyeda download so no HTTP happens
    import jlcpcb_mapper.io.easyeda as ez
    def _fake_dl(lcsc, d):
        Path(d).mkdir(parents=True, exist_ok=True)
        p = Path(d) / f"{lcsc}_fake.kicad_mod"
        p.write_text("(module fake)")
        return p
    monkeypatch.setattr(ez, "download_footprint", _fake_dl)

    project = _mk_project(tmp_path)
    cfg = load_config(tmp_path / "nope.yaml")  # returns defaults-only Config
    cfg.parts_db = str(_mk_db(tmp_path))

    report = run_map(
        project_pro=project, config=cfg,
        non_interactive=True, force=True, allow_stale_db=True,
        fill_lcsc_only=False, include_dnp=True, apply_suggestions=False,
    )
    assert report.filtered_in == 1
    text = (tmp_path / "p.kicad_sch").read_text()
    assert 'C16133' in text
    assert 'LCSC:C16133' in text
    # Trace file exists
    traces = list((tmp_path / ".jlcpcb-mapper" / "traces").iterdir())
    assert len(traces) == 1
    assert (traces[0] / "groups.jsonl").exists()
```

- [ ] **Step 2: Rewrite `commands/map_cmd.py`**

```python
"""map_cmd: new pipeline-driven implementation."""
from __future__ import annotations
from pathlib import Path
from datetime import datetime
from ..config import Config
from ..project import load_project, select_targets
from ..io.parts_db import PartsDB
from ..io.schematic import atomic_update
from ..io.llm import ClaudeClient
from ..preflight import run_preflight, lib_id_coverage_report
from ..report import RunReport
from ..core.pipeline import run_pipeline, Instance
from ..categories import default_registry
from ..observability.writer import write_group_traces


def _autodetect_parts_db() -> Path:
    return Path.home() / "Library/Application Support/kicad/9.0/3rdparty/plugins/com_github_bouni_kicad-jlcpcb-tools/jlcpcb_parts.db"


def run_map(
    *, project_pro: Path, config: Config,
    non_interactive: bool, force: bool, allow_stale_db: bool,
    fill_lcsc_only: bool, include_dnp: bool, apply_suggestions: bool,
) -> RunReport:
    proj = load_project(project_pro)
    parts_db_path = Path(config.parts_db).expanduser() if config.parts_db else _autodetect_parts_db()

    run_preflight(proj.schematics, parts_db_path, force=force,
                  allow_stale_db=allow_stale_db, skip_claude_check=False)

    report = RunReport()
    report.schematics = [str(p) for p in proj.schematics]

    # Coverage check
    fp_out_dir = proj.root / config.download.output_dir / "footprints.pretty"
    registry = default_registry(fp_out_dir=fp_out_dir)
    all_insts = [i for p in proj.schematics for i in proj.loaded[p].instances()]
    report.total_empty_instances = sum(1 for i in all_insts if i.footprint == "")
    cov = lib_id_coverage_report([i.lib_id for i in all_insts], registry)
    if cov["unmatched"] and not non_interactive:
        import click
        click.echo("Unmatched lib_ids:")
        for lid in cov["unmatched"]:
            click.echo(f"  {lid}: {cov['unmatched_counts'][lid]}")
        if not click.confirm("Continue with these skipped?", default=False):
            raise click.Abort()

    targets = select_targets(proj, fill_lcsc_only=fill_lcsc_only, include_dnp=include_dnp)
    report.filtered_in = len(targets)
    if not targets:
        return report

    instances = [
        Instance(sch_path=t.sch_path, reference=t.inst.reference,
                 lib_id=t.inst.lib_id, value=t.inst.value,
                 footprint=t.inst.footprint, dnp=t.inst.dnp,
                 on_board=t.inst.on_board, in_bom=t.inst.in_bom)
        for t in targets
    ]

    llm = ClaudeClient(model=config.llm.model,
                       timeout=config.llm.timeout_seconds,
                       retry=config.llm.retry_on_parse_fail)

    decisions = run_pipeline(
        instances=instances, db=PartsDB(parts_db_path),
        llm=llm, hints=config.hints,
        score_tiebreak_threshold=getattr(config, "score_tiebreak_threshold", 0.1),
        llm_tiebreak_top_n=getattr(config, "llm_tiebreak_top_n", 5),
        min_stock=config.selection.min_stock,
        fp_out_dir=fp_out_dir,
        registry=registry,
        concurrency=config.llm.concurrency,
    )

    # Apply edits
    ref_to_sch = {t.inst.reference: t.sch_path for t in targets}
    from collections import defaultdict
    edits_by_sch: dict[Path, list[tuple[str, str, str]]] = defaultdict(list)
    for d in decisions:
        report.record_source(d.source if d.chosen_lcsc else "failed")
        if not d.chosen_lcsc:
            report.add_failure(kind="no_candidates",
                               detail=f"{d.group.category.name} {d.group.spec.display()} refs={[i.reference for i in d.group.instances]}")
            continue
        report.add_group_result(
            group_label=f"{d.group.category.name} {d.group.spec.display()} {d.group.package_hint}".strip(),
            refs=[i.reference for i in d.group.instances],
            lcsc=d.chosen_lcsc, footprint=d.footprint,
            downloaded=d.downloaded, source=d.source,
        )
        for inst in d.group.instances:
            sch_path = ref_to_sch.get(inst.reference)
            if sch_path is None: continue
            fp_to_write = "" if inst.footprint else d.footprint
            edits_by_sch[sch_path].append((inst.reference, d.chosen_lcsc, fp_to_write))

    ts = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    backup_root = proj.root / ".jlcpcb-mapper" / "backups" / ts
    for sch_path, edits in edits_by_sch.items():
        atomic_update(sch_path, _build_mutator(edits), backup_dir=backup_root)

    # Write traces + run log
    traces_dir = proj.root / ".jlcpcb-mapper" / "traces" / ts
    write_group_traces(decisions, traces_dir)
    log_path = proj.root / ".jlcpcb-mapper" / f"run-{ts}.json"
    report.write_json(log_path)
    return report


def _build_mutator(edits):
    def mutate(sch):
        by_ref = {i.reference: i for i in sch.instances()}
        for ref, lcsc, fp in edits:
            inst = by_ref.get(ref)
            if inst is None: continue
            if lcsc: sch.set_lcsc(inst, lcsc)
            if fp: sch.set_footprint(inst, fp)
    return mutate
```

- [ ] **Step 3: Run the new integration test**

Run: `pytest tests/commands/test_map_cmd_new.py -v`
Expected: PASS.

- [ ] **Step 4: Run the full suite**

Run: `pytest -x`
Expected: all green. If old `tests/test_map_cmd.py` still exists and uses old select/candidates/grouper imports directly, delete it in Task 28.

- [ ] **Step 5: Commit**

```bash
git add src/jlcpcb_mapper/commands/map_cmd.py tests/commands/test_map_cmd_new.py
git commit -m "refactor(map_cmd): drive new pipeline end-to-end"
```

---

### Task 27: Golden-file regression harness

**Files:**
- Create: `tests/golden/__init__.py`
- Create: `tests/golden/cases/` directory with inputs
- Create: `tests/golden/expected/` directory with expected traces
- Create: `tests/golden/conftest.py` — test generator + `--update-golden` opt-in

- [ ] **Step 1: Sketch harness**

`tests/golden/conftest.py`:
```python
import json
from pathlib import Path
import pytest
import yaml

CASES_DIR = Path(__file__).parent / "cases"
EXPECTED_DIR = Path(__file__).parent / "expected"

def pytest_addoption(parser):
    parser.addoption("--update-golden", action="store_true",
                     help="Regenerate golden trace files")

def _normalize(jsonl: str) -> str:
    """Strip timestamp_ms for deterministic comparison."""
    out = []
    for line in jsonl.splitlines():
        obj = json.loads(line)
        for e in obj.get("events", []):
            e["timestamp_ms"] = 0
        out.append(json.dumps(obj, ensure_ascii=False, sort_keys=True))
    return "\n".join(out)

def pytest_generate_tests(metafunc):
    if "golden_case" in metafunc.fixturenames:
        cases = sorted(CASES_DIR.glob("*.yaml"))
        metafunc.parametrize("golden_case", cases, ids=[c.stem for c in cases])
```

`tests/golden/test_golden.py`:
```python
from pathlib import Path
import json, sqlite3, yaml
from jlcpcb_mapper.core.pipeline import run_pipeline, Instance
from jlcpcb_mapper.categories import default_registry
from jlcpcb_mapper.io.parts_db import PartsDB
from jlcpcb_mapper.observability.writer import write_group_traces
from .conftest import EXPECTED_DIR, _normalize

class _DeterministicLLM:
    def __init__(self, mapping): self.mapping = mapping
    def call(self, prompt, schema_keys):
        class R: pass
        r = R()
        for key, val in self.mapping.items():
            if key in prompt:
                r.data = val; return r
        r.data = {"lcsc": None, "reason": "no rule"}; return r

def test_golden(golden_case, tmp_path, request):
    case = yaml.safe_load(golden_case.read_text())
    # Build in-memory DB
    dbp = tmp_path / "p.db"
    conn = sqlite3.connect(str(dbp))
    conn.executescript(case["db_schema"])
    conn.commit(); conn.close()

    instances = [Instance(sch_path=tmp_path/"x.kicad_sch", **i) for i in case["instances"]]
    llm = _DeterministicLLM(case.get("llm_responses", {}))

    decisions = run_pipeline(
        instances=instances, db=PartsDB(dbp), llm=llm, hints=case.get("hints",""),
        score_tiebreak_threshold=case.get("tau", 0.05),
        llm_tiebreak_top_n=5, min_stock=case.get("min_stock", 1000),
        fp_out_dir=tmp_path/"fp",
    )
    write_group_traces(decisions, tmp_path / "out")
    produced = _normalize((tmp_path/"out"/"groups.jsonl").read_text())

    expected_path = EXPECTED_DIR / (golden_case.stem + ".jsonl")
    if request.config.getoption("--update-golden"):
        expected_path.write_text(produced + "\n")
        return
    assert expected_path.read_text().rstrip() == produced
```

- [ ] **Step 2: Add one case file**

`tests/golden/cases/polarized_cap_220uf_10v.yaml`:
```yaml
db_schema: |
  CREATE TABLE parts (
    lcsc TEXT PRIMARY KEY, category TEXT, mfr TEXT, mfr_part TEXT,
    package TEXT, description TEXT, basic INTEGER, preferred INTEGER,
    stock INTEGER, price REAL
  );
  INSERT INTO parts VALUES ('C16133','Aluminum Electrolytic','Nichicon','X','D6.3','220uF 10V',1,0,25000,0.05);
  INSERT INTO parts VALUES ('C471773','Aluminum Electrolytic','Other','Y','D6.3','220uF 10V',0,0,15000,0.04);
instances:
  - reference: "C12"
    lib_id: "Device:CP"
    value: "220uF/10V"
    footprint: ""
```

- [ ] **Step 3: Generate baseline**

Run: `pytest tests/golden/ --update-golden`
Verify the generated `tests/golden/expected/polarized_cap_220uf_10v.jsonl` is correct by hand.

- [ ] **Step 4: Lock in**

Run: `pytest tests/golden/ -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/golden/
git commit -m "test(golden): regression harness + polarized_cap 220µF/10V case"
```

---

### Task 28: Delete legacy modules

**Files:**
- Delete: `src/jlcpcb_mapper/values.py`
- Delete: `src/jlcpcb_mapper/candidates.py`
- Delete: `src/jlcpcb_mapper/footprint.py`
- Delete: `src/jlcpcb_mapper/kicad_fp.py`
- Delete: `src/jlcpcb_mapper/grouper.py`
- Delete: `src/jlcpcb_mapper/select.py`
- Delete: `src/jlcpcb_mapper/review.py`
- Delete: `src/jlcpcb_mapper/resolver.py`
- Delete legacy tests that reference them: `tests/test_values.py`, `tests/test_candidates.py`, `tests/test_footprint.py`, `tests/test_kicad_fp.py`, `tests/test_grouper.py`, `tests/test_select.py`, `tests/test_review.py`, `tests/test_resolver.py`
- Also delete the legacy `PartsDB.query_candidates` method from `io/parts_db.py`.

- [ ] **Step 1: Verify no runtime imports remain**

Run: `grep -rn "from jlcpcb_mapper.\(values\|candidates\|footprint\|kicad_fp\|grouper\|select\|review\|resolver\)\|from .\(values\|candidates\|footprint\|kicad_fp\|grouper\|select\|review\|resolver\) " src`
Expected: no hits.

- [ ] **Step 2: Delete**

```bash
git rm src/jlcpcb_mapper/values.py src/jlcpcb_mapper/candidates.py \
       src/jlcpcb_mapper/footprint.py src/jlcpcb_mapper/kicad_fp.py \
       src/jlcpcb_mapper/grouper.py src/jlcpcb_mapper/select.py \
       src/jlcpcb_mapper/review.py src/jlcpcb_mapper/resolver.py
git rm tests/test_values.py tests/test_candidates.py tests/test_footprint.py \
       tests/test_kicad_fp.py tests/test_grouper.py tests/test_select.py \
       tests/test_review.py tests/test_resolver.py
```

- [ ] **Step 3: Remove `query_candidates` from `io/parts_db.py`**

Delete the old `query_candidates` method body and the `COLS` constant usage in it. Keep `COLS` (still used by `execute`).

- [ ] **Step 4: Run full suite**

Run: `pytest`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: remove legacy category-specific modules and tests (superseded by categories/ and components/)"
```

---

### Task 29: Config additions + docs refresh

**Files:**
- Modify: `src/jlcpcb_mapper/default_config.yaml` — add `score_tiebreak_threshold`, `llm_tiebreak_top_n`
- Modify: `src/jlcpcb_mapper/config.py` — surface those fields on `Config`
- Modify: `README.md` — note traces and coverage prompt

- [ ] **Step 1: Add config keys**

`src/jlcpcb_mapper/default_config.yaml`:
```yaml
# ... existing keys ...
score_tiebreak_threshold: 0.1
llm_tiebreak_top_n: 5
```

- [ ] **Step 2: Extend `Config` dataclass**

Add to `config.py`:
```python
@dataclass
class Config:
    parts_db: str | None
    llm: LLMSettings
    selection: SelectionSettings
    verify: VerifySettings
    download: DownloadSettings
    kicad_footprint_map_overrides: dict
    hints: str
    score_tiebreak_threshold: float = 0.1
    llm_tiebreak_top_n: int = 5
    _used_defaults_only: bool = False
```
and extend the `load_config` constructor to pull from `merged`.

- [ ] **Step 3: Update README**

Append to README.md:
```markdown
## Observability

Each `map` run writes:
- `.jlcpcb-mapper/run-<ts>.json` — summary (same as before; adds per-source counts)
- `.jlcpcb-mapper/traces/<ts>/groups.jsonl` — one line per group with full stage trace
- `.jlcpcb-mapper/traces/<ts>/index.json` — reference → line-offset index

Preflight now lists unmatched `lib_id`s and (in interactive mode) asks before proceeding.
```

- [ ] **Step 4: Run suite + commit**

Run: `pytest`
```bash
git add -A
git commit -m "chore: surface pipeline thresholds in config; document traces in README"
```

---

## Self-review checklist

- [ ] Every task lists Files: Create / Modify / Test paths.
- [ ] Every code step contains the code to be written (no "fill in").
- [ ] Every test step shows the assertion content.
- [ ] Commits are small (one task per commit in general).
- [ ] Phase B proves the architecture on the motivating acceptance case before Phase C.
- [ ] Phase E's deletion happens only after all call-sites have migrated (Phase D wires new, Phase E deletes old).

## Open items noted in spec

- Exact BuiltinMap contents for crystal/IC/connector — filled in as each category task lands.
- `explain <ref>` CLI — deferred; `index.json` is written now for later use.
- `components/` flat vs sub-packages — decide after Task 20 ships.
