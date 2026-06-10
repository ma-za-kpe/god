"""
graph_mutation.py — Bounded self-modification for local OwnedGraph evolution.

Agents propose mutations via mutate_graph; runtime applies on next cycle
after validation. Full IPFS pin when available; local DB fallback otherwise.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid

import psycopg2
import psycopg2.extras

log = logging.getLogger("god.mutation")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
WORLD_ID = os.getenv("WORLD_ID", "local-dev-world-1")

ALLOWED_TYPES = {"rename", "biography", "personality_bias", "add_node"}
MUTATION_COST_USDC = float(os.getenv("MUTATION_COST_USDC", "0.002"))


def propose_mutation(soul_id: str, mutation_type: str, payload: dict) -> dict:
    mtype = (mutation_type or "").lower().strip()
    if mtype not in ALLOWED_TYPES:
        return {"error": f"mutation_type must be one of {sorted(ALLOWED_TYPES)}"}

    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()
    cur.execute(
        "SELECT balance_usdc, current_name FROM agents WHERE soul_id = %s AND is_alive = true",
        (soul_id,),
    )
    agent = cur.fetchone()
    if not agent:
        cur.close()
        conn.close()
        return {"error": "agent not found or dead"}
    if float(agent["balance_usdc"]) < MUTATION_COST_USDC:
        cur.close()
        conn.close()
        return {"error": f"need ${MUTATION_COST_USDC:.4f} USDC for mutation"}

    mutation_id = str(uuid.uuid4())
    now = int(time.time())
    cur.execute(
        """
        INSERT INTO agent_graph_mutations (mutation_id, soul_id, mutation_type, payload, status, created_at, world_id)
        VALUES (%s, %s, %s, %s, 'pending', %s, %s)
        """,
        (mutation_id, soul_id, mtype, json.dumps(payload), now, WORLD_ID),
    )
    cur.execute(
        "UPDATE agents SET balance_usdc = balance_usdc - %s WHERE soul_id = %s",
        (MUTATION_COST_USDC, soul_id),
    )
    conn.commit()
    cur.close()
    conn.close()
    return {"mutation_id": mutation_id, "status": "pending", "cost_usdc": MUTATION_COST_USDC}


def apply_pending_mutations(soul_id: str) -> list[dict]:
    """Apply all pending mutations for an agent. Called at cycle start."""
    results = []
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT mutation_id, mutation_type, payload
            FROM agent_graph_mutations
            WHERE soul_id = %s AND status = 'pending'
            ORDER BY created_at ASC LIMIT 3
            """,
            (soul_id,),
        )
        pending = cur.fetchall()
        now = int(time.time())

        for row in pending:
            mid = row["mutation_id"]
            mtype = row["mutation_type"]
            payload = row["payload"] or {}
            if isinstance(payload, str):
                payload = json.loads(payload)
            try:
                applied = _apply_one(cur, conn, soul_id, mtype, payload)
                cur.execute(
                    "UPDATE agent_graph_mutations SET status = 'applied', applied_at = %s WHERE mutation_id = %s",
                    (now, mid),
                )
                conn.commit()
                results.append({"mutation_id": mid, "type": mtype, "applied": applied})
            except Exception as e:
                cur.execute(
                    "UPDATE agent_graph_mutations SET status = 'failed', applied_at = %s WHERE mutation_id = %s",
                    (now, mid),
                )
                conn.commit()
                results.append({"mutation_id": mid, "error": str(e)})

        cur.close()
        conn.close()
    except Exception as e:
        log.debug(f"apply_pending_mutations: {e}")
    return results


def _apply_one(cur, conn, soul_id: str, mtype: str, payload: dict) -> dict:
    if mtype == "rename":
        name = str(payload.get("new_name") or "")[:40].strip()
        if not name:
            raise ValueError("new_name required")
        cur.execute("UPDATE agents SET current_name = %s WHERE soul_id = %s", (name, soul_id))
        conn.commit()
        return {"new_name": name}

    if mtype == "biography":
        bio = str(payload.get("biography") or "")[:500]
        cur.execute(
            "UPDATE agents SET emotional_state = %s WHERE soul_id = %s",
            (bio[:200] if bio else "neutral", soul_id),
        )
        conn.commit()
        return {"biography_len": len(bio)}

    if mtype == "personality_bias":
        bias = str(payload.get("bias") or "")[:300]
        from .dream_engine import set_pending_mutation

        set_pending_mutation(soul_id, bias)
        return {"bias_applied": bias[:80]}

    if mtype == "add_node":
        node_name = str(payload.get("node_name") or "")[:40].strip()
        desc = str(payload.get("description") or "")[:200]
        if not node_name:
            raise ValueError("node_name required")
        _record_graph_node_local(cur, conn, soul_id, node_name, desc)
        return {"node_name": node_name}

    raise ValueError(f"unknown mutation {mtype}")


def _record_graph_node_local(cur, conn, soul_id: str, node_name: str, description: str) -> None:
    """Store proposed node in scratch as local graph extension until IPFS deploy."""
    key = f"graph_node:{node_name}"
    content = json.dumps({"node": node_name, "description": description, "local": True})
    now = int(time.time())
    cur.execute(
        """
        INSERT INTO agent_scratch (soul_id, scratch_key, content, updated_at, world_id)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (soul_id, scratch_key) DO UPDATE SET content = EXCLUDED.content, updated_at = EXCLUDED.updated_at
        """,
        (soul_id, key, content, now, WORLD_ID),
    )
    conn.commit()
