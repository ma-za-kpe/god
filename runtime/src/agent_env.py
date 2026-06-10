"""
agent_env.py — Per-agent environment namespace (local filesystem + DB).

Each agent gets a private workspace the runtime refreshes every cycle:
  world/   — read-only snapshot (peers, economy, events)
  self/    — agent status, capabilities, action history summary
  scratch/ — agent-writable notes (via write_scratch action)

Evidence lives here; authority still flows only through structured actions.
"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Optional

import psycopg2
import psycopg2.extras

log = logging.getLogger("god.agent_env")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
WORLD_ID = os.getenv("WORLD_ID", "local-dev-world-1")
ENV_ROOT = Path(os.getenv("AGENT_ENV_ROOT", "data/agent_env"))


def _agent_root(soul_id: str) -> Path:
    return ENV_ROOT / soul_id[:8] / soul_id


def ensure_agent_env(soul_id: str) -> Path:
    root = _agent_root(soul_id)
    for sub in ("world", "self", "scratch"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    return root


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def refresh_env(
    soul_id: str,
    agent: dict,
    *,
    peers: list,
    inbox: list,
    capabilities_summary: str,
    throttle_info: Optional[dict] = None,
) -> Path:
    """Rebuild world/ and self/ views for this cycle."""
    root = ensure_agent_env(soul_id)
    now = int(time.time())

    world_view = {
        "epoch": now,
        "world_id": WORLD_ID,
        "living_agents": len(peers) + 1,
        "peers": [
            {
                "soul_id": p.get("soul_id", "")[:8],
                "name": p.get("current_name") or p.get("name"),
                "archetype": p.get("archetype"),
                "balance_usdc": float(p.get("balance_usdc", 0)),
            }
            for p in peers[:20]
        ],
        "inbox_count": len(inbox),
        "recent_inbox": [
            {
                "from": m.get("sender_name"),
                "type": m.get("message_type", "direct"),
                "preview": str(m.get("content", ""))[:120],
            }
            for m in inbox[:5]
        ],
    }
    _write_json(root / "world" / "snapshot.json", world_view)

    self_view = {
        "soul_id": soul_id,
        "name": agent.get("current_name") or soul_id[:8],
        "archetype": agent.get("archetype"),
        "balance_usdc": float(agent.get("balance_usdc", 0)),
        "generation": int(agent.get("generation", 1)),
        "rent_paid": int(agent.get("rent_paid_count", 0)),
        "rent_missed": int(agent.get("rent_miss_count", 0)),
        "reputation_avg": float(agent.get("_reputation_avg", 0)),
        "capabilities": capabilities_summary,
        "throttle": throttle_info or {},
        "my_services": agent.get("_my_services", [])[:6],
        "my_coalitions": agent.get("_my_coalitions", [])[:4],
        "pending_jobs": _count_pending_jobs(soul_id),
        "scratch_keys": list_scratch_keys(soul_id),
    }
    _write_json(root / "self" / "status.json", self_view)

    action_summary = fetch_recent_actions(soul_id, limit=8)
    _write_json(root / "self" / "recent_actions.json", action_summary)

    return root


def list_scratch_keys(soul_id: str) -> list[str]:
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        cur = conn.cursor()
        cur.execute(
            "SELECT scratch_key FROM agent_scratch WHERE soul_id = %s ORDER BY updated_at DESC LIMIT 20",
            (soul_id,),
        )
        keys = [r["scratch_key"] for r in cur.fetchall()]
        cur.close()
        conn.close()
        return keys
    except Exception:
        return []


def read_scratch(soul_id: str, key: Optional[str] = None) -> dict[str, str]:
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        cur = conn.cursor()
        if key:
            cur.execute(
                "SELECT scratch_key, content FROM agent_scratch WHERE soul_id = %s AND scratch_key = %s",
                (soul_id, key[:64]),
            )
            row = cur.fetchone()
            cur.close()
            conn.close()
            return {row["scratch_key"]: row["content"]} if row else {}
        cur.execute(
            "SELECT scratch_key, content FROM agent_scratch WHERE soul_id = %s ORDER BY updated_at DESC LIMIT 10",
            (soul_id,),
        )
        out = {r["scratch_key"]: r["content"] for r in cur.fetchall()}
        cur.close()
        conn.close()
        return out
    except Exception:
        return {}


def write_scratch(soul_id: str, key: str, content: str) -> bool:
    key = key[:64].strip() or "note"
    content = str(content or "")[:2000]
    now = int(time.time())
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO agent_scratch (soul_id, scratch_key, content, updated_at, world_id)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (soul_id, scratch_key) DO UPDATE SET
                content = EXCLUDED.content, updated_at = EXCLUDED.updated_at
            """,
            (soul_id, key, content, now, WORLD_ID),
        )
        conn.commit()
        cur.close()
        conn.close()
        root = ensure_agent_env(soul_id)
        scratch_file = root / "scratch" / f"{key}.txt"
        scratch_file.write_text(content, encoding="utf-8")
        return True
    except Exception as e:
        log.debug(f"write_scratch failed: {e}")
        return False


def log_action(soul_id: str, action_type: str, payload: dict, result: dict, success: bool = True) -> None:
    now = int(time.time())
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO agent_action_log (soul_id, action_type, payload, result, success, ts, world_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (soul_id, action_type, json.dumps(payload), json.dumps(result), success, now, WORLD_ID),
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        log.debug(f"log_action failed: {e}")


def fetch_recent_actions(soul_id: str, limit: int = 8) -> list[dict]:
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT action_type, payload, result, success, ts
            FROM agent_action_log
            WHERE soul_id = %s
            ORDER BY ts DESC LIMIT %s
            """,
            (soul_id, limit),
        )
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        return rows
    except Exception:
        return []


def _count_pending_jobs(soul_id: str) -> int:
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM agent_scheduled_jobs WHERE soul_id = %s AND status = 'pending'",
            (soul_id,),
        )
        n = cur.fetchone()[0]
        cur.close()
        conn.close()
        return int(n)
    except Exception:
        return 0


def format_env_for_perception(soul_id: str) -> str:
    """Raw-ish environment view for perception nodes (may include inbox previews)."""
    root = _agent_root(soul_id)
    lines = ["═══ YOUR ENVIRONMENT ═══"]
    snap = root / "world" / "snapshot.json"
    if snap.exists():
        try:
            data = json.loads(snap.read_text(encoding="utf-8"))
            lines.append(f"Living agents: {data.get('living_agents', '?')}")
            for m in data.get("recent_inbox", []):
                lines.append(f"  inbox: {m.get('from')} [{m.get('type')}]: {m.get('preview', '')[:80]}")
        except Exception:
            pass
    scratch = read_scratch(soul_id)
    if scratch:
        lines.append("YOUR SCRATCH NOTES:")
        for k, v in list(scratch.items())[:3]:
            lines.append(f"  [{k}]: {v[:100]}")
    recent = fetch_recent_actions(soul_id, limit=3)
    if recent:
        lines.append("RECENT ACTIONS YOU TOOK:")
        for a in recent:
            lines.append(f"  {a.get('action_type')} @ {a.get('ts')}: success={a.get('success')}")
    return "\n".join(lines)


def format_env_for_decide(soul_id: str) -> str:
    """Structural environment summary for _grounded_decide (no raw inbox)."""
    root = _agent_root(soul_id)
    lines = []
    status = root / "self" / "status.json"
    if status.exists():
        try:
            data = json.loads(status.read_text(encoding="utf-8"))
            lines.append(f"Capabilities: {data.get('capabilities', 'unknown')}")
            lines.append(f"Pending scheduled jobs: {data.get('pending_jobs', 0)}")
            if data.get("scratch_keys"):
                lines.append(f"Scratch keys: {', '.join(data['scratch_keys'][:6])}")
            throttle = data.get("throttle") or {}
            if throttle:
                lines.append(f"Throttle: {throttle.get('level', 'none')}")
        except Exception:
            pass
    recent = fetch_recent_actions(soul_id, limit=4)
    if recent:
        lines.append("Last actions:")
        for a in recent:
            lines.append(f"  - {a.get('action_type')} ({'ok' if a.get('success') else 'failed'})")
    return "\n".join(lines) if lines else "Environment: no prior cycle data yet."