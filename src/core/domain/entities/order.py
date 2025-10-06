from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional


OrderSide = Literal["buy", "sell"]
OrderType = Literal["market", "limit"]


@dataclass
class Order:
    id: str
    symbol: str
    side: OrderSide
    type: OrderType
    qty: float
    price: Optional[float] = None
    status: str = "open"
