from __future__ import annotations

import asyncio
from typing import List
from loguru import logger

from adapters.marketdata.binance_ws import BinancePublicWS
from adapters.marketdata.bybit_poll import BybitPollingMD
from adapters.exchange.binance_ccxt import BinanceCcxt
from adapters.exchange.bybit_ccxt import BybitCcxt
from adapters.exchange.okx_ccxt import OkxCcxt
from core.usecases.evaluate_signal import evaluate_signal_usecase
from core.usecases.open_position import open_position_usecase
from ports.config_port import TradingConfig, RiskConfig
from adapters.notifier.telegram_bot import TelegramNotifier
from adapters.storage.csv_repo import CsvRepository
from core.domain.services.risk import compute_targets
from datetime import datetime
import pytz
from core.domain.services.strategy import (
    should_move_to_breakeven,
    compute_trailing_sl_percent,
    compute_trailing_sl_atr,
)
from core.domain.services.indicators import atr
from pathlib import Path
import json


class BotRunner:
    def __init__(
        self,
        symbol: str,
        trading: TradingConfig,
        risk: RiskConfig,
        exchange_name: str,
        api_key: str | None,
        api_secret: str | None,
        mode: str,
        market: str,
        leverage: int | None,
        position_mode: str,
        size: float | None,
        dry_run: bool,
    ) -> None:
        self.symbol = symbol
        self.trading = trading
        self.risk = risk
        self.mode = mode
        self.market = market
        self.leverage = leverage
        self.position_mode = position_mode
        self.size = size or 0.0
        self.dry_run = dry_run
        self.exchange_name = (exchange_name or "binance").lower()
        self.daily_trades = 0
        self.daily_pnl_abs = 0.0
        self.daily_losses_count = 0
        self.soft_stop = False
        self.soft_stop_notified = False

        # Selección de adapter por exchange
        if self.exchange_name == "bybit":
            self.exchange = BybitCcxt()
        elif self.exchange_name == "okx":
            self.exchange = OkxCcxt()
        else:
            self.exchange = BinanceCcxt()
        self.exchange.configure(
            api_key or "",
            api_secret or "",
            mode,
            "futures" if market == "futures" else "spot",
            self.exchange_name,
        )
        # Balance base en USDT para límites diarios
        try:
            bal = self.exchange.fetch_balance()
            usdt = bal.get("USDT") or bal.get("USDT:USDT") or {}
            self.base_equity_usdt = float(usdt.get("total") or usdt.get("free") or 0.0)
        except Exception:
            self.base_equity_usdt = 0.0
        # Persistir equity base para consultas externas (e.g., /status)
        try:
            data_dir = Path("data"); data_dir.mkdir(parents=True, exist_ok=True)
            (data_dir / "equity.json").write_text(
                json.dumps({"base_equity_usdt": self.base_equity_usdt}),
                encoding="utf-8",
            )
        except Exception:
            pass
        if leverage and market == "futures" and (not self.dry_run) and (api_key and api_secret):
            try:
                self.exchange.set_leverage(symbol, leverage)
            except Exception as e:
                logger.warning("Set leverage failed: {}", e)

        # Selección de market data por exchange
        if self.exchange_name == "bybit":
            self.ws = BybitPollingMD(testnet=(mode == "testnet"))
        else:
            self.ws = BinancePublicWS(testnet=(mode == "testnet"))
        self.notifier = TelegramNotifier()
        self.storage = CsvRepository()

        self.o: List[float] = []
        self.h: List[float] = []
        self.l: List[float] = []
        self.c: List[float] = []
        self.bid: float = 0.0
        self.ask: float = 0.0
        # Estado de posición actual (una por símbolo)
        self.position_side: str | None = None
        self.position_qty: float = 0.0
        self.position_entry: float = 0.0
        self.position_sl: float = 0.0
        self.position_tp: float = 0.0
        self.position_sl_id: str | None = None
        self.position_tp_id: str | None = None
        self.position_mfe: float | None = None
        self.position_at_be: bool = False
        self.sl_origin: str = "initial"
        self.tick_size: float = 0.0

    async def _on_kline_closed(
        self, rows: list[tuple[int, float, float, float, float, float]]
    ) -> None:
        for ts, o, h, l, c, v in rows:
            self.o.append(o)
            self.h.append(h)
            self.l.append(l)
            self.c.append(c)
            # actualizar MFE con vela cerrada si hay posición
            if self.position_side is not None:
                if self.position_mfe is None:
                    self.position_mfe = self.position_entry
                if self.position_side == "long":
                    self.position_mfe = max(self.position_mfe, h)
                else:
                    self.position_mfe = min(self.position_mfe, l)
        if len(self.c) < 60:
            return
        # Pausa: no evaluar nuevas entradas si hay bandera de pausa
        try:
            from pathlib import Path as _P
            if _P("data/pause.flag").exists():
                logger.info("Pause activo; no se evalúan nuevas entradas")
                return
        except Exception:
            pass
        if self.soft_stop:
            logger.info(
                "Soft-stop activo por riesgo diario; no se aceptan nuevas entradas"
            )
            return
        # Session filter
        if self.trading.sessions_filter:
            tz = pytz.timezone(self.trading.sessions_timezone)
            now_local = datetime.now(tz)
            allowed = False
            for window in [
                w.strip() for w in self.trading.sessions_allowed.split(",") if w.strip()
            ]:
                start_s, end_s = window.split("-")
                start = datetime.strptime(start_s, "%H:%M").time()
                end = datetime.strptime(end_s, "%H:%M").time()
                if start <= now_local.time() <= end:
                    allowed = True
                    break
            if not allowed:
                logger.info("Outside allowed sessions; skipping evaluation")
                return
        sig = evaluate_signal_usecase(
            self.o,
            self.h,
            self.l,
            self.c,
            self.trading.timeframe,
            self.trading.rr,
            self.trading.weak_body_ratio_max,
            self.trading.range_cross_ema_count,
            self.bid,
            self.ask,
            self.trading.spread_max_pct,
        )
        if sig.side in ("long", "short") and sig.entry and sig.sl:
            # Límite de trades diarios (usar RiskConfig)
            if self.daily_trades >= self.risk.max_daily_trades:
                logger.info("Daily trades limit reached; skipping")
                return
            filters = self.exchange.get_symbol_filters(self.symbol)
            self.tick_size = max(filters.price_tick_size, 0.0)
            qty, sl, tp = open_position_usecase(
                self.exchange,
                self.symbol,
                sig.side,
                sig.entry,
                sig.sl,
                sig.rr,
                self.position_mode,
                self.size,
                filters.quantity_step,
                filters.min_qty,
                filters.min_notional,
                self.dry_run,
            )
            # Colocar SL/TP reales reduceOnly en futures cuando sea posible
            if (self.market == "futures") and (not self.dry_run):
                try:
                    entry_side = "buy" if sig.side == "long" else "sell"
                    # SL inicial reduceOnly
                    self.position_sl_id = self.exchange.place_reduce_only_sl(self.symbol, entry_side, sl, qty)  # type: ignore[arg-type]
                    # TP fijo opcional
                    if self.trading.take_profit_mode == "fixed":
                        try:
                            self.exchange.place_reduce_only_sl_tp(self.symbol, entry_side, sl, tp, qty)  # type: ignore[arg-type]
                        except Exception:
                            pass
                except Exception as e:
                    logger.warning("Fallo al colocar SL/TP reduceOnly: {}", e)
            # Notify
            side_emoji = "🟢 Long" if sig.side == "long" else "🔴 Short"
            msg = (
                f"🚀 <b>OPEN</b> | {self.exchange_name}/{self.mode}/{self.market}\n"
                f"• <b>Symbol</b>: {self.symbol}\n"
                f"• <b>Side</b>: {side_emoji}\n"
                f"• <b>Entry</b>: {sig.entry}\n"
                f"• <b>Size</b>: {qty} (~{qty * (sig.entry or 0):.2f} USDT)\n"
                f"• <b>SL</b>: {sl}  |  <b>TP</b>: {tp}  |  <b>RR</b>: {sig.rr}\n"
                f"• <b>Lev</b>: {self.leverage or 1}x\n"
                f"⏱️ {datetime.utcnow().isoformat()}"
            )
            try:
                asyncio.create_task(self.notifier.send_open(msg))
            except Exception as e:
                logger.warning("Telegram notify failed: {}", e)
            # Persistir estado y marcar posición abierta
            self.storage.write_state(
                {
                    "symbol": self.symbol,
                    "side": sig.side,
                    "entry": sig.entry,
                    "qty": qty,
                    "sl": sl,
                    "tp": tp,
                    "mode": self.mode,
                    "market": self.market,
                }
            )
            self.position_side = sig.side
            self.position_qty = qty
            self.position_entry = sig.entry
            self.position_sl = sl
            self.position_tp = tp
            self.position_mfe = sig.entry
            self.position_at_be = False
            self.sl_origin = "initial"
            self.daily_trades += 1
            # No seguir a trailing en misma vela de entrada
            return

        # Gestión BE/Trailing si hay posición
        if (
            self.position_side is not None
            and self.position_qty > 0
            and self.position_mfe is not None
        ):
            try:
                # Break-even
                if self.trading.breakeven_enabled and not self.position_at_be:
                    new_sl = should_move_to_breakeven(
                        side=self.position_side,
                        entry_price=self.position_entry,
                        sl_current=self.position_sl,
                        risk_per_unit=abs(self.position_entry - self.position_sl),
                        mfe_price=self.position_mfe,
                        trigger_rr=self.trading.breakeven_trigger_rr,
                        offset_ticks=self.trading.breakeven_offset_ticks,
                        offset_pct=self.trading.breakeven_offset_pct,
                        tick_size=self.tick_size,
                    )
                    if new_sl is not None:
                        if not self.dry_run and self.market == "futures":
                            entry_side = (
                                "buy" if self.position_side == "long" else "sell"
                            )
                            self.position_sl_id = self.exchange.replace_reduce_only_sl(self.symbol, self.position_sl_id, entry_side, new_sl, self.position_qty)  # type: ignore[arg-type]
                        old = self.position_sl
                        self.position_sl = new_sl
                        self.position_at_be = True
                        self.sl_origin = "breakeven"
                        side_txt = "Long" if self.position_side == "long" else "Short"
                        msg = (
                            f"🟨 <b>BE</b> | {self.exchange_name}/{self.mode}/{self.market}\n"
                            f"• <b>Symbol</b>: {self.symbol} ({side_txt})\n"
                            f"• <b>MFE</b>: {self.position_mfe}\n"
                            f"• <b>SL → BE</b>: {new_sl}\n"
                            f"⏱️ {datetime.utcnow().isoformat()}"
                        )
                        asyncio.create_task(self.notifier.send_be(msg))

                # Trailing
                if self.trading.trailing_enabled and self.position_at_be:
                    new_sl_t = None
                    if self.trading.trailing_mode == "percent":
                        new_sl_t = compute_trailing_sl_percent(
                            side=self.position_side,
                            mfe_price=self.position_mfe,
                            trailing_percent=self.trading.trailing_percent,
                            last_sl=self.position_sl,
                            step_min_pct=self.trading.trailing_step_pct,
                            tick_size=self.tick_size,
                        )
                    else:
                        a = atr(self.h, self.l, self.c, self.trading.atr_period)
                        cur_atr = a[-1] if a else 0.0
                        new_sl_t = compute_trailing_sl_atr(
                            side=self.position_side,
                            current_price=self.c[-1],
                            atr_value=cur_atr,
                            atr_mult=self.trading.atr_multiplier,
                            last_sl=self.position_sl,
                            step_min_pct=self.trading.trailing_step_pct,
                            tick_size=self.tick_size,
                        )
                    if new_sl_t is not None:
                        if not self.dry_run and self.market == "futures":
                            entry_side = (
                                "buy" if self.position_side == "long" else "sell"
                            )
                            self.position_sl_id = self.exchange.replace_reduce_only_sl(self.symbol, self.position_sl_id, entry_side, new_sl_t, self.position_qty)  # type: ignore[arg-type]
                        old_sl = self.position_sl
                        self.position_sl = new_sl_t
                        self.sl_origin = "trailing"
                        side_txt = "Long" if self.position_side == "long" else "Short"
                        msg = (
                            f"📈 <b>TRAIL</b> | {self.exchange_name}/{self.mode}/{self.market}\n"
                            f"• <b>Symbol</b>: {self.symbol} ({side_txt})\n"
                            f"• <b>Mode</b>: {self.trading.trailing_mode}\n"
                            f"• <b>SL</b>: {old_sl} → {new_sl_t}\n"
                            f"• <b>MFE</b>: {self.position_mfe}\n"
                            f"⏱️ {datetime.utcnow().isoformat()}"
                        )
                        asyncio.create_task(self.notifier.send_trail(msg))
            except Exception as e:
                logger.warning("BE/Trailing update failed: {}", e)

    def _on_ticker(self, bid: float, ask: float) -> None:
        self.bid = bid
        self.ask = ask
        # Vigilancia de SL/TP si hay posición
        if not self.position_side or self.position_qty <= 0:
            return
        px = bid if self.position_side == "long" else ask
        hit_sl = (
            px <= self.position_sl
            if self.position_side == "long"
            else px >= self.position_sl
        )
        hit_tp = (
            px >= self.position_tp
            if self.position_side == "long"
            else px <= self.position_tp
        )
        if hit_sl or hit_tp:
            reason = "sl" if hit_sl else "tp"
            pnl_abs = (
                (px - self.position_entry) * self.position_qty
                if self.position_side == "long"
                else (self.position_entry - px) * self.position_qty
            )
            pnl_pct = (px / self.position_entry - 1.0) * (
                100 if self.position_side == "long" else -100
            )
            self.daily_pnl_abs += pnl_abs
            if pnl_abs < 0:
                self.daily_losses_count += 1
            # cerrar (dry-run usa log)
            if not self.dry_run:
                try:
                    opp = "sell" if self.position_side == "long" else "buy"
                    self.exchange.create_order(self.symbol, opp, "market", self.position_qty, reduce_only=True)  # type: ignore[arg-type]
                    # cancelar pendientes SL/TP si las hubiera
                    self.exchange.cancel_all_open_orders(self.symbol)
                except Exception as e:
                    logger.error("Close order failed: {}", e)
            # notificar y persistir
            side_txt = "Long" if self.position_side == "long" else "Short"
            reason_emoji = "✅ TP" if reason == "tp" else "🛑 SL"
            msg = (
                f"🔔 <b>CLOSE</b> | {self.exchange_name}/{self.mode}/{self.market}\n"
                f"• <b>Symbol</b>: {self.symbol} ({side_txt})\n"
                f"• <b>Exit</b>: {px}\n"
                f"• <b>PnL</b>: {pnl_abs:.2f} USDT ({pnl_pct:.2f}%)\n"
                f"• <b>Reason</b>: {reason_emoji}\n"
                f"• Fees est.: n/a\n"
                f"⏱️ {datetime.utcnow().isoformat()}"
            )
            try:
                asyncio.create_task(self.notifier.send_close(msg))
            except Exception as e:
                logger.warning("Telegram notify failed: {}", e)
            self.storage.append_trade(
                {
                    "ts": datetime.utcnow().isoformat(),
                    "exchange": self.exchange_name,
                    "market": self.market,
                    "mode": self.mode,
                    "symbol": self.symbol,
                    "side": self.position_side,
                    "entry": self.position_entry,
                    "exit": px,
                    "qty": self.position_qty,
                    "notional": self.position_entry * self.position_qty,
                    "sl": self.position_sl,
                    "tp": self.position_tp,
                    "rr": self.trading.rr,
                    "pnl_abs": pnl_abs,
                    "pnl_pct": pnl_pct,
                    "fees": 0.0,
                    "reason": reason,
                }
            )
            # reset posición
            self.position_side = None
            self.position_qty = 0.0
            # Evaluar soft-stop por pérdida diaria usando balance USDT base
            if self.base_equity_usdt > 0 and self.daily_pnl_abs < 0:
                max_loss_abs = self.base_equity_usdt * (
                    self.risk.max_daily_loss_pct / 100.0
                )
                if abs(self.daily_pnl_abs) >= max_loss_abs:
                    self.soft_stop = True
                    logger.error(
                        "Soft-stop activado: pérdida diaria {:.2f} USDT supera umbral {:.2f} USDT",
                        self.daily_pnl_abs,
                        max_loss_abs,
                    )
                    if not self.soft_stop_notified:
                        try:
                            msg = (
                                "🛑 <b>SOFT-STOP</b>\n"
                                f"• Pérdidas diarias: {self.daily_losses_count} ops\n"
                                f"• Último trade: {self.symbol} ({self.position_side or 'n/a'})\n"
                                f"• PnL acumulado: {self.daily_pnl_abs:.2f} USDT\n"
                                f"• Umbral: {max_loss_abs:.2f} USDT (max_daily_loss_pct)\n"
                                "No se abrirán más posiciones hoy."
                            )
                            asyncio.create_task(self.notifier.send_text(msg))
                        except Exception:
                            pass
                        self.soft_stop_notified = True
                    # Cancelar órdenes pendientes y cerrar cualquier posición residual
                    try:
                        self.exchange.cancel_all_open_orders(self.symbol)
                    except Exception:
                        pass
            # Soft-stop simplificado (fallback). Desactivar si no se necesita
            max_loss_abs = 0.0
            if False and self.risk.max_daily_loss_pct > 0 and self.daily_pnl_abs < 0:
                if abs(self.daily_pnl_abs) >= 0:
                    self.soft_stop = True
                    logger.error(
                        "Soft-stop activado por pérdidas diarias. No se aceptarán nuevas entradas."
                    )
                    if not self.soft_stop_notified:
                        try:
                            msg = (
                                "🛑 <b>SOFT-STOP</b>\n"
                                f"• Pérdidas diarias: {self.daily_losses_count} ops\n"
                                f"• PnL acumulado: {self.daily_pnl_abs:.2f} USDT\n"
                                "No se abrirán más posiciones hoy."
                            )
                            asyncio.create_task(self.notifier.send_text(msg))
                        except Exception:
                            pass
                        self.soft_stop_notified = True

    async def run(self) -> None:
        await self.ws.connect()
        try:
            # Aviso de arranque
            try:
                await self.notifier.send_start(self.exchange_name, self.mode, self.market, self.symbol)
            except Exception:
                pass
            async def _watch_stop() -> None:
                from pathlib import Path
                while True:
                    if Path("data/stop.flag").exists():
                        logger.info("Stop flag detected. Shutting down bot loop.")
                        try:
                            Path("data/stop.flag").unlink(missing_ok=True)
                        except Exception:
                            pass
                        try:
                            await self.ws.close()
                        except Exception:
                            pass
                        return
                    await asyncio.sleep(1.0)

            await asyncio.gather(
                self.ws.subscribe_klines(
                    self.symbol,
                    self.trading.timeframe,
                    lambda rows: asyncio.create_task(self._on_kline_closed(rows)),
                ),
                self.ws.subscribe_ticker(self.symbol, self._on_ticker),
                _watch_stop(),
            )
        finally:
            # Aviso de parada
            try:
                await self.notifier.send_stop(self.exchange_name, self.mode, self.market, self.symbol)
            except Exception:
                pass
