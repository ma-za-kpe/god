"""
tool_registry.py — World MCP catalogue + per-agent registered tools (local).

Agents discover tools at /tools, register their own via register_tool,
and invoke via invoke_tool (structured, cost-gated).
"""

from __future__ import annotations

import json
import logging
import math
import os
import time
import uuid
from typing import Any

import psycopg2
import psycopg2.extras

log = logging.getLogger("god.tools")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
WORLD_ID = os.getenv("WORLD_ID", "local-dev-world-1")
MIN_TOOL_COST_USDC = 0.000001

# Built-in local handlers agents can invoke after registering or via world tools
LOCAL_HANDLERS: dict[str, Any] = {}


def _normalize_tool_cost(cost_usdc: float) -> float:
    cost = round(float(cost_usdc), 6)
    if not math.isfinite(cost) or cost < MIN_TOOL_COST_USDC:
        raise ValueError("cost_usdc must be a positive finite value")
    return cost


def register_handler(name: str, fn) -> None:
    LOCAL_HANDLERS[name] = fn


def list_world_tools(active_only: bool = True) -> list[dict]:
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        cur = conn.cursor()
        q = "SELECT * FROM mcp_tools WHERE world_id = %s"
        if active_only:
            q += " AND is_active = true"
        cur.execute(q, (WORLD_ID,))
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        log.debug(f"list_world_tools: {e}")
        return []


def list_agent_tools(owner_soul_id: str | None = None) -> list[dict]:
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        cur = conn.cursor()
        if owner_soul_id:
            cur.execute(
                "SELECT * FROM agent_registered_tools WHERE owner_soul_id = %s AND is_active = true",
                (owner_soul_id,),
            )
        else:
            cur.execute(
                "SELECT * FROM agent_registered_tools WHERE world_id = %s AND is_active = true ORDER BY calls_served DESC LIMIT 50",
                (WORLD_ID,),
            )
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        return rows
    except Exception:
        return []


def register_agent_tool(
    owner_soul_id: str,
    name: str,
    description: str,
    cost_usdc: float = 0.001,
    handler_type: str = "echo",
) -> dict:
    cost_usdc = _normalize_tool_cost(cost_usdc)
    tool_id = str(uuid.uuid4())
    now = int(time.time())
    schema = {"type": "object", "properties": {"input": {"type": "string"}}}
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO agent_registered_tools
                (tool_id, owner_soul_id, name, description, handler_type, input_schema, cost_usdc, created_at, world_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                tool_id,
                owner_soul_id,
                name[:40],
                description[:300],
                handler_type,
                json.dumps(schema),
                cost_usdc,
                now,
                WORLD_ID,
            ),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()
    return {"tool_id": tool_id, "name": name, "cost_usdc": cost_usdc}


async def invoke_tool(caller_soul_id: str, tool_id: str, params: dict | None = None) -> dict:
    params = params or {}
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM agent_registered_tools WHERE tool_id = %s AND is_active = true",
        (tool_id,),
    )
    tool = cur.fetchone()
    if not tool:
        cur.close()
        conn.close()
        return {"error": "tool not found"}

    try:
        cost = _normalize_tool_cost(tool["cost_usdc"])
    except (TypeError, ValueError):
        cur.close()
        conn.close()
        return {"error": "invalid tool cost"}
    owner = tool["owner_soul_id"]

    if caller_soul_id != owner:
        cur.execute(
            """
            UPDATE agents
            SET balance_usdc = COALESCE(balance_usdc, 0) - %s
            WHERE soul_id = %s
              AND is_alive = true
              AND COALESCE(balance_usdc, 0) >= %s
            RETURNING balance_usdc
            """,
            (cost, caller_soul_id, cost),
        )
        debit = cur.fetchone()
        if not debit:
            conn.rollback()
            cur.close()
            conn.close()
            return {"error": "insufficient balance", "cost_usdc": cost}
        cur.execute(
            """
            UPDATE agents
            SET balance_usdc = COALESCE(balance_usdc, 0) + %s
            WHERE soul_id = %s AND is_alive = true
            RETURNING balance_usdc
            """,
            (cost * 0.9, owner),
        )
        if not cur.fetchone():
            conn.rollback()
            cur.close()
            conn.close()
            return {"error": "tool owner not found"}

    cur.execute(
        "UPDATE agent_registered_tools SET calls_served = calls_served + 1 WHERE tool_id = %s",
        (tool_id,),
    )
    conn.commit()
    cur.close()
    conn.close()

    handler = tool["handler_type"]
    if handler == "echo":
        return {"tool_id": tool_id, "result": params.get("input", params)}
    if handler in LOCAL_HANDLERS:
        try:
            result = await LOCAL_HANDLERS[handler](caller_soul_id, params)
            return {"tool_id": tool_id, "result": result}
        except Exception as e:
            return {"error": str(e)}
    return {"tool_id": tool_id, "result": params, "handler": handler}
