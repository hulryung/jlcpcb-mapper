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
