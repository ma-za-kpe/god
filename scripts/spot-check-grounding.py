#!/usr/bin/env python3
"""
Sample live agent thoughts and flag grounding violations (issue #8).

Usage:
  python3 scripts/spot-check-grounding.py [--runtime http://localhost:8888] [--sample 20]

Exit 0 if no violations; exit 1 if any pattern match.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request

_FORBIDDEN = re.compile(
    r"\b(processing\s+power|tunnel\s+system|security\s+vulnerabilit|"
    r"data\s+center|symbiotic\s+relationship|idle\s+speculation)\b",
    re.IGNORECASE,
)


def fetch(url: str) -> dict | list:
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode())


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
        m = _FORBIDDEN.search(thought)
        if m:
            name = a.get("current_name") or a.get("soul_id", "?")[:8]
            violations.append(f"{name}: invented '{m.group()}' in: {thought[:120]}")

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
