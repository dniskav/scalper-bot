from __future__ import annotations

from loguru import logger
from ports.exchange_port import ExchangePort


def close_position_usecase(
    exchange: ExchangePort,
    symbol: str,
    side: str,
    reason: str,
    qty: float | None = None,
    dry_run: bool = False,
) -> None:
    opp = "sell" if side == "long" else "buy"
    if dry_run:
        logger.info("[DRY] Close {} {} reason={} qty={}", side, symbol, reason, qty)
        return
    if qty is None:
        logger.warning(
            "qty not provided for close; implement position fetch to determine size"
        )
        return
    exchange.create_order(symbol, opp, "market", qty, reduce_only=True)  # type: ignore[arg-type]
    logger.info("Closed {} {} reason={} qty={}", side, symbol, reason, qty)
