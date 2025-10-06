from __future__ import annotations

from typing import List, Tuple


def ema(values: List[float], period: int) -> List[float]:
    if period <= 0:
        raise ValueError("period must be > 0")
    if not values:
        return []
    k = 2 / (period + 1)
    result: List[float] = []
    ema_prev: float | None = None
    for v in values:
        if ema_prev is None:
            ema_prev = v
        else:
            ema_prev = v * k + ema_prev * (1 - k)
        result.append(ema_prev)
    return result


def rsi(values: List[float], period: int = 14) -> List[float]:
    if period <= 0:
        raise ValueError("period must be > 0")
    if len(values) < 2:
        return [50.0 for _ in values]
    gains: List[float] = [0.0]
    losses: List[float] = [0.0]
    for i in range(1, len(values)):
        change = values[i] - values[i - 1]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    avg_gain = ema(gains, period)
    avg_loss = ema(losses, period)
    rsi_values: List[float] = []
    for g, l in zip(avg_gain, avg_loss):
        if l == 0:
            rs = float("inf")
        else:
            rs = g / l
        rsi_values.append(100 - (100 / (1 + rs)))
    return rsi_values


def _true_range(high: List[float], low: List[float], close: List[float]) -> List[float]:
    tr: List[float] = [high[0] - low[0]]
    for i in range(1, len(close)):
        tr.append(
            max(
                high[i] - low[i],
                abs(high[i] - close[i - 1]),
                abs(low[i] - close[i - 1]),
            )
        )
    return tr


def _dx(
    high: List[float], low: List[float], close: List[float], period: int
) -> Tuple[List[float], List[float]]:
    plus_dm = [0.0]
    minus_dm = [0.0]
    for i in range(1, len(high)):
        up_move = high[i] - high[i - 1]
        down_move = low[i - 1] - low[i]
        plus_dm.append(up_move if up_move > down_move and up_move > 0 else 0.0)
        minus_dm.append(down_move if down_move > up_move and down_move > 0 else 0.0)

    tr = _true_range(high, low, close)
    atr = ema(tr, period)
    plus_di = [
        0.0 if a == 0 else (p / a) * 100 for p, a in zip(ema(plus_dm, period), atr)
    ]
    minus_di = [
        0.0 if a == 0 else (m / a) * 100 for m, a in zip(ema(minus_dm, period), atr)
    ]
    dx = [
        0.0 if (p + m) == 0 else (abs(p - m) / (p + m)) * 100
        for p, m in zip(plus_di, minus_di)
    ]
    return dx, atr


def adx(
    high: List[float], low: List[float], close: List[float], period: int
) -> List[float]:
    dx, _ = _dx(high, low, close, period)
    return ema(dx, period)


def atr(
    high: List[float], low: List[float], close: List[float], period: int
) -> List[float]:
    tr = _true_range(high, low, close)
    # Wilder's ATR approximated using EMA
    return ema(tr, period)
