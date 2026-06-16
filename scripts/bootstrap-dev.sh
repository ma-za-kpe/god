#!/usr/bin/env bash
# bootstrap-dev.sh — install local dev hooks (pre-commit). CI enforces the same checks.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python3 -m pip install --upgrade pip
python3 -m pip install -r requirements-dev.txt
python3 -m pre_commit install
python3 -m pre_commit install --hook-type commit-msg 2>/dev/null || true

echo "Pre-commit hooks installed. Run: python3 -m pre_commit run --all-files"
echo "That hook chain now includes the local validation pipeline."
