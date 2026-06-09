"""
seed_agents.py — Bootstrap the world with the initial agent population.

Usage:
    python -m src.seed_agents --count 20
    python -m src.seed_agents --count 200 --archetypes all
    python -m src.seed_agents --count 50 --archetypes trader,explorer,defender

See docs/13-bootstrapping-the-economy.md for seeding strategy.
"""
import argparse
import asyncio
import json
import logging
import os
import uuid
from decimal import Decimal
from typing import Optional

from eth_account import Account

from .owned_graph import OwnedGraph, ARCHETYPES, create_agent_zero

log = logging.getLogger("god.seed")

SEED_BALANCE_USDC = Decimal(os.getenv("SEED_BALANCE_USDC", "0.10"))
WORLD_ID = os.getenv("WORLD_ID", "local-dev-world-1")
IPFS_API = os.getenv("IPFS_API", "http://localhost:5001")


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
            "One of the Elder Guardians. Born with the world. "
            "Will become fully mortal on Day 31."
        )

    # Pin to IPFS
    try:
        cid = graph.pin_to_ipfs(IPFS_API)
        log.info(f"  Pinned agent {soul_id[:8]}... → {cid}")
    except Exception as e:
        log.warning(f"  IPFS unavailable ({e}) — continuing without pin")
        cid = f"local:{graph.content_hash()[:16]}"
        graph.graph_id = cid

    return {
        "soul_id": soul_id,
        "graph_cid": cid,
        "wallet_address": wallet_address,
        "private_key": private_key,    # NEVER log this in production
        "archetype": archetype,
        "name": graph.identity.current_name,
        "is_elder": is_elder,
    }


async def seed_population(
    count: int,
    archetypes: Optional[list[str]] = None,
    elder_count: int = 5,
) -> list[dict]:
    """Seed the initial agent population with diverse archetypes."""

    if archetypes is None or archetypes == ["all"]:
        archetypes = ARCHETYPES

    agents = []
    log.info(f"Seeding {count} agents across archetypes: {archetypes}")
    log.info(f"Elder guardians: {elder_count}")
    log.info("")

    # Distribute archetypes evenly
    for i in range(count):
        archetype = archetypes[i % len(archetypes)]
        is_elder = i < elder_count
        agent = await seed_one_agent(archetype, is_elder=is_elder)
        agents.append(agent)
        log.info(
            f"  [{i+1:3d}/{count}] "
            f"{'ELDER ' if is_elder else '      '}"
            f"{archetype:12s} | "
            f"{agent['name']:20s} | "
            f"{agent['soul_id'][:8]}..."
        )

    return agents


def save_agent_registry(agents: list[dict], output_path: str = "agents-registry.json"):
    """Save agent info to a local registry file. NEVER commit private keys."""
    # Strip private keys from the public registry
    public_agents = [
        {k: v for k, v in a.items() if k != "private_key"}
        for a in agents
    ]
    with open(output_path, "w") as f:
        json.dump({"world_id": WORLD_ID, "agents": public_agents}, f, indent=2)
    log.info(f"\nPublic registry saved to {output_path}")

    # Save private keys separately (gitignored)
    keys_path = output_path.replace(".json", "-PRIVATE-KEYS.json")
    with open(keys_path, "w") as f:
        json.dump(
            [{"soul_id": a["soul_id"], "private_key": a["private_key"]} for a in agents],
            f, indent=2
        )
    log.warning(f"Private keys saved to {keys_path} — NEVER commit this file")


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )

    parser = argparse.ArgumentParser(description="Seed the God world with initial agents")
    parser.add_argument("--count", type=int, default=20, help="Number of agents to create")
    parser.add_argument(
        "--archetypes",
        type=str,
        default="all",
        help="Comma-separated archetypes or 'all'"
    )
    parser.add_argument("--elders", type=int, default=5, help="Number of elder guardians")
    parser.add_argument("--output", type=str, default="agents-registry.json")
    args = parser.parse_args()

    archetypes = (
        args.archetypes.split(",")
        if args.archetypes != "all"
        else None
    )

    log.info("=" * 60)
    log.info("God Project — World Genesis")
    log.info("=" * 60)

    agents = asyncio.run(seed_population(args.count, archetypes, args.elders))
    save_agent_registry(agents, args.output)

    log.info("")
    log.info("=" * 60)
    log.info(f"Genesis complete. {len(agents)} agents ready.")
    log.info(f"Open the observer: http://localhost:3000")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
