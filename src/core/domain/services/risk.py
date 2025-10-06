from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


PositionMode = Literal["usdt_value", "contracts"]


@dataclass
class SizingResult:
    qty: float
    notional: float


def compute_sizing(
    position_mode: PositionMode,
    size: float,
    price: float,
    step: float,
    min_qty: float,
    min_notional: float,
) -> SizingResult:
    if position_mode == "usdt_value":
        qty = size / max(price, 1e-12)
    else:
        qty = size
    # round to step
    steps = int(qty / step)
    qty = max(steps * step, min_qty)
    notional = qty * price
    if notional < min_notional:
        # bump qty to satisfy min notional
        min_qty_by_notional = min_notional / max(price, 1e-12)
        steps = int((min_qty_by_notional + step - 1e-18) / step)
        qty = steps * step
        notional = qty * price
    return SizingResult(qty=qty, notional=notional)


def compute_targets(entry: float, sl: float, rr: float, side: str) -> float:
    if side == "long":
        risk = entry - sl
        return entry + rr * risk
    else:
        risk = sl - entry
        return entry - rr * risk
