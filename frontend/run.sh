#!/usr/bin/env bash
# Starts the InfraWatch frontend on port 3000. Run ./setup.sh first if you haven't yet.
set -e
cd "$(dirname "${BASH_SOURCE[0]}")"

if [ ! -d "node_modules" ]; then
  echo "No node_modules found — run ./setup.sh first."
  exit 1
fi

npm run dev
