from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Literal, Optional, Dict, Any


MarketType = Literal["spot", "futures"]
ModeType = Literal["testnet", "real"]
OrderSide = Literal["buy", "sell"]
OrderType = Literal["market", "limit"]
PositionSide = Literal["long", "short"]


@dataclass
class ExchangeFilters:
    price_tick_size: float
    quantity_step: float
    min_qty: float
    min_notional: float


@dataclass
class PlacedOrder:
    id: str
    symbol: str
    side: OrderSide
    type: OrderType
    price: Optional[float]
    qty: float
    status: str


class ExchangePort(Protocol):
    def configure(
        self,
        api_key: str,
        api_secret: str,
        mode: ModeType,
        market: MarketType,
        exchange: str,
        passphrase: Optional[str] = None,
    ) -> None: ...

    def set_leverage(self, symbol: str, leverage: int) -> None: ...  # futures only

    def load_markets(self) -> Dict[str, Any]: ...

    def get_symbol_filters(self, symbol: str) -> ExchangeFilters: ...

    def fetch_balance(self) -> Dict[str, Any]: ...

    def create_order(
        self,
        symbol: str,
        side: OrderSide,
        type: OrderType,
        qty: float,
        price: Optional[float] = None,
        reduce_only: bool = False,
    ) -> PlacedOrder: ...

    def close_position(self, symbol: str, position_side: PositionSide) -> None: ...

    def fetch_ticker(self, symbol: str) -> Dict[str, Any]: ...

    # Opcionales avanzados (cuando el exchange lo soporte)
    def place_reduce_only_sl_tp(
        self, symbol: str, side: OrderSide, sl_price: float, tp_price: float, qty: float
    ) -> None: ...
    def cancel_all_open_orders(self, symbol: str) -> None: ...
    def place_reduce_only_sl(
        self, symbol: str, side: OrderSide, stop_price: float, qty: float
    ) -> str: ...
    def replace_reduce_only_sl(
        self,
        symbol: str,
        order_id: str | None,
        side: OrderSide,
        new_stop_price: float,
        qty: float,
    ) -> str: ...
    def cancel_order(self, symbol: str, order_id: str) -> None: ...
