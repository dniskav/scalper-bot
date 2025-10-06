#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
PY="$ROOT_DIR/.venv/bin/python"

if [[ ! -x "$PY" ]]; then
  echo "Python venv not found at $PY" >&2
  echo "Create it with: python3 -m venv .venv && .venv/bin/pip install -r deploy/requirements.txt" >&2
  exit 1
fi

export PYTHONPATH="$ROOT_DIR/src"

exec "$PY" -m src.app tele-poll


