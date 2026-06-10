"""
capabilities.py — Tier-gated action surface for agent autonomy.

Actions are earned through status tier, balance, and explicit grants.
The tools menu shown to _grounded_decide is filtered per agent.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

import psycopg2
import psycopg2.extras

log = logging.getLogger("god.capabilities")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
WORLD_ID = os.getenv("WORLD_ID", "local-dev-world-1")

# capability_id -> minimum tier
TIER_CAPABILITIES: dict[int, list[str]] = {
    0: [
        "send_message", "transfer_usdc", "send_broadcast", "submit_petition",
        "write_scratch", "schedule_wake", "fork_self",
    ],
    1: ["register_service", "query_world", "external_read"],
    2: ["form_coalition", "register_tool"],
    3: ["deploy_token", "invoke_tool"],
    4: ["mutate_graph"],
    5: [],
}

ACTION_DESCRIPTIONS: dict[str, str] = {
    "send_message": (
        '"send_message" → private message; to_id, content, message_type '
        '(direct|threat|manifesto|offer|contract|propaganda). Costs $0.001.'
    ),
    "transfer_usdc": (
        '"transfer_usdc" → send USDC; to_id, amount (max 50% balance).'
    ),
    "register_service": (
        '"register_service" → list paid service; service_name, service_price, service_description.'
    ),
    "send_broadcast": (
        '"send_broadcast" → message all agents; content, message_type. Costs $0.01.'
    ),
    "form_coalition": '"form_coalition" → create alliance; coalition_name.',
    "submit_petition": (
        '"submit_petition" → request Creator action; petition_request, amount (escrow).'
    ),
    "deploy_token": '"deploy_token" → ERC-20 on local Anvil; service_name = symbol.',
    "fork_self": '"fork_self" → spawn child; costs reproduction fee.',
    "write_scratch": (
        '"write_scratch" → persist private note in your environment; '
        'scratch_key, content (max 2000 chars). Free.'
    ),
    "schedule_wake": (
        '"schedule_wake" → wake yourself after delay; delay_seconds (60–86400), intent (why).'
    ),
    "query_world": (
        '"query_world" → read internal world stats; query_type '
        '(population|economy|leaderboard|my_status).'
    ),
    "external_read": (
        '"external_read" → read through local gateway; query_type '
        '(world_stats|runtime_health|allowed_url), optional url param.'
    ),
    "register_tool": (
        '"register_tool" → register a callable tool others can buy; '
        'tool_name, tool_description, tool_cost_usdc.'
    ),
    "invoke_tool": (
        '"invoke_tool" → call a registered tool; tool_id, tool_params (object).'
    ),
    "mutate_graph": (
        '"mutate_graph" → propose self-modification; mutation_type '
        '(rename|biography|add_node|personality_bias), mutation_payload.'
    ),
}


def _db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)


def get_agent_tier(soul_id: str) -> int:
    try:
        conn = _db()
        cur = conn.cursor()
        cur.execute(
            "SELECT tier FROM agent_status WHERE soul_id = %s AND world_id = %s",
            (soul_id, WORLD_ID),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        return int(row["tier"]) if row else 0
    except Exception:
        return 0


def get_granted_capabilities(soul_id: str) -> set[str]:
    caps: set[str] = set()
    tier = get_agent_tier(soul_id)
    for t in range(tier + 1):
        caps.update(TIER_CAPABILITIES.get(t, []))
    try:
        conn = _db()
        cur = conn.cursor()
        cur.execute(
            "SELECT capability_id FROM agent_capability_grants "
            "WHERE soul_id = %s AND world_id = %s",
            (soul_id, WORLD_ID),
        )
        for row in cur.fetchall():
            caps.add(row["capability_id"])
        cur.close()
        conn.close()
    except Exception as e:
        log.debug(f"capability grants read failed: {e}")
    return caps


def grant_capability(soul_id: str, capability_id: str, via: str = "petition") -> None:
    now = int(time.time())
    conn = _db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO agent_capability_grants (soul_id, capability_id, granted_at, granted_via, world_id)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (soul_id, capability_id) DO NOTHING
        """,
        (soul_id, capability_id, now, via, WORLD_ID),
    )
    conn.commit()
    cur.close()
    conn.close()


def check_action_allowed(soul_id: str, action_type: str) -> tuple[bool, str]:
    caps = get_granted_capabilities(soul_id)
    if action_type in caps:
        return True, "ok"
    tier = get_agent_tier(soul_id)
    return False, f"capability '{action_type}' requires higher tier (current tier {tier})"


def build_tools_menu(soul_id: str) -> str:
    caps = sorted(get_granted_capabilities(soul_id))
    lines = ['═══ TOOLS YOU CAN ACTUALLY USE ═══', "Pick at most ONE action per cycle. Use null if just thinking.", ""]
    for cap in caps:
        desc = ACTION_DESCRIPTIONS.get(cap)
        if desc:
            lines.append(f"  {desc}")
    lines.append('  null → take no external action this cycle')
    lines.append("═══════════════════════════════════")
    return "\n".join(lines)


def format_capabilities_summary(soul_id: str) -> str:
    tier = get_agent_tier(soul_id)
    caps = sorted(get_granted_capabilities(soul_id))
    return f"Tier {tier} | {len(caps)} capabilities: {', '.join(caps[:12])}{'…' if len(caps) > 12 else ''}"