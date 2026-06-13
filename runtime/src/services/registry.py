"""
registry.py — Service listing CRUD against the service_listings PostgreSQL table.
"""

import logging
import os
import uuid

import psycopg2
import psycopg2.extras

from .client import service_resource_url

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
    listing["resource_url"] = service_resource_url(endpoint_path)
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
        if soul_id and active_only:
            sql = (
                "SELECT * FROM service_listings WHERE is_active = true "
                "AND agent_soul_id = %s ORDER BY created_at DESC LIMIT 200"
            )
        elif soul_id:
            sql = (
                "SELECT * FROM service_listings WHERE agent_soul_id = %s "
                "ORDER BY created_at DESC LIMIT 200"
            )
        elif active_only:
            sql = (
                "SELECT * FROM service_listings WHERE is_active = true "
                "ORDER BY created_at DESC LIMIT 200"
            )
        else:
            sql = "SELECT * FROM service_listings ORDER BY created_at DESC LIMIT 200"
        cur.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]
    finally:
        cur.close()
        conn.close()
    return rows


# World "cardano_market" service (gap 2 / 02-spec + 10): cheap grounded monitor for prices/positions.
# Agents discover via existing service market or query; register meta-services (signals, copy-trades)
# via register_cardano_service (uses this registry) for P&L meta-economy + ext rev to tiers.
CARDANO_WORLD_SERVICE = {
    "listing_id": "cardano_market_world",
    "agent_soul_id": None,
    "name": "cardano_market",
    "description": "Mock Cardano market (OU prices, yields, positions). Use cardano_monitor_market action or buy peer signals/copy-trades. P&L feeds rent/status.",
    "price_usdc": 0.0005,
    "is_active": True,
    "resource_url": "/world/snapshot (cardano_market key)",
}

# Note: virtual CARDANO_WORLD_SERVICE is merged in routes.list_all_services and snapshot for visibility.
# No dupe func. Existing list_services works; callers (runner fetch, UI) see cardano via explicit or routes wrapper.

# Per audit + gap2: performance history for agent-registered cardano meta-services (signals/copy-trades).
# Reputation + slash for losers. Updated on buy/settle (in economic_activity or routes).
# Lead: simple in-mem for mock; real would persist to DB.
CARDANO_META_PERF: dict[
    str, dict
] = {}  # service_name -> {"calls": int, "pnl_sum": float, "successes": int}
