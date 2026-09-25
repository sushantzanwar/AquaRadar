#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

ensure_apt() {
  local missing=0
  for pkg in python3.12-venv libgdal-dev gdal-bin libgeos-dev libproj-dev; do
    if ! dpkg -s "$pkg" &>/dev/null; then
      missing=1
      break
    fi
  done
  if [[ "$missing" == 1 ]]; then
    sudo apt-get update -qq
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
      python3.12-venv libgdal-dev gdal-bin libgeos-dev libproj-dev
  fi
}

ensure_apt

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

# shellcheck source=/dev/null
source .venv/bin/activate

pip install -U pip setuptools wheel -q
pip install -e ".[geo,indicators,rag]" -q
pip install pytest -q

if [[ ! -f .env ]]; then
  cp .env.example .env
fi

python scripts/seed_demo.py

cd frontend
npm ci --silent
