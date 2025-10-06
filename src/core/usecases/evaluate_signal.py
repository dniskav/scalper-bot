from __future__ import annotations

from typing import List, Tuple
from loguru import logger

from core.domain.services.strategy import evaluate_strategy, Signal


def evaluate_signal_usecase(
    o: List[float],
    h: List[float],
    l: List[float],
    c: List[float],
    timeframe: str,
    rr: float,
    weak_body_ratio_max: float,
    range_cross_ema_count: int,
    bid: float,
    ask: float,
    spread_max_pct: float,
) -> Signal:
    mid = (bid + ask) / 2 if (bid and ask) else (c[-1] if c else 0)
    spread_pct = abs(ask - bid) / mid * 100 if mid else 0
    sig = evaluate_strategy(
        o,
        h,
        l,
        c,
        timeframe,
        rr,
        weak_body_ratio_max,
        range_cross_ema_count,
        spread_pct,
        spread_max_pct,
    )
    logger.debug("Signal: {}", sig)
    return sig
