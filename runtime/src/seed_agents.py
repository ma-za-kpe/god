"""
seed_agents.py — Single-agent factory used by POST /creator/genesis.

For world genesis, call: POST /creator/genesis  (see main.py)
This module provides seed_one_agent() which /creator/genesis calls per archetype.
"""

import asyncio
import logging
import os
import time
import uuid
from decimal import Decimal

import psycopg2
from eth_account import Account

from .owned_graph import create_agent_zero

log = logging.getLogger("god.seed")

SEED_BALANCE_USDC = Decimal(os.getenv("SEED_BALANCE_USDC", "0.10"))
WORLD_ID = os.getenv("WORLD_ID", "local-dev-world-1")
IPFS_API = os.getenv("IPFS_API", "http://localhost:5001")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
AVATAR_GENESIS_ENABLED = os.getenv("AVATAR_GENESIS_ENABLED", "true").lower() in ("1", "true", "yes", "on")


def _persist_agent(agent: dict):
    """Register agent in PostgreSQL so the runtime and observer can see it."""
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO agents
            (soul_id, graph_cid, wallet_address, current_name,
             birth_timestamp, is_alive, world_id, archetype, balance_usdc)
        VALUES (%s, %s, %s, %s, %s, true, %s, %s, %s)
        ON CONFLICT (soul_id) DO NOTHING
        """,
        (
            agent["soul_id"],
            agent["graph_cid"],
            agent["wallet_address"],
            agent["name"],
            int(time.time()),
            WORLD_ID,
            agent["archetype"],
            float(agent.get("seed_balance", SEED_BALANCE_USDC)),
        ),
    )
    conn.commit()
    cur.close()
    conn.close()


async def seed_one_agent(
    archetype: str,
    seed_balance: Decimal = SEED_BALANCE_USDC,
    is_elder: bool = False,
) -> dict:
    """Create, pin, and register one seed agent. Returns registration info."""

    # Generate a fresh wallet for this agent
    acct = Account.create()
    wallet_address = acct.address
    private_key = acct.key.hex()
    soul_id = str(uuid.uuid4())

    # Create the genesis graph
    graph = create_agent_zero(
        soul_id=soul_id,
        owner_key=acct._key_obj.public_key.to_hex(),
        wallet_address=wallet_address,
        world_id=WORLD_ID,
        archetype=archetype,
        seed_balance=seed_balance,
    )

    if is_elder:
        graph.identity.current_name = f"Elder-{graph.identity.current_name}"
        graph.identity.biography = (
            "One of the Elder Guardians. Born with the world. Will become fully mortal on Day 31."
        )

    # Pin to IPFS
    try:
        cid = graph.pin_to_ipfs(IPFS_API)
        log.info(f"  Pinned agent {soul_id[:8]}... → {cid}")
    except Exception as e:
        log.warning(f"  IPFS unavailable ({e}) — continuing without pin")
        cid = f"local:{graph.content_hash()[:16]}"
        graph.graph_id = cid

    from .wallet_store import store_wallet

    store_wallet(soul_id, wallet_address, private_key)

    result = {
        "soul_id": soul_id,
        "graph_cid": cid,
        "wallet_address": wallet_address,
        "private_key": private_key,  # NEVER log this in production
        "archetype": archetype,
        "name": graph.identity.current_name,
        "is_elder": is_elder,
        "seed_balance": seed_balance,
    }

    try:
        _persist_agent(result)
    except Exception as e:
        log.warning(f"  DB persist failed for {soul_id[:8]}: {e}")

    if AVATAR_GENESIS_ENABLED:
        try:
            from .avatar import GenesisPipeline

            pipeline = GenesisPipeline()
            asyncio.create_task(pipeline.execute(soul_id, archetype, graph))
        except Exception as exc:
            log.warning("  Avatar genesis schedule failed for %s: %s", soul_id[:8], exc)

    try:
        from .chain_rent import fund_agent_wallet, is_configured, register_agent_on_chain

        if is_configured():
            register_agent_on_chain(soul_id, wallet_address)
            fund_agent_wallet(wallet_address, seed_balance)
    except Exception as e:
        log.warning(f"  On-chain genesis register failed for {soul_id[:8]}: {e}")

    return result
