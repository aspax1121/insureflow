#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

if [[ ! -x .venv/bin/python ]]; then
  echo "Missing .venv. Create it and install requirements.txt first." >&2
  exit 1
fi

.venv/bin/python -m uvicorn backend.api:app --host 127.0.0.1 --port 8000 &
backend_pid=$!
.venv/bin/python -m streamlit run frontend/app.py &
frontend_pid=$!

cleanup() {
  kill "$backend_pid" "$frontend_pid" 2>/dev/null || true
  wait "$backend_pid" "$frontend_pid" 2>/dev/null || true
}
trap cleanup EXIT

for ((attempt = 0; attempt < 40; attempt++)); do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1 &&
     curl -fsS http://127.0.0.1:8501/ >/dev/null 2>&1; then
    echo "InsureFlow is ready at http://localhost:8501"
    open http://localhost:8501
    wait "$frontend_pid"
    exit
  fi

  if ! kill -0 "$backend_pid" 2>/dev/null || ! kill -0 "$frontend_pid" 2>/dev/null; then
    echo "A server stopped during startup. Check the errors above." >&2
    exit 1
  fi
  sleep 0.5
done

echo "Servers did not become ready. Check the errors above." >&2
exit 1
