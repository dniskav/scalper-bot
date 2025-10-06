from __future__ import annotations

import ccxt
from typing import Optional, Dict, Any
from loguru import logger

from ports.exchange_port import (
    ExchangePort,
    ModeType,
    MarketType,
    ExchangeFilters,
    PlacedOrder,
    OrderType,
    OrderSide,
    PositionSide,
)


class OkxCcxt(ExchangePort):
    """Mínimo viable; para derivados puede requerir passphrase y parámetros adicionales."""

    def __init__(self) -> None:
        self._client: Optional[ccxt.okx] = None
        self._market: MarketType = "spot"
        self._mode: ModeType = "testnet"

    def configure(
        self,
        api_key: str,
        api_secret: str,
        mode: ModeType,
        market: MarketType,
        exchange: str,
        passphrase: Optional[str] = None,
    ) -> None:
        self._market = market
        self._mode = mode
        self._client = ccxt.okx(
            {
                "apiKey": api_key or None,
                "secret": api_secret or None,
                "password": passphrase or None,
                "enableRateLimit": True,
            }
        )
        if self._mode == "testnet":
            self._client.set_sandbox_mode(True)
        logger.info("OKX configured: market={}, mode={}", market, mode)

    def set_leverage(self, symbol: str, leverage: int) -> None:
        logger.warning("OKX set_leverage not implemented in minimal adapter")

    def load_markets(self) -> Dict[str, Any]:
        assert self._client is not None
        return self._client.load_markets()

    def get_symbol_filters(self, symbol: str) -> ExchangeFilters:
        assert self._client is not None
        m = self._client.market(symbol)
        qty_step = m.get("limits", {}).get("amount", {}).get("min", 0.0) or 0.0
        price_tick = m.get("limits", {}).get("price", {}).get("min", 0.0) or 0.0
        min_qty = m.get("limits", {}).get("amount", {}).get("min", 0.0) or 0.0
        min_notional = m.get("limits", {}).get("cost", {}).get("min", 0.0) or 0.0
        return ExchangeFilters(
            price_tick_size=price_tick,
            quantity_step=qty_step,
            min_qty=min_qty,
            min_notional=min_notional,
        )

    def fetch_balance(self) -> Dict[str, Any]:
        assert self._client is not None
        return self._client.fetch_balance()

    def create_order(
        self,
        symbol: str,
        side: OrderSide,
        type: OrderType,
        qty: float,
        price: Optional[float] = None,
        reduce_only: bool = False,
    ) -> PlacedOrder:
        assert self._client is not None
        params = {}
        order = self._client.create_order(
            symbol=symbol, type=type, side=side, amount=qty, price=price, params=params
        )
        return PlacedOrder(
            id=str(order.get("id")),
            symbol=order.get("symbol", symbol),
            side=side,
            type=type,
            price=order.get("price") or price,
            qty=float(order.get("amount") or qty),
            status=str(order.get("status", "open")),
        )

    def close_position(self, symbol: str, position_side: PositionSide) -> None:
        logger.warning(
            "OKX close_position minimal; implement position query + reduceOnly if needed"
        )

    def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        assert self._client is not None
        return self._client.fetch_ticker(symbol)
