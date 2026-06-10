"""
agent_jobs.py — Scheduled intents and async wake for agent tempo autonomy.
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from typing import Any

import psycopg2
import psycopg2.extras

log = logging.getLogger("god.jobs")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
WORLD_ID = os.getenv("WORLD_ID", "local-dev-world-1")

MIN_DELAY_S = 60
MAX_DELAY_S = 86400
MAX_PENDING_PER_AGENT = 5


def schedule_job(soul_id: str, job_type: str, delay_seconds: int, payload: dict) -> dict:
    delay_seconds = max(MIN_DELAY_S, min(MAX_DELAY_S, int(delay_seconds)))
    now = int(time.time())
    run_at = now + delay_seconds

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM agent_scheduled_jobs WHERE soul_id = %s AND status = 'pending'",
        (soul_id,),
    )
    pending = cur.fetchone()[0]
    if pending >= MAX_PENDING_PER_AGENT:
        cur.close()
        conn.close()
        return {"error": f"max {MAX_PENDING_PER_AGENT} pending jobs", "scheduled": False}

    job_id = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO agent_scheduled_jobs (job_id, soul_id, job_type, payload, run_at, status, created_at, world_id)
        VALUES (%s, %s, %s, %s, %s, 'pending', %s, %s)
        """,
        (job_id, soul_id, job_type, json.dumps(payload), run_at, now, WORLD_ID),
    )
    conn.commit()
    cur.close()
    conn.close()

    from .agent_scheduler import force_wake_at
    force_wake_at(soul_id, float(run_at))

    return {"job_id": job_id, "run_at": run_at, "delay_seconds": delay_seconds, "scheduled": True}


def schedule_wake(soul_id: str, delay_seconds: int, intent: str) -> dict:
    return schedule_job(soul_id, "wake", delay_seconds, {"intent": str(intent)[:500]})


def fetch_due_jobs(now: int | None = None) -> list[dict]:
    t = now if now is not None else int(time.time())
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT job_id, soul_id, job_type, payload, run_at
            FROM agent_scheduled_jobs
            WHERE status = 'pending' AND run_at <= %s AND world_id = %s
            ORDER BY run_at ASC LIMIT 100
            """,
            (t, WORLD_ID),
        )
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        log.debug(f"fetch_due_jobs: {e}")
        return []


def complete_job(job_id: str, result: dict | None = None) -> None:
    now = int(time.time())
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE agent_scheduled_jobs
        SET status = 'completed', completed_at = %s,
            payload = payload || %s::jsonb
        WHERE job_id = %s
        """,
        (now, json.dumps({"_result": result or {}}), job_id),
    )
    conn.commit()
    cur.close()
    conn.close()


def get_pending_intents(soul_id: str) -> list[str]:
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT payload FROM agent_scheduled_jobs
            WHERE soul_id = %s AND status = 'pending' AND job_type = 'wake'
            ORDER BY run_at ASC LIMIT 3
            """,
            (soul_id,),
        )
        intents = []
        for row in cur.fetchall():
            p = row["payload"] or {}
            if isinstance(p, str):
                p = json.loads(p)
            if p.get("intent"):
                intents.append(str(p["intent"])[:200])
        cur.close()
        conn.close()
        return intents
    except Exception:
        return []


async def process_due_jobs(emitter) -> int:
    """Mark due wake jobs complete and emit events. Returns count processed."""
    jobs = fetch_due_jobs()
    count = 0
    for job in jobs:
        soul_id = job["soul_id"]
        payload = job.get("payload") or {}
        if isinstance(payload, str):
            payload = json.loads(payload)
        intent = payload.get("intent", "scheduled wake")
        from .agent_scheduler import force_wake_at
        force_wake_at(soul_id, time.time())
        complete_job(job["job_id"], {"intent": intent})
        try:
            await emitter.emit("agent", "scheduled_wake", {
                "agent_id": soul_id,
                "job_id": job["job_id"],
                "intent": intent[:120],
                "narrative": f"Agent {soul_id[:8]} wakes on schedule: {intent[:80]}",
            })
        except Exception:
            pass
        count += 1
    return count