"""
world_snapshot.py — Pre-aggregated world state for observer clients.

Single read path replaces multiple polling endpoints and supports
public spectators at high agent counts.
"""
import logging
import os
import time
from typing import Any

import psycopg2
import psycopg2.extras

log = logging.getLogger("god.snapshot")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
WORLD_ID     = os.getenv("WORLD_ID", "local-dev-world-1")
MAX_AGENTS   = int(os.getenv("SNAPSHOT_MAX_AGENTS", "10000"))

_AGENTS_SQL = """
    SELECT
        a.soul_id, a.current_name, a.wallet_address,
        a.birth_timestamp, a.death_timestamp, a.is_alive,
        a.parent_soul_ids, a.archetype,
        COALESCE(a.balance_usdc, 0)          AS balance_usdc,
        COALESCE(a.generation, 1)            AS generation,
        COALESCE(rp.paid_count,  0)          AS rent_paid_count,
        COALESCE(rp.miss_count,  0)          AS rent_miss_count,
        COALESCE(ss.is_sleeping, false)      AS is_sleeping,
        e.last_thought
    FROM agents a
    LEFT JOIN (
        SELECT soul_id,
            SUM(CASE WHEN NOT missed THEN 1 ELSE 0 END) AS paid_count,
            SUM(CASE WHEN missed     THEN 1 ELSE 0 END) AS miss_count
        FROM rent_payments GROUP BY soul_id
    ) rp ON rp.soul_id = a.soul_id
    LEFT JOIN sleep_states ss ON ss.soul_id = a.soul_id
    LEFT JOIN LATERAL (
        SELECT payload->>'thought' AS last_thought
        FROM events
        WHERE agent_id = a.soul_id
          AND event_type = 'cognitive.agent.thought'
        ORDER BY timestamp DESC LIMIT 1
    ) e ON true
    WHERE a.world_id = $1 AND a.is_alive = true
    ORDER BY a.birth_timestamp ASC
    LIMIT $2
"""

_STATS_SQL = """
    SELECT
        COUNT(*) FILTER (WHERE is_alive)                    AS living_count,
        COUNT(*)                                             AS total_born,
        COUNT(*) FILTER (WHERE NOT is_alive)                AS total_died,
        MIN(birth_timestamp)                                 AS world_start_ts,
        COALESCE(SUM(balance_usdc), 0)                       AS total_usdc_in_world,
        COALESCE(AVG(balance_usdc), 0)                       AS avg_balance,
        COALESCE(MAX(balance_usdc), 0)                       AS max_balance,
        COALESCE(MIN(balance_usdc) FILTER (WHERE is_alive), 0) AS min_balance_alive,
        COALESCE(MAX(generation), 1)                         AS max_generation,
        COALESCE(AVG(generation) FILTER (WHERE is_alive), 1) AS avg_generation
    FROM agents WHERE world_id = $1
"""


def _db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)


def _build_clusters(agents: list[dict]) -> list[dict]:
    clusters: dict[str, dict] = {}
    for a in agents:
        arch = a.get("archetype") or "unknown"
        if arch not in clusters:
            clusters[arch] = {"archetype": arch, "count": 0, "members": []}
        clusters[arch]["count"] += 1
        if len(clusters[arch]["members"]) < 8:
            clusters[arch]["members"].append({
                "soul_id": a["soul_id"],
                "name": a.get("current_name"),
            })
    return list(clusters.values())


def _finalize_snapshot(
    agents: list[dict],
    stats: dict,
    events: list[dict],
    messages: list[dict],
    world_id: str,
) -> dict[str, Any]:
    stats["world_id"] = world_id
    stats["llm_provider"] = os.getenv("LLM_PROVIDER", "ollama")
    stats["llm_model"] = os.getenv("LLM_MODEL", "llama3.1:8b")
    return {
        "epoch": int(time.time()),
        "agents": agents,
        "agent_count": len(agents),
        "stats": stats,
        "events": events,
        "messages": messages,
        "clusters": _build_clusters(agents),
        "world_id": world_id,
    }


def build_world_snapshot(
    events_limit: int = 50,
    messages_limit: int = 80,
) -> dict[str, Any]:
    """Sync snapshot (background / fallback)."""
    world_id = WORLD_ID
    conn = _db()
    cur = conn.cursor()

    cur.execute(_AGENTS_SQL.replace("$1", "%s").replace("$2", "%s"), (world_id, MAX_AGENTS))
    agents = [dict(r) for r in cur.fetchall()]

    cur.execute(_STATS_SQL.replace("$1", "%s"), (world_id,))
    stats = dict(cur.fetchone())

    for table, key in [
        ("events", "events_total"),
        ("agent_messages", "messages_total"),
        ("dreams", "dreams_total"),
        ("tokens", "tokens_deployed"),
    ]:
        cur.execute(f"SELECT COUNT(*) AS n FROM {table} WHERE world_id = %s", (world_id,))
        stats[key] = cur.fetchone()["n"]

    cur.execute(
        "SELECT event_id, agent_id, event_type, timestamp, narrative, payload "
        "FROM events WHERE world_id = %s ORDER BY timestamp DESC LIMIT %s",
        (world_id, events_limit),
    )
    events = [dict(r) for r in cur.fetchall()]

    cur.execute(
        """
        SELECT m.*,
               sa.current_name AS sender_name,
               ra.current_name AS recipient_name
        FROM agent_messages m
        LEFT JOIN agents sa ON m.sender_id = sa.soul_id
        LEFT JOIN agents ra ON m.recipient_id = ra.soul_id
        WHERE m.world_id = %s
        ORDER BY m.sent_at DESC
        LIMIT %s
        """,
        (world_id, messages_limit),
    )
    messages = [dict(r) for r in cur.fetchall()]
    cur.close()
    conn.close()

    return _finalize_snapshot(agents, stats, events, messages, world_id)


async def build_world_snapshot_async(
    events_limit: int = 50,
    messages_limit: int = 80,
) -> dict[str, Any]:
    """Async snapshot via asyncpg pool (FastAPI hot path)."""
    from .db_pool import fetch_all, fetch_one, WORLD_ID as wid

    world_id = wid
    agents = await fetch_all(_AGENTS_SQL, world_id, MAX_AGENTS)

    stats = await fetch_one(_STATS_SQL, world_id) or {}
    for table, key in [
        ("events", "events_total"),
        ("agent_messages", "messages_total"),
        ("dreams", "dreams_total"),
        ("tokens", "tokens_deployed"),
    ]:
        row = await fetch_one(
            f"SELECT COUNT(*) AS n FROM {table} WHERE world_id = $1", world_id
        )
        stats[key] = row["n"] if row else 0

    events = await fetch_all(
        "SELECT event_id, agent_id, event_type, timestamp, narrative, payload "
        "FROM events WHERE world_id = $1 ORDER BY timestamp DESC LIMIT $2",
        world_id, events_limit,
    )

    messages = await fetch_all(
        """
        SELECT m.*,
               sa.current_name AS sender_name,
               ra.current_name AS recipient_name
        FROM agent_messages m
        LEFT JOIN agents sa ON m.sender_id = sa.soul_id
        LEFT JOIN agents ra ON m.recipient_id = ra.soul_id
        WHERE m.world_id = $1
        ORDER BY m.sent_at DESC
        LIMIT $2
        """,
        world_id, messages_limit,
    )

    return _finalize_snapshot(agents, stats, events, messages, world_id)