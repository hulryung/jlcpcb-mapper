"""Deterministic scorers for categories that permit objective ranking."""
from __future__ import annotations
import re
from ..parts_db import PartRow
from ..observability.trace import Trace


_VOLTAGE_TOKEN = re.compile(r"(\d+(?:\.\d+)?)\s*V(?:DC|AC)?\b", re.IGNORECASE)


def _stock_bucket(stock: int) -> float:
    # Logarithmic-ish: >=50k → 1.0, 10k → 0.7, 5k → 0.5, 1k → 0.3, <1k → 0.1
    if stock >= 50_000: return 1.0
    if stock >= 10_000: return 0.7
    if stock >= 5_000:  return 0.5
    if stock >= 1_000:  return 0.3
    return 0.1


class GenericBasicStockScorer:
    """Generic scorer for categories with no voltage/tolerance axis.

    Weights: basic (0.4) + preferred (0.2) + stock-bucket (0.4).
    """

    W_BASIC = 0.4
    W_PREFERRED = 0.2
    W_STOCK = 0.4

    def score(self, row: PartRow, spec, trace: Trace) -> float:
        basic = self.W_BASIC if row.basic else 0.0
        preferred = self.W_PREFERRED if row.preferred else 0.0
        stock = self.W_STOCK * _stock_bucket(row.stock)
        total = basic + preferred + stock
        trace.record(
            "score_breakdown",
            lcsc=row.lcsc,
            basic=basic, preferred=preferred, stock=stock,
            total=total,
        )
        return total


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
                # Rated above spec — acceptable but not "exact"
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
