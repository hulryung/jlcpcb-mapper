"""Category bundle: composition of pipeline-stage components."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol, runtime_checkable
from ..core.types import QuerySpec, Spec
from ..io.parts_db import PartRow
from ..observability.trace import Trace


@runtime_checkable
class Matcher(Protocol):
    def matches(self, lib_id: str) -> bool: ...


@runtime_checkable
class ValueParser(Protocol):
    def parse(self, raw: str, *, lib_id: str | None = None) -> Spec | None: ...


@runtime_checkable
class PackageExtractor(Protocol):
    def extract(self, kicad_footprint: str) -> str | None: ...


@runtime_checkable
class CandidateSource(Protocol):
    def query(self, spec: Spec, package_hint: str) -> QuerySpec: ...
    def post_filter(self, rows: list[PartRow], spec: Spec, package_hint: str) -> list[PartRow]: ...


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
