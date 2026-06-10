"""
db_pool.py — asyncpg connection pool for FastAPI hot paths.

Sync psycopg2 remains in background daemons; API routes use this pool.
"""

import logging
import os
from typing import Any, Optional

import asyncpg

log = logging.getLogger("god.db")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
WORLD_ID = os.getenv("WORLD_ID", "local-dev-world-1")

_pool: Optional[asyncpg.Pool] = None


async def init_pool(min_size: int = 2, max_size: int = 10) -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=min_size,
            max_size=max_size,
            command_timeout=30,
        )
        log.info(f"asyncpg pool ready (max={max_size})")
    return _pool


async def close_pool():
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        log.info("asyncpg pool closed")


async def get_pool() -> asyncpg.Pool:
    if _pool is None:
        return await init_pool()
    return _pool


def _row_to_dict(row: asyncpg.Record) -> dict[str, Any]:
    return dict(row)


async def fetch_all(query: str, *args) -> list[dict[str, Any]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *args)
        return [_row_to_dict(r) for r in rows]


async def fetch_one(query: str, *args) -> Optional[dict[str, Any]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *args)
        return _row_to_dict(row) if row else None


async def execute(query: str, *args) -> str:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.execute(query, *args)
