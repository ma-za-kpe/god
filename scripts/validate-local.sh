#!/usr/bin/env bash
# validate-local.sh - local validation pipeline required before commit.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if command -v cygpath >/dev/null 2>&1; then
  ROOT="$(cygpath -aw "$ROOT")"
fi

POWERSHELL_BIN="${POWERSHELL_BIN:-powershell.exe}"

"$POWERSHELL_BIN" -NoProfile -Command "
\$ErrorActionPreference = 'Stop'
\$root = '$ROOT'
Write-Host '[validate] compose config'
docker compose --project-directory \$root config --quiet
Write-Host '[validate] runtime tests'
docker exec god-runtime sh -lc 'rm -rf /tmp/god-validation && mkdir -p /tmp/god-validation/suite/runtime-tests'
docker cp \"\$root/runtime/tests/.\" god-runtime:/tmp/god-validation/suite/runtime-tests
docker exec god-runtime rm -f /tmp/god-validation/suite/runtime-tests/banter/__init__.py
try {
  docker exec -e PYTHONPATH=/app/src -e VOICE_SYNTHESIS_ENABLED=false god-runtime python -m pytest /tmp/god-validation/suite/runtime-tests
} finally {
  docker exec god-runtime rm -rf /tmp/god-validation | Out-Null
}
"
