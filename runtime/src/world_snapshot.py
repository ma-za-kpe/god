"""
world_snapshot.py — Pre-aggregated world state for observer clients.

Single read path replaces multiple polling endpoints and supports
public spectators at high agent counts.
"""
import logging
import os
from typing import Any

import psycopg2
import psycopg2.extras

log = logging.getLogger("god.snapshot")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
WORLD_ID     = os.getenv("WORLD_ID", "local-dev-world-1")
MAX_AGENTS   = int(os.getenv("SNAPSHOT_MAX_AGENTS", "10000"))


def _db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)


def build_world_snapshot(
    events_limit: int = 50,
    messages_limit: int = 80,
) -> dict[str, Any]:
    """Return agents, stats, recent events, messages, and archetype clusters."""
    world_id = WORLD_ID
    conn = _db()
    cur = conn.cursor()

    cur.execute(
        """
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
        WHERE a.world_id = %s AND a.is_alive = true
        ORDER BY a.birth_timestamp ASC
        LIMIT %s
        """,
        (world_id, MAX_AGENTS),
    )
    agents = [dict(r) for r in cur.fetchall()]

    cur.execute(
        """
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
        FROM agents WHERE world_id = %s
        """,
        (world_id,),
    )
    stats = dict(cur.fetchone())

    cur.execute("SELECT COUNT(*) AS n FROM events WHERE world_id = %s", (world_id,))
    stats["events_total"] = cur.fetchone()["n"]
    cur.execute("SELECT COUNT(*) AS n FROM agent_messages WHERE world_id = %s", (world_id,))
    stats["messages_total"] = cur.fetchone()["n"]
    cur.execute("SELECT COUNT(*) AS n FROM dreams WHERE world_id = %s", (world_id,))
    stats["dreams_total"] = cur.fetchone()["n"]
    cur.execute("SELECT COUNT(*) AS n FROM tokens WHERE world_id = %s", (world_id,))
    stats["tokens_deployed"] = cur.fetchone()["n"]
    stats["world_id"] = world_id
    stats["llm_provider"] = os.getenv("LLM_PROVIDER", "ollama")
    stats["llm_model"] = os.getenv("LLM_MODEL", "llama3.1:8b")

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

    # Archetype clusters for observer LOD layout
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

    cur.close()
    conn.close()

    return {
        "epoch": int(__import__("time").time()),
        "agents": agents,
        "agent_count": len(agents),
        "stats": stats,
        "events": events,
        "messages": messages,
        "clusters": list(clusters.values()),
        "world_id": world_id,
    }