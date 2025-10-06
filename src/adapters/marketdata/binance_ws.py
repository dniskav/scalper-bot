from __future__ import annotations

import asyncio
import json
from typing import Callable, List, Tuple, Optional
from loguru import logger
import websockets
import ssl, certifi
from adapters.notifier.telegram_bot import TelegramNotifier

from ports.marketdata_port import MarketDataPort, Kline


def _stream_name(symbol: str, timeframe: str) -> str:
    return f"{symbol.lower()}@kline_{timeframe}"


def _ticker_stream(symbol: str) -> str:
    return f"{symbol.lower()}@bookTicker"


class BinancePublicWS(MarketDataPort):
    def __init__(self, testnet: bool = False) -> None:
        self._base = (
            "wss://testnet.binance.vision/ws"
            if testnet
            else "wss://stream.binance.com:9443/ws"
        )
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._tasks: list[asyncio.Task] = []
        self._last_alert_klines: float = 0.0
        self._last_alert_ticker: float = 0.0
        self._alert_cooldown_sec: float = 120.0

    async def connect(self) -> None:
        # connection will be created per subscription
        return

    async def subscribe_klines(
        self,
        symbol: str,
        timeframe: str,
        on_kline_closed: Callable[[List[Kline]], None],
    ) -> None:
        stream = _stream_name(symbol, timeframe)
        uri = f"{self._base}/{stream}"

        async def _runner() -> None:
            while True:
                try:
                    ssl_ctx = ssl.create_default_context()
                    ssl_ctx.load_verify_locations(certifi.where())
                    async with websockets.connect(uri, ping_interval=20, ssl=ssl_ctx) as ws:
                        async for msg in ws:
                            data = json.loads(msg)
                            if data.get("e") == "kline":
                                k = data["k"]
                                if k.get("x"):
                                    row: Kline = (
                                        int(k["t"]),
                                        float(k["o"]),
                                        float(k["h"]),
                                        float(k["l"]),
                                        float(k["c"]),
                                        float(k["v"]),
                                    )
                                    on_kline_closed([row])
                except Exception as e:
                    logger.error("WS klines error: {}", e)
                    # Avoid spamming the same alert too frequently
                    now = __import__("time").time()
                    if now - self._last_alert_klines > self._alert_cooldown_sec:
                        try:
                            await TelegramNotifier().send_error(f"❗ WS klines error: {e}")
                        except Exception:
                            pass
                        self._last_alert_klines = now
                    await asyncio.sleep(2)

        await _runner()

    async def subscribe_ticker(
        self, symbol: str, on_ticker: Callable[[float, float], None]
    ) -> None:
        stream = _ticker_stream(symbol)
        uri = f"{self._base}/{stream}"

        async def _runner() -> None:
            while True:
                try:
                    ssl_ctx = ssl.create_default_context()
                    ssl_ctx.load_verify_locations(certifi.where())
                    async with websockets.connect(uri, ping_interval=20, ssl=ssl_ctx) as ws:
                        async for msg in ws:
                            data = json.loads(msg)
                            bid = float(data.get("b", 0))
                            ask = float(data.get("a", 0))
                            on_ticker(bid, ask)
                except Exception as e:
                    logger.error("WS ticker error: {}", e)
                    now = __import__("time").time()
                    if now - self._last_alert_ticker > self._alert_cooldown_sec:
                        try:
                            await TelegramNotifier().send_error(f"❗ WS ticker error: {e}")
                        except Exception:
                            pass
                        self._last_alert_ticker = now
                    await asyncio.sleep(2)

        await _runner()

    async def close(self) -> None:
        for t in self._tasks:
            t.cancel()
        self._tasks.clear()
