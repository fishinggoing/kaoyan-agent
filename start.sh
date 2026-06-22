#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"

echo "========================================"
echo "  GradSchool Advisor - 考研智能决策系统"
echo "========================================"
echo ""

echo "[1/3] Starting backend server..."
cd "$DIR/backend"
if [ -f "$DIR/.venv/Scripts/python.exe" ]; then
  "$DIR/.venv/Scripts/python.exe" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
else
  "$DIR/.venv/bin/python" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
fi
BACKEND_PID=$!

echo "[2/3] Waiting for backend..."
sleep 3

echo "[3/3] Starting frontend dev server..."
cd "$DIR/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "Backend:  http://localhost:8000"
echo "Frontend: http://localhost:5173"
echo "API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop all servers."

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM
wait
