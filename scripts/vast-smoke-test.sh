#!/usr/bin/env bash
# Vast host smoke test for the native GOD stack.
# Usage:
#   bash scripts/vast-smoke-test.sh
#
# Verifies the live host contract directly instead of the older docker-compose
# assumptions. Fails fast if the running stack is stale.

set -euo pipefail

HOST="${VAST_HOST:-ssh7.vast.ai}"
PORT="${VAST_SSH_PORT:-10784}"
SSH_TARGET="${VAST_SSH_USER:-root}@${HOST}"

ssh_host() {
  ssh -p "$PORT" "$SSH_TARGET" "$@"
}

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

echo "Checking runtime /ready..."
ssh_host 'curl -sf http://localhost:8888/ready | python3 -m json.tool >/dev/null' \
  || fail "runtime /ready is not healthy"

echo "Checking creator auth is locked..."
if ssh_host 'curl -sf -X POST http://localhost:8888/creator/genesis -H "Content-Type: application/json" -d "{\"confirm\": true}"'; then
  fail "creator/genesis succeeded without X-Creator-Token"
fi

echo "Checking nginx bindings..."
ssh_host 'ss -ltnp | grep -E "127\.0\.0\.1:10515|127\.0\.0\.1:10516|0\.0\.0\.0:10517" >/dev/null' \
  || fail "nginx bindings are not pinned as expected"

echo "Checking observer static server..."
ssh_host 'curl -sf http://localhost:3000/stage >/dev/null' \
  || fail "observer static server is not responding"
ssh_host 'curl -sf http://localhost:10517/stage >/dev/null' \
  || fail "public observer proxy is not responding"

echo "Checking startup report..."
ssh_host 'test -s /var/log/god/startup-report.json' \
  || fail "startup report missing"

echo "Smoke test passed."
