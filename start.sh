#!/usr/bin/env bash
# One-command launcher for QUORUM (API + UI). Ctrl-C stops both.
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# --- Backend ---
if [ ! -d ".venv" ]; then
  echo "→ Creating Python venv & installing backend deps…"
  python3 -m venv .venv
  ./.venv/bin/pip install -q --upgrade pip
  ./.venv/bin/pip install -q -r backend/requirements.txt
fi

echo "→ Starting API on http://127.0.0.1:8077"
( cd backend && PYTHONPATH=. ../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8077 --log-level warning ) &
API_PID=$!

# --- Frontend ---
if [ ! -d "frontend/node_modules" ]; then
  echo "→ Installing frontend deps…"
  ( cd frontend && npm install --silent )
fi

echo "→ Starting Committee Room on http://localhost:3000"
( cd frontend && npm run dev ) &
UI_PID=$!

trap "echo; echo 'Stopping…'; kill $API_PID $UI_PID 2>/dev/null; exit 0" INT TERM
echo "──────────────────────────────────────────────"
echo "  QUORUM is up:"
echo "    UI   →  http://localhost:3000"
echo "    API  →  http://127.0.0.1:8077/api/health"
echo "  Press Ctrl-C to stop."
echo "──────────────────────────────────────────────"
wait
