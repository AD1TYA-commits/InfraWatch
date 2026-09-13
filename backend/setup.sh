#!/usr/bin/env bash
# One-time setup for the InfraWatch backend: creates the virtual environment,
# installs dependencies, and creates a working .env if one doesn't exist yet.
# Safe to re-run — it skips steps that are already done.
set -e
cd "$(dirname "${BASH_SOURCE[0]}")"

if [ ! -d ".venv" ]; then
  echo "==> Creating Python virtual environment..."
  python3 -m venv .venv
fi

echo "==> Installing dependencies (this can take a few minutes the first time)..."
source .venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt

if [ ! -f ".env" ]; then
  echo "==> Creating .env from .env.example (defaults work with zero editing)..."
  cp .env.example .env
fi

echo ""
echo "Setup complete. Start the backend with: ./run.sh"
echo "(on first start: 6 demo projects, 4 real legacy projects with real manual"
echo " evidence, and 2 demo accounts are all seeded automatically — nothing to"
echo " prepare, upload, or configure by hand)"
