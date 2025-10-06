from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Candle:
    timestamp: int  # ms
    open: float
    high: float
    low: float
    close: float
    volume: float
