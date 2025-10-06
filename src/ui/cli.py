from __future__ import annotations

import asyncio
from typing import Optional
import typer
from loguru import logger

from infra.logging import setup_logging
from adapters.config.text_files_loader import TextFilesConfigLoader
from core.usecases.run_bot import BotRunner
from core.domain.services.strategy import evaluate_strategy
from core.domain.services.risk import compute_targets
from adapters.notifier.telegram_bot import TelegramNotifier
import csv as _csv
from pathlib import Path


app = typer.Typer(add_completion=False, help="Scalping bot CLI")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logs"),
    exchange: str = typer.Option("binance", "--exchange", case_sensitive=False),
    mode: Optional[str] = typer.Option(None, "--mode", help="testnet|real"),
    market: str = typer.Option("futures", "--market", case_sensitive=False),
    symbol: Optional[str] = typer.Option(None, "--symbol"),
    leverage: Optional[int] = typer.Option(None, "--leverage"),
    size: Optional[float] = typer.Option(None, "--size"),
    position_mode: Optional[str] = typer.Option(None, "--position-mode"),
    pairs_source: Optional[str] = typer.Option(None, "--pairs-source", help="exchange|file"),
    breakeven_enabled: Optional[bool] = typer.Option(None, "--breakeven-enabled/--no-breakeven-enabled"),
    breakeven_trigger_rr: Optional[float] = typer.Option(None, "--breakeven-trigger-rr"),
    trailing_enabled: Optional[bool] = typer.Option(None, "--trailing-enabled/--no-trailing-enabled"),
    trailing_mode: Optional[str] = typer.Option(None, "--trailing-mode", help="percent|atr"),
    trailing_percent: Optional[float] = typer.Option(None, "--trailing-percent"),
    atr_period: Optional[int] = typer.Option(None, "--atr-period"),
    atr_multiplier: Optional[float] = typer.Option(None, "--atr-multiplier"),
    take_profit_mode: Optional[str] = typer.Option(None, "--take-profit-mode", help="fixed|none"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    spread_max_pct: Optional[float] = typer.Option(None, "--spread-max-pct"),
    max_daily_loss_pct: Optional[float] = typer.Option(None, "--max-daily-loss-pct"),
):
    setup_logging(verbose=verbose)
    if ctx.invoked_subcommand is None:
        run(  # type: ignore[misc]
            exchange=exchange,
            mode=mode,
            market=market,
            symbol=symbol,
            leverage=leverage,
            size=size,
            position_mode=position_mode,
            pairs_source=pairs_source,
            breakeven_enabled=breakeven_enabled,
            breakeven_trigger_rr=breakeven_trigger_rr,
            trailing_enabled=trailing_enabled,
            trailing_mode=trailing_mode,
            trailing_percent=trailing_percent,
            atr_period=atr_period,
            atr_multiplier=atr_multiplier,
            take_profit_mode=take_profit_mode,
            dry_run=dry_run,
            spread_max_pct=spread_max_pct,
            max_daily_loss_pct=max_daily_loss_pct,
        )


@app.command()
def run(
    exchange: str = typer.Option("binance", "--exchange", case_sensitive=False),
    mode: Optional[str] = typer.Option(None, "--mode", help="testnet|real"),
    market: str = typer.Option("futures", "--market", case_sensitive=False),
    symbol: Optional[str] = typer.Option(None, "--symbol"),
    leverage: Optional[int] = typer.Option(None, "--leverage"),
    size: Optional[float] = typer.Option(None, "--size"),
    position_mode: Optional[str] = typer.Option(None, "--position-mode"),
    pairs_source: Optional[str] = typer.Option(
        None, "--pairs-source", help="exchange|file"
    ),
    breakeven_enabled: Optional[bool] = typer.Option(
        None, "--breakeven-enabled/--no-breakeven-enabled"
    ),
    breakeven_trigger_rr: Optional[float] = typer.Option(
        None, "--breakeven-trigger-rr"
    ),
    trailing_enabled: Optional[bool] = typer.Option(
        None, "--trailing-enabled/--no-trailing-enabled"
    ),
    trailing_mode: Optional[str] = typer.Option(
        None, "--trailing-mode", help="percent|atr"
    ),
    trailing_percent: Optional[float] = typer.Option(None, "--trailing-percent"),
    atr_period: Optional[int] = typer.Option(None, "--atr-period"),
    atr_multiplier: Optional[float] = typer.Option(None, "--atr-multiplier"),
    take_profit_mode: Optional[str] = typer.Option(
        None, "--take-profit-mode", help="fixed|none"
    ),
    dry_run: bool = typer.Option(False, "--dry-run"),
    spread_max_pct: Optional[float] = typer.Option(None, "--spread-max-pct"),
    max_daily_loss_pct: Optional[float] = typer.Option(None, "--max-daily-loss-pct"),
):
    """Start the trading bot."""
    cfg = TextFilesConfigLoader()
    cfg.ensure_defaults()

    api = cfg.load_api_keys(preferred_exchange=exchange)
    trade_cfg = cfg.load_trading()
    risk_cfg = cfg.load_risk()

    if mode is not None:
        api.mode = mode  # type: ignore[assignment]

    if position_mode is not None:
        trade_cfg.position_mode = position_mode
    if pairs_source is not None:
        trade_cfg.pairs_source = pairs_source
    if breakeven_enabled is not None:
        trade_cfg.breakeven_enabled = breakeven_enabled
    if breakeven_trigger_rr is not None:
        trade_cfg.breakeven_trigger_rr = breakeven_trigger_rr
    if trailing_enabled is not None:
        trade_cfg.trailing_enabled = trailing_enabled
    if trailing_mode is not None:
        trade_cfg.trailing_mode = trailing_mode
    if trailing_percent is not None:
        trade_cfg.trailing_percent = trailing_percent
    if atr_period is not None:
        trade_cfg.atr_period = atr_period
    if atr_multiplier is not None:
        trade_cfg.atr_multiplier = atr_multiplier
    if take_profit_mode is not None:
        trade_cfg.take_profit_mode = take_profit_mode
    if spread_max_pct is not None:
        trade_cfg.spread_max_pct = spread_max_pct
    if max_daily_loss_pct is not None:
        risk_cfg.max_daily_loss_pct = max_daily_loss_pct  # type: ignore[assignment]

    logger.info(
        "Starting bot: exchange={}, mode={}, market={}, dry_run={}",
        api.exchange,
        api.mode,
        market,
        dry_run,
    )

    if symbol is None:
        default_sym = "BTCUSDT"
        pairs: list[str] = []
        try:
            if trade_cfg.pairs_source == "file":
                pairs = cfg.load_pairs_from_file(trade_cfg.pairs_file)
            else:
                # pairs_source exchange (por defecto)
                if exchange.lower() == "binance":
                    from adapters.exchange.binance_ccxt import BinanceCcxt

                    ex = BinanceCcxt()
                    ex.configure(
                        api.api_key or "",
                        api.api_secret or "",
                        api.mode,
                        "futures" if market == "futures" else "spot",
                        exchange,
                    )
                    markets = ex.load_markets()
                    # Filtrar símbolos USDT y por tipo de mercado
                    for sym, meta in markets.items():
                        if not isinstance(sym, str):
                            continue
                        if "USDT" not in sym:
                            continue
                        if market == "futures":
                            if not meta.get("contract"):
                                continue
                        else:
                            if meta.get("contract"):
                                continue
                        pairs.append(sym.replace(":USDT", "USDT"))
                    pairs = sorted(set(pairs))
        except Exception:
            pairs = []
        if pairs:
            default_sym = pairs[0]
        symbol = typer.prompt("Símbolo", default=default_sym)
    # No solicitar leverage de forma interactiva; si no se pasa, se omite set_leverage

    if market not in ("futures", "spot"):
        raise typer.BadParameter("--market debe ser 'futures' o 'spot'\n")

    if trade_cfg.position_mode not in ("usdt_value", "contracts"):
        raise typer.BadParameter("position_mode inválido")

    size_value = (
        size
        if size is not None
        else float(typer.prompt("Tamaño (USDT o contratos)", default="50"))
    )

    runner = BotRunner(
        symbol=symbol,
        trading=trade_cfg,
        risk=risk_cfg,
        exchange_name=exchange,
        api_key=api.api_key,
        api_secret=api.api_secret,
        mode=api.mode,
        market=market,
        leverage=leverage,
        position_mode=trade_cfg.position_mode,
        size=size_value,
        dry_run=dry_run,
    )

    import asyncio

    asyncio.run(runner.run())


@app.command()
def backtest(
    csv_path: str = typer.Argument(
        ..., help="Ruta a CSV 5m (ts,open,high,low,close,volume)"
    ),
    rr: float = typer.Option(1.5, "--rr"),
    weak_body_ratio_max: float = typer.Option(0.25, "--weak-body-ratio-max"),
    range_cross_ema_count: int = typer.Option(3, "--range-cross-ema-count"),
    spread_max_pct: float = typer.Option(0.08, "--spread-max-pct"),
):
    """Ejecuta la estrategia sobre un CSV y reporta métricas simples."""
    import csv as _csv

    o: list[float] = []
    h: list[float] = []
    l: list[float] = []
    c: list[float] = []
    with open(csv_path, "r") as f:
        r = _csv.reader(f)
        for row in r:
            if not row or row[0].startswith("#"):
                continue
            o.append(float(row[1]))
            h.append(float(row[2]))
            l.append(float(row[3]))
            c.append(float(row[4]))

    trades = 0
    wins = 0
    pnl_usdt = 0.0
    trade_rows: list[dict] = []
    pos = None
    entry = sl = tp = 0.0
    for i in range(len(c)):
        # Emular cierre de vela y evaluación
        if i < 60:
            continue
        if pos is None:
            sig = evaluate_strategy(
                o[: i + 1],
                h[: i + 1],
                l[: i + 1],
                c[: i + 1],
                "5m",
                rr,
                weak_body_ratio_max,
                range_cross_ema_count,
                0.0,
                spread_max_pct,
            )
            if sig.side in ("long", "short") and sig.entry and sig.sl:
                entry = sig.entry
                sl = sig.sl
                tp = compute_targets(entry, sl, sig.rr, sig.side)  # type: ignore[arg-type]
                pos = sig.side
        else:
            px = c[i]
            hit_sl = px <= sl if pos == "long" else px >= sl
            hit_tp = px >= tp if pos == "long" else px <= tp
            if hit_sl or hit_tp:
                trades += 1
                win = 1 if hit_tp else 0
                wins += win
                trade_pnl = (px - entry) if pos == "long" else (entry - px)
                pnl_usdt += trade_pnl
                trade_rows.append(
                    {
                        "ts": i,
                        "side": pos,
                        "entry": entry,
                        "exit": px,
                        "sl": sl,
                        "tp": tp,
                        "pnl": trade_pnl,
                        "win": win,
                    }
                )
                pos = None

    logger.info(
        "BT: trades={}, winrate={:.1f}%, pnl(usdt per 1 qty)={:.4f}",
        trades,
        (wins / trades * 100) if trades else 0.0,
        pnl_usdt,
    )

    # Exportar trades a CSV
    from pathlib import Path
    import csv as _csv

    data_dir = Path("data")
    data_dir.mkdir(parents=True, exist_ok=True)
    out_path = data_dir / "backtest_trades.csv"
    with out_path.open("w", newline="") as f:
        writer = _csv.DictWriter(
            f, fieldnames=["ts", "side", "entry", "exit", "sl", "tp", "pnl", "win"]
        )
        writer.writeheader()
        for r in trade_rows:
            writer.writerow(r)
    logger.info("Backtest trades exportados a {}", out_path)


@app.command()
def notify_test() -> None:
    """Envía mensajes de prueba (OPEN y CLOSE) a Telegram."""
    async def _run():
        n = TelegramNotifier()
        await n.send_open(
            "🚀 <b>OPEN</b> | testnet/demo\n"
            "• <b>Symbol</b>: BTCUSDT\n"
            "• <b>Side</b>: 🟢 Long\n"
            "• <b>Entry</b>: 60000\n"
            "• <b>Size</b>: 0.01 (~600 USDT)\n"
            "• <b>SL</b>: 59400  |  <b>TP</b>: 60900  |  <b>RR</b>: 1.5\n"
            "• <b>Lev</b>: 5x\n"
            "⏱️ demo"
        )
        await n.send_close(
            "🔔 <b>CLOSE</b> | testnet/demo\n"
            "• <b>Symbol</b>: BTCUSDT (Long)\n"
            "• <b>Exit</b>: 60750\n"
            "• <b>PnL</b>: 7.50 USDT (1.25%)\n"
            "• <b>Reason</b>: ✅ TP\n"
            "• Fees est.: 0.02 USDT\n"
            "⏱️ demo"
        )

    asyncio.run(_run())


@app.command()
def notify_test_adv() -> None:
    """Envía mensajes de prueba para BE y TRAIL a Telegram."""
    async def _run():
        n = TelegramNotifier()
        await n.send_be(
            "🟨 <b>BE</b> | testnet/demo\n"
            "• <b>Symbol</b>: BTCUSDT (Long)\n"
            "• <b>MFE</b>: 60750\n"
            "• <b>SL → BE</b>: 60000\n"
            "⏱️ demo"
        )
        await n.send_trail(
            "📈 <b>TRAIL</b> | testnet/demo\n"
            "• <b>Symbol</b>: BTCUSDT (Long)\n"
            "• <b>Mode</b>: percent\n"
            "• <b>SL</b>: 60000 → 60300\n"
            "• <b>MFE</b>: 60880\n"
            "⏱️ demo"
        )

    asyncio.run(_run())


@app.command()
def tele_status() -> None:
    """Lee data/trades.csv y data/state.csv y envía un resumen por Telegram."""
    def _read_trades():
        trades_path = Path("data") / "trades.csv"
        rows = []
        if trades_path.exists():
            with trades_path.open() as f:
                r = _csv.DictReader(f)
                for row in r:
                    rows.append(row)
        return rows

    def _read_state():
        state_path = Path("data") / "state.csv"
        rows = []
        if state_path.exists():
            with state_path.open() as f:
                r = _csv.DictReader(f)
                for row in r:
                    rows.append(row)
        return rows

    async def _run():
        rows = _read_trades()
        state = _read_state()
        open_positions = 1 if state else 0
        closed = len(rows)
        wins = sum(1 for r in rows if float(r.get("pnl_abs", 0) or 0) > 0)
        losses = closed - wins
        pnl_usdt = sum(float(r.get("pnl_abs", 0) or 0) for r in rows)
        wins_usdt = sum(float(r.get("pnl_abs", 0) or 0) for r in rows if float(r.get("pnl_abs", 0) or 0) > 0)
        losses_usdt = sum(float(r.get("pnl_abs", 0) or 0) for r in rows if float(r.get("pnl_abs", 0) or 0) < 0)
        base_equity = 0.0
        eq_path = Path("data") / "equity.json"
        if eq_path.exists():
            import json as _json
            try:
                base_equity = float(_json.loads(eq_path.read_text()).get("base_equity_usdt", 0.0))
            except Exception:
                base_equity = 0.0

        n = TelegramNotifier()
        await n.send_text(
            "📊 <b>STATUS</b>\n"
            f"• Posiciones abiertas: {open_positions}\n"
            f"• Cerradas: {closed}\n"
            f"• Ganadas: {wins} (≈ {wins_usdt:.2f} USDT)\n"
            f"• Perdidas: {losses} (≈ {losses_usdt:.2f} USDT)\n"
            f"• PnL neto: {pnl_usdt:.2f} USDT\n"
            f"• Equity base: {base_equity:.2f} USDT\n"
        )
@app.command()
def tele_poll() -> None:
    """Escucha comandos básicos de Telegram (e.g., /status) y responde con resúmenes."""
    import asyncio as _asyncio

    def _read_trades():
        p = Path("data") / "trades.csv"
        rows = []
        if p.exists():
            with p.open() as f:
                r = _csv.DictReader(f)
                for row in r:
                    rows.append(row)
        return rows

    def _read_state():
        p = Path("data") / "state.csv"
        rows = []
        if p.exists():
            with p.open() as f:
                r = _csv.DictReader(f)
                for row in r:
                    rows.append(row)
        return rows

    async def _status(notif: TelegramNotifier) -> None:
        rows = _read_trades()
        state = _read_state()
        open_positions = 1 if state else 0
        closed = len(rows)
        wins = sum(1 for r in rows if float(r.get("pnl_abs", 0) or 0) > 0)
        losses = closed - wins
        pnl_usdt = sum(float(r.get("pnl_abs", 0) or 0) for r in rows)
        wins_usdt = sum(float(r.get("pnl_abs", 0) or 0) for r in rows if float(r.get("pnl_abs", 0) or 0) > 0)
        losses_usdt = sum(float(r.get("pnl_abs", 0) or 0) for r in rows if float(r.get("pnl_abs", 0) or 0) < 0)
        base_equity = 0.0
        eq_path = Path("data") / "equity.json"
        if eq_path.exists():
            import json as _json
            try:
                base_equity = float(_json.loads(eq_path.read_text()).get("base_equity_usdt", 0.0))
            except Exception:
                base_equity = 0.0
        await notif.send_text(
            "📊 <b>STATUS</b>\n"
            f"• Posiciones abiertas: {open_positions}\n"
            f"• Cerradas: {closed}\n"
            f"• Ganadas: {wins} (≈ {wins_usdt:.2f} USDT)\n"
            f"• Perdidas: {losses} (≈ {losses_usdt:.2f} USDT)\n"
            f"• PnL neto: {pnl_usdt:.2f} USDT\n"
            f"• Equity base: {base_equity:.2f} USDT\n"
        )

    async def _run():
        notif = TelegramNotifier()
        # Enviar menú al iniciar el poller
        try:
            await notif.send_menu()
        except Exception:
            pass
        last_update_id = None
        while True:
            updates = await notif.fetch_updates(offset=last_update_id + 1 if last_update_id else None)
            for u in updates:
                last_update_id = u.update_id
                msg = getattr(u, "message", None)
                if not msg:
                    continue
                text = (msg.text or "").strip()
                # Authorization: only configured chat_id and user_id
                if not notif.is_authorized(getattr(msg.chat, "id", None), getattr(getattr(msg, "from_user", None), "id", None)):
                    continue
                if text.lower().startswith("/menu"):
                    await notif.send_menu()
                elif text.lower().startswith("/status"):
                    await _status(notif)
                elif text.lower().startswith("/health"):
                    # Health summary: poller alive, flags, bot process, last log line
                    import subprocess as _sp
                    def _bot_running() -> bool:
                        try:
                            out = _sp.check_output(["ps", "-ef"], text=True)
                            for line in out.splitlines():
                                if "-m src.app" in line and "tele-poll" not in line:
                                    return True
                                if "run-bot.sh" in line and "tele-poll" not in line:
                                    return True
                        except Exception:
                            return False
                        return False
                    stop_on = (Path("data")/"stop.flag").exists()
                    pause_on = (Path("data")/"pause.flag").exists()
                    running = _bot_running()
                    # last log line (optional)
                    last_log = None
                    try:
                        lp = Path("logs")/"bot.log"
                        if lp.exists():
                            with lp.open("r") as f:
                                lines = f.readlines()
                                if lines:
                                    last_log = lines[-1].strip()[:200]
                    except Exception:
                        last_log = None
                    await notif.send_text(
                        "🩺 <b>HEALTH</b>\n"
                        f"• Poller: ✅ vivo\n"
                        f"• Bot proceso: {'✅ running' if running else '❌ no encontrado'}\n"
                        f"• stop.flag: {'ON' if stop_on else 'off'} | pause.flag: {'ON' if pause_on else 'off'}\n"
                        + (f"• Último log: {last_log}" if last_log else "")
                    )
                elif text.lower().startswith("/stop"):
                    # Parada suave + intento de SIGTERM si sigue activo
                    import subprocess as _sp
                    p = Path("data"); p.mkdir(parents=True, exist_ok=True)
                    (p/"stop.flag").write_text("stop", encoding="utf-8")
                    await notif.send_text("🛑 Bot: stop solicitado. Cerrando loop…")
                    try:
                        out = _sp.check_output(["ps", "-ef"], text=True)
                        for line in out.splitlines():
                            if "-m src.app" in line and "tele-poll" not in line:
                                parts = line.split()
                                if len(parts) > 1:
                                    _sp.Popen(["kill", "-TERM", parts[1]])
                    except Exception:
                        pass
                elif text.lower().startswith("/pause"):
                    p = Path("data"); p.mkdir(parents=True, exist_ok=True)
                    (p/"pause.flag").write_text("pause", encoding="utf-8")
                    await notif.send_text("⏸️ Bot: pause activado (no abre nuevas entradas)")
                elif text.lower().startswith("/resume"):
                    p = Path("data"); p.mkdir(parents=True, exist_ok=True)
                    try:
                        (p/"pause.flag").unlink(missing_ok=True)
                    except Exception:
                        pass
                    await notif.send_text("▶️ Bot: pause desactivado (reanuda evaluaciones)")
                elif text.lower().startswith("/restart"):
                    # Reinicio usando systemd si existe; si no, último comando guardado
                    import shutil as _sh
                    import subprocess as _sp
                    p = Path("data"); p.mkdir(parents=True, exist_ok=True)
                    (p/"stop.flag").write_text("stop", encoding="utf-8")
                    try:
                        if _sh.which("systemctl") and Path("/etc/systemd/system/trading-bot.service").exists():
                            _sp.Popen(["systemctl", "restart", "trading-bot"], stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
                            await notif.send_text("🔄 Bot: restart via systemd")
                        else:
                            meta_path = Path("data")/"last_start.json"
                            if meta_path.exists():
                                import json as _json
                                try:
                                    meta = _json.loads(meta_path.read_text())
                                    cmd = meta.get("cmd")
                                except Exception:
                                    cmd = None
                                if isinstance(cmd, list) and cmd:
                                    (Path("logs")).mkdir(parents=True, exist_ok=True)
                                    lf = (Path("logs")/"launcher.log").open("a")
                                    _sp.Popen(cmd, stdout=lf, stderr=lf, stdin=_sp.DEVNULL)
                                    await notif.send_text("🔄 Bot: restart con último comando guardado")
                                else:
                                    await notif.send_text("⚠️ No hay comando previo para reiniciar")
                            else:
                                await notif.send_text("⚠️ No existe data/last_start.json para reiniciar")
                    except Exception as _e:
                        await notif.send_text(f"⚠️ Restart falló: {_e}")
                elif text.lower().startswith("/start_r") or text.lower().startswith("/start_t"):
                    # /start_r -> real, /start_t -> testnet
                    import shutil as _sh
                    import subprocess as _sp
                    mode_to_start = "real" if text.lower().startswith("/start_r") else "testnet"
                    try:
                        # limpiar flags que impiden arranque
                        p = Path("data"); p.mkdir(parents=True, exist_ok=True)
                        try:
                            (p/"stop.flag").unlink(missing_ok=True)
                            (p/"pause.flag").unlink(missing_ok=True)
                        except Exception:
                            pass
                        if _sh.which("systemctl") and Path("/etc/systemd/system/trading-bot.service").exists():
                            _sp.Popen(["systemctl", "start", "trading-bot"], stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
                            await notif.send_text(f"▶️ Bot: start ({mode_to_start}) via systemd (trading-bot.service)")
                        else:
                            cmd = [
                                "bash",
                                "run-bot.sh",
                                "--exchange", "bybit",
                                "--market", "futures",
                                "--mode", mode_to_start,
                                "--symbol", "BTCUSDT",
                                "--size", "10",
                            ]
                            # Capturar salida del launcher para diagnosticar problemas de arranque
                            (Path("logs")).mkdir(parents=True, exist_ok=True)
                            lf = (Path("logs")/"launcher.log").open("a")
                            _sp.Popen(
                                cmd,
                                stdout=lf,
                                stderr=lf,
                                stdin=_sp.DEVNULL,
                            )
                            # Guardar último comando para permitir /restart
                            try:
                                import json as _json
                                (Path("data")).mkdir(parents=True, exist_ok=True)
                                (Path("data")/"last_start.json").write_text(_json.dumps({"cmd": cmd}), encoding="utf-8")
                            except Exception:
                                pass
                            await notif.send_text(f"▶️ Bot: start ({mode_to_start}) solicitado con run-bot.sh")
                    except Exception as _e:
                        await notif.send_text(f"⚠️ No se pudo iniciar el bot: {_e}")
            await _asyncio.sleep(2)

    _import_asyncio = __import__("asyncio")
    _import_asyncio.run(_run())

    asyncio.run(_run())
