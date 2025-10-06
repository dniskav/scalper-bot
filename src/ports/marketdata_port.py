from __future__ import annotations

from typing import Protocol, Callable, List, Tuple


Kline = Tuple[
    int, float, float, float, float, float
]  # ts, open, high, low, close, volume


class MarketDataPort(Protocol):
    async def connect(self) -> None: ...

    async def subscribe_klines(
        self,
        symbol: str,
        timeframe: str,
        on_kline_closed: Callable[[List[Kline]], None],
    ) -> None: ...

    async def subscribe_ticker(
        self, symbol: str, on_ticker: Callable[[float, float], None]
    ) -> None: ...  # bid, ask

    async def close(self) -> None: ...
