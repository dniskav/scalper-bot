from __future__ import annotations

from pathlib import Path
from typing import Optional
from pydantic import ValidationError
from loguru import logger

from ports.config_port import ConfigPort, ApiKeys, TradingConfig, RiskConfig


CONFIG_DIR = Path("config")

API_KEYS_FILE = CONFIG_DIR / "api_keys.txt"
TELEGRAM_FILE = CONFIG_DIR / "telegram.txt"
TRADING_FILE = CONFIG_DIR / "trading.txt"
RISK_FILE = CONFIG_DIR / "risk.txt"
PAIRS_FILE = CONFIG_DIR / "pairs.txt"


DEFAULT_API_KEYS = (
    "# exchange por defecto\n"
    "default_exchange=binance\n"
    "# modo por defecto (CLI tiene prioridad)\n"
    "default_mode=testnet\n\n"
    "[binance]\n"
    "api_key=TU_API_KEY\n"
    "api_secret=TU_API_SECRET\n"
    "use_testnet=true\n\n"
    "[bybit]\n"
    "api_key=\n"
    "api_secret=\n"
    "use_testnet=true\n\n"
    "[okx]\n"
    "api_key=\n"
    "api_secret=\n"
    "passphrase=\n"
    "use_testnet=true\n"
)


DEFAULT_TRADING = (
    "timeframe=5m\n"
    "rr=1.5\n"
    "filter_weak_signal=true\n"
    "weak_body_ratio_max=0.25\n"
    "range_cross_ema_count=3\n"
    "sessions_filter=true\n"
    "sessions_timezone=Europe/Madrid\n"
    "sessions_allowed=08:00-17:00,14:00-22:00\n"
    "position_mode=usdt_value\n"
    "reduce_only_on_exit=true\n"
    "max_retries=5\n"
    "pairs_source=exchange\n"
    "pairs_file=config/pairs.txt\n"
    "spread_max_pct=0.08\n"
    "slippage_pct=0.02\n"
    "# --- Break-even ---\n"
    "breakeven_enabled=true\n"
    "breakeven_trigger_rr=1.0\n"
    "breakeven_offset_ticks=0\n"
    "breakeven_offset_pct=0.02\n"
    "# --- Trailing ---\n"
    "trailing_enabled=true\n"
    "trailing_mode=percent\n"
    "trailing_percent=0.5\n"
    "trailing_step_pct=0.1\n"
    "atr_period=14\n"
    "atr_multiplier=2.0\n"
    "# --- TP ---\n"
    "take_profit_mode=fixed\n"
)


DEFAULT_RISK = "max_open_trades=1\n" "max_daily_loss_pct=3\n" "max_daily_trades=10\n"


DEFAULT_TELEGRAM = "bot_token=\n" "chat_id=\n"


DEFAULT_PAIRS = "BTCUSDT\n" "ETHUSDT\n" "DOGEUSDT\n"


def _parse_simple_kv(text: str) -> dict[str, str]:
    data: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith(";"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            data[k.strip()] = v.strip()
    return data


def _parse_sections(text: str) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    header: dict[str, str] = {}
    sections: dict[str, dict[str, str]] = {}
    current: Optional[str] = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith(";"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1].strip().lower()
            sections.setdefault(current, {})
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            if current is None:
                header[k.strip()] = v.strip()
            else:
                sections[current][k.strip()] = v.strip()
    return header, sections


class TextFilesConfigLoader(ConfigPort):
    def ensure_defaults(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        created = []
        if not API_KEYS_FILE.exists():
            API_KEYS_FILE.write_text(DEFAULT_API_KEYS, encoding="utf-8")
            created.append(str(API_KEYS_FILE))
        if not TRADING_FILE.exists():
            TRADING_FILE.write_text(DEFAULT_TRADING, encoding="utf-8")
            created.append(str(TRADING_FILE))
        if not RISK_FILE.exists():
            RISK_FILE.write_text(DEFAULT_RISK, encoding="utf-8")
            created.append(str(RISK_FILE))
        if not TELEGRAM_FILE.exists():
            TELEGRAM_FILE.write_text(DEFAULT_TELEGRAM, encoding="utf-8")
            created.append(str(TELEGRAM_FILE))
        if not PAIRS_FILE.exists():
            PAIRS_FILE.write_text(DEFAULT_PAIRS, encoding="utf-8")
            created.append(str(PAIRS_FILE))
        if created:
            logger.info("Config files created: {}", ", ".join(created))
            logger.info(
                "Complete your credentials in config files before real trading."
            )

    def load_api_keys(self, preferred_exchange: Optional[str] = None) -> ApiKeys:
        text = (
            API_KEYS_FILE.read_text(encoding="utf-8")
            if API_KEYS_FILE.exists()
            else DEFAULT_API_KEYS
        )
        header, sections = _parse_sections(text)
        exchange = (
            preferred_exchange or header.get("default_exchange", "binance")
        ).lower()
        mode = header.get("default_mode", "testnet").lower()

        sect = sections.get(exchange, {})
        # Prefer explicit sections when present
        chosen: dict[str, str] = sect
        if exchange == "binance":
            if mode == "testnet" and "binance_testnet" in sections:
                chosen = sections["binance_testnet"]
            elif mode == "real" and "binance_real" in sections:
                chosen = sections["binance_real"]
        api_key = chosen.get("api_key") or None
        api_secret = chosen.get("api_secret") or None
        passphrase = chosen.get("passphrase") or None
        use_testnet = (chosen.get("use_testnet") or sect.get("use_testnet") or "true").lower() == "true"

        try:
            return ApiKeys(
                exchange=exchange,
                mode="testnet" if use_testnet or mode == "testnet" else "real",
                api_key=api_key,
                api_secret=api_secret,
                passphrase=passphrase,
                use_testnet=use_testnet,
            )
        except ValidationError as e:
            raise RuntimeError(f"Invalid API keys config: {e}") from e

    def load_trading(self) -> TradingConfig:
        text = (
            TRADING_FILE.read_text(encoding="utf-8")
            if TRADING_FILE.exists()
            else DEFAULT_TRADING
        )
        data = _parse_simple_kv(text)
        try:
            return TradingConfig(
                **{  # type: ignore[arg-type]
                    "timeframe": data.get("timeframe", "5m"),
                    "rr": float(data.get("rr", 1.5)),
                    "filter_weak_signal": data.get("filter_weak_signal", "true").lower()
                    == "true",
                    "weak_body_ratio_max": float(data.get("weak_body_ratio_max", 0.25)),
                    "range_cross_ema_count": int(data.get("range_cross_ema_count", 3)),
                    "sessions_filter": data.get("sessions_filter", "true").lower()
                    == "true",
                    "sessions_timezone": data.get("sessions_timezone", "Europe/Madrid"),
                    "sessions_allowed": data.get(
                        "sessions_allowed", "08:00-17:00,14:00-22:00"
                    ),
                    "position_mode": data.get("position_mode", "usdt_value"),
                    "reduce_only_on_exit": data.get(
                        "reduce_only_on_exit", "true"
                    ).lower()
                    == "true",
                    "max_retries": int(data.get("max_retries", 5)),
                    "pairs_source": data.get("pairs_source", "exchange"),
                    "pairs_file": data.get("pairs_file", "config/pairs.txt"),
                    "spread_max_pct": float(data.get("spread_max_pct", 0.08)),
                    "slippage_pct": float(data.get("slippage_pct", 0.02)),
                    # BE/Trailing/TP
                    "breakeven_enabled": data.get("breakeven_enabled", "true").lower()
                    == "true",
                    "breakeven_trigger_rr": float(
                        data.get("breakeven_trigger_rr", 1.0)
                    ),
                    "breakeven_offset_ticks": int(
                        data.get("breakeven_offset_ticks", 0)
                    ),
                    "breakeven_offset_pct": float(
                        data.get("breakeven_offset_pct", 0.02)
                    ),
                    "trailing_enabled": data.get("trailing_enabled", "true").lower()
                    == "true",
                    "trailing_mode": data.get("trailing_mode", "percent"),
                    "trailing_percent": float(data.get("trailing_percent", 0.5)),
                    "trailing_step_pct": float(data.get("trailing_step_pct", 0.1)),
                    "atr_period": int(data.get("atr_period", 14)),
                    "atr_multiplier": float(data.get("atr_multiplier", 2.0)),
                    "take_profit_mode": data.get("take_profit_mode", "fixed"),
                }
            )
        except (ValueError, ValidationError) as e:
            raise RuntimeError(f"Invalid trading config: {e}") from e

    def load_risk(self) -> RiskConfig:
        text = (
            RISK_FILE.read_text(encoding="utf-8")
            if RISK_FILE.exists()
            else DEFAULT_RISK
        )
        data = _parse_simple_kv(text)
        try:
            return RiskConfig(
                max_open_trades=int(data.get("max_open_trades", 1)),
                max_daily_loss_pct=float(data.get("max_daily_loss_pct", 3)),
                max_daily_trades=int(data.get("max_daily_trades", 10)),
            )
        except (ValueError, ValidationError) as e:
            raise RuntimeError(f"Invalid risk config: {e}") from e

    def load_pairs_from_file(self, path: str) -> list[str]:
        file_path = Path(path)
        if not file_path.exists():
            logger.warning("Pairs file not found at {}, using defaults.", file_path)
            return [s.strip() for s in DEFAULT_PAIRS.splitlines() if s.strip()]
        lines = [
            ln.strip() for ln in file_path.read_text(encoding="utf-8").splitlines()
        ]
        return [ln for ln in lines if ln and not ln.startswith("#")]
