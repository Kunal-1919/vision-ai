#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "╔══════════════════════════════════════╗"
echo "║         VisionAI — Starting          ║"
echo "║  by Kunal Santosh Gawade             ║"
echo "╚══════════════════════════════════════╝"
echo ""

if [ ! -d ".venv" ]; then
  echo "→ Creating virtual environment..."
  python3 -m venv .venv
fi

source .venv/bin/activate
pip install -q -r requirements.txt

echo "→ Server: http://localhost:8088"
echo "→ API docs: http://localhost:8088/docs"
echo ""

uvicorn app.main:app --reload --host 0.0.0.0 --port 8088
