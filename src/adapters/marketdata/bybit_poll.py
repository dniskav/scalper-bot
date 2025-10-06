from __future__ import annotations

import asyncio
import time
from typing import Callable, List, Optional
from loguru import logger
import ccxt

from ports.marketdata_port import MarketDataPort, Kline
from adapters.notifier.telegram_bot import TelegramNotifier


class BybitPollingMD(MarketDataPort):
    """Minimal adapter de mercado para Bybit usando polling HTTP de ccxt.
    - ticker: cada ~1s
    - klines: consulta OHLCV y emite solo cuando hay una vela cerrada nueva
    """

    def __init__(self, testnet: bool = True) -> None:
        self._client: Optional[ccxt.bybit] = ccxt.bybit({"enableRateLimit": True})
        if testnet:
            self._client.set_sandbox_mode(True)  # type: ignore[attr-defined]
        self._stop = False

    async def connect(self) -> None:  # no-op
        return

    async def subscribe_klines(
        self,
        symbol: str,
        timeframe: str,
        on_kline_closed: Callable[[List[Kline]], None],
    ) -> None:
        last_close_ts: Optional[int] = None
        tf = timeframe
        # Warmup: cargar ~1000 velas cerradas para llenar buffers
        try:
            assert self._client is not None
            hist = self._client.fetch_ohlcv(symbol, timeframe=tf, limit=1000)
            if hist and len(hist) > 1:
                rows: list[Kline] = []
                for prev in hist[:-1]:  # omitir la última (puede estar en formación)
                    rows.append(
                        (
                            int(prev[0]),
                            float(prev[1]),
                            float(prev[2]),
                            float(prev[3]),
                            float(prev[4]),
                            float(prev[5] or 0.0),
                        )
                    )
                if rows:
                    on_kline_closed(rows)
                last_close_ts = int(hist[-2][0])
                # warmup silencioso (sin logs de evaluación)
        except Exception as e:
            logger.warning("Bybit warmup klines falló: {}", e)
        while not self._stop:
            try:
                assert self._client is not None
                ohlcv = self._client.fetch_ohlcv(symbol, timeframe=tf, limit=2)
                if ohlcv:
                    # última vela cerrada es la penúltima entrada
                    if len(ohlcv) >= 2:
                        prev = ohlcv[-2]
                        ts = int(prev[0])
                        if last_close_ts != ts:
                            row: Kline = (
                                ts,
                                float(prev[1]),
                                float(prev[2]),
                                float(prev[3]),
                                float(prev[4]),
                                float(prev[5] or 0.0),
                            )
                            on_kline_closed([row])
                            last_close_ts = ts
                await asyncio.sleep(2.0)
            except Exception as e:
                logger.error("Bybit polling klines error: {}", e)
                try:
                    await TelegramNotifier().send_error(f"❗ Bybit klines error: {e}")
                except Exception:
                    pass
                await asyncio.sleep(3.0)

    async def subscribe_ticker(
        self, symbol: str, on_ticker: Callable[[float, float], None]
    ) -> None:
        while not self._stop:
            try:
                assert self._client is not None
                t = self._client.fetch_ticker(symbol)
                bid = float(t.get("bid", 0) or 0)
                ask = float(t.get("ask", 0) or 0)
                if bid and ask:
                    on_ticker(bid, ask)
                await asyncio.sleep(1.0)
            except Exception as e:
                logger.error("Bybit polling ticker error: {}", e)
                try:
                    await TelegramNotifier().send_error(f"❗ Bybit ticker error: {e}")
                except Exception:
                    pass
                await asyncio.sleep(3.0)

    async def close(self) -> None:
        self._stop = True
        # ccxt no necesita cierre explícito


