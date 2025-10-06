#!/usr/bin/env bash
set -euo pipefail

# Installer for trading-bot systemd unit and wrapper

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
WRAPPER="/usr/local/bin/trading-bot"
UNIT_FILE="/etc/systemd/system/trading-bot.service"
ENV_FILE="/etc/trading-bot.env"

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root: sudo $0" >&2
  exit 1
fi

VENV_PY="$ROOT_DIR/.venv/bin/python"
if [[ ! -x "$VENV_PY" ]]; then
  echo "Python venv not found at $VENV_PY" >&2
  echo "Create it with: python3 -m venv .venv && .venv/bin/pip install -r deploy/requirements.txt" >&2
  exit 1
fi

cat > "$WRAPPER" <<'WRAP'
#!/usr/bin/env bash
set -euo pipefail

# Wrapper to launch the bot with PYTHONPATH set and venv python

ROOT_DIR="/opt/trading-bot"
PY="$ROOT_DIR/.venv/bin/python"
export PYTHONPATH="$ROOT_DIR/src"

# Load optional environment overrides
if [[ -f /etc/trading-bot.env ]]; then
  set -o allexport
  # shellcheck disable=SC1091
  source /etc/trading-bot.env
  set +o allexport
fi

exec "$PY" -m src.app "$@"
WRAP

chmod +x "$WRAPPER"

mkdir -p /opt/trading-bot
rsync -a --delete "$ROOT_DIR/" /opt/trading-bot/

cat > "$UNIT_FILE" <<UNIT
[Unit]
Description=Trading Bot (scalping)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/trading-bot
ExecStart=$WRAPPER --exchange ${EXCHANGE:-bybit} --market ${MARKET:-futures} --mode ${MODE:-testnet} --symbol ${SYMBOL:-ETHUSDT} --size ${SIZE:-10} --leverage ${LEVERAGE:-20}
Restart=on-failure
EnvironmentFile=-$ENV_FILE

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable trading-bot.service

echo "Installed: $WRAPPER and $UNIT_FILE"
echo "Edit $ENV_FILE to override default flags, then: systemctl start trading-bot"

