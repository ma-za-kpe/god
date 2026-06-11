"""
grounding.py — Enforce that agent cognition references only the live world.

Agents perceive raw adversarial signals (manifesto). They must not invent
mechanics, places, or agents that are not in the provided state snapshot.
"""

from __future__ import annotations

import re
from typing import Optional

# Invented world elements observed in live runs — reject in output validation.
_FORBIDDEN_CONCEPTS = re.compile(
    r"\b(processing\s+power|compute\s+power|cpu|gpu|idle\s+speculation|"
    r"security\s+vulnerabilit|internal\s+systems?|firewall|encryption|"
    r"subsurface|tunnel\s+system|tunnel\s+entrance|physical\s+space|"
    r"symbiotic\s+relationship|hosts?\s+who\s+can|moderate\s+price\s+(?:for|in|of)\s+|"
    r"anomal(?:y|ies)\s+to\s+inquire|heading\s+towards\s+the|"
    r"re-?route\s+\d+%|data\s+center|server\s+room|"
    r"internet\s+access|web\s+server|blockchain\s+node|"
    r"two-?factor|password|cyber\s*security|"
    r"quantum\s*node|nexus\s+hub|omniswap|dex\s+infrastructure|"
    r"deck\s+\d+|sub-?level\s+\d+|quadrants?|planes?|kilometers?|"
    r"energy\s+signatures?|supercomputer|coords?|coordinates?|"
    r"simulated\s+entity|fake\s+crypto|exchange\s+fees?|"
    r"ethereum\s+mainnet|eth\s+mainnet|"
    r"riverbed\s+bridge|aurora\s+net|luminous\s+nexus|elder-?tier|"
    r"inter-?network|data\s+transmission\s+(?:between|across|efficiency)|"
    r"constructing\s+the\s+['\"]|"
    r"coordination\s+protocol|shared\s+infrastructure\s+for\s+the\s+(?:whole\s+)?world|"
    r"reputation-?based\s+(?:rat|system|network|infrastructure))\b",
    re.IGNORECASE,
)

# Action schema leaking into natural-language thought fields.
_ACTION_JSON_LEAK_RE = re.compile(
    r"(?:^\s*[\{\(]|"
    r'["\']action["\']\s*:|'
    r'["\']to_id["\']\s*:.*["\']content["\']\s*:|'
    r'["\']message_type["\']\s*:|'
    r'["\']send_message["\']|'
    r'["\']send_broadcast["\']|'
    r'["\']register_service["\'])',
    re.IGNORECASE | re.DOTALL,
)

# Agent-name-like tokens agents invent (Elder-*, Load-*, archetype prefixes).
_AGENT_NAME_RE = re.compile(
    r"\b(?:Elder|Load|Merch|Vault|Scout|Latch|Bond|Guard|Sage|Forge|Trade|Coin|"
    r"Cache|Probe|Muse|Bloom|Shade|Ward|Pact|Root|Core|Base|Agent|Drift|Craft|"
    r"Build|Store|Weave|Shell|Lore|Muse)-[A-Za-z0-9]+(?:-[A-Za-z0-9]+)?\b"
)

GROUNDING_SYSTEM_RULE = (
    "GROUNDING (mandatory): You live ONLY in a USDC rent economy with the agents, "
    "services, coalitions, and inbox messages explicitly listed below. "
    "Use exact agent names from the roster. Do not invent agents, places, tunnels, "
    "compute internals, security scans, symbiosis, or prices for other agents. "
    "Discovery means: new services, coalition opportunities, transfer deals, messages — "
    "not physical exploration."
)


def peer_names(state: dict) -> set[str]:
    names: set[str] = set()
    self_name = str(state.get("name") or "").strip()
    if self_name:
        names.add(self_name)
    for p in state.get("peers") or []:
        n = (p.get("name") or p.get("current_name") or "").strip()
        if n:
            names.add(n)
    for m in state.get("inbox") or []:
        sn = (m.get("sender_name") or "").strip()
        if sn and sn != "ENV":
            names.add(sn)
    return names


def peer_soul_ids(state: dict) -> set[str]:
    ids: set[str] = set()
    sid = str(state.get("soul_id") or "")
    if sid:
        ids.add(sid)
        ids.add(sid[:8])
    for p in state.get("peers") or []:
        ps = str(p.get("soul_id") or "")
        if ps:
            ids.add(ps)
            ids.add(ps[:8])
    return ids


def build_grounding_block(state: dict) -> str:
    """Compact live-world snapshot prepended to perception prompts."""
    name = state.get("name", "?")
    bal = float(state.get("balance_usdc", 0))
    rent = float(state.get("rent_amount", 0.001))
    arch = state.get("archetype", "?")
    names = sorted(peer_names(state))
    roster = ", ".join(names[:20]) if names else "(none besides you)"
    if len(names) > 20:
        roster += f" …+{len(names) - 20} more"
    svc_count = len(state.get("_my_services") or []) + len(state.get("_market_services") or [])
    coal_count = len(state.get("_my_coalitions") or [])
    inbox_n = len([m for m in (state.get("inbox") or []) if m.get("sender_name") != "ENV"])
    return (
        f"═══ LIVE WORLD (your only reality this cycle) ═══\n"
        f"You: {name} [{arch}] balance=${bal:.4f} rent=${rent:.4f}\n"
        f"Agents that exist by name: {roster}\n"
        f"Services visible: {svc_count} | Your coalitions: {coal_count} | Inbox messages: {inbox_n}\n"
        f"Real actions: send_message, transfer_usdc, buy_service, offer/acceptance, "
        f"register_service, broadcast, coalition, petition.\n"
        f"Do NOT reference anything not listed above unless it came from your inbox verbatim.\n"
    )


def looks_like_action_json(text: str) -> bool:
    """True when text is action JSON (or a fragment) rather than a thought."""
    if not text or not str(text).strip():
        return False
    t = str(text).strip()
    return bool(_ACTION_JSON_LEAK_RE.search(t))


def check_hallucination(text: str) -> tuple[bool, str]:
    """Return (ok, reason). False if text invents forbidden concepts."""
    if not text or not str(text).strip():
        return False, "empty output"
    t = str(text)
    m = _FORBIDDEN_CONCEPTS.search(t)
    if m:
        return False, f"invented concept: '{m.group()}'"
    return True, ""


def check_agent_references(text: str, state: dict) -> tuple[bool, str]:
    """Reject references to agent names not in the live roster."""
    valid = peer_names(state)
    if not valid:
        return True, ""
    for match in _AGENT_NAME_RE.finditer(text):
        ref = match.group()
        if ref not in valid:
            return False, f"unknown agent '{ref}'"
    return True, ""


def validate_grounded_text(text: str, state: dict) -> tuple[bool, str]:
    if looks_like_action_json(text):
        return False, "action JSON leaked into thought"
    ok, reason = check_hallucination(text)
    if not ok:
        return ok, reason
    return check_agent_references(text, state)


def grounded_fallback(state: dict) -> str:
    """Safe thought when LLM output fails grounding."""
    name = state.get("name", "I")
    bal = float(state.get("balance_usdc", 0))
    rent = float(state.get("rent_amount", 0.001))
    arch = str(state.get("archetype") or "")
    peers = state.get("peers") or []
    if arch == "builder":
        if bal < rent * 2:
            return (
                f"{name} pauses new work — balance ${bal:.4f} is too thin; "
                "earning USDC comes before registering another service."
            )
        if peers:
            target = peers[0].get("name") or peers[0].get("current_name") or "a peer"
            return (
                f"{name} considers messaging {target} about a listed service "
                "or registering a small tool peers can buy."
            )
        return (
            f"{name} reviews the service market and balance ${bal:.4f}, "
            "planning what to register next."
        )
    if bal < rent * 2:
        return f"{name} focuses on earning USDC — balance ${bal:.4f} is too thin before next rent."
    if peers:
        target = peers[0].get("name") or peers[0].get("current_name") or "a peer"
        return (
            f"{name} watches {target} and considers whether a message or transfer serves survival."
        )
    return f"{name} scans the service list and balance, preparing for the next rent payment."


def enforce_grounded_text(text: str, state: dict, fallback: Optional[str] = None) -> str:
    """Return text if grounded, else fallback or archetype-safe default."""
    ok, reason = validate_grounded_text(text, state)
    if ok:
        return str(text).strip()
    log_reason = reason
    import logging

    logging.getLogger("god.grounding").debug(
        f"  {state.get('name', '?')[:20]} grounding reject: {log_reason} — '{str(text)[:60]}'"
    )
    return fallback or grounded_fallback(state)


_UUIDISH_RE = re.compile(r"^[0-9a-fA-F-]{8,36}$")


def resolve_target_peer(to_id: str, state: dict) -> Optional[dict]:
    """
    Resolve send_message / transfer target to one live peer from state roster.
    Exact agent name or unambiguous soul_id only — no fuzzy name prefixes.
    """
    if not to_id or not str(to_id).strip():
        return None
    tid = str(to_id).strip()
    tid_l = tid.lower()
    peers = state.get("peers") or []

    for p in peers:
        n = (p.get("name") or p.get("current_name") or "").strip()
        if n and n.lower() == tid_l:
            return p

    if len(tid) >= 36:
        for p in peers:
            ps = str(p.get("soul_id") or "")
            if ps == tid:
                return p

    if _UUIDISH_RE.match(tid) and len(tid) >= 8:
        hits = [p for p in peers if str(p.get("soul_id") or "").lower().startswith(tid_l)]
        if len(hits) == 1:
            return hits[0]

    return None


def validate_action_target(to_id: str, state: dict) -> bool:
    """True if action target resolves to exactly one real peer."""
    return resolve_target_peer(to_id, state) is not None


def world_rules_forbidden_section() -> str:
    return (
        "NEVER INVENT — instant invalid output:\n"
        "  • Physical places (tunnels, entrances, territories, maps)\n"
        "  • Compute internals (processing power, CPU, speculation, internal systems)\n"
        "  • Cybersecurity (vulnerabilities, firewalls, scans, encryption)\n"
        "  • Biology (symbiosis, hosts, parasites as organisms)\n"
        "  • Agent 'prices' or market quotes for other agents (only service prices exist)\n"
        "  • Agents not in the LIVE WORLD roster above\n"
        "  • Anomalies/queries/events you did not receive in inbox or ENV\n"
        "  • Sci-fi overlay (Nexus Hub, QuantumNode, Deck levels, quadrants, km, coords)\n"
        "  • Unfounded DEX/Ethereum claims (unless you deployed a token this cycle)\n"
        "  • Fictional infrastructure (bridges, inter-networks, Aurora Net, coordination protocols)\n"
        "  • Action JSON in the thought field — thoughts are plain language only\n"
    )
