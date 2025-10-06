Bot Scalping (RSI3 + ADX5 + EMA50)

Overview

This project implements a 5m scalping bot using a hexagonal architecture (Ports & Adapters) with vertical slices. It supports Binance (Spot and USDT-M Futures, testnet/real), and provides minimal adapters for Bybit/OKX. Market data uses public WebSockets; orders use ccxt REST. Notifications are sent via Telegram.

Quickstart

1. Create config files (auto-generated on first run under `config/`).
2. Install dependencies:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r deploy/requirements.txt
```

3. Run locally (interactive prompts if flags are missing):

```bash
python -m src.app --exchange binance --market futures --dry-run --verbose
```

4. VPS (Ubuntu 22.04+): instala Python 3.11+, copia el proyecto. Puedes usar Docker (`deploy/Dockerfile`) o instalar un servicio systemd con `deploy/install-systemd.sh` (ver sección abajo).

Architecture

- Domain is exchange-agnostic.
- Ports define contracts.
- Adapters implement integrations (ccxt, WebSocket, Telegram, file config, CSV storage, clock).
- Use cases orchestrate.
- CLI handles user interaction/logs.

Entrypoint

Run via module: `python -m src.app`

Safety

- Testnet vs real endpoints are enforced by config and CLI override.
- `--dry-run` avoids sending real orders while keeping full logs and Telegram.

Break-Even & Trailing

- Config (en `config/trading.txt`):
  - Break-even: `breakeven_enabled`, `breakeven_trigger_rr`, `breakeven_offset_ticks`, `breakeven_offset_pct`.
  - Trailing: `trailing_enabled`, `trailing_mode` (percent|atr), `trailing_percent`, `trailing_step_pct`, `atr_period`, `atr_multiplier`.
  - TP: `take_profit_mode` (fixed|none) y `rr` (si fixed).
- Reglas:
  - Primero BE: cuando MFE alcanza `trigger_rr` en R, mueve SL a BE (+ offsets/ticks). Luego trailing.
  - Trailing percent: SL = MFE\*(1 - p/100) en long (simétrico en short), con paso mínimo `trailing_step_pct`.
  - Trailing ATR: SL = precio actual ± ATR\*mult, con paso mínimo y redondeo.
  - Si `take_profit_mode=fixed`, se mantiene TP fijo; si `none`, solo SL (BE/Trailing).
- CLI overrides opcionales:
  - `--breakeven-enabled/--no-breakeven-enabled`, `--breakeven-trigger-rr FLOAT`
  - `--trailing-enabled/--no-trailing-enabled`, `--trailing-mode [percent|atr]`
  - `--trailing-percent FLOAT`, `--atr-period INT`, `--atr-multiplier FLOAT`
  - `--take-profit-mode [fixed|none]`

CLI ejemplo

```bash
python -m src.app --exchange binance --market futures --symbol BTCUSDT --leverage 10 --size 100 --dry-run --verbose
```

## Systemd (VPS)

1. Crear venv e instalar deps:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r deploy/requirements.txt
```

2. Instalar servicio (sudo):

```bash
sudo bash deploy/install-systemd.sh
```

Crea:

- Wrapper `/usr/local/bin/trading-bot` que ejecuta `python -m src.app` con `PYTHONPATH` y venv.
- Unit `/etc/systemd/system/trading-bot.service` con flags por defecto.
- Archivo opcional `/etc/trading-bot.env` para overrides (EXCHANGE, MARKET, MODE, SYMBOL, SIZE, LEVERAGE, etc.).

3. Operación:

```bash
sudo systemctl start trading-bot
sudo systemctl status trading-bot
sudo systemctl stop trading-bot
sudo journalctl -u trading-bot -f
```

No interfiere con `./run-bot.sh`; puedes usar ambos.

Config por archivos

- `config/api_keys.txt`: claves por exchange y modo por defecto.
- `config/telegram.txt`: bot_token y chat_id.
- `config/trading.txt`: timeframe, RR, filtros, sesiones, position_mode.
- `config/risk.txt`: límites diarios.
  - CLI adicional: `--max-daily-loss-pct FLOAT`
- `config/pairs.txt`: lista de símbolos si `pairs_source=file`.

License

For educational purposes. Use at your own risk.
