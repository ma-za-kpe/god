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

from .json_safe import json_safe
from .showrunner import build_showrunner_plan

log = logging.getLogger("god.snapshot")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
WORLD_ID = os.getenv("WORLD_ID", "local-dev-world-1")
MAX_AGENTS = int(os.getenv("SNAPSHOT_MAX_AGENTS", "10000"))

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
            clusters[arch]["members"].append(
                {
                    "soul_id": a["soul_id"],
                    "name": a.get("current_name"),
                }
            )
    return list(clusters.values())


def _attach_economy_stats(cur, stats: dict, world_id: str) -> None:
    """Circulation + top-earner metrics for Phase 1 local monitoring."""
    now = int(time.time())
    day_ago = now - 86400

    cur.execute(
        "SELECT COUNT(*) AS n FROM episodes WHERE world_id = %s",
        (world_id,),
    )
    stats["episodes_total"] = cur.fetchone()["n"]

    cur.execute(
        """
        SELECT COUNT(*) AS n
        FROM events
        WHERE world_id = %s AND timestamp >= %s
          AND event_type = 'economy.agent.transfer'
        """,
        (world_id, day_ago),
    )
    stats["transfers_24h"] = cur.fetchone()["n"]

    cur.execute(
        """
        SELECT COUNT(*) AS n
        FROM events
        WHERE world_id = %s AND timestamp >= %s
          AND event_type = 'economy.service.purchased'
        """,
        (world_id, day_ago),
    )
    stats["service_purchases_24h"] = cur.fetchone()["n"]

    cur.execute(
        """
        SELECT COALESCE(SUM(amount_usdc), 0) AS total
        FROM external_payments
        WHERE world_id = %s AND NOT is_internal AND timestamp >= %s
        """,
        (world_id, now - 30 * 86400),
    )
    stats["external_revenue_30d"] = float(cur.fetchone()["total"] or 0)

    cur.execute(
        """
        SELECT a.soul_id, a.current_name, a.archetype,
               COALESCE(a.balance_usdc, 0) AS balance_usdc,
               COALESCE(s.external_revenue_30d, 0) AS external_revenue_30d,
               COALESCE(s.tier, 0) AS tier,
               COALESCE(s.prestige_score, 0) AS prestige_score
        FROM agents a
        LEFT JOIN agent_status s ON s.soul_id = a.soul_id AND s.world_id = %s
        WHERE a.world_id = %s AND a.is_alive = true
        ORDER BY COALESCE(s.external_revenue_30d, 0) DESC, a.balance_usdc DESC
        LIMIT 8
        """,
        (world_id, world_id),
    )
    stats["top_earners"] = [dict(r) for r in cur.fetchall()]


def _finalize_snapshot(
    agents: list[dict],
    stats: dict,
    events: list[dict],
    messages: list[dict],
    world_id: str,
) -> dict[str, Any]:
    epoch = int(time.time())
    stats["world_id"] = world_id
    stats["llm_provider"] = os.getenv("LLM_PROVIDER", "ollama")
    stats["llm_model"] = os.getenv("LLM_MODEL", "llama3.1:8b")
    snapshot = {
        "epoch": epoch,
        "agents": agents,
        "agent_count": len(agents),
        "stats": stats,
        "events": events,
        "messages": messages,
        "clusters": _build_clusters(agents),
        "leaderboard": stats.get("top_earners", []),
        "world_id": world_id,
    }
    try:
        from .audience import build_audience_state

        snapshot["audience"] = build_audience_state(snapshot)
    except Exception as e:
        log.debug(f"audience state build skipped: {e}")
    snapshot["showrunner"] = build_showrunner_plan(snapshot)
    try:
        import psycopg2
        import psycopg2.extras as _extras
        _conn = psycopg2.connect(DATABASE_URL, cursor_factory=_extras.RealDictCursor)
        _cur = _conn.cursor()
        _cur.execute(
            """
            SELECT m.body AS content, m.sent_at, m.message_id, m.reply_to_id, m.metadata,
                   s.current_name AS sender_name, s.archetype AS sender_archetype,
                   r.current_name AS recipient_name
            FROM agent_messages m
            JOIN agents s ON s.soul_id = m.sender_id AND s.world_id = %s
            LEFT JOIN agents r ON r.soul_id = m.recipient_id
            WHERE m.message_type NOT IN ('system', 'env_event')
            ORDER BY m.sent_at DESC LIMIT 1
            """,
            (world_id,)
        )
        row = _cur.fetchone()
        _cur.close()
        _conn.close()
        snapshot["last_dialogue_turn"] = dict(row) if row else {}
    except Exception:
        snapshot["last_dialogue_turn"] = {}
    try:
        from .content_bank import build_content_bank_state

        snapshot["content_bank"] = build_content_bank_state(snapshot)
    except Exception as e:
        log.debug(f"content bank build skipped: {e}")
    try:
        from .viewer import build_viewer_state

        snapshot["viewer"] = build_viewer_state(snapshot)
    except Exception as e:
        log.debug(f"viewer state build skipped: {e}")
    try:
        from .nemo import build_nemo_directive

        snapshot["nemo"] = build_nemo_directive(snapshot)
    except Exception as e:
        log.debug(f"nemo directive build skipped: {e}")
    try:
        from .voice import build_voice_state

        snapshot["voice"] = build_voice_state(snapshot)
    except Exception as e:
        log.debug(f"voice state build skipped: {e}")
    try:
        from .avatar import build_avatar_state

        snapshot["avatar"] = build_avatar_state(snapshot)
    except Exception as e:
        log.debug(f"avatar state build skipped: {e}")
    try:
        from .broadcast import build_broadcast_state

        snapshot["broadcast"] = build_broadcast_state(snapshot)
    except Exception as e:
        log.debug(f"broadcast state build skipped: {e}")
    try:
        from .resilience import build_resilience_status

        snapshot["resilience"] = build_resilience_status(snapshot)
    except Exception as e:
        log.debug(f"resilience state build skipped: {e}")
    return json_safe(
        snapshot
    )


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

    _count_sql = {
        "events_total": "SELECT COUNT(*) AS n FROM events WHERE world_id = %s",
        "messages_total": "SELECT COUNT(*) AS n FROM agent_messages WHERE world_id = %s",
        "dreams_total": "SELECT COUNT(*) AS n FROM dreams WHERE world_id = %s",
        "tokens_deployed": "SELECT COUNT(*) AS n FROM tokens WHERE world_id = %s",
    }
    for key, sql in _count_sql.items():
        cur.execute(sql, (world_id,))
        stats[key] = cur.fetchone()["n"]

    _attach_economy_stats(cur, stats, world_id)

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
    from .db_pool import WORLD_ID as wid
    from .db_pool import fetch_all, fetch_one

    world_id = wid
    agents = await fetch_all(_AGENTS_SQL, world_id, MAX_AGENTS)

    stats = await fetch_one(_STATS_SQL, world_id) or {}
    _count_sql_async = {
        "events_total": "SELECT COUNT(*) AS n FROM events WHERE world_id = $1",
        "messages_total": "SELECT COUNT(*) AS n FROM agent_messages WHERE world_id = $1",
        "dreams_total": "SELECT COUNT(*) AS n FROM dreams WHERE world_id = $1",
        "tokens_deployed": "SELECT COUNT(*) AS n FROM tokens WHERE world_id = $1",
    }
    for key, sql in _count_sql_async.items():
        row = await fetch_one(sql, world_id)
        stats[key] = row["n"] if row else 0

    # Economy stats (sync helper — small queries)
    conn = _db()
    cur = conn.cursor()
    _attach_economy_stats(cur, stats, world_id)
    cur.close()
    conn.close()

    events = await fetch_all(
        "SELECT event_id, agent_id, event_type, timestamp, narrative, payload "
        "FROM events WHERE world_id = $1 ORDER BY timestamp DESC LIMIT $2",
        world_id,
        events_limit,
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
        world_id,
        messages_limit,
    )

    return _finalize_snapshot(agents, stats, events, messages, world_id)
