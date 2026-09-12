#!/usr/bin/env bash
# One-time setup for the InfraWatch frontend: installs dependencies and
# creates a working .env.local if one doesn't exist yet.
# Safe to re-run — it skips steps that are already done.
set -e
cd "$(dirname "${BASH_SOURCE[0]}")"

if [ ! -f ".env.local" ]; then
  echo "==> Creating .env.local from .env.example (defaults work with zero editing)..."
  cp .env.example .env.local
fi

echo "==> Installing dependencies (this can take a minute or two the first time)..."
npm install

echo ""
echo "Setup complete. Start the frontend with: ./run.sh"
