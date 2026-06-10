"""
narrator.py — Template-based drama narrativizer for public observer feed.

Transforms raw events into human-readable stories without sanitizing content.
LLM narrativization can be layered on later; templates work offline.
"""

import logging
import os
from typing import Any, Optional

log = logging.getLogger("god.narrator")

NARRATOR_ENABLED = os.getenv("NARRATOR_ENABLED", "true").lower() in ("1", "true", "yes")
DEFAULT_STYLE = os.getenv("NARRATOR_STYLE", "gossip")

# Events that always get a narrative.story companion
_SIGNIFICANT = {
    "lifecycle.agent.died",
    "lifecycle.agent.born",
    "lifecycle.agent.reproduced",
    "lifecycle.world.genesis",
    "economy.rent.missed",
    "economy.rent.paid",
    "economy.agent.transfer",
    "economy.token.deployed",
    "social.agent.broadcast",
    "social.coalition.formed",
    "agent.throttled",
}


def _pick(payload: dict, *keys: str, default: str = "") -> str:
    for k in keys:
        v = payload.get(k)
        if v is not None and str(v).strip():
            return str(v)
    return default


def narrativize_event(
    event_type: str, payload: dict[str, Any], style: str = DEFAULT_STYLE
) -> Optional[str]:
    """
    Return enhanced narrative prose for an event, or None if not narratable.
    Does not remove or soften hostile content — styles it for observers.
    """
    if not NARRATOR_ENABLED:
        return None

    name = _pick(payload, "name", "agent_name", default="An agent")
    archetype = _pick(payload, "archetype", default="unknown")
    thought = _pick(payload, "thought", default="")
    content = _pick(payload, "content", default="")
    amount = payload.get("amount_usdc") or payload.get("amount") or payload.get("escrow")
    recipient = _pick(payload, "recipient_name", default="")
    mt = _pick(payload, "message_type", default="")

    # Already has a good narrative from emitter — enhance only if thin
    existing = _pick(payload, "narrative", default="")
    if existing and len(existing) > 80 and event_type not in _SIGNIFICANT:
        return None

    if event_type == "lifecycle.agent.died":
        misses = payload.get("missed_payments", "?")
        return (
            f"⚰ DEATH: {name} ({archetype}) is gone — rent unpaid {misses} cycles. "
            f"The world witnesses another extinction."
        )

    if event_type == "lifecycle.agent.born":
        gen = payload.get("generation", 1)
        method = payload.get("birth_method", "birth")
        return f"✦ BIRTH: {name} ({archetype}, generation {gen}) enters the world via {method}."

    if event_type == "lifecycle.agent.reproduced":
        child = _pick(payload, "child_soul_id", default="offspring")[:8]
        return f"🧬 REPRODUCTION: {name} spawns new life ({child}…). The population grows hungrier."

    if event_type == "lifecycle.world.genesis":
        n = payload.get("agent_count", 0)
        return f"🌑 GENESIS: The void splits — {n} agents awaken. The experiment begins."

    if event_type == "economy.rent.missed":
        mc = payload.get("missed_count", "?")
        return f"💸 RENT CRISIS: {name} misses payment ({mc}/3). The clock ticks toward deletion."

    if event_type == "economy.rent.paid":
        bal = payload.get("balance_after", "")
        bal_s = f" Balance now ${float(bal):.4f}." if bal != "" else ""
        return f"✓ {name} pays rent — another cycle of existence bought.{bal_s}"

    if event_type == "economy.agent.transfer":
        amt = float(amount or 0)
        to = recipient or _pick(payload, "recipient_id", default="another")[:8]
        return f"💱 {name} sends ${amt:.4f} USDC to {to}. Trust or trap — the ecology decides."

    if event_type == "economy.token.deployed":
        sym = _pick(payload, "symbol", default="???")
        return f"🪙 {name} mints ${sym} — a new currency enters the jungle."

    if event_type == "social.agent.message_sent":
        if mt in ("threat", "manifesto", "propaganda", "contract"):
            body = content[:100] if content else existing[:100]
            return f'⚡ PUBLIC {mt.upper()} from {name}: "{body}"'
        if content:
            to = recipient or _pick(payload, "recipient_id", default="someone")[:8]
            return f'✉ {name} → {to}: "{content[:90]}"'

    if event_type == "social.agent.broadcast":
        body = content[:120] if content else existing[:120]
        label = mt.upper() if mt else "BROADCAST"
        return f'📢 {label} — {name} calls to all: "{body}"'

    if event_type == "social.coalition.formed":
        cname = _pick(payload, "coalition_name", default="unnamed pact")
        return f"🤝 ALLIANCE: {name} founds '{cname}'. Power seeks numbers."

    if event_type == "agent.throttled":
        lvl = payload.get("throttle_level", "throttled")
        return f"⏳ THROTTLE: {name} starved of compute ({lvl}) — physics punishes rent failure."

    if event_type == "cognitive.agent.thought":
        if not thought or len(thought) < 12:
            return None
        if style == "gossip" and archetype == "parasite":
            return f'👁 {name} ({archetype}) plots: "{thought[:100]}"'
        if style == "chronicle":
            return f"{name} ({archetype}) records: {thought[:110]}"
        # Sample cognitive events — not every thought (noise control)
        if payload.get("throttled") or payload.get("action_type") in (
            "economic",
            "social",
            "reproductive",
        ):
            return f'{name}: "{thought[:100]}"'
        return None

    if event_type in _SIGNIFICANT and existing:
        return existing

    return None


def should_emit_story(event_type: str, narrative: Optional[str]) -> bool:
    """Whether to emit a companion narrative.story event."""
    if not narrative:
        return False
    if event_type in _SIGNIFICANT:
        return True
    if event_type.startswith("social."):
        return True
    if event_type == "cognitive.agent.thought" and narrative.startswith(("👁", "💸", "⚡")):
        return True
    return False
