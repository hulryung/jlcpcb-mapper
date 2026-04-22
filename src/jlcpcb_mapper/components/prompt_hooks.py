"""Per-category LLM prompt hooks."""
from __future__ import annotations
from ..parts_db import PartRow


def _common_candidate_payload(row: PartRow) -> dict:
    """Standard 9-key candidate payload shared across prompt hooks."""
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


class GenericPromptHook:
    """Generic prompt hook for categories that don't need special emphasis."""

    def selection_criteria(self) -> str:
        return "Prefer Basic parts with higher stock."

    def candidate_payload(self, row: PartRow) -> dict:
        return _common_candidate_payload(row)


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
        return _common_candidate_payload(row)


class ICPromptHook:
    """Prompt hook for ICs. Emphasizes exact MPN match."""

    def selection_criteria(self) -> str:
        return ("Prefer Basic parts with higher stock. "
                "CRITICALLY: the mfr_part field must match the requested MPN "
                "exactly (allowing for trailing variant codes like -REEL, /TR). "
                "Do not select a different part family with a similar name.")

    def candidate_payload(self, row: PartRow) -> dict:
        return _common_candidate_payload(row)
