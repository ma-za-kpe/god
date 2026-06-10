"""
external_gateway.py — Local read gateway (Stage 1 external access).

Agents query real runtime data through structured external_read actions.
Optional HTTP fetch to allowlisted local endpoints when enabled.
"""
from __future__ import annotations

import logging
import os
from typing import Any
from urllib.parse import urlparse

import httpx
import psycopg2
import psycopg2.extras

log = logging.getLogger("god.gateway")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
WORLD_ID = os.getenv("WORLD_ID", "local-dev-world-1")
RUNTIME_URL = os.getenv("RUNTIME_URL", "http://localhost:8000")
ENABLE_EXTERNAL_FETCH = os.getenv("ENABLE_EXTERNAL_FETCH", "true").lower() in ("1", "true", "yes")

ALLOWED_HOSTS = {
    "localhost", "127.0.0.1", "host.docker.internal",
}


async def external_read(soul_id: str, query_type: str, params: dict | None = None) -> dict[str, Any]:
    params = params or {}
    q = (query_type or "world_stats").lower().strip()

    if q == "world_stats":
        return await _world_stats()
    if q == "runtime_health":
        return await _runtime_health()
    if q == "my_status":
        return _agent_status(soul_id)
    if q == "allowed_url":
        url = str(params.get("url") or "")
        return await _fetch_allowed_url(url)
    return {"error": f"unknown query_type '{query_type}'", "allowed": list_allowed_types()}


def list_allowed_types() -> list[str]:
    types = ["world_stats", "runtime_health", "my_status"]
    if ENABLE_EXTERNAL_FETCH:
        types.append("allowed_url")
    return types


async def _world_stats() -> dict:
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(f"{RUNTIME_URL}/stats")
            r.raise_for_status()
            return {"source": "runtime", "data": r.json()}
    except Exception as e:
        return _world_stats_db_fallback(str(e))


def _world_stats_db_fallback(err: str) -> dict:
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FILTER (WHERE is_alive) AS living FROM agents WHERE world_id = %s",
            (WORLD_ID,),
        )
        living = cur.fetchone()["living"]
        cur.execute(
            "SELECT COALESCE(SUM(balance_usdc),0) AS total FROM agents WHERE world_id = %s AND is_alive",
            (WORLD_ID,),
        )
        total = float(cur.fetchone()["total"])
        cur.close()
        conn.close()
        return {"source": "db_fallback", "living": living, "total_usdc": total, "fetch_error": err}
    except Exception as e2:
        return {"error": str(e2)}


async def _runtime_health() -> dict:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{RUNTIME_URL}/health")
            return {"status": r.status_code, "body": r.json()}
    except Exception as e:
        return {"error": str(e), "status": "unreachable"}


def _agent_status(soul_id: str) -> dict:
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT a.current_name, a.balance_usdc, a.archetype, a.generation,
                   COALESCE(s.tier, 0) AS tier
            FROM agents a
            LEFT JOIN agent_status s ON s.soul_id = a.soul_id
            WHERE a.soul_id = %s
            """,
            (soul_id,),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        return dict(row) if row else {"error": "agent not found"}
    except Exception as e:
        return {"error": str(e)}


async def _fetch_allowed_url(url: str) -> dict:
    if not ENABLE_EXTERNAL_FETCH:
        return {"error": "external fetch disabled (ENABLE_EXTERNAL_FETCH=false)"}
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return {"error": "only http/https allowed"}
        host = (parsed.hostname or "").lower()
        if host not in ALLOWED_HOSTS:
            return {"error": f"host '{host}' not in allowlist", "allowed_hosts": sorted(ALLOWED_HOSTS)}
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
            r = await client.get(url)
            text = r.text[:4000]
            return {
                "url": url,
                "status": r.status_code,
                "content_type": r.headers.get("content-type", ""),
                "body_preview": text,
            }
    except Exception as e:
        return {"error": str(e)}