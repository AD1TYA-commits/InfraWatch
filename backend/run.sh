#!/usr/bin/env bash
# Starts the InfraWatch backend on port 8000. Run ./setup.sh first if you haven't yet.
# The demo database and 6 sample projects are created automatically on first run.
set -e
cd "$(dirname "${BASH_SOURCE[0]}")"

if [ ! -d ".venv" ]; then
  echo "No .venv found — run ./setup.sh first."
  exit 1
fi

source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
