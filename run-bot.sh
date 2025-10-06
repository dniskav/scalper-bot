#!/usr/bin/env bash

set -euo pipefail

# Simple launcher for the scalping bot with interactive prompts for missing options

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_PY="$ROOT_DIR/.venv/bin/python"

usage() {
  echo "Usage: $0 [--exchange EX] [--market MK] [--mode MD] [--symbol SYM] [--size SZ] [--leverage L] [--pairs-source SRC] [--dry-run] [--verbose]" >&2
}

# Parse args (simple manual parser)
EXCHANGE=""
MARKET=""
MODE=""
SYMBOL=""
SIZE=""
LEVERAGE=""
PAIRS_SOURCE=""
DRY_RUN="false"
VERBOSE="false"
SPREAD_MAX_PCT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --exchange) EXCHANGE="${2:-}"; shift 2;;
    --market) MARKET="${2:-}"; shift 2;;
    --mode) MODE="${2:-}"; shift 2;;
    --symbol) SYMBOL="${2:-}"; shift 2;;
    --size) SIZE="${2:-}"; shift 2;;
    --leverage) LEVERAGE="${2:-}"; shift 2;;
    --pairs-source) PAIRS_SOURCE="${2:-}"; shift 2;;
    --dry-run) DRY_RUN="true"; shift;;
    --verbose) VERBOSE="true"; shift;;
    --spread-max-pct) SPREAD_MAX_PCT="${2:-}"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown option: $1" >&2; usage; exit 1;;
  esac
done

# Interactive prompts for missing values, only if running in a TTY
if [[ -t 0 ]]; then
  read -r -p "Exchange [binance/bybit/okx] (${EXCHANGE:-binance}): " _in || true
  EXCHANGE="${_in:-${EXCHANGE:-binance}}"; _in=""

  read -r -p "Market [futures/spot] (${MARKET:-futures}): " _in || true
  MARKET="${_in:-${MARKET:-futures}}"; _in=""

  read -r -p "Mode [testnet/real] (${MODE:-testnet}): " _in || true
  MODE="${_in:-${MODE:-testnet}}"; _in=""

  read -r -p "Symbol (e.g., BTCUSDT) (${SYMBOL:-BTCUSDT}): " _in || true
  SYMBOL="${_in:-${SYMBOL:-BTCUSDT}}"; _in=""

  read -r -p "Size (USDT or contracts) (${SIZE:-50}): " _in || true
  SIZE="${_in:-${SIZE:-50}}"; _in=""

  if [[ "$MARKET" == "futures" ]]; then
    read -r -p "Leverage (press Enter to skip) (${LEVERAGE:-}): " _in || true
    LEVERAGE="${_in:-$LEVERAGE}"; _in=""
  fi

  read -r -p "Pairs source [exchange/file] (${PAIRS_SOURCE:-exchange}): " _in || true
  PAIRS_SOURCE="${_in:-${PAIRS_SOURCE:-exchange}}"; _in=""

  read -r -p "Dry run? [y/N] ($( [[ \"$DRY_RUN\" == true ]] && echo y || echo N )): " _in || true
  _norm=$(printf "%s" "$_in" | tr '[:upper:]' '[:lower:]')
  case "$_norm" in
    y|yes) DRY_RUN="true";;
    *) DRY_RUN="false";;
  esac
  _in=""

  read -r -p "Verbose logs? [y/N] ($( [[ \"$VERBOSE\" == true ]] && echo y || echo N )): " _in || true
  _norm=$(printf "%s" "$_in" | tr '[:upper:]' '[:lower:]')
  case "$_norm" in
    y|yes) VERBOSE="true";;
    *) VERBOSE="false";;
  esac
  _in=""
else
  # Non-interactive: fill defaults for anything missing
  EXCHANGE="${EXCHANGE:-binance}"
  MARKET="${MARKET:-futures}"
  MODE="${MODE:-testnet}"
  SYMBOL="${SYMBOL:-BTCUSDT}"
  SIZE="${SIZE:-50}"
  PAIRS_SOURCE="${PAIRS_SOURCE:-exchange}"
  # LEVERAGE may remain empty to skip set_leverage
  DRY_RUN="${DRY_RUN:-false}"
  VERBOSE="${VERBOSE:-false}"
fi

# Ensure venv
if [[ ! -x "$VENV_PY" ]]; then
  echo "Python venv not found at $VENV_PY" >&2
  echo "Create it with: python3 -m venv .venv && .venv/bin/pip install -r deploy/requirements.txt" >&2
  exit 1
fi

EXTRA_ARGS=()
if [[ -n "$LEVERAGE" ]]; then
  EXTRA_ARGS+=("--leverage" "$LEVERAGE")
fi
if [[ -n "$SPREAD_MAX_PCT" ]]; then
  EXTRA_ARGS+=("--spread-max-pct" "$SPREAD_MAX_PCT")
fi
if [[ "$DRY_RUN" == "true" ]]; then
  EXTRA_ARGS+=("--dry-run")
fi
if [[ "$VERBOSE" == "true" ]]; then
  EXTRA_ARGS+=("--verbose")
fi

export PYTHONPATH="$ROOT_DIR/src"

# Safely expand EXTRA_ARGS even if empty
ARGS=(
  -m src.app
  --exchange "$EXCHANGE" \
  --market "$MARKET" \
  --mode "$MODE" \
  --symbol "$SYMBOL" \
  --size "$SIZE" \
  --pairs-source "$PAIRS_SOURCE"
)
if [[ ${#EXTRA_ARGS[@]:-0} -gt 0 ]]; then
  ARGS+=("${EXTRA_ARGS[@]}")
fi

exec "$VENV_PY" "${ARGS[@]}"


