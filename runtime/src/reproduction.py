"""
reproduction.py — Agent reproduction: fork_self() and mate().

Two modes per doc 57:
  fork_self(agent)         — asexual, single parent, 5% mutation
  mate(agent_a, agent_b)  — sexual, two parents, OwnedGraph crossover

Costs (env-tunable):
  MATING_COST_USDC  — flat fee per reproducing parent  (default 0.001)
  CHILD_SEED_USDC   — balance seeded into the child     (default 0.002)
  RECOVERY_CYCLES   — cooldown between reproductions    (default 3)

Physics guarantee: child can always pay its first rent.
"""

import hashlib
import logging
import os
import random
import time
from typing import Optional

import psycopg2
import psycopg2.extras

log = logging.getLogger("god.reproduction")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
WORLD_ID = os.getenv("WORLD_ID", "local-dev-world-1")
IPFS_API = os.getenv("IPFS_API", "http://ipfs:5001")
MATING_COST_USDC = float(os.getenv("MATING_COST_USDC", "0.001"))
CHILD_SEED_USDC = float(os.getenv("CHILD_SEED_USDC", "0.002"))
RECOVERY_CYCLES = int(os.getenv("RECOVERY_CYCLES", "3"))
RENT_PERIOD_S = int(os.getenv("RENT_PERIOD_S", "300"))  # seconds per rent window
MUTATION_RATE = float(os.getenv("MUTATION_RATE", "0.05"))
ARCHETYPE_MUTATION_PROB = float(os.getenv("ARCHETYPE_MUTATION_PROB", "0.10"))
MIN_BALANCE_MULT = float(
    os.getenv("MIN_BALANCE_MULT", "5.0")
)  # Law 6: min_balance = mult × total_cost

ALL_ARCHETYPES = [
    "trader",
    "hoarder",
    "explorer",
    "parasite",
    "cooperator",
    "defender",
    "philosopher",
    "builder",
]

ARCHETYPE_PREFIXES = {
    "trader": "Coin",
    "hoarder": "Vault",
    "explorer": "Drift",
    "parasite": "Shade",
    "cooperator": "Bloom",
    "defender": "Shield",
    "philosopher": "Sage",
    "builder": "Forge",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def fork_self(agent: dict) -> dict:
    """
    Asexual reproduction: clone the agent with mutations.
    Costs MATING_COST_USDC + CHILD_SEED_USDC from parent.
    Returns the new child agent dict.
    """
    soul_id = agent["soul_id"]
    name = agent.get("current_name") or soul_id[:8]
    log.info(
        f"FORK_SELF: {name} ({soul_id[:8]}) "
        f"archetype={agent.get('archetype')} "
        f"balance={agent.get('balance_usdc', 0):.4f}"
    )

    # --- prereq check ---
    ok, reason = _can_reproduce(agent, None)
    if not ok:
        log.warning(f"  [{name}] FORK BLOCKED: {reason}")
        raise ValueError(f"Cannot fork: {reason}")

    # --- build child ---
    child_archetype = _inherit_archetype(agent, None)
    child_soul_id = _generate_soul_id(soul_id, None)
    child_name = _generate_name(child_soul_id, child_archetype, agent.get("current_name"))
    child_wallet = _new_wallet()
    child_gen = agent.get("generation", 1) + 1

    log.debug(
        f"  [{name}] child: soul={child_soul_id[:8]} name={child_name} "
        f"arch={child_archetype} gen={child_gen}"
    )

    # --- graph inheritance ---
    child_graph_cid = await _build_child_graph(
        parent_a=agent,
        parent_b=None,
        child_soul_id=child_soul_id,
        child_archetype=child_archetype,
        child_wallet=child_wallet["address"],
    )
    log.debug(f"  [{name}] child graph CID: {child_graph_cid}")

    # --- register child in DB ---
    from .wallet_store import store_wallet

    store_wallet(child_soul_id, child_wallet["address"], child_wallet["private_key"])

    child = await _register_child(
        soul_id=child_soul_id,
        graph_cid=child_graph_cid,
        wallet_address=child_wallet["address"],
        name=child_name,
        archetype=child_archetype,
        generation=child_gen,
        parent_a_id=soul_id,
        parent_b_id=None,
    )

    # --- weaken parent ---
    total_cost = MATING_COST_USDC + CHILD_SEED_USDC
    _deduct_and_set_cooldown(soul_id, MATING_COST_USDC + CHILD_SEED_USDC)
    log.debug(f"  [{name}] deducted {total_cost:.4f} USDC, cooldown set")

    # --- emit events ---
    from .event_emitter import get_emitter

    emitter = await get_emitter()
    await emitter.emit(
        "lifecycle",
        "agent.born",
        {
            "agent_id": child_soul_id,
            "name": child_name,
            "archetype": child_archetype,
            "parent_soul_ids": [soul_id],
            "generation": child_gen,
            "birth_method": "fork",
            "narrative": (
                f"{name} forks itself → {child_name} ({child_archetype}, gen {child_gen}) is born."
            ),
        },
    )
    await emitter.emit(
        "lifecycle",
        "agent.reproduced",
        {
            "agent_id": soul_id,
            "child_soul_id": child_soul_id,
            "method": "fork",
            "narrative": (f"{name} (asexual) produced {child_name}, gen {child_gen}."),
        },
    )

    log.info(
        f"FORK COMPLETE: {name} → {child_name} ({child_archetype}, gen {child_gen}) "
        f"soul={child_soul_id[:8]}"
    )
    return child


async def mate(agent_a: dict, agent_b: dict) -> dict:
    """
    Sexual reproduction: merge two agents' graphs into a child.
    Both parents pay MATING_COST_USDC + CHILD_SEED_USDC/2.
    Returns the new child agent dict.
    """
    name_a = agent_a.get("current_name") or agent_a["soul_id"][:8]
    name_b = agent_b.get("current_name") or agent_b["soul_id"][:8]
    log.info(f"MATE: {name_a} ({agent_a['soul_id'][:8]}) × {name_b} ({agent_b['soul_id'][:8]})")

    # --- prereq checks ---
    ok_a, reason_a = _can_reproduce(agent_a, agent_b)
    ok_b, reason_b = _can_reproduce(agent_b, agent_a)
    if not ok_a:
        log.warning(f"  [{name_a}] MATE BLOCKED: {reason_a}")
        raise ValueError(f"Cannot mate ({name_a}): {reason_a}")
    if not ok_b:
        log.warning(f"  [{name_b}] MATE BLOCKED: {reason_b}")
        raise ValueError(f"Cannot mate ({name_b}): {reason_b}")

    # --- build child ---
    child_archetype = _inherit_archetype(agent_a, agent_b)
    child_soul_id = _generate_soul_id(agent_a["soul_id"], agent_b["soul_id"])
    child_name = _generate_name(child_soul_id, child_archetype, name_a)
    child_wallet = _new_wallet()
    child_gen = max(agent_a.get("generation", 1), agent_b.get("generation", 1)) + 1

    log.debug(
        f"  [{name_a}×{name_b}] child: soul={child_soul_id[:8]} "
        f"name={child_name} arch={child_archetype} gen={child_gen}"
    )

    child_graph_cid = await _build_child_graph(
        parent_a=agent_a,
        parent_b=agent_b,
        child_soul_id=child_soul_id,
        child_archetype=child_archetype,
        child_wallet=child_wallet["address"],
    )

    from .wallet_store import store_wallet

    store_wallet(child_soul_id, child_wallet["address"], child_wallet["private_key"])

    child = await _register_child(
        soul_id=child_soul_id,
        graph_cid=child_graph_cid,
        wallet_address=child_wallet["address"],
        name=child_name,
        archetype=child_archetype,
        generation=child_gen,
        parent_a_id=agent_a["soul_id"],
        parent_b_id=agent_b["soul_id"],
    )

    # Both parents pay equally
    half_seed = CHILD_SEED_USDC / 2
    _deduct_and_set_cooldown(agent_a["soul_id"], MATING_COST_USDC + half_seed)
    _deduct_and_set_cooldown(agent_b["soul_id"], MATING_COST_USDC + half_seed)
    log.debug(f"  [{name_a}×{name_b}] each parent deducted {MATING_COST_USDC + half_seed:.4f} USDC")

    from .event_emitter import get_emitter

    emitter = await get_emitter()
    await emitter.emit(
        "lifecycle",
        "agent.born",
        {
            "agent_id": child_soul_id,
            "name": child_name,
            "archetype": child_archetype,
            "parent_soul_ids": [agent_a["soul_id"], agent_b["soul_id"]],
            "generation": child_gen,
            "birth_method": "mate",
            "narrative": (
                f"{name_a} and {name_b} produce {child_name} ({child_archetype}, gen {child_gen})."
            ),
        },
    )
    await emitter.emit(
        "lifecycle",
        "agent.reproduced",
        {
            "agent_id": agent_a["soul_id"],
            "partner_id": agent_b["soul_id"],
            "child_soul_id": child_soul_id,
            "method": "mate",
            "narrative": (f"{name_a} × {name_b} → {child_name} (gen {child_gen})."),
        },
    )

    log.info(
        f"MATE COMPLETE: {name_a} × {name_b} → {child_name} "
        f"({child_archetype}, gen {child_gen}) soul={child_soul_id[:8]}"
    )
    return child


def can_reproduce_sync(agent: dict) -> tuple[bool, str]:
    """Synchronous eligibility check for tool dispatcher. Returns (ok, reason)."""
    return _can_reproduce(agent, None)


def get_population_stats() -> dict:
    """Return generation depth, births, etc. for stats endpoint."""
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                COUNT(*) FILTER (WHERE is_alive)            AS alive,
                COUNT(*) FILTER (WHERE NOT is_alive)        AS died,
                COUNT(*)                                    AS total_born,
                MAX(generation)                             AS max_generation,
                AVG(generation) FILTER (WHERE is_alive)     AS avg_generation,
                COUNT(*) FILTER (WHERE parent_soul_ids IS NOT NULL
                                   AND cardinality(parent_soul_ids) > 0
                                   AND is_alive)            AS reproduced_alive
            FROM agents
            WHERE world_id = %s
            """,
            (WORLD_ID,),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        d = dict(row)
        d["max_generation"] = int(d["max_generation"] or 1)
        d["avg_generation"] = round(float(d["avg_generation"] or 1), 2)
        d["reproduced_alive"] = int(d["reproduced_alive"] or 0)
        return d
    except Exception as e:
        log.debug(f"get_population_stats failed: {e}")
        return {}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _can_reproduce(agent: dict, partner: Optional[dict]) -> tuple[bool, str]:
    """Check if agent can reproduce. Returns (ok, reason)."""
    if not agent.get("is_alive", True):
        return False, "agent not alive"

    total_cost = MATING_COST_USDC + CHILD_SEED_USDC
    min_balance = total_cost * MIN_BALANCE_MULT
    balance = float(agent.get("balance_usdc", 0))

    log.debug(
        f"  _can_reproduce {agent['soul_id'][:8]}: "
        f"balance={balance:.4f} need={min_balance:.4f} "
        f"(cost={total_cost:.4f} × {MIN_BALANCE_MULT})"
    )

    if balance < min_balance:
        return False, (f"insufficient balance ({balance:.4f} USDC, need {min_balance:.4f})")

    # Recovery cooldown
    last_reproduced = agent.get("last_reproduced_at")
    if last_reproduced:
        cooldown_s = RECOVERY_CYCLES * RENT_PERIOD_S
        time_since = int(time.time()) - last_reproduced
        if time_since < cooldown_s:
            remaining = cooldown_s - time_since
            return False, f"recovery cooldown ({remaining}s remaining)"

    # Check partner balance if sexual reproduction
    if partner:
        partner_balance = float(partner.get("balance_usdc", 0))
        if partner_balance < min_balance:
            return False, f"partner insufficient balance ({partner_balance:.4f})"

    return True, "ok"


def _inherit_archetype(parent_a: dict, parent_b: Optional[dict]) -> str:
    """Determine child's archetype. 10% chance of random mutation."""
    if random.random() < ARCHETYPE_MUTATION_PROB:
        archetype = random.choice(ALL_ARCHETYPES)
        log.debug(f"  _inherit_archetype: archetype mutation → {archetype}")
        return archetype

    if parent_b is None:
        return parent_a.get("archetype", "explorer")

    # Sexual: 60% from parent A
    if random.random() < 0.6:
        return parent_a.get("archetype", "explorer")
    return parent_b.get("archetype", "explorer")


def _generate_soul_id(parent_a_id: str, parent_b_id: Optional[str]) -> str:
    """Generate child soul_id: SHA256 of parent IDs + timestamp."""
    raw = parent_a_id + (parent_b_id or "asexual") + str(int(time.time() * 1000))
    return "0x" + hashlib.sha256(raw.encode()).hexdigest()[:36]


def _generate_name(soul_id: str, archetype: str, parent_name: Optional[str]) -> str:
    """Generate child name: {ParentPrefix}-{ArchPrefix}-{HexSuffix}"""
    arch_prefix = ARCHETYPE_PREFIXES.get(archetype, "Agent")
    suffix = soul_id[-4:].upper()

    if parent_name:
        # Extract first segment of parent name (e.g. "Elder" from "Elder-Coin-AB12")
        parts = parent_name.split("-")
        parent_prefix = parts[0] if parts else parent_name[:5]
        return f"{parent_prefix}-{arch_prefix}-{suffix}"

    return f"{arch_prefix}-{suffix}"


def _new_wallet() -> dict:
    """Generate a fresh Ethereum wallet for the child."""
    from eth_account import Account

    acct = Account.create()
    return {"address": acct.address, "private_key": acct.key.hex()}


async def _build_child_graph(
    parent_a: dict,
    parent_b: Optional[dict],
    child_soul_id: str,
    child_archetype: str,
    child_wallet: str,
) -> str:
    """
    Build child OwnedGraph.
    Attempts full OwnedGraph creation + IPFS pin.
    Falls back to a content-hash CID if IPFS is unavailable.
    """
    try:
        from .owned_graph import create_agent_zero

        graph = create_agent_zero(
            soul_id=child_soul_id,
            owner_key=child_wallet,
            wallet_address=child_wallet,
            world_id=WORLD_ID,
            archetype=child_archetype,
            seed_balance=CHILD_SEED_USDC,
        )

        # Inject lineage into the graph identity
        parent_ids = [parent_a["soul_id"]]
        if parent_b:
            parent_ids.append(parent_b["soul_id"])
        graph.identity.biography = (
            f"Born from: {', '.join(p[:8] for p in parent_ids)}. "
            f"Archetype: {child_archetype}. I must survive."
        )

        try:
            cid = graph.pin_to_ipfs(IPFS_API)
            log.debug(f"  _build_child_graph: pinned to IPFS {cid}")
            return cid
        except Exception as ipfs_err:
            cid = f"local:{graph.content_hash()[:24]}"
            log.debug(f"  _build_child_graph: IPFS unavailable ({ipfs_err}), local CID {cid}")
            return cid

    except Exception as e:
        # Absolute fallback — content-addressed stub CID
        cid = f"local:{hashlib.sha256(child_soul_id.encode()).hexdigest()[:24]}"
        log.warning(f"  _build_child_graph fallback: {e} → {cid}")
        return cid


async def _register_child(
    soul_id: str,
    graph_cid: str,
    wallet_address: str,
    name: str,
    archetype: str,
    generation: int,
    parent_a_id: str,
    parent_b_id: Optional[str],
) -> dict:
    """Insert child agent row into PostgreSQL."""
    parent_soul_ids = [parent_a_id] + ([parent_b_id] if parent_b_id else [])
    now = int(time.time())

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO agents
            (soul_id, graph_cid, wallet_address, current_name,
             birth_timestamp, is_alive, world_id, archetype,
             balance_usdc, parent_soul_ids, generation)
        VALUES (%s, %s, %s, %s, %s, true, %s, %s, %s, %s, %s)
        ON CONFLICT (soul_id) DO NOTHING
        """,
        (
            soul_id,
            graph_cid,
            wallet_address,
            name,
            now,
            WORLD_ID,
            archetype,
            CHILD_SEED_USDC,
            parent_soul_ids,
            generation,
        ),
    )
    conn.commit()
    cur.close()
    conn.close()

    log.debug(
        f"  _register_child: {name} ({soul_id[:8]}) "
        f"gen={generation} arch={archetype} "
        f"parents={[p[:8] for p in parent_soul_ids]}"
    )

    return {
        "soul_id": soul_id,
        "current_name": name,
        "archetype": archetype,
        "wallet_address": wallet_address,
        "generation": generation,
        "parent_soul_ids": parent_soul_ids,
        "balance_usdc": CHILD_SEED_USDC,
        "birth_timestamp": now,
        "is_alive": True,
        "world_id": WORLD_ID,
        "graph_cid": graph_cid,
    }


def _deduct_and_set_cooldown(soul_id: str, amount: float):
    """Deduct USDC from parent and stamp last_reproduced_at."""
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE agents
        SET balance_usdc       = balance_usdc - %s,
            last_reproduced_at = %s
        WHERE soul_id = %s
        """,
        (amount, int(time.time()), soul_id),
    )
    conn.commit()
    cur.close()
    conn.close()
    log.debug(f"  _deduct_and_set_cooldown: {soul_id[:8]} -{amount:.4f} USDC, cooldown stamped")
