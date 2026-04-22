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
