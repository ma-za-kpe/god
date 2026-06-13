#!/usr/bin/env python3
"""
Smoke test: two agents — seller lists world_stats, buyer invokes via x402 402→200.

Usage (runtime must be up on localhost:8888):
  python3 scripts/smoke-x402-service.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

RUNTIME = os.getenv("RUNTIME_BASE_URL", "http://localhost:8888")


def _get(path: str) -> dict:
    req = urllib.request.Request(f"{RUNTIME}{path}")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def _post(path: str, body: dict) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{RUNTIME}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def main() -> int:
    print("x402 smoke: listing services…")
    services = _get("/services")
    active = services.get("services") or []
    if not active:
        print("FAIL: no service listings — run genesis first")
        return 1

    listing = active[0]
    seller_id = listing["agent_soul_id"]
    name = listing["name"]
    endpoint = listing.get("endpoint_path") or f"/services/{seller_id}/{name}"
    resource = f"{RUNTIME}{endpoint}"

    agents = _get("/agents").get("agents") or []
    buyer = next((a for a in agents if a["soul_id"] != seller_id and a.get("is_alive")), None)
    if not buyer:
        print("FAIL: need at least two living agents")
        return 1

    wallet = buyer.get("wallet_address") or "0xmock"
    bal_before = float(buyer.get("balance_usdc") or 0)

    print(f"  seller={seller_id[:8]} service={name}")
    print(f"  buyer={buyer['soul_id'][:8]} wallet={wallet[:10]}…")

    req1 = urllib.request.Request(resource)
    try:
        urllib.request.urlopen(req1, timeout=15)
        print("FAIL: expected 402 on first call")
        return 1
    except urllib.error.HTTPError as e:
        if e.code != 402:
            print(f"FAIL: expected 402, got {e.code}")
            return 1
        print("  ✓ 402 payment required")

    req2 = urllib.request.Request(resource, headers={"X-Payment-Authorization": wallet})
    with urllib.request.urlopen(req2, timeout=15) as resp:
        body = json.loads(resp.read())
    if resp.status != 200:
        print(f"FAIL: paid call returned {resp.status}")
        return 1
    print(f"  ✓ 200 service response keys={list(body.keys())[:5]}")

    agents_after = _get("/agents").get("agents") or []
    seller_after = next(a for a in agents_after if a["soul_id"] == seller_id)
    seller_bal = float(seller_after.get("balance_usdc") or 0)
    print(f"  seller balance after call: ${seller_bal:.4f}")
    print("PASS: x402 402→200 flow completed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
