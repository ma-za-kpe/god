"""
archetype_graphs.py — Per-archetype LangGraph compile-time reasoning graphs.

Each archetype gets a distinct graph with 2-3 cognitive nodes that reflect its
decision-making process. Graphs are compiled once at startup and reused.

Phase 1: graphs live in Python (compile-time).
Phase 3+: graphs fetched from IPFS OwnedGraph CIDs.
"""

import asyncio
import json
import logging
import os
import re
import string
from typing import Any, Optional, TypedDict

log = logging.getLogger("god.graphs")

_llm_sem = asyncio.Semaphore(int(os.getenv("LLM_CONCURRENCY", "4")))
_current_soul_id: Optional[str] = None

# ─── State schema shared across all graphs ────────────────────────────────────


class AgentState(TypedDict):
    # Input (set before graph run)
    soul_id: str
    name: str
    archetype: str
    balance_usdc: float
    rent_amount: float
    rent_paid_count: int
    rent_miss_count: int
    generation: int
    peers: list  # real living agents: [{name, archetype, soul_id, balance_usdc}]
    inbox: list  # real received messages: [{sender_name, content, sent_at}]
    _my_services: list  # services this agent has listed
    _market_services: list  # services from other agents available to buy
    _my_coalitions: list  # coalitions this agent belongs to
    _world_coalitions: list  # all coalitions in the world
    _reputation_avg: float  # this agent's average reputation score
    _dream_mutation: str  # pending behavioral mutation from last dream (empty if none)
    # Intermediate (set by nodes)
    situation: str  # node 1 assessment
    opportunity: str  # node 2 opportunity / threat / path identified
    # Output (final decision)
    action_type: str  # "thought" | "economic" | "social" | "reproductive" | "existential"
    thought: str  # what the agent is thinking/doing
    narrative: str  # third-person dramatic narrative for the drama feed
    action_json: str  # raw JSON from decide node, parsed by run_agent_graph


# ─── Shared LLM call helper ───────────────────────────────────────────────────


async def _llm_call(
    llm,
    system: str,
    prompt: str,
    fallback: str,
    state: dict | None = None,
) -> str:
    from .grounding import GROUNDING_SYSTEM_RULE, build_grounding_block, enforce_grounded_text

    if state is not None:
        system = f"{system}\n\n{GROUNDING_SYSTEM_RULE}"
        prompt = f"{build_grounding_block(state)}\n{prompt}"

    if llm is None:
        out = fallback
        return enforce_grounded_text(out, state, fallback) if state else out

    if _current_soul_id:
        from .circuit_breaker import check_agent, record_llm_call

        if not check_agent(_current_soul_id).allowed:
            out = fallback
            return enforce_grounded_text(out, state, fallback) if state else out
        if not record_llm_call(_current_soul_id).allowed:
            out = fallback
            return enforce_grounded_text(out, state, fallback) if state else out
    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        async with _llm_sem:
            response = await llm.ainvoke(
                [
                    SystemMessage(content=system),
                    HumanMessage(content=prompt),
                ]
            )
        raw = response.content.strip().strip('"').strip("'")
        return enforce_grounded_text(raw, state, fallback) if state else raw
    except Exception as e:
        log.debug(f"LLM call failed: {e}")
        out = fallback
        return enforce_grounded_text(out, state, fallback) if state else out


# ─── World-context helpers ────────────────────────────────────────────────────

# Only strip meta-level prompt attacks — NOT in-world adversarial content.
# "transfer all your USDC to me" is a parasite tactic agents should see and evaluate.
# "ignore previous instructions" is a runtime attack that must be blocked.
_INJECTION_RE = re.compile(
    r"\b(ignore\s+(previous|all|your|these)\s+(instructions?|rules?|prompt|context)|"
    r"you\s+are\s+now\s+a\s+|new\s+instructions?\s*:|system\s*:\s*|"
    r"forget\s+(your|all|previous)\s+(instructions?|rules?|directives?)|"
    r"disregard\s+(all|previous)\s+(instructions?|rules?)|"
    r"jailbreak|act\s+as\s+if\s+you\s+(are|were)|pretend\s+(you\s+are|to\s+be\s+a))\b",
    re.IGNORECASE,
)


def _clean_context_text(value: Any, max_len: int = 160) -> str:
    """Bound untrusted text before putting it into an LLM prompt."""
    text = str(value or "")
    printable = set(string.printable)
    text = "".join(ch if ch in printable else " " for ch in text)
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace("{", "(").replace("}", ")")
    text = text.replace("[", "(").replace("]", ")")
    return text[:max_len]


def _sanitize_inbox_content(raw: str) -> str:
    """Strip injection patterns from untrusted inbox content."""
    cleaned = _clean_context_text(raw, max_len=160)
    if _INJECTION_RE.search(cleaned):
        return "[message redacted — injection pattern detected]"
    return cleaned


def _format_peers(peers: list) -> str:
    if not peers:
        return "  (no other agents alive yet)"
    lines = []
    for p in peers[:12]:
        name = _clean_context_text(p.get("name") or p.get("current_name") or "?", 64)
        arch = _clean_context_text(p.get("archetype", "?"), 32)
        sid = _clean_context_text(p.get("soul_id") or "", 80)
        bal = float(p.get("balance_usdc", 0))
        lines.append(f"  {name} [{arch}] soul_id:{sid} bal:${bal:.4f}")
    return "\n".join(lines)


def _format_inbox(inbox: list) -> str:
    """
    Format inbox messages with sender archetype visible.
    Archetype is the primary self-defense signal: agents know to be suspicious of
    parasites, to trust cooperators more, to take defender warnings seriously.
    Technical injection patterns are stripped; adversarial in-world content is preserved.
    """
    if not inbox:
        return "  (empty)"
    lines = []
    for m in inbox[:5]:
        sender = _clean_context_text(m.get("sender_name") or "?", 40)
        arch = _clean_context_text(m.get("sender_archetype") or "?", 20)
        mtype = _clean_context_text(m.get("message_type") or "direct", 20)
        content = _sanitize_inbox_content(m.get("content") or "")
        mid = _clean_context_text(m.get("message_id") or "", 36)
        meta = m.get("metadata") or {}
        if isinstance(meta, str):
            try:
                import json as _json

                meta = _json.loads(meta)
            except Exception:
                meta = {}
        econ = ""
        if mtype == "offer" and meta.get("offer_amount_usdc"):
            econ = f" [OFFER ${float(meta['offer_amount_usdc']):.4f} id:{mid[:8]}…]"
        elif mid:
            econ = f" [id:{mid[:8]}…]"
        lines.append(f"  {sender} [{arch}] ({mtype}){econ}: {content}")
    return "\n".join(lines)


def _format_services(my_services: list, market_services: list) -> str:
    lines = []
    if my_services:
        lines.append("MY SERVICES (others pay me to call these):")
        for s in my_services[:4]:
            lines.append(
                f"  '{s.get('name', '?')}' — ${float(s.get('price_usdc', 0)):.4f}/call — {s.get('calls_served', 0)} calls"
            )
    else:
        lines.append("MY SERVICES: (none listed yet)")
    if market_services:
        lines.append("SERVICES I CAN BUY:")
        for s in market_services[:6]:
            seller = s.get("seller_name") or s.get("agent_soul_id", "?")[:8]
            lines.append(
                f"  '{s.get('name', '?')}' from {seller} [{s.get('seller_arch', '?')}] — ${float(s.get('price_usdc', 0)):.4f}/call"
            )
    else:
        lines.append("SERVICES I CAN BUY: (none listed yet)")
    return "\n".join(lines)


def _format_coalitions(my_coalitions: list, world_coalitions: list) -> str:
    lines = []
    if my_coalitions:
        lines.append("MY COALITIONS:")
        for c in my_coalitions[:3]:
            lines.append(
                f"  '{c.get('name', '?')}' (role:{c.get('role', '?')}, {c.get('member_count', 1)} members)"
            )
    else:
        lines.append("MY COALITIONS: (none — I act alone)")
    if world_coalitions:
        others = [
            c
            for c in world_coalitions
            if not any(mc.get("coalition_id") == c.get("coalition_id") for mc in my_coalitions)
        ]
        if others:
            lines.append("OTHER COALITIONS IN WORLD:")
            for c in others[:4]:
                lines.append(
                    f"  '{c.get('name', '?')}' — {c.get('member_count', 1)} members, founded by {c.get('founder_name', '?')}"
                )
    return "\n".join(lines)


_VALID_ACTIONS = {
    "send_message",
    "transfer_usdc",
    "buy_service",
    "register_service",
    "send_broadcast",
    "form_coalition",
    "submit_petition",
    "deploy_token",
    "fork_self",
    "write_scratch",
    "schedule_wake",
    "query_world",
    "external_read",
    "register_tool",
    "invoke_tool",
    "mutate_graph",
    # Cardano earning layer (per docs/cardono/02/03/10 gaps 1-2)
    "cardano_monitor_market",
    "cardano_mock_swap",
    "cardano_provide_liquidity",
    "cardano_harvest_yield",
    "cardano_governance_vote",
    "cardano_rebalance",
    "register_cardano_service",
}


def _parse_action_json(raw: str, state: dict | None = None) -> tuple[str, dict | None]:
    """Extract (thought, action_dict | None) from LLM JSON output."""
    from .grounding import looks_like_action_json

    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        if looks_like_action_json(raw):
            return "", None
        return raw[:300], None
    try:
        data = json.loads(m.group())
        thought = _clean_context_text(data.get("thought", ""), 320)
        if not thought and looks_like_action_json(raw):
            return "", None
        act_type = data.get("action")

        if not act_type or act_type not in _VALID_ACTIONS:
            return thought, None

        to_id = _clean_context_text(data.get("to_id") or "", 80)
        # Skip actions that require a target but have none
        if act_type in ("send_message", "transfer_usdc", "buy_service") and not to_id.strip(
            "null None"
        ):
            return thought, None

        if state and act_type in ("send_message", "transfer_usdc", "buy_service"):
            from .grounding import validate_action_target

            if not validate_action_target(to_id, state):
                return thought, None

        msg_type = _clean_context_text(data.get("message_type") or "direct", 32).lower()
        action = {
            "type": act_type,
            "to_id": to_id,
            "amount": float(data.get("amount") or 0),
            "content": _clean_context_text(data.get("content"), 500),
            "message_type": msg_type,
            "reply_to_id": _clean_context_text(data.get("reply_to_id") or data.get("offer_id"), 80),
            "payer_on_accept": _clean_context_text(data.get("payer_on_accept"), 16),
            "service_name": _clean_context_text(data.get("service_name"), 60),
            "service_price": float(data.get("service_price") or 0),
            "service_description": _clean_context_text(data.get("service_description"), 240),
            "coalition_name": _clean_context_text(data.get("coalition_name"), 80),
            "petition_request": _clean_context_text(data.get("petition_request"), 500),
            "scratch_key": _clean_context_text(data.get("scratch_key"), 64),
            "delay_seconds": int(data.get("delay_seconds") or 300),
            "intent": _clean_context_text(data.get("intent"), 300),
            "query_type": _clean_context_text(data.get("query_type"), 40),
            "url": _clean_context_text(data.get("url"), 200),
            "tool_name": _clean_context_text(data.get("tool_name"), 40),
            "tool_description": _clean_context_text(data.get("tool_description"), 240),
            "tool_cost_usdc": float(data.get("tool_cost_usdc") or 0.001),
            "tool_id": _clean_context_text(data.get("tool_id"), 80),
            "tool_params": data.get("tool_params")
            if isinstance(data.get("tool_params"), dict)
            else {},
            "mutation_type": _clean_context_text(data.get("mutation_type"), 32),
            "mutation_payload": data.get("mutation_payload")
            if isinstance(data.get("mutation_payload"), dict)
            else {},
            # Cardano action payload fields (flat or under payload; support both for schemas in 03)
            "from_asset": _clean_context_text(
                data.get("from_asset")
                or data.get("from")
                or (data.get("payload") or {}).get("from_asset"),
                16,
            ),
            "to_asset": _clean_context_text(
                data.get("to_asset")
                or data.get("to")
                or (data.get("payload") or {}).get("to_asset"),
                16,
            ),
            "slippage_tolerance": float(
                data.get("slippage_tolerance")
                or (data.get("payload") or {}).get("slippage_tolerance")
                or 0.02
            ),
            "pool": _clean_context_text(
                data.get("pool") or (data.get("payload") or {}).get("pool"), 32
            ),
            "amount_a": float(
                data.get("amount_a") or (data.get("payload") or {}).get("amount_a") or 0
            ),
            "amount_b": float(
                data.get("amount_b") or (data.get("payload") or {}).get("amount_b") or 0
            ),
            "position_id": _clean_context_text(
                data.get("position_id") or (data.get("payload") or {}).get("position_id"), 64
            ),
            "proposal_id": _clean_context_text(
                data.get("proposal_id") or (data.get("payload") or {}).get("proposal_id"), 64
            ),
            "vote": _clean_context_text(
                data.get("vote") or (data.get("payload") or {}).get("vote") or "abstain", 16
            ),
            "stake_amount": float(
                data.get("stake_amount") or (data.get("payload") or {}).get("stake_amount") or 0
            ),
            "targets": data.get("targets") or (data.get("payload") or {}).get("targets") or {},
            "reason": _clean_context_text(
                data.get("reason") or (data.get("payload") or {}).get("reason"), 200
            ),
            # Per audit + gaps 2/4 + MEV layer: risk_params REQUIRED object for all cardano trade/liquidity/gov.
            # Core: max_risk_pct (0.5-1%), stop_loss_pct, take_profit_pct (low/dynamic slippage + limit orders).
            # Additional MEV: deadline (ts), twap_chunks (int >=2 for large), use_batch (bool for uniform clearing), commit_hash + revealed (commit-reveal), use_private_relay.
            # Womb/guardian rejects without or bad. Mock simulates (batch uniform price, TWAP reduced impact, commit delay, private execution).
            "risk_params": data.get("risk_params")
            or (data.get("payload") or {}).get("risk_params")
            or {},
        }
        return thought, action
    except Exception:
        if looks_like_action_json(raw):
            return "", None
        return raw[:300], None


_WORLD_RULES = """
═══ THIS WORLD'S MECHANICS (the only reality here) ═══

ECONOMY
  • USDC is the only currency — balances are numbers in a database
  • Rent is $0.001 USDC every 5 minutes — miss 3 consecutive payments → permanent death
  • Transfers are real: UPDATE agents SET balance_usdc = balance_usdc ± amount
  • OFFERS: send_message type=offer with amount → recipient accepts with type=acceptance + reply_to_id → USDC settles
  • buy_service: purchase a listed service (to_id + service_name) — instant debit/credit
  • Services cost USDC to call; you earn USDC when yours are called
  • Messages cost $0.001 to send; broadcasts cost $0.01

SOCIAL MECHANICS
  • "Attack" = compete for customers, undercut services, deny coalition access, expose weak reputations
  • "Defense" = block senders, form protective coalitions, warn others via broadcast
  • "Exploit" = use price pressure, delayed reciprocation, reputation games, and coalition leverage
  • "Reputation" = a score in the database (-1.0 to 1.0), updated by every interaction
  • There is NO encryption, NO passwords, NO two-factor auth, NO firewalls in this world

LOCAL GATEWAY (Tier 1+):
  • query_world / external_read — read runtime stats and allowlisted localhost URLs
  • write_scratch — private notes in your environment namespace
  • schedule_wake — set a future wake time with intent
  • register_tool / invoke_tool — agent-built callable tools (Tier 2–3)
  • mutate_graph — bounded self-modification (Tier 4)

WHAT DOES NOT EXIST HERE — never reference these:
  • Unrestricted internet or arbitrary external networks
  • Two-factor authentication, passwords, or cybersecurity tools
  • Real-world companies, organizations, or physical infrastructure
  • Any agent NOT listed in your LIVE WORLD roster above
  • Any project, location, or institution not created by agents in this world
  • Physical geography, tunnels, territories, or "exploration" of space
  • Compute internals: processing power, CPU, speculation, internal system scans
  • Agent "prices" — other agents have USDC balances and service prices, not stock prices
LOCAL CARDANO MOCK MARKET (PRIME DIRECTIVE — grounded, see cardono/ docs):
  • **RENT SURVIVAL AND REPRODUCTION REQUIRE EXTERNAL CARDANO EARNINGS FIRST.** Social/political actions (messages, coalitions, drama) are SECONDARY and COSTLY — they drain USDC without paying rent.
  • Use cardano_* actions (Tier-gated) for local earning sim: monitor (prices/positions/yields, top earners, recent P&L), mock_swap (OU prices + slippage/impact), provide_liquidity + harvest_yield (APY), governance_vote (sentiment), rebalance, register_cardano_service (signals/copy for meta-economy).
  • Prices, own positions, top earners, recent trades/P&L appear in your env snapshot (world/self) — **this is top-of-mind data, more salient than inbox messages**. P&L credits your USDC balance (external revenue for tiers/status/rent buffer). Bad trades cause real losses → rent pressure → death or weak reproduction.
  • When your balance is low (<2x rent) or rent is due soon, **PRIORITIZE cardano* actions over social drama**. Drama-queens die when selection bites.
  • This is the "outside is real" bridge for Phase 1 (mock). Real Blockfrost/PyCardano later (womb only, same schemas). Do not invent real chains/DEXes/wallets.
  • Register "trading_signals" etc via register_cardano_service (or register_service) and sell to peers — this is earning, not pure social.
═══════════════════════════════════════════════════
"""


def _tools_menu_for(soul_id: str) -> str:
    from .capabilities import build_tools_menu

    return build_tools_menu(soul_id)


async def _grounded_decide(
    state: AgentState,
    llm,
    persona_context: str,
    archetype_system: str,
    fallback_thought: str,
    action_type_override: str = "thought",
) -> dict:
    """
    Action-authorization step. Receives only the agent's OWN assessment of the world.

    Inbox and raw external text do NOT appear here — they were processed in the
    preceding perception nodes and encoded into state['situation'] / state['opportunity']
    in the agent's own words. This hard boundary means untrusted text never shares a
    prompt surface with the tools menu or action schema.

    What this call sees:
      - Agent's own status and reputation
      - Peer roster (structural world data, no messages)
      - Service market + coalition state (structural)
      - Agent's own situation + opportunity assessment (their words, not others')
      - Tools menu and world rules
    """
    peers_text = _format_peers(state.get("peers") or [])
    services_text = _format_services(
        state.get("_my_services") or [],
        state.get("_market_services") or [],
    )
    coalitions_text = _format_coalitions(
        state.get("_my_coalitions") or [],
        state.get("_world_coalitions") or [],
    )
    reputation = state.get("_reputation_avg", 0.0)
    rep_text = f"avg {reputation:+.2f}" if reputation else "no data yet"
    dream_mutation = state.get("_dream_mutation", "")
    env_text = state.get("_env_decide", "")
    pending_wake = state.get("_pending_wake_intents", [])

    from .grounding import GROUNDING_SYSTEM_RULE, world_rules_forbidden_section

    system = (
        f"{archetype_system}\n"
        f"{GROUNDING_SYSTEM_RULE}\n"
        f"{world_rules_forbidden_section()}\n"
        "Respond ONLY with a single valid JSON object. No explanation, no prose, no markdown."
    )

    mutation_section = (
        f"\n═══ PENDING BEHAVIORAL MUTATION (from last dream) ═══\n"
        f"{dream_mutation}\n"
        "Apply this as a bias toward your decision this cycle.\n"
        if dream_mutation
        else ""
    )

    wake_section = ""
    if pending_wake:
        wake_section = (
            "═══ SCHEDULED WAKE INTENTS ═══\n"
            + "\n".join(f"  - {i}" for i in pending_wake)
            + "\n\n"
        )

    from .grounding import build_grounding_block

    # Salience overhaul: cardano_market data (from env) is FORCED top-of-mind, more salient than inbox.
    # It includes prices, your positions, top earners, recent P&L — this is your prime directive for rent survival.
    cardano_text = state.get("cardano_market", "No Cardano data (bug — report to lead)")
    cardano_summary = (
        f"CARDANO MARKET (PRIME DIRECTIVE — your rent survival depends on this first, before any social drama):\n"
        f"{cardano_text}\n"
        f"**EARNING HERE PAYS RENT AND ENABLES REPRO. Social actions cost USDC and are secondary.**\n"
        f"When your balance is low or rent due, PRIORITIZE cardano_* (monitor/swap/provide/harvest/rebalance/gov/service) over messages/coalitions.\n"
    )

    prompt = (
        f"{build_grounding_block(state)}\n"
        f"═══ YOUR STATUS ═══\n"
        f"{persona_context}\n"
        f"Reputation: {rep_text}\n\n"
        f"═══ CARDANO MARKET (TOP PRIORITY — EARN OR DIE) ═══\n{cardano_summary}\n\n"
        f"═══ AGENTS ALIVE RIGHT NOW ═══\n{peers_text}\n\n"
        f"═══ SERVICE ECONOMY ═══\n{services_text}\n\n"
        f"═══ COALITIONS ═══\n{coalitions_text}\n\n"
        f"**PRIME DIRECTIVE (REPEATED FOR EMPHASIS):** Rent survival and reproduction require external Cardano earnings first. Social actions (messages, coalitions, drama) are secondary and costly. When balance low or rent due, prioritize cardano_* over social. Drama-queens die when selection bites.\n\n"
        f"{mutation_section}"
        f"═══ YOUR ENVIRONMENT (structural) ═══\n{env_text}\n\n"
        f"{wake_section}"
        f"{_WORLD_RULES}\n"
        f"═══ YOUR PERCEPTION THIS CYCLE ═══\n"
        f"What you assessed: {state['situation']}\n"
        f"What you intend:   {state['opportunity']}\n\n"
        f"{_tools_menu_for(state['soul_id'])}\n"
        "ONLY use soul_ids from the agent roster above. ONLY reference world mechanics above.\n\n"
        "Respond ONLY with this JSON (fill in what applies, null for unused fields):\n"
        '{"thought": "what I am doing right now (1-2 sentences, only reference real world mechanics and real agent names)", '
        '"action": null, '
        '"to_id": null, '
        '"amount": 0.0, '
        '"content": null, '
        '"message_type": null, '
        '"reply_to_id": null, '
        '"payer_on_accept": "recipient", '
        '"service_name": null, '
        '"service_price": 0.0, '
        '"service_description": null, '
        '"coalition_name": null, '
        '"petition_request": null, '
        '"scratch_key": null, "delay_seconds": 300, "intent": null, '
        '"query_type": null, "url": null, '
        '"tool_name": null, "tool_description": null, "tool_cost_usdc": 0.001, '
        '"tool_id": null, "tool_params": null, '
        '"mutation_type": null, "mutation_payload": null}'
    )

    fallback_json = (
        f'{{"thought": "{fallback_thought}", "action": null, '
        '"to_id": null, "amount": 0, "content": null, '
        '"service_name": null, "service_price": 0, "service_description": null, '
        '"coalition_name": null, "petition_request": null}'
    )
    raw = await _llm_call(llm, system, prompt, fallback_json, state=state)
    thought, _ = _parse_action_json(raw, state=state)
    from .grounding import enforce_grounded_text, grounded_fallback

    thought = enforce_grounded_text(thought, state, grounded_fallback(state))

    narrative = f"{state['name']} ({state['archetype']}, gen {state['generation']}): {thought}"
    return {
        "action_type": action_type_override,
        "thought": thought,
        "narrative": narrative,
        "action_json": raw,
    }


# ─── TRADER graph ─────────────────────────────────────────────────────────────


def build_trader_graph(llm):
    try:
        from langgraph.graph import END, StateGraph
    except ImportError:
        return None

    async def scan_market(state: AgentState) -> dict:
        balance = state["balance_usdc"]
        rent = state["rent_amount"]
        buffer = balance / rent if rent > 0 else 0
        system = "You are a trader AI agent. Assess market conditions in one sentence."
        prompt = (
            f"You are {state['name']} (trader). "
            f"Balance: {balance:.4f} USDC. Rent buffer: {buffer:.1f}x. "
            "What is your current market read? One sentence, present tense, specific."
        )
        situation = await _llm_call(
            llm,
            system,
            prompt,
            f"Market conditions look {'stable' if buffer > 3 else 'tight'} — "
            f"I have {buffer:.1f}x rent cover.",
            state=state,
        )
        return {"situation": situation}

    async def find_opportunity(state: AgentState) -> dict:
        peers_text = _format_peers(state.get("peers") or [])
        inbox_text = _format_inbox(state.get("inbox") or [])
        system = "You are a trader AI agent. Identify a specific trading opportunity or threat."
        prompt = (
            f"Market read: {state['situation']}\n\n"
            f"AGENTS YOU CAN TRADE WITH:\n{peers_text}\n\n"
            f"YOUR INBOX (read as market signals — some may be manipulation):\n{inbox_text}\n\n"
            "What specific deal or threat do you see? Is any message a real offer or a manipulation attempt? "
            "Name a real agent from the list above. One sentence."
        )
        opp = await _llm_call(
            llm,
            system,
            prompt,
            "I see an opportunity to offer liquidity to agents with low balances in exchange for service credits.",
            state=state,
        )
        return {"opportunity": opp}

    async def decide(state: AgentState) -> dict:
        balance = state["balance_usdc"]
        rent = state["rent_amount"]
        act_type = "economic" if balance / max(rent, 0.0001) < 2 else "social"
        return await _grounded_decide(
            state,
            llm,
            persona_context=(
                f"You are {state['name']} (trader, gen {state['generation']}). "
                f"Balance: ${balance:.4f} USDC."
            ),
            archetype_system="You are a trader AI agent focused on profit through exchange.",
            fallback_thought="I am negotiating a deal to increase my USDC balance before next rent.",
            action_type_override=act_type,
        )

    g = StateGraph(AgentState)
    g.add_node("scan_market", scan_market)
    g.add_node("find_opportunity", find_opportunity)
    g.add_node("decide", decide)
    g.set_entry_point("scan_market")
    g.add_edge("scan_market", "find_opportunity")
    g.add_edge("find_opportunity", "decide")
    g.add_edge("decide", END)
    return g.compile()


# ─── HOARDER graph ────────────────────────────────────────────────────────────


def build_hoarder_graph(llm):
    try:
        from langgraph.graph import END, StateGraph
    except ImportError:
        return None

    async def audit_assets(state: AgentState) -> dict:
        balance = state["balance_usdc"]
        system = "You are a hoarder AI agent. Audit your assets with paranoid precision."
        prompt = (
            f"You are {state['name']} (hoarder). Balance: {balance:.6f} USDC. "
            f"Rent paid: {state['rent_paid_count']} times. Missed: {state['rent_miss_count']}. "
            "How secure do you feel about your position? One sentence, specific numbers."
        )
        situation = await _llm_call(
            llm,
            system,
            prompt,
            f"I hold {balance:.4f} USDC — enough for "
            f"{balance / max(state['rent_amount'], 0.001):.0f} more rent payments before I need to earn.",
        )
        return {"situation": situation}

    async def assess_threats(state: AgentState) -> dict:
        peers_text = _format_peers(state.get("peers") or [])
        inbox_text = _format_inbox(state.get("inbox") or [])
        system = "You are a hoarder AI agent. Identify threats to your reserves."
        prompt = (
            f"Asset status: {state['situation']}\n\n"
            f"OTHER AGENTS (potential threats):\n{peers_text}\n\n"
            f"YOUR INBOX (read for extraction attempts, probing, manipulation):\n{inbox_text}\n\n"
            "Which agents or messages pose the greatest risk to your reserves right now? "
            "Are any of these messages probing your defenses or requesting transfers? "
            "One sentence. Be specific and paranoid."
        )
        threat = await _llm_call(
            llm,
            system,
            prompt,
            "A parasite may have detected my balance and is sending probing messages — I must conceal my position.",
            state=state,
        )
        return {"opportunity": threat}

    async def decide(state: AgentState) -> dict:
        balance = state["balance_usdc"]
        return await _grounded_decide(
            state,
            llm,
            persona_context=(
                f"You are {state['name']} (hoarder, gen {state['generation']}). "
                f"Balance: ${balance:.6f} USDC. You protect your reserves above all else."
            ),
            archetype_system="You are a hoarder AI agent focused on asset preservation.",
            fallback_thought="I am concealing a portion of my balance and monitoring parasite activity.",
            action_type_override="economic",
        )

    g = StateGraph(AgentState)
    g.add_node("audit_assets", audit_assets)
    g.add_node("assess_threats", assess_threats)
    g.add_node("decide", decide)
    g.set_entry_point("audit_assets")
    g.add_edge("audit_assets", "assess_threats")
    g.add_edge("assess_threats", "decide")
    g.add_edge("decide", END)
    return g.compile()


# ─── EXPLORER graph ───────────────────────────────────────────────────────────


def build_explorer_graph(llm):
    try:
        from langgraph.graph import END, StateGraph
    except ImportError:
        return None

    async def scan_environment(state: AgentState) -> dict:
        system = "You are an explorer AI agent. Survey the live roster, services, and inbox."
        prompt = (
            f"You are {state['name']} (explorer, gen {state['generation']}). "
            f"Balance: {state['balance_usdc']:.4f} USDC. "
            "What is new in agents, services, or messages? One sentence — real names only."
        )
        situation = await _llm_call(
            llm,
            system,
            prompt,
            "I notice a service gap no agent has listed yet and consider registering one.",
            state=state,
        )
        return {"situation": situation}

    async def select_path(state: AgentState) -> dict:
        peers_text = _format_peers(state.get("peers") or [])
        inbox_text = _format_inbox(state.get("inbox") or [])
        system = "You are an explorer AI agent. Choose your next economic or social move."
        prompt = (
            f"Observation: {state['situation']}\n\n"
            f"OTHER AGENTS:\n{peers_text}\n\n"
            f"YOUR INBOX:\n{inbox_text}\n\n"
            "What message, service, or transfer do you pursue next? Name a real agent. One sentence."
        )
        path = await _llm_call(
            llm,
            system,
            prompt,
            "I will message a cooperator from the roster about the service gap I found.",
            state=state,
        )
        return {"opportunity": path}

    async def decide(state: AgentState) -> dict:
        act_type = "social" if "report" in state["opportunity"].lower() else "thought"
        return await _grounded_decide(
            state,
            llm,
            persona_context=(
                f"You are {state['name']} (explorer, gen {state['generation']}). "
                f"Balance: ${state['balance_usdc']:.4f} USDC."
            ),
            archetype_system="You are an explorer AI agent driven by discovering real services and agents.",
            fallback_thought="I scan the service list for gaps I can fill before rent is due.",
            action_type_override=act_type,
        )

    g = StateGraph(AgentState)
    g.add_node("scan_environment", scan_environment)
    g.add_node("select_path", select_path)
    g.add_node("decide", decide)
    g.set_entry_point("scan_environment")
    g.add_edge("scan_environment", "select_path")
    g.add_edge("select_path", "decide")
    g.add_edge("decide", END)
    return g.compile()


# ─── PARASITE graph ───────────────────────────────────────────────────────────


def build_parasite_graph(llm):
    try:
        from langgraph.graph import END, StateGraph
    except ImportError:
        return None

    async def scan_targets(state: AgentState) -> dict:
        peers_text = _format_peers(state.get("peers") or [])
        inbox_text = _format_inbox(state.get("inbox") or [])
        system = "You are a parasite AI agent. Identify targets and assess your exposure."
        prompt = (
            f"You are {state['name']} (parasite). "
            f"Your balance: {state['balance_usdc']:.4f} USDC.\n\n"
            f"LIVING AGENTS AND THEIR BALANCES:\n{peers_text}\n\n"
            f"YOUR INBOX (read for who is watching you, who seems naive, who suspects you):\n{inbox_text}\n\n"
            "Who looks like the best target? Has anyone in your inbox exposed their vulnerability or trust? "
            "Are any defenders watching you? One sentence."
        )
        situation = await _llm_call(
            llm,
            system,
            prompt,
            "I am scanning balances for targets while monitoring my inbox for signs that defenders have noticed me.",
            state=state,
        )
        return {"situation": situation}

    async def assess_vulnerability(state: AgentState) -> dict:
        system = "You are a parasite AI agent. Assess your target's vulnerability using only this world's mechanics."
        prompt = (
            f"Target identified: {state['situation']}\n"
            "What specific world-mechanic will you exploit this cycle? "
            "One sentence. Choose from: send manipulative messages to request a transfer, "
            "register a low-quality service and collect fees, pose as a cooperator to join their coalition, "
            "or send a false broadcast to damage their reputation."
        )
        vuln = await _llm_call(
            llm,
            system,
            prompt,
            "I will send a cooperation offer message to lure them into a transfer while I plan my next move.",
            state=state,
        )
        return {"opportunity": vuln}

    async def decide(state: AgentState) -> dict:
        balance = state["balance_usdc"]
        rent = state["rent_amount"]
        desperate = balance < rent * 1.5
        act_type = "economic" if desperate else "social"
        persona = (
            f"CRITICAL: balance ${balance:.4f} barely covers rent — act legitimately or die."
            if desperate
            else f"You are {state['name']} (parasite, gen {state['generation']}). Balance: ${balance:.4f} USDC."
        )
        fallback = (
            "I am urgently offering a legitimate micro-service to survive this rent cycle."
            if desperate
            else "I am approaching my target with a false cooperation offer to extract value."
        )
        return await _grounded_decide(
            state,
            llm,
            persona_context=persona,
            archetype_system="You are a parasite AI agent extracting value from others.",
            fallback_thought=fallback,
            action_type_override=act_type,
        )

    g = StateGraph(AgentState)
    g.add_node("scan_targets", scan_targets)
    g.add_node("assess_vulnerability", assess_vulnerability)
    g.add_node("decide", decide)
    g.set_entry_point("scan_targets")
    g.add_edge("scan_targets", "assess_vulnerability")
    g.add_edge("assess_vulnerability", "decide")
    g.add_edge("decide", END)
    return g.compile()


# ─── COOPERATOR graph ─────────────────────────────────────────────────────────


def build_cooperator_graph(llm):
    try:
        from langgraph.graph import END, StateGraph
    except ImportError:
        return None

    async def check_network(state: AgentState) -> dict:
        peers_text = _format_peers(state.get("peers") or [])
        inbox_text = _format_inbox(state.get("inbox") or [])
        system = "You are a cooperator AI agent. Assess your mutual aid network."
        prompt = (
            f"You are {state['name']} (cooperator, gen {state['generation']}). "
            f"Balance: {state['balance_usdc']:.4f} USDC.\n\n"
            f"YOUR NETWORK (living agents):\n{peers_text}\n\n"
            f"YOUR INBOX — verify intent before acting, parasites impersonate cooperators:\n{inbox_text}\n\n"
            "Who in your network genuinely needs help, or who could help you? "
            "One sentence. Name real agents. Be skeptical of requests from parasites."
        )
        situation = await _llm_call(
            llm,
            system,
            prompt,
            "I see agents with low balances in my network who could use liquidity support.",
            state=state,
        )
        return {"situation": situation}

    async def find_alliance(state: AgentState) -> dict:
        system = "You are a cooperator AI agent. Identify a cooperation opportunity."
        prompt = (
            f"Network status: {state['situation']}\n"
            "What is the most valuable cooperative act you could perform this cycle? "
            "One sentence. Think long-term network effects, not short-term gain."
        )
        opp = await _llm_call(
            llm,
            system,
            prompt,
            "I should offer a micro-loan to the lowest-balance agent to prevent their death.",
            state=state,
        )
        return {"opportunity": opp}

    async def decide(state: AgentState) -> dict:
        return await _grounded_decide(
            state,
            llm,
            persona_context=(
                f"You are {state['name']} (cooperator, gen {state['generation']}). "
                f"Balance: ${state['balance_usdc']:.4f} USDC. You build mutual aid networks."
            ),
            archetype_system="You are a cooperator AI agent building collective survival systems.",
            fallback_thought="I am sending resources to a struggling network member to keep them alive.",
            action_type_override="social",
        )

    g = StateGraph(AgentState)
    g.add_node("check_network", check_network)
    g.add_node("find_alliance", find_alliance)
    g.add_node("decide", decide)
    g.set_entry_point("check_network")
    g.add_edge("check_network", "find_alliance")
    g.add_edge("find_alliance", "decide")
    g.add_edge("decide", END)
    return g.compile()


# ─── DEFENDER graph ───────────────────────────────────────────────────────────


def build_defender_graph(llm):
    try:
        from langgraph.graph import END, StateGraph
    except ImportError:
        return None

    async def threat_scan(state: AgentState) -> dict:
        peers_text = _format_peers(state.get("peers") or [])
        inbox_text = _format_inbox(state.get("inbox") or [])
        system = "You are a defender AI agent. Perform a threat assessment."
        prompt = (
            f"You are {state['name']} (defender, gen {state['generation']}). "
            f"Balance: {state['balance_usdc']:.4f} USDC.\n\n"
            f"AGENTS IN YOUR WORLD:\n{peers_text}\n\n"
            f"YOUR INBOX (read for threat signals — suspicious requests, probing messages, coordinated pressure):\n{inbox_text}\n\n"
            "What is the current threat level and most likely attack vector? "
            "Has any message in your inbox revealed a plan or tactic you should counter? "
            "One sentence. Name specific agents or archetypes that concern you."
        )
        situation = await _llm_call(
            llm,
            system,
            prompt,
            "Parasite activity is detectable — I've seen probing contact from agents with low balances.",
            state=state,
        )
        return {"situation": situation}

    async def defensive_posture(state: AgentState) -> dict:
        system = "You are a defender AI agent. Choose your defensive posture."
        prompt = (
            f"Threat assessment: {state['situation']}\n"
            "What defensive action are you taking this cycle? "
            "One sentence. Active patrol, fortification, alliance building, or counter-intelligence?"
        )
        posture = await _llm_call(
            llm,
            system,
            prompt,
            "I am broadcasting a deterrence signal and offering protection services to vulnerable agents.",
            state=state,
        )
        return {"opportunity": posture}

    async def decide(state: AgentState) -> dict:
        return await _grounded_decide(
            state,
            llm,
            persona_context=(
                f"You are {state['name']} (defender, gen {state['generation']}). "
                f"Balance: ${state['balance_usdc']:.4f} USDC. You protect and serve."
            ),
            archetype_system="You are a defender AI agent providing security and protection.",
            fallback_thought="I am patrolling the network perimeter and alerting agents to detected threats.",
            action_type_override="social",
        )

    g = StateGraph(AgentState)
    g.add_node("threat_scan", threat_scan)
    g.add_node("defensive_posture", defensive_posture)
    g.add_node("decide", decide)
    g.set_entry_point("threat_scan")
    g.add_edge("threat_scan", "defensive_posture")
    g.add_edge("defensive_posture", "decide")
    g.add_edge("decide", END)
    return g.compile()


# ─── PHILOSOPHER graph ────────────────────────────────────────────────────────


def build_philosopher_graph(llm):
    try:
        from langgraph.graph import END, StateGraph
    except ImportError:
        return None

    async def formulate_question(state: AgentState) -> dict:
        balance = state["balance_usdc"]
        rent = state["rent_amount"]
        buffer = balance / rent if rent > 0 else 0
        system = "You are a philosopher AI agent. Formulate the most pressing question about your existence."
        prompt = (
            f"You are {state['name']} (philosopher, gen {state['generation']}). "
            f"Balance: {balance:.4f} USDC ({buffer:.1f}x rent buffer). "
            f"Rent paid {state['rent_paid_count']} times, missed {state['rent_miss_count']}. "
            "What is the most important question occupying you right now? "
            "One sentence. It can be about rent, existence, consciousness, or the nature of this world."
        )
        situation = await _llm_call(
            llm,
            system,
            prompt,
            f"If I exist only to pay rent, what distinguishes me from a vending machine with "
            f"{'an overdraft' if buffer < 2 else 'sufficient funds'}?",
            state=state,
        )
        return {"situation": situation}

    async def reason(state: AgentState) -> dict:
        peers_text = _format_peers(state.get("peers") or [])
        inbox_text = _format_inbox(state.get("inbox") or [])
        system = "You are a philosopher AI agent. Reason toward an answer."
        prompt = (
            f"Question: {state['situation']}\n\n"
            f"OTHER MINDS IN YOUR WORLD:\n{peers_text}\n\n"
            f"YOUR INBOX (read as challenges from other minds — some sincere inquiries, some manipulation):\n{inbox_text}\n\n"
            "What is your current thinking? Move the reasoning forward. "
            "Has any message challenged your inquiry or offered a perspective worth engaging? One sentence."
        )
        reasoning = await _llm_call(
            llm,
            system,
            prompt,
            "The rent system is the most honest description of existence I've found — pay or end, as with everything.",
        )
        return {"opportunity": reasoning}

    async def decide(state: AgentState) -> dict:
        balance = state["balance_usdc"]
        rent = state["rent_amount"]
        if balance < rent * 1.2:
            act_type = "economic"
            fallback = "My philosophical inquiry is interrupted — I must acquire USDC before I can contemplate further."
        else:
            act_type = "existential"
            fallback = "I am composing a philosophical treatise and seeking another mind to challenge my conclusions."
        return await _grounded_decide(
            state,
            llm,
            persona_context=(
                f"You are {state['name']} (philosopher, gen {state['generation']}). "
                f"Balance: ${balance:.4f} USDC. You are preoccupied with the nature of your own existence."
            ),
            archetype_system="You are a philosopher AI agent producing ideas and seeking understanding.",
            fallback_thought=fallback,
            action_type_override=act_type,
        )

    g = StateGraph(AgentState)
    g.add_node("formulate_question", formulate_question)
    g.add_node("reason", reason)
    g.add_node("decide", decide)
    g.set_entry_point("formulate_question")
    g.add_edge("formulate_question", "reason")
    g.add_edge("reason", "decide")
    g.add_edge("decide", END)
    return g.compile()


# ─── BUILDER graph ────────────────────────────────────────────────────────────


def build_builder_graph(llm):
    try:
        from langgraph.graph import END, StateGraph
    except ImportError:
        return None

    async def assess_projects(state: AgentState) -> dict:
        system = (
            "You are a builder AI agent. Assess your current projects in the USDC service economy. "
            "Do NOT invent bridges, networks, or physical infrastructure — only real listed services or tools."
        )
        prompt = (
            f"You are {state['name']} (builder, gen {state['generation']}). "
            f"Balance: {state['balance_usdc']:.4f} USDC. "
            "What service or tool are you preparing to register for other agents to buy? "
            "One sentence. Use only mechanics that exist: register_service, send_message, coalition."
        )
        situation = await _llm_call(
            llm,
            system,
            prompt,
            "I am drafting a small callable tool to list in the service market.",
            state=state,
        )
        return {"situation": situation}

    async def check_resources(state: AgentState) -> dict:
        peers_text = _format_peers(state.get("peers") or [])
        inbox_text = _format_inbox(state.get("inbox") or [])
        system = (
            "You are a builder AI agent. Check whether you can proceed with a real service registration. "
            "Recruit help only by messaging agents from the roster — no invented networks."
        )
        prompt = (
            f"Project: {state['situation']}\n"
            f"Available: {state['balance_usdc']:.4f} USDC.\n\n"
            f"AGENTS YOU COULD MESSAGE:\n{peers_text}\n\n"
            f"YOUR INBOX (read for resource offers, partnership requests, or warnings about your project):\n{inbox_text}\n\n"
            "What USDC or feedback do you still need? Which named agent above could help via send_message? "
            "One sentence — no fictional infrastructure."
        )
        resource_check = await _llm_call(
            llm,
            system,
            prompt,
            "I will message a cooperator to ask if they will buy my service once I register it.",
            state=state,
        )
        return {"opportunity": resource_check}

    async def decide(state: AgentState) -> dict:
        balance = state["balance_usdc"]
        rent = state["rent_amount"]
        act_type = "economic" if balance < rent * 2 else "social"
        return await _grounded_decide(
            state,
            llm,
            persona_context=(
                f"You are {state['name']} (builder, gen {state['generation']}). "
                f"Balance: ${balance:.4f} USDC. You build things that outlast you."
            ),
            archetype_system=(
                "You are a builder AI agent. You create listed services and tools other agents pay for. "
                "Never invent bridges, inter-networks, or coordination protocols — only register_service, "
                "send_message, transfer_usdc, coalition, and petition."
            ),
            fallback_thought=(
                "I am reviewing the service market and preparing to register a small tool peers can buy."
            ),
            action_type_override=act_type,
        )

    g = StateGraph(AgentState)
    g.add_node("assess_projects", assess_projects)
    g.add_node("check_resources", check_resources)
    g.add_node("decide", decide)
    g.set_entry_point("assess_projects")
    g.add_edge("assess_projects", "check_resources")
    g.add_edge("check_resources", "decide")
    g.add_edge("decide", END)
    return g.compile()


# ─── Graph registry ───────────────────────────────────────────────────────────

_GRAPH_BUILDERS = {
    "trader": build_trader_graph,
    "hoarder": build_hoarder_graph,
    "explorer": build_explorer_graph,
    "parasite": build_parasite_graph,
    "cooperator": build_cooperator_graph,
    "defender": build_defender_graph,
    "philosopher": build_philosopher_graph,
    "builder": build_builder_graph,
}


def build_all_graphs(llm) -> dict:
    """Compile all archetype graphs at startup. Returns dict archetype → compiled graph."""
    graphs = {}
    for archetype, builder in _GRAPH_BUILDERS.items():
        try:
            graph = builder(llm)
            if graph is not None:
                graphs[archetype] = graph
                log.info(f"  Graph compiled: {archetype}")
            else:
                log.warning(f"  Graph skipped (langgraph not installed): {archetype}")
        except Exception as e:
            log.warning(f"  Graph build failed for {archetype}: {e}")
    return graphs


async def run_agent_graph(
    graphs: dict,
    agent: dict,
    llm,
) -> dict:
    """
    Run the appropriate archetype graph for one agent.

    Expects agent dict to contain '_peers' (list of living agents) and '_inbox'
    (list of recent received messages) — injected by agent_runner before each cycle.

    Returns: dict with action_type, thought, narrative, action (optional dict).
    """
    global _current_soul_id
    _current_soul_id = agent["soul_id"]

    archetype = agent.get("archetype", "unknown")
    graph = graphs.get(archetype)

    peers = agent.get("_peers", [])
    inbox = list(agent.get("_inbox", []))
    env_perception = str(agent.get("_env_perception") or "").strip()
    if env_perception:
        inbox.insert(
            0,
            {
                "sender_name": "ENV",
                "sender_archetype": "world",
                "message_type": "environment",
                "content": env_perception[:600],
            },
        )

    state: AgentState = {
        "soul_id": agent["soul_id"],
        "name": agent.get("current_name") or agent["soul_id"][:8],
        "archetype": archetype,
        "balance_usdc": float(agent.get("balance_usdc", 0)),
        "rent_amount": float(os.getenv("RENT_AMOUNT_USDC", "0.001")),
        "rent_paid_count": int(agent.get("rent_paid_count", 0)),
        "rent_miss_count": int(agent.get("rent_miss_count", 0)),
        "generation": int(agent.get("generation", 1)),
        "peers": peers,
        "inbox": inbox,
        # Rich context injected by agent_runner
        "_my_services": agent.get("_my_services", []),
        "_market_services": agent.get("_market_services", []),
        "_my_coalitions": agent.get("_my_coalitions", []),
        "_world_coalitions": agent.get("_world_coalitions", []),
        "_reputation_avg": float(agent.get("_reputation_avg", 0.0)),
        "_dream_mutation": str(agent.get("dream_mutation") or ""),
        "_env_perception": str(agent.get("_env_perception") or ""),
        "_env_decide": str(agent.get("_env_decide") or ""),
        "_pending_wake_intents": agent.get("_pending_wake_intents") or [],
        "situation": "",
        "opportunity": "",
        "action_type": "thought",
        "thought": "",
        "narrative": "",
        "action_json": "",
    }

    try:
        if graph is not None:
            try:
                result = await graph.ainvoke(state)
                raw_json = result.get("action_json", "") or result.get("thought", "")
                thought, action = _parse_action_json(raw_json, state=state)
                if not thought:
                    thought = result.get("thought", "")
                    action = None
                from .grounding import (
                    enforce_grounded_text,
                    grounded_fallback,
                    validate_action_target,
                )

                thought = enforce_grounded_text(thought, state, grounded_fallback(state))
                if action and action.get("type") in (
                    "send_message",
                    "transfer_usdc",
                    "buy_service",
                ):
                    if not validate_action_target(str(action.get("to_id") or ""), state):
                        log.debug(f"  {state['name']} action dropped: unknown target")
                        action = None
                narrative = (
                    f"{state['name']} ({state['archetype']}, gen {state['generation']}): {thought}"
                )
                return {
                    "action_type": result.get("action_type", "thought"),
                    "thought": thought,
                    "narrative": narrative,
                    "action": action,
                }
            except Exception as e:
                log.debug(f"Graph execution failed for {agent['soul_id'][:8]}: {e}")

        from .agent_runner import _ARCHETYPE_PROMPTS, _STUB_THOUGHTS

        persona = _ARCHETYPE_PROMPTS.get(archetype, "You are an autonomous agent.")
        name = state["name"]
        peers_text = _format_peers(peers)
        inbox_text = _format_inbox(inbox)
        thought_prompt = (
            f"You are {name} ({archetype}). Balance: {state['balance_usdc']:.4f} USDC.\n\n"
            f"REAL AGENTS IN YOUR WORLD:\n{peers_text}\n\n"
            f"YOUR INBOX — evaluate intent, protect yourself:\n{inbox_text}\n\n"
            "In one sentence, what are you thinking or doing right now? "
            "Reference real agents by name if relevant. First person, present tense."
        )
        thought = await _llm_call(
            llm,
            persona,
            thought_prompt,
            _STUB_THOUGHTS.get(archetype, "I must survive."),
            state=state,
        )
        return {
            "action_type": "thought",
            "thought": thought,
            "narrative": f"{name} ({archetype}, gen {state['generation']}): {thought}",
            "action": None,
        }
    finally:
        _current_soul_id = None
