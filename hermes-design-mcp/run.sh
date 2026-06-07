#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
# Use Python 3.11+ (mcp SDK requires >=3.10; system default on macOS may be 3.9)
PYTHON="${HERMES_PYTHON:-$(command -v python3.11 || command -v python3.12 || command -v python3)}"
"$PYTHON" -m venv .venv 2>/dev/null || true
source .venv/bin/activate
pip install -q -r requirements.txt
export PORT="${PORT:-8012}"
exec python server.py
