#!/usr/bin/env bash
# validate-local.sh - local validation pipeline required before commit.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if command -v cygpath >/dev/null 2>&1; then
  ROOT="$(cygpath -aw "$ROOT")"
fi

if [[ -z "${POWERSHELL_BIN:-}" ]]; then
  if command -v pwsh >/dev/null 2>&1; then
    POWERSHELL_BIN="pwsh"
  elif command -v powershell.exe >/dev/null 2>&1; then
    POWERSHELL_BIN="powershell.exe"
  else
    echo "[validate] ERROR: neither pwsh nor powershell.exe is available" >&2
    exit 127
  fi
fi

"$POWERSHELL_BIN" -NoProfile -Command "
\$ErrorActionPreference = 'Stop'
\$root = '$ROOT'
function Invoke-Checked([scriptblock]\$Command, [string]\$Name) {
  & \$Command
  if (\$LASTEXITCODE -ne 0) {
    throw \"\$Name failed with exit code \$LASTEXITCODE\"
  }
}
Write-Host '[validate] compose config'
Invoke-Checked { docker compose --project-directory \$root config --quiet } 'compose config'
Write-Host '[validate] runtime tests'
\$testStatus = 0
Invoke-Checked { docker exec god-runtime sh -lc 'rm -rf /tmp/god-validation && mkdir -p /tmp/god-validation/suite/src /tmp/god-validation/suite/runtime-tests /tmp/god-validation/observer/src' } 'prepare runtime test dir'
Invoke-Checked { docker cp \"\$root/runtime/src/.\" god-runtime:/tmp/god-validation/suite/src } 'copy runtime src'
Invoke-Checked { docker cp \"\$root/runtime/workflows\" god-runtime:/tmp/god-validation/suite/workflows } 'copy runtime workflows'
Invoke-Checked { docker cp \"\$root/runtime/seed_utterances\" god-runtime:/tmp/god-validation/suite/seed_utterances } 'copy seed utterances'
Invoke-Checked { docker cp \"\$root/runtime/tests/.\" god-runtime:/tmp/god-validation/suite/runtime-tests } 'copy runtime tests'
Invoke-Checked { docker cp \"\$root/scripts\" god-runtime:/tmp/god-validation/scripts } 'copy scripts'
Invoke-Checked { docker cp \"\$root/docker-compose.vast.yml\" god-runtime:/tmp/god-validation/docker-compose.vast.yml } 'copy vast compose override'
Invoke-Checked { docker cp \"\$root/observer/stage.html\" god-runtime:/tmp/god-validation/observer/stage.html } 'copy observer stage'
Invoke-Checked { docker cp \"\$root/observer/src/.\" god-runtime:/tmp/god-validation/observer/src } 'copy observer src'
try {
  docker exec -e PYTHONPATH=/tmp/god-validation/suite/src -e VOICE_SYNTHESIS_ENABLED=false god-runtime python -m pytest /tmp/god-validation/suite/runtime-tests
  \$testStatus = \$LASTEXITCODE
} finally {
  docker exec god-runtime rm -rf /tmp/god-validation | Out-Null
}
if (\$testStatus -ne 0) {
  throw \"runtime tests failed with exit code \$testStatus\"
}
"
