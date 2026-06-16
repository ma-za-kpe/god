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
docker exec god-runtime sh -lc 'rm -rf /tmp/god-runtime-tests && mkdir -p /tmp/god-runtime-tests'
docker cp \"\$root/runtime/tests/.\" god-runtime:/tmp/god-runtime-tests
try {
  docker exec -e PYTHONPATH=/app/src god-runtime python -m pytest /tmp/god-runtime-tests
} finally {
  docker exec god-runtime rm -rf /tmp/god-runtime-tests | Out-Null
}
"
