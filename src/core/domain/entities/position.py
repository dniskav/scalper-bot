from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional


PositionSide = Literal["long", "short"]


@dataclass
class Position:
    symbol: str
    side: PositionSide
    entry_price: float
    qty: float
    sl: Optional[float]
    tp: Optional[float]
    opened_ts: int
    leverage: Optional[int] = None
    market: str = "futures"
    mode: str = "testnet"
    # BE/Trailing state
    risk_per_unit: float | None = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    mfe_price: float | None = None
    is_at_breakeven: bool = False
    sl_origin: str = "initial"  # initial | breakeven | trailing
    sl_order_id: Optional[str] = None
    tp_order_id: Optional[str] = None
