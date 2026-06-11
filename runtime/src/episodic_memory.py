"""
episodic_memory.py — Commit agent cycle memories to IPFS + PostgreSQL index.

Dream engine reads episodes; this module is the missing writer (GH #25).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import uuid
from typing import Any, Optional

import httpx
import psycopg2
import psycopg2.extras

log = logging.getLogger("god.memory")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
WORLD_ID = os.getenv("WORLD_ID", "local-dev-world-1")
IPFS_API = os.getenv("IPFS_API", "http://ipfs:5001")
MAX_SUMMARY_LEN = 400


def _db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)


def _emotional_imprint(agent: dict, action_type: str) -> float:
    """Lightweight valence estimate for dream weighting."""
    balance = float(agent.get("balance_usdc") or 0)
    misses = int(agent.get("rent_miss_count") or 0)
    base = 0.1
    if action_type in ("transfer_usdc", "buy_service", "register_service"):
        base += 0.25
    if action_type == "send_message":
        base += 0.15
    if misses > 0:
        base -= min(0.4, misses * 0.1)
    if balance < 0.5:
        base -= 0.2
    elif balance > 3.0:
        base += 0.15
    return round(max(-1.0, min(1.0, base)), 4)


def _sanitize_text(text: str, limit: int = MAX_SUMMARY_LEN) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) > limit:
        return cleaned[: limit - 3] + "..."
    return cleaned


async def _pin_payload(payload: dict) -> str:
    body = json.dumps(payload, default=str).encode("utf-8")
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            resp = await client.post(
                f"{IPFS_API}/api/v0/add",
                files={"file": ("episode.json", body, "application/json")},
            )
            resp.raise_for_status()
            data = resp.json()
            return data["Hash"]
    except Exception as e:
        digest = hashlib.sha256(body).hexdigest()[:46]
        log.debug(f"IPFS pin failed ({e}); using local digest cid")
        return f"local-{digest}"


async def commit_cycle_episode(
    agent: dict,
    *,
    thought: str,
    action_type: str,
    structured_action: Optional[dict] = None,
    cycle_number: int = 0,
) -> Optional[str]:
    """
    Persist one cognition-cycle episode. Returns episode_id or None on failure.
    """
    soul_id = agent.get("soul_id")
    if not soul_id:
        return None

    action = structured_action or {}
    participants: list[str] = []
    for key in ("to_id", "recipient_id", "seller_id", "target_soul_id"):
        pid = action.get(key)
        if pid and pid != soul_id and pid not in participants:
            participants.append(str(pid))

    summary = _sanitize_text(thought)
    imprint = _emotional_imprint(agent, action_type)
    tags = [t for t in [agent.get("archetype"), action_type] if t]

    episode_id = str(uuid.uuid4())
    ts = int(time.time())
    payload = {
        "episode_id": episode_id,
        "soul_id": soul_id,
        "event_type": "cognition.cycle",
        "timestamp": ts,
        "cycle_number": cycle_number,
        "summary": summary,
        "action_type": action_type,
        "structured_action": {
            k: action[k]
            for k in ("type", "to_id", "service_name", "amount_usdc", "message_type")
            if k in action
        },
        "balance_usdc": float(agent.get("balance_usdc") or 0),
        "emotional_imprint": imprint,
        "participants": participants,
        "tags": tags,
        "world_id": WORLD_ID,
    }

    try:
        cid = await _pin_payload(payload)
    except Exception as e:
        log.warning(f"commit_cycle_episode pin failed {soul_id[:8]}: {e}")
        return None

    try:
        conn = _db()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO episodes (
                episode_id, soul_id, event_type, timestamp, cycle_number,
                emotional_imprint, tags, ipfs_cid, participants, world_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (episode_id) DO NOTHING
            """,
            (
                episode_id,
                soul_id,
                "cognition.cycle",
                ts,
                cycle_number,
                imprint,
                tags,
                cid,
                participants or None,
                WORLD_ID,
            ),
        )
        conn.commit()
        cur.close()
        conn.close()
        log.debug(f"episode committed {soul_id[:8]} id={episode_id[:8]} cid={cid[:12]}")
        return episode_id
    except Exception as e:
        log.warning(f"commit_cycle_episode DB error {soul_id[:8]}: {e}")
        return None


def list_episodes(soul_id: str, limit: int = 20) -> list[dict[str, Any]]:
    """Recent episode index rows for debug / observer."""
    limit = max(1, min(limit, 100))
    try:
        conn = _db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT episode_id, soul_id, event_type, timestamp, cycle_number,
                   emotional_imprint, tags, ipfs_cid, participants
            FROM episodes
            WHERE soul_id = %s AND world_id = %s
            ORDER BY timestamp DESC
            LIMIT %s
            """,
            (soul_id, WORLD_ID, limit),
        )
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        log.warning(f"list_episodes error: {e}")
        return []
