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


class BinanceCcxt(ExchangePort):
    def __init__(self) -> None:
        self._client: Optional[ccxt.binance] = None
        self._market: MarketType = "futures"
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
        if market == "futures":
            options = {"defaultType": "future"}
        else:
            options = {"defaultType": "spot"}

        self._client = ccxt.binance(
            {
                "apiKey": api_key or None,
                "secret": api_secret or None,
                "enableRateLimit": True,
                "options": options,
            }
        )
        assert self._client is not None

        if self._mode == "testnet":
            if market == "futures":
                # Map endpoints to Binance Futures Testnet
                self._client.urls["api"] = {
                    **self._client.urls.get("api", {}),
                    "fapi": "https://testnet.binancefuture.com/fapi",
                    "public": "https://testnet.binancefuture.com/fapi",
                    "private": "https://testnet.binancefuture.com/fapi",
                }
            else:
                # Binance spot testnet
                self._client.set_sandbox_mode(True)

        logger.info("Binance configured: market={}, mode={}", market, mode)

    def set_leverage(self, symbol: str, leverage: int) -> None:
        if self._market != "futures":
            return
        assert self._client is not None
        try:
            if hasattr(self._client, "set_leverage"):
                try:
                    getattr(self._client, "set_leverage")(symbol, leverage, {})  # type: ignore[misc]
                    logger.info("Set leverage {}x for {} (unified)", leverage, symbol)
                    return
                except Exception as e:
                    logger.debug("Unified set_leverage failed: {}", e)
            if hasattr(self._client, "fapiPrivatePostLeverage"):
                getattr(self._client, "fapiPrivatePostLeverage")({"symbol": symbol, "leverage": leverage})
            elif hasattr(self._client, "fapiPrivate_post_leverage"):
                getattr(self._client, "fapiPrivate_post_leverage")({"symbol": symbol, "leverage": leverage})
            else:
                logger.warning("Leverage endpoint not available; skipping")
            logger.info("Set leverage {}x for {}", leverage, symbol)
        except Exception as e:
            logger.error("Failed to set leverage: {}", e)

    def place_reduce_only_sl_tp(
        self, symbol: str, side: OrderSide, sl_price: float, tp_price: float, qty: float
    ) -> None:
        """Coloca SL/TP reduceOnly usando órdenes stop y take-profit en futures si disponible."""
        if self._market != "futures":
            return
        assert self._client is not None
        # Para Binance futures: STOP_MARKET (SL) y TAKE_PROFIT_MARKET (TP) con reduceOnly
        opp = "sell" if side == "buy" else "buy"
        try:
            params = {"reduceOnly": True}
            # SL
            self._client.create_order(
                symbol,
                type="STOP_MARKET",
                side=opp,
                amount=qty,
                price=None,
                params={**params, "stopPrice": sl_price},
            )
            # TP
            self._client.create_order(
                symbol,
                type="TAKE_PROFIT_MARKET",
                side=opp,
                amount=qty,
                price=None,
                params={**params, "stopPrice": tp_price},
            )
        except Exception as e:
            logger.error("Failed to place SL/TP reduceOnly: {}", e)

    def cancel_all_open_orders(self, symbol: str) -> None:
        assert self._client is not None
        try:
            self._client.cancel_all_orders(symbol)
        except Exception as e:
            logger.error("Failed to cancel open orders: {}", e)

    def place_reduce_only_sl(
        self, symbol: str, side: OrderSide, stop_price: float, qty: float
    ) -> str:
        if self._market != "futures":
            raise RuntimeError(
                "reduceOnly SL only supported on futures in this adapter"
            )
        assert self._client is not None
        opp = "sell" if side == "buy" else "buy"
        order = self._client.create_order(
            symbol,
            type="STOP_MARKET",
            side=opp,
            amount=qty,
            params={"reduceOnly": True, "stopPrice": stop_price},
        )
        return str(order.get("id"))

    def replace_reduce_only_sl(
        self,
        symbol: str,
        order_id: str | None,
        side: OrderSide,
        new_stop_price: float,
        qty: float,
    ) -> str:
        assert self._client is not None
        if order_id:
            try:
                self._client.cancel_order(order_id, symbol)
            except Exception:
                pass
        return self.place_reduce_only_sl(symbol, side, new_stop_price, qty)

    def cancel_order(self, symbol: str, order_id: str) -> None:
        assert self._client is not None
        self._client.cancel_order(order_id, symbol)

    def load_markets(self) -> Dict[str, Any]:
        assert self._client is not None
        return self._client.load_markets()

    def get_symbol_filters(self, symbol: str) -> ExchangeFilters:
        assert self._client is not None
        m = self._client.market(symbol)
        price_tick = m.get("precision", {}).get("price")
        # derive tick size
        price_tick_size = (
            1 / (10**price_tick)
            if isinstance(price_tick, int)
            else m.get("limits", {}).get("price", {}).get("min", 0.0) or 0.0
        )
        quantity_step = m.get("precision", {}).get("amount")
        quantity_step = (
            1 / (10**quantity_step)
            if isinstance(quantity_step, int)
            else m.get("limits", {}).get("amount", {}).get("min", 0.0) or 0.0
        )
        min_qty = m.get("limits", {}).get("amount", {}).get("min", 0.0) or 0.0
        min_notional = m.get("limits", {}).get("cost", {}).get("min", 0.0) or 0.0
        return ExchangeFilters(
            price_tick_size=price_tick_size,
            quantity_step=quantity_step,
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
        if self._market == "futures":
            params["reduceOnly"] = reduce_only
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
        # Simplified: place market order in opposite direction with reduceOnly
        assert self._client is not None
        side = "sell" if position_side == "long" else "buy"
        # Quantity should be derived from position size; omitted in this minimal implementation
        logger.warning(
            "close_position requires current position qty; implement via exchange position fetch."
        )

    def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        assert self._client is not None
        return self._client.fetch_ticker(symbol)
