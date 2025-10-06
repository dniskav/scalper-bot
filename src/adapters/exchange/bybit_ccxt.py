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


class BybitCcxt(ExchangePort):
    """Mínimo viable. Nota: Algunas operaciones de derivados pueden requerir parámetros adicionales.
    Fallback: Spot si una feature no está lista.
    """

    def __init__(self) -> None:
        self._client: Optional[ccxt.bybit] = None
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
        options = {"defaultType": "linear" if market == "futures" else "spot"}
        self._client = ccxt.bybit(
            {
                "apiKey": api_key or None,
                "secret": api_secret or None,
                "enableRateLimit": True,
                "options": options,
            }
        )
        if self._mode == "testnet":
            self._client.set_sandbox_mode(True)
        logger.info("Bybit configured: market={}, mode={}", market, mode)

    def set_leverage(self, symbol: str, leverage: int) -> None:
        assert self._client is not None
        try:
            m = self._client.market(symbol)
            # linear USDT perpetuals: set leverage per symbol
            # ccxt unificado suele soportar set_leverage(symbol, leverage)
            if hasattr(self._client, "set_leverage"):
                self._client.set_leverage(leverage, symbol)
                logger.info("Bybit leverage set to {}x for {}", leverage, symbol)
                return
        except Exception as e:
            logger.debug("Unified set_leverage failed: {}", e)
        # Fallback raw endpoints (v5 / legacy)
        lev = int(leverage)
        # Try v5 first
        try:
            if hasattr(self._client, "privatePostV5PositionSetLeverage"):
                self._client.privatePostV5PositionSetLeverage({  # type: ignore[attr-defined]
                    "category": "linear",
                    "symbol": symbol,
                    "buyLeverage": str(lev),
                    "sellLeverage": str(lev),
                })
                logger.info("Bybit leverage set via v5 endpoint to {}x for {}", leverage, symbol)
                return
        except Exception as e:
            logger.debug("Bybit v5 leverage endpoint failed: {}", e)
        # Try legacy endpoint
        try:
            if hasattr(self._client, "privatePostPositionSetLeverage"):
                self._client.privatePostPositionSetLeverage({  # type: ignore[attr-defined]
                    "symbol": symbol,
                    "buy_leverage": lev,
                    "sell_leverage": lev,
                })
                logger.info("Bybit leverage set via legacy endpoint to {}x for {}", leverage, symbol)
                return
        except Exception as e:
            logger.debug("Bybit legacy leverage endpoint failed: {}", e)
        logger.warning("Bybit set_leverage: all methods failed; using exchange default leverage")

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
            "Bybit close_position minimal; implement position query + reduceOnly if needed"
        )

    def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        assert self._client is not None
        return self._client.fetch_ticker(symbol)
