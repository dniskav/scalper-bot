from __future__ import annotations

from loguru import logger
from typing import Optional

from ports.exchange_port import ExchangePort
from ports.exchange_port import OrderType
from core.domain.services.risk import compute_sizing, compute_targets


def open_position_usecase(
    exchange: ExchangePort,
    symbol: str,
    side: str,
    entry: float,
    sl: float,
    rr: float,
    position_mode: str,
    size: float,
    filters_step: float,
    filters_min_qty: float,
    filters_min_notional: float,
    dry_run: bool = False,
) -> tuple[float, float, float]:
    target = compute_targets(entry, sl, rr, side)
    sizing = compute_sizing(
        position_mode, size, entry, filters_step, filters_min_qty, filters_min_notional
    )
    qty = sizing.qty
    if dry_run:
        logger.info(
            "[DRY] Open {} {} qty={} entry={} sl={} tp={}",
            side,
            symbol,
            qty,
            entry,
            sl,
            target,
        )
        return qty, sl, target
    order_side = "buy" if side == "long" else "sell"
    # OrderType es un Literal; se pasa como cadena tipada, no se instancia
    exchange.create_order(symbol, order_side, "market", qty)
    # Nota: Colocación de SL/TP reduceOnly y tracking de IDs se gestiona en el runner
    logger.info(
        "Opened {} {} qty={} entry={} sl={} tp={}", side, symbol, qty, entry, sl, target
    )
    return qty, sl, target
