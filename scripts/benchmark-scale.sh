#!/usr/bin/env bash
# Phase A observation-path benchmark (issue #4). Requires running stack.
set -euo pipefail

RUNTIME="${RUNTIME:-http://localhost:8888}"
SAMPLES="${SAMPLES:-20}"
AGENT_TARGET="${AGENT_TARGET:-5000}"

echo "== GOD scale benchmark (T-5000-01 Phase A observation path) =="
echo "Runtime: ${RUNTIME}"

alive=$(curl -sf "${RUNTIME}/agents?limit=1&alive_only=true" | python3 -c "
import json,sys
d=json.load(sys.stdin)
print(len(d) if isinstance(d,list) else d.get('total', len(d.get('agents',[]))))
" 2>/dev/null || echo "0")

echo "C1 alive agents (target ${AGENT_TARGET}): ${alive}"
if [[ "${alive}" -lt "${AGENT_TARGET}" ]]; then
  echo "WARN: seed with: docker exec god-runtime python -m scripts.seed_bulk_agents --count ${AGENT_TARGET}"
fi

echo "C2 snapshot p95 (${SAMPLES} samples)…"
python3 - <<PY
import json, statistics, time, urllib.request
url = "${RUNTIME}/world/snapshot"
times = []
for _ in range(int("${SAMPLES}")):
    t0 = time.perf_counter()
    with urllib.request.urlopen(url, timeout=60) as r:
        json.load(r)
    times.append((time.perf_counter() - t0) * 1000)
times.sort()
p95 = times[int(len(times) * 0.95)]
print(f"  p50={statistics.median(times):.0f}ms p95={p95:.0f}ms max={max(times):.0f}ms")
print("  PASS" if p95 < 500 else "  FAIL (p95 >= 500ms)")
PY

echo "C4/C5/C6: run observer soak + WS stability manually (doc 78)"
echo "Post [FIELD-DATA] T-5000-01 with runtime logs on PR #1"
