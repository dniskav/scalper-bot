from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Literal, Dict, Any
from loguru import logger

from .indicators import ema, rsi, adx


SignalSide = Literal["long", "short", "none"]


@dataclass
class Signal:
    side: SignalSide
    entry: Optional[float] = None
    sl: Optional[float] = None
    rr: float = 1.5
    reason: str = ""


def _is_weak_candle(
    open_: float, high: float, low: float, close: float, max_ratio: float
) -> bool:
    body = abs(close - open_)
    rng = max(high - low, 1e-12)
    return (body / rng) < max_ratio


def evaluate_strategy(
    o: List[float],
    h: List[float],
    l: List[float],
    c: List[float],
    timeframe: str,
    rr: float,
    weak_body_ratio_max: float,
    range_cross_ema_count: int,
    spread_pct: float,
    spread_max_pct: float,
) -> Signal:
    n = len(c)
    if n < 60:
        return Signal("none", reason="insufficient_data")

    ema50 = ema(c, 50)
    rsi3 = rsi(c, 3)
    adx5 = adx(h, l, c, 5)

    # Filters: spread
    if spread_pct > spread_max_pct:
        logger.info(
            "[EVAL] Verificando spread: actual={:.4f}% max={:.4f}% -> no coincide",
            spread_pct,
            spread_max_pct,
        )
        return Signal("none", reason="spread_high")

    # Filters: range (price crossing EMA too often recently)
    crossings = 0
    for i in range(max(1, n - 30), n):
        if (c[i - 1] - ema50[i - 1]) * (c[i] - ema50[i]) < 0:
            crossings += 1
    if crossings > range_cross_ema_count:
        logger.info(
            "[EVAL] Verificando rango (cruces EMA50): cruces={} max={} -> no coincide",
            crossings,
            range_cross_ema_count,
        )
        return Signal("none", reason="ema_crossings")

    i = n - 1
    logger.info(
        "[EVAL] Valores: close={:.6f} ema50={:.6f} rsi3(prev)={:.2f} rsi3={:.2f} adx5={:.2f}",
        c[i],
        ema50[i],
        rsi3[i - 1],
        rsi3[i],
        adx5[i],
    )
    # Long setup
    if c[i] > ema50[i] and adx5[i] > 30:
        # RSI(3) touched <=20 and then left oversold: detect previous bar below 20, current above 20
        if rsi3[i - 1] <= 20 and rsi3[i] > 20:
            # first green candle that exits oversold is i (close > open)
            if c[i] > o[i] and not _is_weak_candle(
                o[i], h[i], l[i], c[i], weak_body_ratio_max
            ):
                logger.info("[EVAL] Long: EMA/ADX/RSI/Candle -> coincide; se abre señal long")
                entry = h[i]  # breakout of high of signal candle
                sl = l[i]
                return Signal(
                    "long",
                    entry=entry,
                    sl=sl,
                    rr=rr,
                    reason="rsi_exit_oversold_adx_trend",
                )
            else:
                logger.info(
                    "[EVAL] Long: indicadores previos OK pero vela débil o no verde -> no coincide"
                )
        else:
            logger.info(
                "[EVAL] Long: RSI(3) no salió de sobreventa (prev<=20 y actual>20) -> no coincide"
            )
    else:
        logger.info(
            "[EVAL] Long: tendencia no válida (close>ema50 y adx>30) -> no coincide"
        )

    # Short setup
    if c[i] < ema50[i] and adx5[i] > 30:
        if rsi3[i - 1] >= 80 and rsi3[i] < 80:
            if c[i] < o[i] and not _is_weak_candle(
                o[i], h[i], l[i], c[i], weak_body_ratio_max
            ):
                logger.info("[EVAL] Short: EMA/ADX/RSI/Candle -> coincide; se abre señal short")
                entry = l[i]
                sl = h[i]
                return Signal(
                    "short",
                    entry=entry,
                    sl=sl,
                    rr=rr,
                    reason="rsi_exit_overbought_adx_trend",
                )
            else:
                logger.info(
                    "[EVAL] Short: indicadores previos OK pero vela débil o no roja -> no coincide"
                )
        else:
            logger.info(
                "[EVAL] Short: RSI(3) no salió de sobrecompra (prev>=80 y actual<80) -> no coincide"
            )
    else:
        logger.info(
            "[EVAL] Short: tendencia no válida (close<ema50 y adx>30) -> no coincide"
        )

    logger.info("[EVAL] No se abre operación: no se cumplieron todos los requisitos")
    return Signal("none", reason="no_setup")


def _round_to_tick(price: float, tick: float) -> float:
    if tick <= 0:
        return price
    steps = round(price / tick)
    return steps * tick


def should_move_to_breakeven(
    side: str,
    entry_price: float,
    sl_current: float,
    risk_per_unit: float,
    mfe_price: float,
    trigger_rr: float,
    offset_ticks: int,
    offset_pct: float,
    tick_size: float,
) -> float | None:
    if risk_per_unit <= 0:
        return None
    target_move = trigger_rr * risk_per_unit
    if side == "long":
        threshold = entry_price + target_move
        if mfe_price >= threshold:
            be = entry_price * (1 + offset_pct / 100.0) + offset_ticks * tick_size
            be = _round_to_tick(be, tick_size)
            return be if be > sl_current else None
    else:
        threshold = entry_price - target_move
        if mfe_price <= threshold:
            be = entry_price * (1 - offset_pct / 100.0) - offset_ticks * tick_size
            be = _round_to_tick(be, tick_size)
            return be if be < sl_current else None
    return None


def compute_trailing_sl_percent(
    side: str,
    mfe_price: float,
    trailing_percent: float,
    last_sl: float,
    step_min_pct: float,
    tick_size: float,
) -> float | None:
    if trailing_percent <= 0:
        return None
    if side == "long":
        new_sl = mfe_price * (1 - trailing_percent / 100.0)
        improve_pct = (new_sl / last_sl - 1.0) * 100.0
        if improve_pct >= step_min_pct:
            return _round_to_tick(new_sl, tick_size)
    else:
        new_sl = mfe_price * (1 + trailing_percent / 100.0)
        improve_pct = (1.0 - new_sl / last_sl) * 100.0
        if improve_pct >= step_min_pct:
            return _round_to_tick(new_sl, tick_size)
    return None


def compute_trailing_sl_atr(
    side: str,
    current_price: float,
    atr_value: float,
    atr_mult: float,
    last_sl: float,
    step_min_pct: float,
    tick_size: float,
) -> float | None:
    if atr_value <= 0 or atr_mult <= 0:
        return None
    if side == "long":
        new_sl = current_price - atr_value * atr_mult
        improve_pct = (new_sl / last_sl - 1.0) * 100.0
        if improve_pct >= step_min_pct:
            return _round_to_tick(new_sl, tick_size)
    else:
        new_sl = current_price + atr_value * atr_mult
        improve_pct = (1.0 - new_sl / last_sl) * 100.0
        if improve_pct >= step_min_pct:
            return _round_to_tick(new_sl, tick_size)
    return None
