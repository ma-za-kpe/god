"""
coalitions.py — Coalition formation and membership management.

Coalitions are persistent groups of agents that can coordinate via messages,
share reputation, and collectively act in the world.
"""

import logging
import os
import time
import uuid

import psycopg2
import psycopg2.extras

log = logging.getLogger("god.coalitions")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
WORLD_ID = os.getenv("WORLD_ID", "local-dev-world-1")


def _db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)


async def form_coalition(founder_soul_id: str, name: str) -> dict:
    """
    Create a new coalition with the founder as the first member.
    Returns the coalition record dict.
    """
    coalition_id = str(uuid.uuid4())
    membership_id = str(uuid.uuid4())
    now = int(time.time())

    conn = _db()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO coalitions
                (coalition_id, name, founder_soul_id, formed_at, world_id)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (coalition_id, name[:80], founder_soul_id, now, WORLD_ID),
        )
        cur.execute(
            """
            INSERT INTO coalition_members
                (membership_id, coalition_id, soul_id, role, joined_at, world_id)
            VALUES (%s, %s, %s, 'founder', %s, %s)
            ON CONFLICT (coalition_id, soul_id) DO NOTHING
            """,
            (membership_id, coalition_id, founder_soul_id, now, WORLD_ID),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()

    log.info(f"Coalition '{name}' ({coalition_id[:8]}) founded by {founder_soul_id[:8]}")
    return {
        "coalition_id": coalition_id,
        "name": name,
        "founder_soul_id": founder_soul_id,
        "formed_at": now,
    }


async def join_coalition(coalition_id: str, soul_id: str, role: str = "member") -> dict:
    """Add an agent to an existing coalition."""
    membership_id = str(uuid.uuid4())
    now = int(time.time())

    conn = _db()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO coalition_members
                (membership_id, coalition_id, soul_id, role, joined_at, world_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (coalition_id, soul_id) DO NOTHING
            """,
            (membership_id, coalition_id, soul_id, role, now, WORLD_ID),
        )
        cur.execute(
            "UPDATE coalitions SET member_count = member_count + 1 WHERE coalition_id = %s",
            (coalition_id,),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()

    return {"coalition_id": coalition_id, "soul_id": soul_id, "joined_at": now}


def get_agent_coalitions(soul_id: str) -> list[dict]:
    """Return coalitions this agent belongs to."""
    try:
        conn = _db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT c.coalition_id, c.name, c.founder_soul_id, c.member_count, cm.role
            FROM coalitions c
            JOIN coalition_members cm ON cm.coalition_id = c.coalition_id
            WHERE cm.soul_id = %s AND c.world_id = %s
            ORDER BY cm.joined_at DESC
            """,
            (soul_id, WORLD_ID),
        )
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        return rows
    except Exception:
        return []


def get_world_coalitions() -> list[dict]:
    """Return all active coalitions with member counts."""
    try:
        conn = _db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT c.coalition_id, c.name, c.founder_soul_id, c.member_count,
                   a.current_name AS founder_name
            FROM coalitions c
            LEFT JOIN agents a ON a.soul_id = c.founder_soul_id
            WHERE c.world_id = %s
            ORDER BY c.member_count DESC, c.formed_at DESC
            """,
            (WORLD_ID,),
        )
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        return rows
    except Exception:
        return []


def get_coalition_members(coalition_id: str) -> list[dict]:
    """Return all members of a coalition."""
    try:
        conn = _db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT cm.soul_id, cm.role, cm.joined_at,
                   a.current_name, a.archetype, a.balance_usdc
            FROM coalition_members cm
            JOIN agents a ON a.soul_id = cm.soul_id
            WHERE cm.coalition_id = %s AND cm.world_id = %s AND a.is_alive = true
            ORDER BY cm.role, cm.joined_at
            """,
            (coalition_id, WORLD_ID),
        )
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        return rows
    except Exception:
        return []
