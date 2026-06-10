#!/usr/bin/env python3
"""
seed-bulk-agents.py — Fast population seed for scale testing (local dev only).

Inserts N alive agents directly into PostgreSQL without IPFS pin or LLM.
Use for observer/runtime lag testing at 5000+ agents.

Usage:
  python scripts/seed-bulk-agents.py --count 5000
  python scripts/seed-bulk-agents.py --count 5000 --clear
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import uuid

# Allow import from runtime when run from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "runtime"))

import psycopg2
from eth_account import Account

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
WORLD_ID = os.getenv("WORLD_ID", "local-dev-world-1")
ARCHETYPES = [
    "trader", "hoarder", "explorer", "parasite",
    "cooperator", "defender", "philosopher", "builder",
]


def main():
    parser = argparse.ArgumentParser(description="Bulk seed agents for scale testing")
    parser.add_argument("--count", type=int, default=5000)
    parser.add_argument("--clear", action="store_true", help="Delete all agents first")
    parser.add_argument("--balance", type=float, default=0.5, help="USDC balance per agent")
    args = parser.parse_args()

    if args.count < 1 or args.count > 50000:
        print("count must be 1–50000")
        sys.exit(1)

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    if args.clear:
        print("Clearing existing agents and related rows...")
        for table in (
            "agent_messages", "reputation", "sleep_states", "dreams",
            "agent_action_log", "agent_scratch", "agent_scheduled_jobs",
            "agent_registered_tools", "agent_graph_mutations", "agent_capability_grants",
            "rent_payments", "events", "agent_status",
        ):
            try:
                cur.execute(f"DELETE FROM {table} WHERE world_id = %s", (WORLD_ID,))
            except Exception:
                conn.rollback()
        cur.execute("DELETE FROM agents WHERE world_id = %s", (WORLD_ID,))
        conn.commit()
        print("Cleared.")

    cur.execute("SELECT COUNT(*) FROM agents WHERE world_id = %s AND is_alive = true", (WORLD_ID,))
    existing = cur.fetchone()[0]
    print(f"Existing living agents: {existing}")

    now = int(time.time())
    batch_size = 500
    created = 0

    try:
        from src.wallet_store import store_wallet
    except ImportError:
        store_wallet = None

    for start in range(0, args.count, batch_size):
        rows = []
        wallets = []
        n = min(batch_size, args.count - start)
        for i in range(n):
            soul_id = str(uuid.uuid4())
            acct = Account.create()
            arch = ARCHETYPES[(start + i) % len(ARCHETYPES)]
            name = f"Load-{arch[:4].title()}-{soul_id[:4].upper()}"
            graph_cid = f"local:bulk:{soul_id[:16]}"
            rows.append((
                soul_id, graph_cid, acct.address, name, now, True, WORLD_ID,
                arch, args.balance, 1,
            ))
            wallets.append((soul_id, acct.address, acct.key.hex()))

        cur.executemany(
            """
            INSERT INTO agents
                (soul_id, graph_cid, wallet_address, current_name, birth_timestamp,
                 is_alive, world_id, archetype, balance_usdc, generation)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (soul_id) DO NOTHING
            """,
            rows,
        )
        conn.commit()
        if store_wallet:
            for soul_id, addr, pk in wallets:
                store_wallet(soul_id, addr, pk)
        created += n
        print(f"  inserted {created}/{args.count}...")

    cur.execute("SELECT COUNT(*) FROM agents WHERE world_id = %s AND is_alive = true", (WORLD_ID,))
    total = cur.fetchone()[0]
    cur.close()
    conn.close()
    print(f"Done. Living agents: {total}")


if __name__ == "__main__":
    main()
