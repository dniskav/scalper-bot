#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

"$ROOT_DIR/.venv/bin/pip" install --upgrade pip wheel setuptools
"$ROOT_DIR/.venv/bin/pip" install -r deploy/requirements.txt

export PYTHONPATH="$ROOT_DIR/src"
exec "$ROOT_DIR/.venv/bin/python" -m src.app "$@"


