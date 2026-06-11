#!/usr/bin/env python3
"""
Sample live agent thoughts and flag grounding violations (issue #8, #53).

Usage:
  python3 scripts/spot-check-grounding.py [--runtime http://localhost:8888] [--sample 20]

Exit 0 if no violations; exit 1 if any pattern match.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "runtime", "src"))

from grounding import looks_like_action_json, validate_grounded_text  # noqa: E402


def fetch(url: str) -> dict | list:
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode())


def _peer_state(agents: list[dict], agent: dict) -> dict:
    peers = []
    for a in agents:
        name = (a.get("current_name") or a.get("name") or "").strip()
        sid = str(a.get("soul_id") or "")
        if name:
            peers.append({"name": name, "current_name": name, "soul_id": sid})
    return {
        "name": agent.get("current_name") or agent.get("soul_id", "?")[:8],
        "archetype": agent.get("archetype", ""),
        "balance_usdc": float(agent.get("balance_usdc") or 0),
        "rent_amount": 0.001,
        "peers": peers,
        "inbox": [],
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Spot-check agent thought grounding")
    p.add_argument("--runtime", default="http://localhost:8888")
    p.add_argument("--sample", type=int, default=20)
    args = p.parse_args()
    base = args.runtime.rstrip("/")

    try:
        agents = fetch(f"{base}/agents?limit={args.sample}&alive_only=true")
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"FAIL: cannot reach runtime at {base}: {e}", file=sys.stderr)
        return 2

    if not isinstance(agents, list):
        agents = agents.get("agents", []) if isinstance(agents, dict) else []

    violations: list[str] = []
    checked = 0
    for a in agents[: args.sample]:
        thought = (a.get("last_thought") or "").strip()
        if not thought:
            continue
        checked += 1
        state = _peer_state(agents, a)
        if looks_like_action_json(thought):
            name = a.get("current_name") or a.get("soul_id", "?")[:8]
            violations.append(f"{name}: action JSON in thought: {thought[:120]}")
            continue
        ok, reason = validate_grounded_text(thought, state)
        if not ok:
            name = a.get("current_name") or a.get("soul_id", "?")[:8]
            violations.append(f"{name}: {reason} in: {thought[:120]}")

    print(f"Checked {checked} agents with thoughts (sample {args.sample})")
    if violations:
        print("VIOLATIONS:")
        for v in violations:
            print(f"  - {v}")
        return 1
    print("OK: no hallucination patterns in sample")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
