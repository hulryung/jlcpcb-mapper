from __future__ import annotations
from dataclasses import dataclass, field, asdict
from pathlib import Path
import json

@dataclass
class GroupOutcome:
    group_label: str
    refs: list[str]
    lcsc: str | None
    footprint: str
    downloaded: bool
    source: str  # "llm" | "single-candidate" | "llm-failed-fallback"

@dataclass
class Failure:
    kind: str
    detail: str

@dataclass
class RunReport:
    schematics: list[str] = field(default_factory=list)
    total_empty_instances: int = 0
    filtered_in: int = 0
    groups: list[GroupOutcome] = field(default_factory=list)
    failures: list[Failure] = field(default_factory=list)
    sources: dict[str, int] = field(default_factory=dict)

    def add_group_result(self, **kw) -> None:
        self.groups.append(GroupOutcome(**kw))

    def add_failure(self, **kw) -> None:
        self.failures.append(Failure(**kw))

    def record_source(self, source: str) -> None:
        self.sources[source] = self.sources.get(source, 0) + 1

    def to_dict(self) -> dict:
        return asdict(self)

    def to_text(self) -> str:
        lines = [
            "=== jlcpcb-mapper summary ===",
            f"Schematics: {len(self.schematics)} files, {self.total_empty_instances} empty-footprint instances",
            f"Filtered in: {self.filtered_in}",
            f"Groups: {len(self.groups)}",
        ]
        if self.sources:
            lines.append("Sources:")
            for k, v in sorted(self.sources.items()):
                lines.append(f"  {k}: {v}")
        if self.failures:
            lines.append("Failures:")
            for f in self.failures:
                lines.append(f"  - [{f.kind}] {f.detail}")
        return "\n".join(lines)

    def write_json(self, path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False))
