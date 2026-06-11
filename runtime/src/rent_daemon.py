"""
rent_daemon.py — Periodic rent collection for all living agents.

Modes:
  - RENT_COLLECTOR_ADDRESS + CREATOR_PRIVATE_KEY: on-chain via RentCollector.sol
  - Otherwise: local DB simulation (dev default)

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
from .ipfs_client import pin_json

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
    {
        "name": "rentPeriod",
        "type": "function",
        "inputs": [],
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
    },
]


def _db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)


def _throttle_level(misses: int) -> str:
    if misses >= MAX_MISSES:
        return "blocked"
    if misses == 2:
        return "severe"
    if misses == 1:
        return "throttled"
    return "none"


async def _emit_throttle(emitter, soul_id: str, name: str, misses: int):
    level = _throttle_level(misses)
    if level == "none":
        return
    await emitter.emit(
        "economy",
        "rent.throttled",
        {
            "agent_id": soul_id,
            "name": name,
            "missed_count": misses,
            "throttle_level": level,
            "compute_capacity": {"throttled": 0.5, "severe": 0.1, "blocked": 0.0}.get(level, 1.0),
            "narrative": f"{name} rent throttle: {level} ({misses}/{MAX_MISSES} misses).",
        },
    )


def _fetch_death_archive_data(soul_id: str, conn) -> dict:
    cur = conn.cursor()

    cur.execute("SELECT * FROM agents WHERE soul_id = %s", (soul_id,))
    agent_row = dict(cur.fetchone() or {})

    cur.execute(
        "SELECT amount_usdc, paid_at, missed FROM rent_payments "
        "WHERE soul_id = %s ORDER BY paid_at DESC LIMIT 50",
        (soul_id,),
    )
    rent_history = [dict(r) for r in cur.fetchall()]

    cur.execute(
        "SELECT COUNT(*) FILTER (WHERE NOT missed) AS paid, "
        "       COUNT(*) FILTER (WHERE missed) AS missed "
        "FROM rent_payments WHERE soul_id = %s",
        (soul_id,),
    )
    rent_row = dict(cur.fetchone() or {})

    cur.execute(
        "SELECT episode_id, event_type, timestamp, ipfs_cid, emotional_imprint "
        "FROM episodes WHERE soul_id = %s ORDER BY timestamp DESC LIMIT 30",
        (soul_id,),
    )
    episodes = [dict(r) for r in cur.fetchall()]

    cur.execute(
        "SELECT message_id, sender_id, recipient_id, subject, body, sent_at "
        "FROM agent_messages WHERE sender_id = %s OR recipient_id = %s "
        "ORDER BY sent_at DESC LIMIT 30",
        (soul_id, soul_id),
    )
    messages = [dict(r) for r in cur.fetchall()]

    cur.execute(
        "SELECT event_type, timestamp, narrative FROM events "
        "WHERE agent_id = %s ORDER BY timestamp DESC LIMIT 20",
        (soul_id,),
    )
    events = [dict(r) for r in cur.fetchall()]

    cur.close()
    return {
        "agent_row": agent_row,
        "rent_history": rent_history,
        "rent_row": rent_row,
        "episodes": episodes,
        "messages": messages,
        "events": events,
    }


async def _create_death_archive(soul_id: str, name: str, conn) -> str:
    """
    Compress agent state into a death archive and pin to IPFS cluster.
    Returns the IPFS CID, or empty string if pinning failed.
    """
    try:
        data = _fetch_death_archive_data(soul_id, conn)
        agent_row = data["agent_row"]
        rent_row = data["rent_row"]

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
            "episode_cids": [e.get("ipfs_cid") for e in data["episodes"] if e.get("ipfs_cid")],
            "episodes": data["episodes"],
            "message_summary": data["messages"],
            "rent_history": data["rent_history"],
            "significant_events": data["events"],
            "world_id": WORLD_ID,
        }

        archive_json = json.dumps(archive, indent=2, default=str).encode("utf-8")
        result = await pin_json(archive_json)
        if result.ok:
            log.info(
                f"  Death archive pinned: ipfs://{result.cid} ({name}, {result.pinned_nodes} nodes)"
            )
            return result.cid

        log.warning(f"Death archive pin failed for {name}: {result.errors}")
        return ""

    except Exception as e:
        log.warning(f"Death archive failed for {name}: {e}")
        return ""


async def _finalize_death(
    emitter,
    conn,
    cur,
    soul_id: str,
    name: str,
    new_misses: int,
    now: int,
    *,
    on_chain_tx: str | None = None,
):
    """Create archive, mark dead, emit lifecycle event. Blocks death if archive fails."""
    archive_cid = await _create_death_archive(soul_id, name, conn)
    if not archive_cid:
        await emitter.emit(
            "lifecycle",
            "death_archive.failed",
            {
                "agent_id": soul_id,
                "name": name,
                "missed_payments": new_misses,
                "narrative": (
                    f"⚠ {name} reached death threshold but archive pinning failed — "
                    "death deferred until IPFS cluster accepts the archive."
                ),
            },
        )
        log.error(f"  ☠  {name}: death deferred — archive pin failed")
        return False

    cur.execute(
        "UPDATE agents SET is_alive = false, death_timestamp = %s, "
        "death_archive_cid = %s WHERE soul_id = %s",
        (now, archive_cid, soul_id),
    )
    conn.commit()

    archive_note = f" Archive: ipfs://{archive_cid}"
    payload = {
        "agent_id": soul_id,
        "name": name,
        "cause": "rent_default",
        "missed_payments": new_misses,
        "death_archive_cid": archive_cid,
        "narrative": (
            f"⚰ {name} has died — rent unpaid for {new_misses} consecutive cycles.{archive_note}"
        ),
    }
    if on_chain_tx:
        payload["on_chain_tx"] = on_chain_tx

    await emitter.emit("lifecycle", "agent.died", payload)
    log.warning(f"  ☠  {name} DIED — rent default{archive_note}")
    return True


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
            continue

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
            await _emit_throttle(emitter, soul_id, name, new_misses)
            log.warning(f"  ✗ {name}: missed ({new_misses}/{MAX_MISSES})")

            if new_misses >= MAX_MISSES:
                await _finalize_death(emitter, conn, cur, soul_id, name, new_misses, now)

    cur.close()
    conn.close()


async def _run_cycle_onchain(emitter):
    """Collect rent on-chain and mirror outcomes to PostgreSQL."""
    from .chain_rent import (
        collect_rent_on_chain,
        ensure_rent_allowance,
        fund_agent_wallet,
        is_configured,
        register_agent_on_chain,
    )
    from .wallet_store import get_agent_private_key

    if not is_configured():
        log.warning(
            "On-chain rent configured address but missing CREATOR_PRIVATE_KEY/USDC — sim fallback"
        )
        await _run_cycle_local(emitter)
        return

    now = int(time.time())
    conn = _db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT soul_id, current_name, wallet_address, balance_usdc, birth_timestamp
        FROM agents WHERE is_alive = true AND world_id = %s
        """,
        (WORLD_ID,),
    )
    agents = cur.fetchall()
    log.info(f"Rent cycle (on-chain): {len(agents)} living agents")

    w3 = Web3(Web3.HTTPProvider(ANVIL_RPC))
    rent = w3.eth.contract(
        address=Web3.to_checksum_address(RENT_COLLECTOR_ADDR),
        abi=RENT_ABI,
    )

    for ag in agents:
        soul_id = ag["soul_id"]
        name = ag["current_name"] or soul_id[:8]
        wallet = ag["wallet_address"]
        balance = Decimal(str(ag["balance_usdc"] or 0))

        try:
            register_agent_on_chain(soul_id, wallet)
            fund_agent_wallet(wallet, balance)
            private_key = get_agent_private_key(soul_id)
            if private_key:
                ensure_rent_allowance(wallet, private_key, RENT_AMOUNT_USDC * 10)

            soul_bytes = Web3.keccak(text=soul_id)
            lease = rent.functions.leases(soul_bytes).call()
            if not lease[3]:
                continue

            rent_period = int(rent.functions.rentPeriod().call())
            last_paid = int(lease[1])
            if now < last_paid + rent_period:
                continue

            outcome = collect_rent_on_chain(soul_id)
            if not outcome.get("ok"):
                log.debug(f"  {name}: on-chain skip — {outcome.get('error')}")
                continue

            tx_hash = outcome.get("tx_hash")
            if outcome.get("paid"):
                amount = float(outcome.get("amount_usdc") or RENT_AMOUNT_USDC)
                chain_bal = float(outcome.get("wallet_balance") or 0)
                cur.execute(
                    "UPDATE agents SET balance_usdc = %s WHERE soul_id = %s",
                    (chain_bal, soul_id),
                )
                cur.execute(
                    "INSERT INTO rent_payments (soul_id, amount_usdc, paid_at, missed, on_chain_tx) "
                    "VALUES (%s, %s, %s, false, %s)",
                    (soul_id, amount, now, tx_hash),
                )
                conn.commit()
                await emitter.emit(
                    "economy",
                    "rent.paid",
                    {
                        "agent_id": soul_id,
                        "name": name,
                        "amount_usdc": amount,
                        "balance_after": chain_bal,
                        "on_chain_tx": tx_hash,
                        "narrative": f"{name} paid rent on-chain (${amount:.4f}). Balance: ${chain_bal:.4f}",
                    },
                )
                log.info(f"  ✓ {name}: on-chain rent paid tx={tx_hash[:16]}…")
            else:
                misses = int(outcome.get("missed_payments") or 0)
                cur.execute(
                    "INSERT INTO rent_payments (soul_id, amount_usdc, paid_at, missed, on_chain_tx) "
                    "VALUES (%s, 0, %s, true, %s)",
                    (soul_id, now, tx_hash),
                )
                chain_bal = float(outcome.get("wallet_balance") or 0)
                cur.execute(
                    "UPDATE agents SET balance_usdc = %s WHERE soul_id = %s",
                    (chain_bal, soul_id),
                )
                conn.commit()
                await emitter.emit(
                    "economy",
                    "rent.missed",
                    {
                        "agent_id": soul_id,
                        "name": name,
                        "missed_count": misses,
                        "on_chain_tx": tx_hash,
                        "narrative": f"{name} missed rent on-chain ({misses}/{MAX_MISSES}).",
                    },
                )
                await _emit_throttle(emitter, soul_id, name, misses)
                log.warning(f"  ✗ {name}: on-chain missed ({misses}/{MAX_MISSES})")

                if outcome.get("deleted") or misses >= MAX_MISSES:
                    await _finalize_death(
                        emitter, conn, cur, soul_id, name, misses, now, on_chain_tx=tx_hash
                    )

        except Exception as e:
            log.error(f"  {name}: on-chain rent error: {e}", exc_info=True)

    cur.close()
    conn.close()


async def rent_daemon():
    log.info("Rent daemon starting...")
    log.info(f"  period={RENT_PERIOD_S}s  amount=${RENT_AMOUNT_USDC}  max_misses={MAX_MISSES}")

    from .chain_rent import is_configured

    on_chain = is_configured()
    if RENT_COLLECTOR_ADDR:
        log.info(f"  RentCollector: {RENT_COLLECTOR_ADDR}")
        if on_chain:
            log.info("  On-chain mode active")
        else:
            log.info(
                "  On-chain address set but CREATOR_PRIVATE_KEY/USDC missing — simulation mode"
            )
    else:
        log.info("  Simulation mode (set RENT_COLLECTOR_ADDRESS for on-chain)")

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
            if on_chain:
                await _run_cycle_onchain(emitter)
            else:
                await _run_cycle_local(emitter)
        except Exception as e:
            log.error(f"Rent cycle error: {e}", exc_info=True)
        await asyncio.sleep(CYCLE_S)
