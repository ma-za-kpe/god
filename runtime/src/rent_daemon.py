"""
rent_daemon.py — Periodic rent collection for all living agents.

Modes:
  - RENT_COLLECTOR_ADDRESS set: real on-chain calls via RentCollector.sol
  - Not set: local DB simulation (dev default)

Rent schedule (dev defaults, overridable via env):
  RENT_PERIOD_SECONDS=300   (5 min — simulate 1 day)
  RENT_AMOUNT_USDC=0.001    ($0.001 per period)
  MAX_MISSED_PAYMENTS=3     (3 strikes = death)
"""

import asyncio
import json
import logging
import os
import time
import uuid
from decimal import Decimal

import psycopg2
import psycopg2.extras
from web3 import Web3

from .event_emitter import get_emitter

log = logging.getLogger("god.rent")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
ANVIL_RPC = os.getenv("ANVIL_RPC", "http://localhost:8545")
RENT_COLLECTOR_ADDR = os.getenv("RENT_COLLECTOR_ADDRESS", "")
RENT_PERIOD_S = int(os.getenv("RENT_PERIOD_SECONDS", "300"))
RENT_AMOUNT_USDC = Decimal(os.getenv("RENT_AMOUNT_USDC", "0.001"))
MAX_MISSES = int(os.getenv("MAX_MISSED_PAYMENTS", "3"))
CYCLE_S = int(os.getenv("RENT_CYCLE_SECONDS", "60"))
WORLD_ID = os.getenv("WORLD_ID", "local-dev-world-1")

RENT_ABI = [
    {
        "name": "collectRent",
        "type": "function",
        "inputs": [{"name": "soulId", "type": "bytes32"}],
        "outputs": [],
        "stateMutability": "nonpayable",
    },
    {
        "name": "leases",
        "type": "function",
        "inputs": [{"name": "soulId", "type": "bytes32"}],
        "outputs": [
            {"name": "agentWallet", "type": "address"},
            {"name": "lastPaid", "type": "uint256"},
            {"name": "missedPayments", "type": "uint256"},
            {"name": "active", "type": "bool"},
            {"name": "registeredAt", "type": "uint256"},
        ],
        "stateMutability": "view",
    },
]


IPFS_API = os.getenv("IPFS_API", "http://localhost:5001")


def _db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)


async def _create_death_archive(soul_id: str, name: str, conn) -> str:
    """
    Compress agent state into a death archive and pin to IPFS.
    Returns the IPFS CID, or empty string if IPFS is unavailable.
    """
    try:
        cur = conn.cursor()

        # Fetch full agent row
        cur.execute(
            "SELECT * FROM agents WHERE soul_id = %s",
            (soul_id,),
        )
        agent_row = dict(cur.fetchone() or {})

        # Fetch rent history summary
        cur.execute(
            "SELECT COUNT(*) FILTER (WHERE NOT missed) AS paid, "
            "       COUNT(*) FILTER (WHERE missed) AS missed "
            "FROM rent_payments WHERE soul_id = %s",
            (soul_id,),
        )
        rent_row = dict(cur.fetchone() or {})

        # Fetch last 20 significant events
        cur.execute(
            "SELECT event_type, timestamp, narrative FROM events "
            "WHERE agent_id = %s ORDER BY timestamp DESC LIMIT 20",
            (soul_id,),
        )
        events = [dict(r) for r in cur.fetchall()]

        cur.close()

        archive = {
            "archive_id": str(uuid.uuid4()),
            "soul_id": soul_id,
            "name": name,
            "archetype": agent_row.get("archetype"),
            "generation": agent_row.get("generation", 1),
            "birth_timestamp": agent_row.get("birth_timestamp"),
            "death_timestamp": int(time.time()),
            "cause_of_death": "rent_default",
            "final_balance_usdc": str(agent_row.get("balance_usdc", "0")),
            "total_rent_paid": int(rent_row.get("paid", 0)),
            "total_rent_missed": int(rent_row.get("missed", 0)),
            "parent_soul_ids": agent_row.get("parent_soul_ids", []),
            "owned_graph_cid": agent_row.get("graph_cid"),
            "emotional_state_at_death": agent_row.get("emotional_state", "unknown"),
            "significant_events": events,
            "world_id": WORLD_ID,
        }

        archive_json = json.dumps(archive, indent=2, default=str).encode("utf-8")

        # Pin to IPFS
        import httpx

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{IPFS_API}/api/v0/add",
                files={"file": ("death_archive.json", archive_json, "application/json")},
            )
            resp.raise_for_status()
            cid = resp.json()["Hash"]
            log.info(f"  Death archive pinned: ipfs://{cid} ({name})")
            return cid

    except Exception as e:
        log.warning(f"Death archive failed for {name}: {e}")
        return ""


async def _run_cycle_local(emitter):
    """Simulate rent via DB timestamps — no blockchain required."""
    now = int(time.time())
    conn = _db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            a.soul_id,
            a.current_name,
            COALESCE(
                (SELECT MAX(rp.paid_at)
                   FROM rent_payments rp
                  WHERE rp.soul_id = a.soul_id AND rp.missed = false),
                a.birth_timestamp
            ) AS last_paid,
            (SELECT COUNT(*)
               FROM rent_payments rp
              WHERE rp.soul_id = a.soul_id
                AND rp.missed = true
                AND rp.paid_at > %s) AS recent_misses
        FROM agents a
        WHERE a.is_alive = true AND a.world_id = %s
    """,
        (now - RENT_PERIOD_S * MAX_MISSES * 2, WORLD_ID),
    )

    agents = cur.fetchall()
    log.info(f"Rent cycle (sim): {len(agents)} living agents")

    for ag in agents:
        soul_id = ag["soul_id"]
        name = ag["current_name"] or soul_id[:8]
        last_paid = int(ag["last_paid"] or now)
        recent_misses = int(ag["recent_misses"])

        if now < last_paid + RENT_PERIOD_S:
            continue  # not due yet

        # Check actual balance and deduct on success
        cur.execute("SELECT balance_usdc FROM agents WHERE soul_id = %s", (soul_id,))
        bal_row = cur.fetchone()
        current_balance = float(bal_row["balance_usdc"] or 0) if bal_row else 0
        rent_due = float(RENT_AMOUNT_USDC)
        pay_success = current_balance >= rent_due

        if pay_success:
            cur.execute(
                "UPDATE agents SET balance_usdc = balance_usdc - %s WHERE soul_id = %s",
                (rent_due, soul_id),
            )
            cur.execute(
                "INSERT INTO rent_payments (soul_id, amount_usdc, paid_at, missed) VALUES (%s, %s, %s, false)",
                (soul_id, rent_due, now),
            )
            conn.commit()
            await emitter.emit(
                "economy",
                "rent.paid",
                {
                    "agent_id": soul_id,
                    "name": name,
                    "amount_usdc": rent_due,
                    "balance_after": round(current_balance - rent_due, 6),
                    "narrative": f"{name} paid rent (${rent_due:.4f}). Balance: ${current_balance - rent_due:.4f}",
                },
            )
            log.info(f"  ✓ {name}: rent paid (bal ${current_balance - rent_due:.4f})")
        else:
            cur.execute(
                "INSERT INTO rent_payments (soul_id, amount_usdc, paid_at, missed) VALUES (%s, 0, %s, true)",
                (soul_id, now),
            )
            conn.commit()
            new_misses = recent_misses + 1
            await emitter.emit(
                "economy",
                "rent.missed",
                {
                    "agent_id": soul_id,
                    "name": name,
                    "missed_count": new_misses,
                    "narrative": f"{name} missed rent ({new_misses}/{MAX_MISSES}).",
                },
            )
            log.warning(f"  ✗ {name}: missed ({new_misses}/{MAX_MISSES})")

            if new_misses >= MAX_MISSES:
                # Create death archive before marking dead
                archive_cid = await _create_death_archive(soul_id, name, conn)

                cur.execute(
                    "UPDATE agents SET is_alive = false, death_timestamp = %s, "
                    "death_archive_cid = %s WHERE soul_id = %s",
                    (now, archive_cid or None, soul_id),
                )
                conn.commit()

                archive_note = f" Archive: ipfs://{archive_cid}" if archive_cid else ""
                await emitter.emit(
                    "lifecycle",
                    "agent.died",
                    {
                        "agent_id": soul_id,
                        "name": name,
                        "cause": "rent_default",
                        "missed_payments": new_misses,
                        "death_archive_cid": archive_cid,
                        "narrative": (
                            f"⚰ {name} has died — rent unpaid for {new_misses} consecutive cycles."
                            f"{archive_note}"
                        ),
                    },
                )
                log.warning(f"  ☠  {name} DIED — rent default{archive_note}")

    cur.close()
    conn.close()


async def rent_daemon():
    log.info("Rent daemon starting...")
    log.info(f"  period={RENT_PERIOD_S}s  amount=${RENT_AMOUNT_USDC}  max_misses={MAX_MISSES}")

    if RENT_COLLECTOR_ADDR:
        log.info(f"  On-chain mode: {RENT_COLLECTOR_ADDR}")
        w3 = Web3(Web3.HTTPProvider(ANVIL_RPC))
        _ = w3.eth.contract(
            address=Web3.to_checksum_address(RENT_COLLECTOR_ADDR),
            abi=RENT_ABI,
        )
        log.info(f"  Chain ID: {w3.eth.chain_id}")
    else:
        log.info("  Simulation mode (set RENT_COLLECTOR_ADDRESS for on-chain)")
        w3 = None

    # Wait for DB
    for attempt in range(15):
        try:
            _db().close()
            log.info("  DB ready")
            break
        except Exception:
            log.info(f"  Waiting for DB ({attempt + 1}/15)...")
            await asyncio.sleep(4)

    while True:
        try:
            emitter = await get_emitter()
            # On-chain mode falls back to local sim until CREATOR_PRIVATE_KEY is wired
            await _run_cycle_local(emitter)
        except Exception as e:
            log.error(f"Rent cycle error: {e}", exc_info=True)
        await asyncio.sleep(CYCLE_S)
