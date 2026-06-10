#!/usr/bin/env bash
# security-audit.sh — local secret + static security scan (run before push).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "== GOD security audit =="

FAIL=0

echo "-- pre-commit (includes detect-private-key) --"
if python3 -m pre_commit run detect-private-key --all-files; then
  echo "OK: detect-private-key"
else
  echo "FAIL: private key pattern detected"
  FAIL=1
fi

echo "-- bandit (Python runtime) --"
if python3 -m bandit -r runtime/src -ll -q 2>/dev/null; then
  echo "OK: bandit"
else
  BANDIT_EXIT=$?
  if [[ "$BANDIT_EXIT" -eq 1 ]]; then
    echo "FAIL: bandit found issues"
    FAIL=1
  else
    echo "SKIP: bandit not installed (pip install bandit)"
  fi
fi

echo "-- gitleaks (if installed) --"
if command -v gitleaks >/dev/null 2>&1; then
  if gitleaks detect --source . --config .gitleaks.toml --verbose; then
    echo "OK: gitleaks"
  else
    echo "FAIL: gitleaks found leaks"
    FAIL=1
  fi
else
  echo "SKIP: gitleaks not installed (brew install gitleaks)"
fi

echo "-- tracked secret paths --"
BAD=$(git ls-files | grep -E '\.env\.local$|swarm\.key$|agent_wallets\.json$|\.pem$' || true)
if [[ -n "$BAD" ]]; then
  echo "FAIL: secret files tracked by git:"
  echo "$BAD"
  FAIL=1
else
  echo "OK: no tracked secret paths"
fi

if [[ "$FAIL" -ne 0 ]]; then
  echo "== AUDIT FAILED =="
  exit 1
fi

echo "== AUDIT PASSED =="
