"""
registry.py — Service listing CRUD against the service_listings PostgreSQL table.
"""

import logging
import os
import uuid

import psycopg2
import psycopg2.extras

log = logging.getLogger("god.services.registry")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
WORLD_ID = os.getenv("WORLD_ID", "local-dev-world-1")


def _db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)


async def register_service(
    soul_id: str,
    name: str,
    description: str,
    price_usdc: float,
    price_model: str = "per_call",
) -> dict:
    """Register a new service listing. Returns the listing dict."""
    listing_id = str(uuid.uuid4())
    endpoint_path = f"/services/{soul_id}/{name}"

    conn = _db()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO service_listings
                (listing_id, agent_soul_id, name, description, endpoint_path, price_usdc, price_model)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (listing_id) DO NOTHING
            RETURNING listing_id, name, endpoint_path, price_usdc
            """,
            (listing_id, soul_id, name, description, endpoint_path, price_usdc, price_model),
        )
        row = cur.fetchone()
        conn.commit()
    finally:
        cur.close()
        conn.close()

    listing = (
        dict(row)
        if row
        else {
            "listing_id": listing_id,
            "name": name,
            "endpoint_path": endpoint_path,
            "price_usdc": price_usdc,
        }
    )
    log.info(f"Service registered: {soul_id[:8]} → {name} @ ${price_usdc:.4f}")
    return listing


async def deregister_service(soul_id: str, name: str) -> bool:
    """Mark a service listing inactive."""
    conn = _db()
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE service_listings SET is_active = false, updated_at = NOW() "
            "WHERE agent_soul_id = %s AND name = %s AND is_active = true",
            (soul_id, name),
        )
        affected = cur.rowcount
        conn.commit()
    finally:
        cur.close()
        conn.close()
    return affected > 0


async def increment_call_count(soul_id: str, name: str):
    """Increment calls_served counter after a successful paid call."""
    conn = _db()
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE service_listings SET calls_served = calls_served + 1, updated_at = NOW() "
            "WHERE agent_soul_id = %s AND name = %s AND is_active = true",
            (soul_id, name),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def get_service(soul_id: str, name: str) -> dict | None:
    """Fetch a single service listing (sync, for use inside route handlers)."""
    conn = _db()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT * FROM service_listings WHERE agent_soul_id = %s AND name = %s AND is_active = true",
            (soul_id, name),
        )
        row = cur.fetchone()
    finally:
        cur.close()
        conn.close()
    return dict(row) if row else None


def get_agent_wallet(soul_id: str) -> str | None:
    """Look up the wallet address for an agent (sync helper)."""
    conn = _db()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT wallet_address FROM agents WHERE soul_id = %s AND is_alive = true", (soul_id,)
        )
        row = cur.fetchone()
    finally:
        cur.close()
        conn.close()
    return row["wallet_address"] if row else None


def list_services(soul_id: str | None = None, active_only: bool = True) -> list[dict]:
    """Query the service registry. Optional filter by soul_id."""
    conn = _db()
    cur = conn.cursor()
    try:
        conditions = []
        params: list = []
        if active_only:
            conditions.append("is_active = true")
        if soul_id:
            conditions.append("agent_soul_id = %s")
            params.append(soul_id)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        cur.execute(
            f"SELECT * FROM service_listings {where} ORDER BY created_at DESC LIMIT 200",
            params,
        )
        rows = [dict(r) for r in cur.fetchall()]
    finally:
        cur.close()
        conn.close()
    return rows
