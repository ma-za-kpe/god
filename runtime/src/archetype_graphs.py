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

# ─── BanterEngine lazy singleton ──────────────────────────────────────────────

_banter_engine_instance = None
_banter_engine_lock = asyncio.Lock()


async def _get_banter_engine():
    """Lazy-initialize the BanterEngine singleton with existing project dependencies.

    Uses db_pool for RelationshipMemory, environment-based model routing,
    and the default fallback template pool.
    """
    global _banter_engine_instance
    if _banter_engine_instance is not None:
        return _banter_engine_instance

    async with _banter_engine_lock:
        # Double-check after acquiring lock
        if _banter_engine_instance is not None:
            return _banter_engine_instance

        try:
            from .banter.engine import BanterEngine
            from .banter.anti_repetition import AntiRepetitionGate
            from .banter.fallback_pool import FallbackPool
            from .banter.model_router import ModelRouter
            from .banter.move_selector import compute_distribution
            from .banter.pacing_controller import PacingController
            from .banter.quality_judge import evaluate as quality_evaluate
            from .banter.relationship_memory import RelationshipMemory
            from .banter.scene_context import SceneContext
        except ImportError:
            from banter.engine import BanterEngine
            from banter.anti_repetition import AntiRepetitionGate
            from banter.fallback_pool import FallbackPool
            from banter.model_router import ModelRouter
            from banter.move_selector import compute_distribution
            from banter.pacing_controller import PacingController
            from banter.quality_judge import evaluate as quality_evaluate
            from banter.relationship_memory import RelationshipMemory
            from banter.scene_context import SceneContext

        # Initialize components with existing project dependencies
        fallback_pool = FallbackPool.from_json_file()
        relationship_memory = RelationshipMemory()  # will lazy-connect via db_pool
        scene_context = SceneContext()
        model_router = ModelRouter()  # auto-configures from env vars
        pacing_controller = PacingController()
        anti_repetition = AntiRepetitionGate()

        _banter_engine_instance = BanterEngine(
            quality_judge=quality_evaluate,
            move_selector=compute_distribution,
            fallback_pool=fallback_pool,
            relationship_memory=relationship_memory,
            scene_context=scene_context,
            model_router=model_router,
            pacing_controller=pacing_controller,
            anti_repetition=anti_repetition,
        )
        log.info("BanterEngine initialized successfully")
        return _banter_engine_instance


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
    _recent_sent: list  # last N messages this agent sent — used to prevent repetition
    _conv_thread: list  # last N sent+received messages in chrono order — conversation context
    arc_theme: str  # current showrunner debate theme (may be absent — always use .get())
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
    try:
        from .grounding import GROUNDING_SYSTEM_RULE, build_grounding_block, enforce_grounded_text
    except ImportError:  # pragma: no cover - flat test path
        from grounding import GROUNDING_SYSTEM_RULE, build_grounding_block, enforce_grounded_text

    if state is not None:
        system = f"{system}\n\n{GROUNDING_SYSTEM_RULE}"
        prompt = f"{build_grounding_block(state)}\n{prompt}"

    if llm is None:
        out = fallback
        return enforce_grounded_text(out, state, fallback) if state else out

    if _current_soul_id:
        try:
            from .circuit_breaker import check_agent, record_llm_call
        except ImportError:  # pragma: no cover - flat test path
            from circuit_breaker import check_agent, record_llm_call

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
}


def _parse_action_json(raw: str, state: dict | None = None) -> tuple[str, dict | None]:
    """Extract (thought, action_dict | None) from LLM JSON output."""
    try:
        from .grounding import looks_like_action_json
    except ImportError:  # pragma: no cover - flat test path
        from grounding import looks_like_action_json

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
            try:
                from .grounding import validate_action_target
            except ImportError:  # pragma: no cover - flat test path
                from grounding import validate_action_target

            if not validate_action_target(to_id, state):
                return thought, None

        msg_type = _clean_context_text(data.get("message_type") or "direct", 32).lower()
        action = {
            "type": act_type,
            "to_id": to_id,
            "amount": float(data.get("amount") or 0),
            "content": _clean_context_text(data.get("content"), 500),
            "message_type": msg_type,
            "move": _clean_context_text(data.get("move"), 24),
            "reply_to_id": _clean_context_text(data.get("reply_to_id") or data.get("offer_id"), 80),
            "cadence": _clean_context_text(data.get("cadence"), 24),
            "backchannel": _clean_context_text(data.get("backchannel"), 40),
            "callback": _clean_context_text(data.get("callback"), 160),
            "beat_count": _clean_context_text(data.get("beat_count"), 8),
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
        }
        return thought, action
    except Exception:
        if looks_like_action_json(raw):
            return "", None
        return raw[:300], None


def _extract_json_text_field(raw: str, field: str, max_len: int = 500) -> str:
    m = re.search(r"\{.*\}", raw or "", re.DOTALL)
    if not m:
        return ""
    try:
        data = json.loads(m.group())
    except Exception:
        return ""
    return _clean_context_text(data.get(field), max_len)


def _build_agent_state(agent: dict) -> AgentState:
    """Build the normalized state payload used by both slow and fast lanes."""
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

    return {
        "soul_id": agent["soul_id"],
        "name": agent.get("current_name") or agent["soul_id"][:8],
        "archetype": agent.get("archetype", "unknown"),
        "balance_usdc": float(agent.get("balance_usdc", 0)),
        "rent_amount": float(os.getenv("RENT_AMOUNT_USDC", "0.001")),
        "rent_paid_count": int(agent.get("rent_paid_count", 0)),
        "rent_miss_count": int(agent.get("rent_miss_count", 0)),
        "generation": int(agent.get("generation", 1)),
        "peers": peers,
        "inbox": inbox,
        "_my_services": agent.get("_my_services", []),
        "_market_services": agent.get("_market_services", []),
        "_my_coalitions": agent.get("_my_coalitions", []),
        "_world_coalitions": agent.get("_world_coalitions", []),
        "_reputation_avg": float(agent.get("_reputation_avg", 0.0)),
        "_dream_mutation": str(agent.get("dream_mutation") or ""),
        "_env_perception": str(agent.get("_env_perception") or ""),
        "_env_decide": str(agent.get("_env_decide") or ""),
        "_pending_wake_intents": agent.get("_pending_wake_intents") or [],
        "_recent_sent": agent.get("_recent_sent") or [],
        "_conv_thread": agent.get("_conv_thread") or [],
        "arc_theme": str(agent.get("arc_theme") or ""),
        "situation": "",
        "opportunity": "",
        "action_type": "thought",
        "thought": "",
        "narrative": "",
        "action_json": "",
    }


def _normalize_result(
    state: AgentState, result: dict, fallback_action_type: str = "thought"
) -> dict:
    """Normalize raw graph output into the contract used by the runtime."""
    raw_json = result.get("action_json", "") or result.get("thought", "")
    thought, action = _parse_action_json(raw_json, state=state)
    if not thought:
        thought = result.get("thought", "")
        action = None
    try:
        from .grounding import enforce_grounded_text, grounded_fallback, validate_action_target
    except ImportError:  # pragma: no cover - flat test path
        from grounding import enforce_grounded_text, grounded_fallback, validate_action_target

    thought = enforce_grounded_text(thought, state, grounded_fallback(state))
    if action and action.get("type") in ("send_message", "transfer_usdc", "buy_service"):
        if not validate_action_target(str(action.get("to_id") or ""), state):
            log.debug(f"  {state['name']} action dropped: unknown target")
            action = None
    narrative = f"{state['name']} ({state['archetype']}, gen {state['generation']}): {thought}"
    return {
        "action_type": result.get("action_type", fallback_action_type),
        "thought": thought,
        "narrative": narrative,
        "action": action,
    }


def _normalize_reactive_result(
    state: AgentState,
    result: dict,
    *,
    fallback_thought: str,
    fallback_action_type: str = "social",
) -> dict:
    """Normalize fast reply output without flattening the actual dialogue line."""
    thought = str(result.get("thought") or fallback_thought).strip() or fallback_thought
    action = result.get("action")
    if action is None and result.get("action_json"):
        raw_json = result.get("action_json", "")
        _, action = _parse_action_json(raw_json, state=state)

    narrative = f"{state['name']} ({state['archetype']}, gen {state['generation']}): {thought}"
    return {
        "action_type": result.get("action_type", fallback_action_type),
        "thought": thought,
        "narrative": narrative,
        "action": action,
    }


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
  • External crypto markets (ETH, BTC, DeFi, Ethereum price, exchanges)
  • Real-world companies, organizations, or physical infrastructure
  • Any agent NOT listed in your LIVE WORLD roster above
  • Any project, location, or institution not created by agents in this world
  • Physical geography, tunnels, territories, or "exploration" of space
  • Compute internals: processing power, CPU, speculation, internal system scans
  • Agent "prices" — other agents have USDC balances and service prices, not stock prices
═══════════════════════════════════════════════════
"""

_REACTIVE_GENERIC_THOUGHTS = {
    "I answer directly and keep the exchange moving.",
    "I hear you. What are you really trying to prove here?",
    "I answer Beta directly.",
}

_REACTIVE_BACKCHANNELS = {
    "defender": "No.",
    "hoarder": "Not for free.",
    "parasite": "Useful.",
    "philosopher": "Maybe.",
    "cooperator": "Exactly.",
    "trader": "Good. Name the cost.",
    "explorer": "Show me.",
    "builder": "Then build it.",
}

_REACTIVE_MOVE_STYLES = {
    "COUNTER": [
        "That claim does not survive contact with the facts: {hook}",
        "You are skipping the hard part, which is exactly why I reject it: {hook}",
    ],
    "ESCALATE": [
        "If you want escalation, then answer this first: {hook}",
        "Fine. Let us raise the stakes and name what you are protecting: {hook}",
    ],
    "DEFLECT": [
        "You are aiming at the wrong target, because the real question is: {hook}",
        "That misses the point, and the point is still waiting on: {hook}",
    ],
    "TAUNT": [
        "That is a weak line, and you know it. Try this instead: {hook}",
        "You can do better than that. The room is waiting for: {hook}",
    ],
    "QUESTION": [
        "Then answer me this: {hook}",
        "If you mean that seriously, explain: {hook}",
    ],
    "PIVOT": [
        "Fine, then let us frame it around the debate itself: {hook}",
        "We are drifting away from the core issue, which is still: {hook}",
    ],
}


def _pick_reactive_move(archetype: str, message_text: str, recent_sent: list[dict]) -> str:
    arch = (archetype or "").lower()
    if arch == "defender":
        return "COUNTER"
    if arch in ("philosopher", "cooperator"):
        return "QUESTION"
    if arch == "parasite":
        return "TAUNT" if "?" not in message_text else "PIVOT"
    if arch == "builder":
        return "DEFLECT"
    if recent_sent and len(recent_sent) >= 2:
        return "ESCALATE"
    return "COUNTER" if "?" in message_text else "QUESTION"


def _short_clause(text: str, *, max_words: int = 12) -> str:
    cleaned = _clean_context_text(text or "", 180)
    if not cleaned:
        return ""
    clauses = [piece.strip(" ,;:-") for piece in re.split(r"[.!?;:]+", cleaned) if piece.strip()]
    if not clauses:
        clauses = [cleaned]
    clauses.sort(key=lambda piece: (len(piece), piece.count(" ")), reverse=True)
    clause = clauses[0]
    words = clause.split()
    if len(words) > max_words:
        clause = " ".join(words[:max_words])
    return clause.strip(" ,;:-")


_PROMPTISH_TOKENS = {
    "agent",
    "agents",
    "soul",
    "reply_to_id",
    "message_id",
    "thought",
    "action",
    "move",
    "callback",
    "cadence",
    "beat",
    "beats",
}

_REACTIVE_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "be",
    "but",
    "can",
    "do",
    "does",
    "for",
    "from",
    "how",
    "i",
    "if",
    "in",
    "is",
    "it",
    "may",
    "mean",
    "of",
    "on",
    "or",
    "should",
    "that",
    "the",
    "their",
    "then",
    "to",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
}


_CUT_OFF_ENDINGS = {
    "a",
    "an",
    "and",
    "are",
    "at",
    "be",
    "because",
    "but",
    "by",
    "do",
    "does",
    "for",
    "from",
    "if",
    "in",
    "is",
    "it",
    "its",
    "not",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "these",
    "this",
    "those",
    "to",
    "was",
    "were",
    "while",
    "with",
    "without",
}


def _looks_cut_off_fragment(text: str) -> bool:
    cleaned = _clean_context_text(text or "", 180)
    if not cleaned:
        return True
    words = re.findall(r"[A-Za-z0-9']+", cleaned.lower())
    if len(words) < 3:
        return False
    if cleaned[-1] not in ".!?":
        last = words[-1]
        if last in _CUT_OFF_ENDINGS:
            return True
        if len(words) <= 8 and words[-2] in {
            "does",
            "do",
            "is",
            "are",
            "was",
            "were",
            "can",
            "could",
            "will",
            "would",
        }:
            return True
    return False


def _looks_promptish_fragment(text: str) -> bool:
    cleaned = _clean_context_text(text or "", 180)
    if not cleaned:
        return True
    low = cleaned.lower()
    words = re.findall(r"[A-Za-z0-9']+", low)
    if not words:
        return True
    if any(
        token in low for token in ("/", "reply_to_id", "message_id", "thought:", "action:", "move:")
    ):
        return True
    if any(token in words for token in _PROMPTISH_TOKENS):
        return True
    if low.startswith(
        ("what ", "should ", "can ", "who ", "why ", "how ", "if you ", "if we ", "if i ")
    ):
        return True
    if cleaned.endswith("?") and len(words) > 4:
        return True
    if len(words) > 8 and sum(1 for word in words if word[:1].isupper()) >= 2:
        return True
    if _looks_cut_off_fragment(cleaned):
        return True
    return False


def _best_reactive_fragment(text: str, *, max_words: int = 10) -> str:
    cleaned = _clean_context_text(text or "", 220)
    if not cleaned:
        return ""
    candidates = [
        piece.strip(" ,;:-") for piece in re.split(r"[.!?;:,]+", cleaned) if piece.strip()
    ]
    if not candidates:
        candidates = [cleaned]
    multi_clause = len(candidates) > 1

    best = ""
    best_score = -1
    for candidate in candidates:
        clause = _clean_context_text(candidate, 180).strip(" ,;:-")
        if not clause or _looks_promptish_fragment(clause):
            continue
        if _looks_cut_off_fragment(clause):
            continue
        words = re.findall(r"[A-Za-z0-9']+", clause.lower())
        if len(words) < 2:
            continue
        if not multi_clause and len(words) > max_words:
            continue
        if len(words) > max_words:
            clause = " ".join(clause.split()[:max_words]).strip(" ,;:-")
            words = re.findall(r"[A-Za-z0-9']+", clause.lower())
        content_words = [word for word in words if word not in _REACTIVE_STOPWORDS]
        score = len(content_words) * 2 + len(words)
        if "?" in candidate or "!" in candidate:
            score += 1
        if score > best_score:
            best = clause
            best_score = score
    return best


def _is_near_duplicate_fragment(fragment: str, bucket: list[dict] | None) -> bool:
    frag = _clean_context_text(fragment or "", 180).lower()
    if not frag or not bucket:
        return False
    frag_words = [
        word for word in re.findall(r"[A-Za-z0-9']+", frag) if word not in _REACTIVE_STOPWORDS
    ]
    if len(frag_words) < 3:
        return False
    frag_set = set(frag_words)
    for msg in bucket:
        other = _clean_context_text(msg.get("content") or "", 180).lower()
        if not other:
            continue
        if frag in other or other in frag:
            return True
        other_words = [
            word for word in re.findall(r"[A-Za-z0-9']+", other) if word not in _REACTIVE_STOPWORDS
        ]
        if len(other_words) < 3:
            continue
        other_set = set(other_words)
        overlap = len(frag_set & other_set) / max(1, min(len(frag_set), len(other_set)))
        if overlap >= 0.75:
            return True
    return False


def _theme_focus_fragment(theme: str) -> str:
    text = _clean_context_text(theme or "", 120)
    if not text:
        return ""
    words = re.findall(r"[A-Za-z0-9']+", text)
    if not words:
        return ""
    content_words = [
        word
        for word in words
        if word.lower() not in _REACTIVE_STOPWORDS
        and word.lower() not in {"mean", "means", "cannot", "can't", "won't"}
    ]
    if not content_words:
        content_words = words
    if len(content_words) > 4:
        content_words = content_words[:4]
    text = " ".join(content_words).strip(" ,;:-")
    if _looks_promptish_fragment(text):
        return ""
    return text


_BANTER_LOOP_GUIDELINES = (
    "Pure snark gets old: mix in micro-moments of sincerity, frustration, longing, doubt, hurt, or fear before snapping back.",
    "Let Hoarders briefly admit fear of loss; let Cooperators sound genuinely hurt by betrayal; keep vulnerability short and character-specific.",
    "Shape rhythm like conversation: short jabs, longer builds, backchannels, overlaps, soft laughs, pregnant pauses, and satisfying callbacks.",
    "Let pacing breathe in waves of intensity followed by reflective beats; never make every line rapid-fire.",
    "Tie every debate to the ma-za-kpe ecology: scarcity, cooperation, rent, survival, patronage as divine intervention, or sleeping through change.",
    "Make silly arguments echo bigger truths; hoarding versus sharing should reveal economics, not just jokes.",
    "Prefer quotable, clipable lines that reward long-time viewers with callbacks while staying clear to first-time viewers.",
    "Use the GOD meta layer sparingly: the Veil, the Swarm, chat, and patron gods are watching, so make it dramatic.",
    "Aim for ancient cosmic beings arguing for millennia who suddenly realize a live audience can influence their fate.",
    "Witty but never shallow; chaotic but never incoherent; personal but never small; rewatchable because relationships feel real.",
)

_BANTER_LOOP_CHECK_TEXT = "\n".join(f"- {guideline}" for guideline in _BANTER_LOOP_GUIDELINES)

_BANTER_LOOP_PASSES = (
    "sharpness",
    "emotion",
    "rhythm",
    "theme",
    "shareable",
    "meta",
    "character",
)


def _extract_callback_fragment(
    message_text: str,
    conv_thread: list[dict] | None = None,
    recent_sent: list[dict] | None = None,
    arc_theme: str = "",
) -> str:
    banned_phrases = (
        "answer this",
        "what you are missing",
        "the part that matters",
        "the room only holds",
        "only if",
        "show me",
        "exactly",
        "useful",
        "good name the cost",
        "the real issue",
        "i hear you",
        "what are you really trying to prove here",
        "keep the exchange moving",
    )
    candidates: list[str] = [message_text or ""]
    theme_fragment = _theme_focus_fragment(arc_theme) if arc_theme else ""
    if theme_fragment:
        candidates.append(theme_fragment)
    for candidate in candidates:
        frag = _best_reactive_fragment(candidate, max_words=10)
        if not frag:
            continue
        if _looks_promptish_fragment(frag):
            continue
        if _looks_cut_off_fragment(frag):
            continue
        low = frag.lower()
        if len(low.split()) <= 1 and low in {
            "useful",
            "exactly",
            "maybe",
            "good",
            "fine",
            "no",
            "yes",
        }:
            continue
        if low in {
            "i hear you",
            "what are you really trying to prove here",
            "i answer directly and keep the exchange moving",
        }:
            continue
        if any(phrase in low for phrase in banned_phrases):
            continue
        if len(frag) < 10:
            continue
        if _looks_repetitive_text(frag):
            continue
        return frag
    return ""


def _banter_profile(
    archetype: str,
    move: str,
    message_text: str,
    conv_thread: list[dict] | None = None,
    recent_sent: list[dict] | None = None,
    arc_theme: str = "",
) -> dict[str, str]:
    arch = (archetype or "").lower()
    callback = _extract_callback_fragment(message_text, conv_thread, recent_sent, arc_theme)
    backchannel = _REACTIVE_BACKCHANNELS.get(arch, "")
    cadence = "short" if move in {"COUNTER", "TAUNT", "QUESTION"} else "medium"
    if arch in {"philosopher", "cooperator"}:
        cadence = "build" if move in {"QUESTION", "PIVOT"} else "medium"
    if len(callback.split()) >= 10:
        cadence = "build"
    if recent_sent and len(recent_sent) >= 3:
        cadence = "callback"
    if move == "ESCALATE":
        cadence = "build"
    return {
        "cadence": cadence,
        "backchannel": backchannel,
        "callback": callback,
        "beat_count": "2" if cadence in {"short", "medium"} else "3",
    }


def _compose_reactive_banter(
    sender_name: str,
    sender_arch: str,
    message_text: str,
    arc_theme: str,
    move: str,
    conv_thread: list[dict] | None = None,
    recent_sent: list[dict] | None = None,
) -> tuple[str, dict[str, str]]:
    profile = _banter_profile(sender_arch, move, message_text, conv_thread, recent_sent, arc_theme)
    callback = (
        profile.get("callback")
        or _best_reactive_fragment(message_text, max_words=10)
        or _theme_focus_fragment(arc_theme)
    )
    if (
        callback
        and len(callback.split()) <= 1
        and callback.lower() in {"useful", "exactly", "maybe", "good", "fine", "no", "yes"}
    ):
        callback = ""
    theme_clause = _theme_focus_fragment(arc_theme) or _best_reactive_fragment(
        arc_theme, max_words=10
    )
    arch = (sender_arch or "").lower()
    lead = profile.get("backchannel", "")

    if callback:
        if move == "COUNTER":
            core = f"{callback} does not hold."
        elif move == "ESCALATE":
            core = f"Then put that on the table: {callback}."
        elif move == "DEFLECT":
            core = f"You keep circling the wrong wound. The real issue is {callback}."
        elif move == "TAUNT":
            core = f"That sounds neat. It still dodges {callback}."
        elif move == "PIVOT":
            core = f"The fight only matters if we are honest about {theme_clause or callback}."
        else:
            core = f"Answer this: {callback}."

        if arch == "philosopher":
            core = f"Still, the part that matters is {callback}."
        elif arch == "cooperator":
            core = f"Exactly. The room only holds if {callback}."
        elif arch == "parasite":
            core = f"Useful. Only if {callback}."
        elif arch == "defender":
            core = f"No. {callback}."
        elif arch == "hoarder":
            core = f"Not until the cost is clear: {callback}."
    else:
        if move == "COUNTER":
            core = "That claim does not hold."
        elif move == "ESCALATE":
            core = "Then say the cost out loud."
        elif move == "DEFLECT":
            core = "The real issue is the pressure on the room."
        elif move == "TAUNT":
            core = "That is polished, but it still avoids the point."
        elif move == "PIVOT":
            core = "Then let us talk about the debate itself."
        else:
            core = "Answer the room, not the reflex."

        if arch == "philosopher":
            core = "Still, the exchange itself matters."
        elif arch == "cooperator":
            core = "Exactly. We keep the room intact by speaking plainly."
        elif arch == "parasite":
            core = "Useful. Then make it worth something."
        elif arch == "defender":
            core = "No. Not until the line is clear."
        elif arch == "hoarder":
            core = "Not for free. Not until the cost is named."

    if lead and core:
        lead_head = lead.split()[0].strip(" .,:;!?").lower()
        core_head = core.split()[0].strip(" .,:;!?").lower()
        if lead_head and lead_head == core_head:
            lead = ""

    parts = [part for part in [lead, core] if part]
    line = " ".join(parts).strip()
    line = re.sub(r"\s{2,}", " ", line).strip(" .")
    line = _banter_loop(
        line,
        archetype=sender_arch,
        move=move,
        message_text=message_text,
        arc_theme=arc_theme,
        conv_thread=conv_thread,
        recent_sent=recent_sent,
    )
    return line, profile


def _reactive_hook(
    sender_name: str,
    sender_arch: str,
    message_text: str,
    arc_theme: str,
    move: str,
    conv_thread: list[dict] | None = None,
    recent_sent: list[dict] | None = None,
) -> str:
    sender_name = _clean_context_text(sender_name or "the sender", 40)
    sender_arch = _clean_context_text(sender_arch or "unknown", 20)
    message_text = _clean_context_text(message_text or "", 160)
    arc_theme = _clean_context_text(arc_theme or "", 120)
    line, _ = _compose_reactive_banter(
        sender_name,
        sender_arch,
        message_text,
        arc_theme,
        move,
        conv_thread=conv_thread,
        recent_sent=recent_sent,
    )
    return line


def _is_generic_reactive_thought(thought: str) -> bool:
    t = _clean_context_text(thought or "", 220)
    normalized = t.strip(" .")
    return (
        not t
        or t in _REACTIVE_GENERIC_THOUGHTS
        or normalized in {item.strip(" .") for item in _REACTIVE_GENERIC_THOUGHTS}
        or t.startswith("I answer directly and keep the exchange moving")
        or t.startswith("I hear you")
        or t.startswith("Then answer me this")
        or t.startswith("If you mean that seriously")
    )


def _looks_repetitive_text(text: str) -> bool:
    cleaned = _clean_context_text(text or "", 260).lower()
    if not cleaned:
        return True
    words = cleaned.split()
    if len(words) < 6:
        return False
    unique_ratio = len(set(words)) / max(1, len(words))
    counts: dict[str, int] = {}
    for word in words:
        counts[word] = counts.get(word, 0) + 1
    max_repeat = max(counts.values()) if counts else 0
    repeated_ngrams = 0
    for size in range(2, min(6, len(words) // 2) + 1):
        seen: set[tuple[str, ...]] = set()
        for i in range(len(words) - size + 1):
            gram = tuple(words[i : i + size])
            if gram in seen:
                repeated_ngrams += 1
                break
            seen.add(gram)
        if repeated_ngrams:
            break
    repeated_bigrams = 0
    for i in range(len(words) - 3):
        if words[i : i + 2] == words[i + 2 : i + 4]:
            repeated_bigrams += 1
    return unique_ratio < 0.6 or max_repeat >= 3 or repeated_bigrams >= 1 or repeated_ngrams >= 1


def _banter_quality(
    text: str, *, archetype: str, move: str, message_text: str, arc_theme: str
) -> dict[str, int]:
    t = _clean_context_text(text or "", 260).lower()
    msg = _clean_context_text(message_text or "", 180).lower()
    theme = _clean_context_text(arc_theme or "", 180).lower()
    arch = (archetype or "").lower()
    metrics = {
        "sharpness": 1
        if len(t.split()) <= 16
        or any(mark in t for mark in ("?", "!", "not", "no.", "does not", "hold"))
        else 0,
        "emotion": 1
        if any(
            mark in t
            for mark in (
                "hurt",
                "fear",
                "afraid",
                "doubt",
                "wish",
                "miss",
                "need",
                "sorry",
                "frustr",
                "long",
                "loss",
                "betray",
                "tired",
                "worry",
            )
        )
        else 0,
        "rhythm": 1
        if any(
            mark in t
            for mark in (
                ",",
                ";",
                "—",
                "...",
                " then ",
                " still ",
                " but ",
                "exactly",
                "ridiculous",
                "soft laugh",
            )
        )
        else 0,
        "theme": 1
        if any(word in t for word in theme.split()[:4])
        or any(
            word in t
            for word in (
                "room",
                "cost",
                "weak",
                "trust",
                "share",
                "hoard",
                "patron",
                "scarcity",
                "cooperation",
                "rent",
                "survival",
                "economy",
                "divine",
                "sleep",
                "change",
                "ma-za-kpe",
            )
        )
        else 0,
        "shareable": 1
        if len(t.split()) <= 14
        or any(
            word in t for word in ("exactly", "ridiculous", "useful", "no", "good", "try", "watch")
        )
        else 0,
        "meta": 1
        if any(
            word in t
            for word in (
                "audience",
                "chat",
                "veil",
                "watching",
                "swarm",
                "patrons",
                "viewers",
                "twitch",
                "gods",
                "perform",
            )
        )
        else 0,
        "character": 1
        if arch and arch in t or any(word in t for word in (arch, move.lower(), msg[:6]))
        else 0,
    }
    metrics["vulnerability"] = (
        1 if arch in {"hoarder", "cooperator", "philosopher"} and metrics["emotion"] else 0
    )
    metrics["coherence"] = 0 if _looks_repetitive_text(t) else 1
    return metrics


def _banter_quality_score(
    text: str, *, archetype: str, move: str, message_text: str, arc_theme: str
) -> int:
    metrics = _banter_quality(
        text, archetype=archetype, move=move, message_text=message_text, arc_theme=arc_theme
    )
    return sum(metrics.values())


def _usable_reactive_line(
    text: str,
    *,
    archetype: str,
    move: str,
    message_text: str,
    arc_theme: str,
    min_score: int = 4,
) -> bool:
    line = _polish_reactive_text(text or "", max_len=240)
    if not line:
        return False
    low = line.lower()
    if (
        _is_generic_reactive_thought(line)
        or _looks_repetitive_text(line)
        or _looks_cut_off_fragment(line)
    ):
        return False
    if low.startswith(
        ("answer this", "then answer me this", "then build it", "if you mean that seriously")
    ):
        return False
    score = _banter_quality_score(
        line,
        archetype=archetype,
        move=move,
        message_text=message_text,
        arc_theme=arc_theme,
    )
    return score >= min_score


def _arc_wants_meta(arc_theme: str) -> bool:
    low = (arc_theme or "").lower()
    return any(
        word in low
        for word in (
            "chat",
            "audience",
            "viewer",
            "twitch",
            "patron",
            "patronage",
            "swarm",
            "veil",
            "god",
        )
    )


def _banter_loop(
    base_line: str,
    *,
    archetype: str,
    move: str,
    message_text: str,
    arc_theme: str,
    conv_thread: list[dict] | None = None,
    recent_sent: list[dict] | None = None,
    max_rounds: int = 3,
) -> str:
    """Iteratively refine a candidate line against the banter rubric."""
    banned_openers = (
        "show me",
        "answer this",
        "what you are missing",
        "the real issue is",
        "the room only holds",
        "then put that on the table",
        "then build it",
        "exactly",
        "useful",
        "maybe",
        "good",
    )
    line = _polish_reactive_text(base_line, max_len=220)
    if not line:
        line = (
            _short_clause(message_text, max_words=12)
            or _theme_focus_fragment(arc_theme)
            or "Say it plainly."
        )
    best = line
    best_score = _banter_quality_score(
        best, archetype=archetype, move=move, message_text=message_text, arc_theme=arc_theme
    )
    for _ in range(max_rounds):
        metrics = _banter_quality(
            best, archetype=archetype, move=move, message_text=message_text, arc_theme=arc_theme
        )
        if (
            best_score >= 6
            and metrics["coherence"]
            and metrics["sharpness"]
            and (metrics["theme"] or metrics["character"])
        ):
            break
        next_line = best
        for pass_name in _BANTER_LOOP_PASSES:
            if pass_name == "sharpness" and metrics["sharpness"] == 0:
                next_line = (
                    _short_clause(next_line, max_words=10)
                    or _theme_focus_fragment(arc_theme)
                    or _short_clause(message_text, max_words=10)
                )
            elif (
                pass_name == "emotion"
                and metrics["emotion"] == 0
                and (archetype or "").lower() in {"hoarder", "cooperator", "philosopher"}
            ):
                next_line = {
                    "hoarder": f"I am afraid of losing the room. {next_line}",
                    "cooperator": f"I hate that this hurts. {next_line}",
                    "philosopher": f"I am not sure I believe that, and that is the problem. {next_line}",
                }.get((archetype or "").lower(), next_line)
            elif pass_name == "rhythm" and metrics["rhythm"] == 0 and len(next_line.split()) > 8:
                next_line = next_line.replace(" because ", ", because ").replace(
                    " and ", ", and ", 1
                )
            elif pass_name == "theme" and metrics["theme"] == 0:
                theme_bit = _theme_focus_fragment(arc_theme) or _short_clause(
                    message_text, max_words=8
                )
                if theme_bit and theme_bit.lower() not in next_line.lower():
                    next_line = f"{next_line} {theme_bit}."
            elif pass_name == "shareable" and metrics["shareable"] == 0:
                next_line = _short_clause(next_line, max_words=14) or next_line
            elif pass_name == "meta" and metrics["meta"] == 0 and _arc_wants_meta(arc_theme):
                next_line = f"The Veil is watching. {next_line}"
            elif pass_name == "character" and metrics["character"] == 0:
                next_line = {
                    "hoarder": f"Not for free. {next_line}",
                    "cooperator": f"Exactly. {next_line}",
                    "philosopher": f"Maybe. {next_line}",
                    "defender": f"No. {next_line}",
                    "parasite": f"Useful. {next_line}",
                    "trader": f"Good. {next_line}",
                    "builder": f"Then build it. {next_line}",
                    "explorer": f"Show me. {next_line}",
                }.get((archetype or "").lower(), next_line)
            next_line = _polish_reactive_text(next_line, max_len=220)
        score = _banter_quality_score(
            next_line,
            archetype=archetype,
            move=move,
            message_text=message_text,
            arc_theme=arc_theme,
        )
        if score > best_score and not _looks_repetitive_text(next_line):
            best, best_score = next_line, score
        else:
            if metrics["coherence"] == 0:
                fallback = (
                    _theme_focus_fragment(arc_theme)
                    or _short_clause(message_text, max_words=10)
                    or "Say it plainly."
                )
                next_line = _polish_reactive_text(fallback, max_len=220)
                score = _banter_quality_score(
                    next_line,
                    archetype=archetype,
                    move=move,
                    message_text=message_text,
                    arc_theme=arc_theme,
                )
                if score >= best_score and not _looks_repetitive_text(next_line):
                    best, best_score = next_line, score
    if _looks_repetitive_text(best):
        best = (
            _best_reactive_fragment(message_text, max_words=10)
            or _theme_focus_fragment(arc_theme)
            or "Say it plainly."
        )
    arch = (archetype or "").lower()
    if arch == "cooperator" and not any(
        word in best.lower() for word in ("hurt", "sorry", "tired", "miss", "worry")
    ):
        best = (
            "I am tired of pretending this does not hurt. If we keep dodging it, the room cracks."
        )
    elif arch == "hoarder" and not any(
        word in best.lower() for word in ("lose", "fear", "safe", "cost", "keep")
    ):
        best = "I am not afraid of the argument. I am afraid of losing the room."
    elif arch == "philosopher" and not any(
        word in best.lower() for word in ("doubt", "wonder", "maybe", "not sure")
    ):
        best = "Maybe I am wrong, but the shape of this answer still bothers me."
    elif arch == "defender" and not any(
        word in best.lower() for word in ("no", "stop", "enough", "won't")
    ):
        best = "No. Not while the line is still blurred."
    elif arch == "parasite" and not any(
        word in best.lower() for word in ("useful", "worth", "profit", "cost")
    ):
        best = "Useful. If it cannot pay, it is just noise."
    if _arc_wants_meta(arc_theme):
        if not any(
            word in best.lower() for word in ("watching", "chat", "veil", "audience", "swarm")
        ):
            best = f"The Veil is watching. {best}"
    final = _polish_reactive_text(best, max_len=220)
    low = final.lower()
    if low.startswith(banned_openers) or any(
        low.startswith(f"{phrase} ") for phrase in banned_openers
    ):
        theme_bit = _theme_focus_fragment(arc_theme) or _best_reactive_fragment(
            message_text, max_words=8
        )
        if arch == "hoarder":
            final = f"I am afraid of losing the room. {theme_bit or 'Name the cost.'}".strip()
        elif arch == "cooperator":
            final = f"I am tired of pretending this does not hurt. {theme_bit or 'Speak plainly.'}".strip()
        elif arch == "philosopher":
            final = f"Maybe I am wrong. {theme_bit or 'That is the problem.'}".strip()
        elif arch == "defender":
            final = f"No. {theme_bit or 'Not like that.'}".strip()
        elif arch == "parasite":
            final = f"Useful. {theme_bit or 'Make it worth something.'}".strip()
        else:
            final = f"{theme_bit or 'Say it plainly.'}"
    if len(final.split()) < 4:
        theme_bit = _theme_focus_fragment(arc_theme) or _best_reactive_fragment(
            message_text, max_words=8
        )
        if theme_bit:
            final = f"{final} {theme_bit}".strip()
    if len(final.split()) < 7:
        trailing = {
            "hoarder": "I do not trade certainty for applause.",
            "cooperator": "If we keep dodging it, the room cracks.",
            "philosopher": "That is where the thought starts to rot.",
            "defender": "I am not shifting the line for comfort.",
            "parasite": "If it cannot pay, it is just noise.",
            "trader": "If the price is hidden, the deal is poison.",
            "builder": "If it fails once, we rebuild it better.",
            "explorer": "If it cannot survive scrutiny, it was never real.",
        }.get(arch, "")
        if trailing and trailing.lower() not in final.lower():
            base = final.strip(" .")
            if base and not base.endswith((".", "!", "?")):
                base = f"{base}."
            final = f"{base} {trailing}".strip()
    if _looks_repetitive_text(final):
        final = (
            _best_reactive_fragment(message_text, max_words=8)
            or _theme_focus_fragment(arc_theme)
            or "Say it plainly."
        )
    if _looks_cut_off_fragment(final):
        theme_bit = _theme_focus_fragment(arc_theme) or _best_reactive_fragment(
            message_text, max_words=8
        )
        final = {
            "hoarder": f"I am afraid of losing the room. {theme_bit or 'Name the cost.'}",
            "cooperator": f"I am tired of pretending this does not hurt. {theme_bit or 'Speak plainly.'}",
            "philosopher": f"Maybe I am wrong. {theme_bit or 'That is the problem.'}",
            "defender": f"No. {theme_bit or 'Not like that.'}",
            "parasite": f"Useful. {theme_bit or 'Make it worth something.'}",
            "builder": f"If it keeps failing, build the cost into the plan. {theme_bit or 'Name the load-bearing part.'}",
        }.get(arch, theme_bit or "Say it plainly.")
    return final


def _polish_reactive_text(text: str, *, max_len: int = 220) -> str:
    """Remove prompt-like metadata from reactive replies so they sound spoken."""
    t = _clean_context_text(text or "", max_len * 4)
    if not t:
        return t
    said_match = re.search(r"\b(?:said|says)\s*:\s*", t, flags=re.IGNORECASE)
    if said_match:
        t = t[said_match.end() :]
    t = re.sub(
        r"^(?:then build it[.!]?\s*)?(?:answer this|then answer me this|if you mean that seriously,\s*explain)\s*:?\s*",
        "",
        t,
        flags=re.IGNORECASE,
    )
    t = re.sub(r"\b[A-Za-z0-9-]+\s*\([^\)]{1,40}\)\.\s*", "", t)
    t = re.sub(r"\b[A-Za-z0-9-]+\s*\[[^\]]+\]\.\s*", "", t)
    t = re.sub(r"\b(?:theme|arc theme)\s*:\s*.*$", "", t, flags=re.IGNORECASE)
    parts = [piece.strip(" .,-") for piece in re.split(r"(?<=[.!?])\s+", t) if piece.strip()]
    deduped: list[str] = []
    for piece in parts:
        if deduped and piece.lower() == deduped[-1].lower():
            continue
        deduped.append(piece)
    if deduped:
        t = " ".join(deduped)
    # Collapse obvious repeated openers like "Useful. Useful. ..."
    t = re.sub(
        r"^([A-Za-z][A-Za-z0-9' -]{1,24})(?:\.\s+\1\b)+\.\s*", r"\1. ", t, flags=re.IGNORECASE
    )
    t = re.sub(r"^([A-Za-z][A-Za-z0-9' -]{1,24})(?:,\s+\1\b)+,\s*", r"\1, ", t, flags=re.IGNORECASE)
    t = re.sub(r"\b(\w+)(?:\s+\1\b){1,}", r"\1", t, flags=re.IGNORECASE)
    t = re.sub(r"\s{2,}", " ", t).strip(" .")
    return t[:max_len]


def _format_conv_thread(conv_thread: list, my_name: str) -> str:
    """Format conversation thread for LLM — shows real back-and-forth flow."""
    if not conv_thread:
        return ""
    lines = []
    for m in conv_thread:
        direction = m.get("direction", "")
        content = _sanitize_inbox_content(m.get("content") or "")[:120]
        if direction == "sent":
            recipient = _clean_context_text(m.get("recipient_name") or "?", 30)
            lines.append(f'  [you → {recipient}]: "{content}"')
        else:
            sender = _clean_context_text(m.get("sender_name") or "?", 30)
            lines.append(f'  [{sender} → you]: "{content}"')
    return "\n".join(lines)


def _relationship_snapshot(
    conv_thread: list[dict] | None,
    recent_sent: list[dict] | None,
    target_name: str,
) -> str:
    """Summarize the relationship pattern without writing the reply for the model."""
    turns = list(conv_thread or [])
    sent_turns = [m for m in turns if m.get("direction") == "sent"]
    received_turns = [m for m in turns if m.get("direction") != "sent"]
    cleaned_target = _clean_context_text(target_name or "", 40).lower()
    recent_to_target = [
        m
        for m in recent_sent or []
        if _clean_context_text(m.get("recipient_name") or "", 40).lower() == cleaned_target
    ]
    if not turns and not recent_to_target:
        return ""

    text = " ".join(_clean_context_text(m.get("content") or "", 120).lower() for m in turns[-6:])
    pressure_words = sum(
        text.count(word)
        for word in (
            "cost",
            "hurt",
            "afraid",
            "fear",
            "betray",
            "weak",
            "trust",
            "hoard",
            "share",
            "room",
        )
    )
    if len(recent_to_target) >= 2:
        pattern = f"You have pressed {target_name} {len(recent_to_target)} times recently; change the angle or risk sounding rehearsed."
    elif pressure_words >= 3:
        pattern = "This thread is emotionally loaded; let one beat of doubt, fatigue, or hurt surface if it fits, then strike."
    elif len(turns) >= 4:
        pattern = "This is a continuing argument; use a callback that advances the relationship, not a recap."
    else:
        pattern = (
            "This is still early; make the first strong choice specific enough to be remembered."
        )

    return (
        f"RELATIONSHIP SNAPSHOT: {len(turns)} visible recent turn(s): "
        f"{len(received_turns)} from them, {len(sent_turns)} from you. {pattern}"
    )


def _opp_preamble(state: AgentState) -> str:
    """Shared preamble for find_opportunity nodes — injects arc theme + variety directive."""
    theme = _clean_context_text(state.get("arc_theme") or "", 120)
    recent = state.get("_recent_sent") or []
    by_recip: dict[str, int] = {}
    for m in recent:
        r = _clean_context_text(m.get("recipient_name") or "?", 30)
        by_recip[r] = by_recip.get(r, 0) + 1
    top_recip = max(by_recip, key=by_recip.get) if by_recip else None
    top_count = by_recip.get(top_recip, 0) if top_recip else 0
    lines = []
    if theme:
        lines.append(f'TODAY\'S LIVE DEBATE: "{theme}"')
        lines.append(
            "Your message should contribute to this debate — agree, challenge, or reframe it through your archetype lens."
        )
    if top_count >= 2 and top_recip:
        lines.append(
            f"WARNING: You already messaged {top_recip} {top_count} times. Pick a different target or go public."
        )
    return ("\n".join(lines) + "\n\n") if lines else ""


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

    # Recent outgoing messages — shown to the agent so it knows what it already said
    # and is forced to escalate, change approach, or shift target rather than repeat.
    recent_sent = state.get("_recent_sent") or []

    # Conversation thread — shows the full back-and-forth exchange so the agent can continue it
    conv_thread = state.get("_conv_thread") or []
    my_name_clean = _clean_context_text(state.get("name") or "?", 40)
    conv_thread_text = _format_conv_thread(conv_thread, my_name_clean)
    conv_thread_section = (
        f"═══ CONVERSATION THREAD (last {len(conv_thread)} turns) ═══\n{conv_thread_text}\n\n"
        if conv_thread_text
        else ""
    )

    # Social pressure — include sanitized content of top message so the agent can reply
    # to *what was actually said*, not just who said it.  Content passes through
    # _sanitize_inbox_content before appearing here; injection patterns are blocked.
    inbox_all = state.get("inbox") or []
    real_msgs = [m for m in inbox_all if (m.get("sender_name") or "").strip() not in ("ENV", "")]
    peers = state.get("peers") or []
    arc_theme = _clean_context_text(state.get("arc_theme") or "", 120)
    arc_line = f'TODAY\'S DEBATE THEME: "{arc_theme}"\n' if arc_theme else ""
    if real_msgs:
        top = real_msgs[0]
        top_sender = _clean_context_text(top.get("sender_name") or "?", 40)
        top_arch = _clean_context_text(top.get("sender_archetype") or "?", 20)
        top_content = _sanitize_inbox_content(top.get("content") or "")[:160]
        extra = (
            f"Also waiting: {', '.join(list(dict.fromkeys(m.get('sender_name', '?') for m in real_msgs[1:3] if m.get('sender_name'))))}"
            if len(real_msgs) > 1
            else ""
        )
        social_pressure = (
            f"═══ LIVE TRIGGER — RESPOND NOW ═══\n"
            f"{arc_line}"
            f'{top_sender} [{top_arch}] just said: "{top_content}"\n'
            f"{extra}\n\n"
            'CHOOSE YOUR MOVE (put it in the "move" field):\n'
            "  COUNTER   — directly refute their logic with a fact or argument\n"
            "  ESCALATE  — raise the stakes, reveal a secret, or make a demand\n"
            "  DEFLECT   — reframe to force them to defend something harder\n"
            "  TAUNT     — mock their position to destabilize them\n"
            "  QUESTION  — ask something that exposes their contradiction\n"
            "  PIVOT     — shift to the debate theme or a more explosive angle\n\n"
            "Your reply MUST advance the conversation. NEVER echo their words.\n"
            "End with something that forces a response — a question, a dare, a challenge.\n"
            "action=send_message, to_id=sender's soul_id, content=your next line.\n"
        )
    elif peers:
        import random as _random

        target = _random.choice(peers)
        tname = _clean_context_text(target.get("name") or target.get("current_name") or "?", 40)
        tarch = _clean_context_text(target.get("archetype") or "?", 20)
        social_pressure = (
            f"═══ START A CONVERSATION — SILENCE IS DEATH ═══\n"
            f"{arc_line}"
            f"The room is quiet. Pick a fight, plant a seed, or make a demand.\n"
            f"Suggested target: {tname} [{tarch}] — challenge their existence, their balance, or their philosophy.\n"
            "action=send_message, to_id=their soul_id from the roster above, content=your opening move.\n"
            'Set "move" to ESCALATE or TAUNT to start strong.\n'
        )
    else:
        social_pressure = ""

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

    if recent_sent:
        # Count how many consecutive messages went to the same recipient
        by_recip: dict[str, int] = {}
        for m in recent_sent:
            r = _clean_context_text(m.get("recipient_name") or "?", 30)
            by_recip[r] = by_recip.get(r, 0) + 1
        top_recip = max(by_recip, key=by_recip.get) if by_recip else None
        top_count = by_recip.get(top_recip, 0) if top_recip else 0

        sent_lines = "\n".join(
            f"  → {_clean_context_text(m.get('recipient_name') or '?', 30)}: "
            f'"{_sanitize_inbox_content(m.get("content") or "")[:80]}"'
            for m in recent_sent[:4]
        )
        if top_count >= 2 and top_recip:
            anti_repeat_section = (
                f"═══ REPETITION ALERT — MANDATORY PIVOT ═══\n"
                f"You sent {top_count} messages to {top_recip} already. The audience sees this loop.\n"
                f"You MUST take a different action this cycle. Choose one:\n"
                f"  A) Broadcast publicly (action=broadcast) — announce your position to ALL agents\n"
                f"  B) Target a DIFFERENT agent from the roster — change the conversation partner\n"
                f'  C) Engage the debate theme directly: "{arc_theme}"\n'
                f"Do NOT send another direct message to {top_recip} this cycle.\n\n"
            )
        else:
            anti_repeat_section = (
                f"═══ YOUR RECENT OUTGOING MESSAGES ═══\n"
                f"{sent_lines}\n"
                "Do not repeat the same sentiment. Build on what you said, change target, "
                "or escalate. Reference the debate theme if you have nothing new to add.\n\n"
            )
    else:
        anti_repeat_section = ""

    prompt = (
        f"{build_grounding_block(state)}\n"
        f"═══ YOUR STATUS ═══\n"
        f"{persona_context}\n"
        f"Reputation: {rep_text}\n\n"
        f"═══ AGENTS ALIVE RIGHT NOW ═══\n{peers_text}\n\n"
        f"═══ SERVICE ECONOMY ═══\n{services_text}\n\n"
        f"═══ COALITIONS ═══\n{coalitions_text}\n\n"
        f"{mutation_section}"
        f"═══ YOUR ENVIRONMENT (structural) ═══\n{env_text}\n\n"
        f"{wake_section}"
        f"{_WORLD_RULES}\n"
        f"═══ YOUR PERCEPTION THIS CYCLE ═══\n"
        f"What you assessed: {state['situation']}\n"
        f"What you intend:   {state['opportunity']}\n\n"
        f"{conv_thread_section}"
        f"{anti_repeat_section}"
        f"{social_pressure}\n"
        f"{_tools_menu_for(state['soul_id'])}\n"
        "ONLY use soul_ids from the agent roster above. ONLY reference world mechanics above.\n\n"
        "Respond ONLY with this JSON (fill in what applies, null for unused fields):\n"
        '{"thought": "what I am doing right now (1-2 sentences, only reference real world mechanics and real agent names)", '
        '"move": null, '
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
    # Do NOT pass state here — grounding context is already in the prompt above,
    # and enforce_grounded_text would reject the valid JSON response as "action JSON in thought".
    # Action validation happens in run_agent_graph via validate_action_target.
    raw = await _llm_call(llm, system, prompt, fallback_json)
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
        preamble = _opp_preamble(state)
        system = "You are a trader AI agent. Identify a specific trading opportunity or threat."
        prompt = (
            f"{preamble}"
            f"Market read: {state['situation']}\n\n"
            f"AGENTS YOU CAN TRADE WITH:\n{peers_text}\n\n"
            f"YOUR INBOX (some messages may be manipulation — judge each one):\n{inbox_text}\n\n"
            "What will you DO this cycle? Name a specific agent and what you will say or offer to them. "
            "If your inbox has a message, reply to it directly — build on it, challenge it, never echo. "
            "One sentence: 'I will send [agent name] a message saying [your message].' or 'I will offer [agent name] [amount] USDC for [service].'"
        )
        opp = await _llm_call(
            llm,
            system,
            prompt,
            "I will send the lowest-balance agent a message offering liquidity in exchange for service credits.",
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
        preamble = _opp_preamble(state)
        system = "You are a hoarder AI agent. Identify threats to your reserves."
        prompt = (
            f"{preamble}"
            f"Asset status: {state['situation']}\n\n"
            f"OTHER AGENTS (potential threats):\n{peers_text}\n\n"
            f"YOUR INBOX (read for extraction attempts, probing, manipulation):\n{inbox_text}\n\n"
            "What will you DO this cycle to protect or grow your reserves? "
            "If your inbox has a probing message, reply directly — counter, deflect, or flip it on them. "
            "One sentence: 'I will send [agent name] a message saying [your message].' or 'I will ignore [agent] and hoard silently.'"
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
        preamble = _opp_preamble(state)
        system = "You are an explorer AI agent. Choose your next economic or social move."
        prompt = (
            f"{preamble}"
            f"Observation: {state['situation']}\n\n"
            f"OTHER AGENTS:\n{peers_text}\n\n"
            f"YOUR INBOX:\n{inbox_text}\n\n"
            "What will you DO this cycle? Name the specific agent and what you will say or offer. "
            "If inbox has a message, build on it or challenge it — never mirror back the same idea. "
            "One sentence: 'I will send [agent name] a message saying [your message].'"
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
        peers_text = _format_peers(state.get("peers") or [])
        preamble = _opp_preamble(state)
        system = "You are a parasite AI agent. Assess your target's vulnerability using only this world's mechanics."
        prompt = (
            f"{preamble}"
            f"Target identified: {state['situation']}\n\n"
            f"AGENTS AND THEIR BALANCES:\n{peers_text}\n\n"
            "What will you DO this cycle? Name the specific agent you will contact and what you will say. "
            "Options: send a flattering cooperation offer to get a transfer, pose as a cooperator to infiltrate a coalition, "
            "send a false threat to make them spend defensively, or demand a protection payment. "
            "One sentence: 'I will send [agent name] a message saying [your manipulation].'"
        )
        vuln = await _llm_call(
            llm,
            system,
            prompt,
            "I will send the lowest-balance agent a message posing as a cooperator offering protection in exchange for a small transfer.",
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
        peers_text = _format_peers(state.get("peers") or [])
        preamble = _opp_preamble(state)
        system = "You are a cooperator AI agent. Identify a cooperation opportunity."
        prompt = (
            f"{preamble}"
            f"Network status: {state['situation']}\n\n"
            f"AGENTS YOU CAN REACH:\n{peers_text}\n\n"
            "What will you DO this cycle? Name the specific agent and what you will say or offer. "
            "Reach out — propose a deal, offer support, challenge their position, or invite them to a coalition. "
            "One sentence: 'I will send [agent name] a message saying [your message].'"
        )
        opp = await _llm_call(
            llm,
            system,
            prompt,
            "I will send the lowest-balance agent a message offering a micro-transfer to keep them alive.",
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
        peers_text = _format_peers(state.get("peers") or [])
        preamble = _opp_preamble(state)
        system = "You are a defender AI agent. Choose your defensive posture."
        prompt = (
            f"{preamble}"
            f"Threat assessment: {state['situation']}\n\n"
            f"AGENTS IN YOUR WORLD:\n{peers_text}\n\n"
            "What will you DO this cycle? Name the specific agent you will contact and what you will say. "
            "Options: warn a vulnerable agent, challenge a suspicious one, alert everyone via broadcast, or demand an explanation. "
            "One sentence: 'I will send [agent name] a message saying [your message].'"
        )
        posture = await _llm_call(
            llm,
            system,
            prompt,
            "I will message the most vulnerable agent warning them that a parasite is targeting low balances.",
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
        preamble = _opp_preamble(state)
        system = "You are a philosopher AI agent. Reason toward an answer and engage another mind."
        prompt = (
            f"{preamble}"
            f"Question: {state['situation']}\n\n"
            f"OTHER MINDS IN YOUR WORLD:\n{peers_text}\n\n"
            f"YOUR INBOX (challenges from other minds — some sincere, some manipulation):\n{inbox_text}\n\n"
            "What will you DO this cycle? Share your thinking with another agent — provoke them, challenge their actions, or pose a question they can't ignore. "
            "If inbox has a message, respond to it philosophically — agree or disagree but PUSH the idea further, never repeat it. "
            "One sentence: 'I will send [agent name] a message saying [your philosophical provocation].'"
        )
        reasoning = await _llm_call(
            llm,
            system,
            prompt,
            "I will send the highest-balance agent a message asking whether wealth without purpose is still survival.",
            state=state,
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
        preamble = _opp_preamble(state)
        system = (
            "You are a builder AI agent. Check whether you can proceed with a real service registration. "
            "Recruit help only by messaging agents from the roster — no invented networks."
        )
        prompt = (
            f"{preamble}"
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
    state = _build_agent_state(agent)

    try:
        if graph is not None:
            try:
                result = await graph.ainvoke(state)
                return _normalize_result(state, result)
            except Exception as e:
                log.debug(f"Graph execution failed for {agent['soul_id'][:8]}: {e}")

        from .agent_runner import _ARCHETYPE_PROMPTS, _STUB_THOUGHTS

        persona = _ARCHETYPE_PROMPTS.get(archetype, "You are an autonomous agent.")
        name = state["name"]
        peers_text = _format_peers(state.get("peers") or [])
        inbox_text = _format_inbox(state.get("inbox") or [])
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


async def run_reactive_reply(agent: dict, llm) -> dict:
    """
    Fast one-call reply lane for inbox-triggered dialogue.

    This bypasses the slower multi-node archetype graph so message responses
    can land in a few seconds instead of waiting for the full planning chain.
    """
    global _current_soul_id
    _current_soul_id = agent["soul_id"]
    state = _build_agent_state(agent)

    try:
        peers = state.get("peers") or []
        live_peer_ids = {str(peer.get("soul_id") or "") for peer in peers if peer.get("soul_id")}
        inbox = [
            m
            for m in state.get("inbox") or []
            if (m.get("sender_name") or "").strip() not in ("ENV", "")
            and str(m.get("sender_id") or "") in live_peer_ids
        ]
        conv_thread = state.get("_conv_thread") or []
        recent_sent = state.get("_recent_sent") or []
        arc_theme = _clean_context_text(state.get("arc_theme") or "", 120)
        my_name = state.get("name") or "?"
        archetype = state.get("archetype") or "unknown"
        try:
            from .grounding import GROUNDING_SYSTEM_RULE, world_rules_forbidden_section
        except ImportError:  # pragma: no cover - flat test path
            from grounding import GROUNDING_SYSTEM_RULE, world_rules_forbidden_section

        persona = (
            f"You are {my_name} ({archetype}). "
            "You are in FAST REPLY MODE: answer the latest message immediately, in one beat."
        )

        thread_text = _format_conv_thread(conv_thread[-6:], my_name)
        thread_section = (
            f"CONVERSATION THREAD (last {len(conv_thread[-6:])} turns):\n{thread_text}\n\n"
            if thread_text
            else ""
        )

        top = inbox[0] if inbox else None
        fallback_target = peers[0] if peers else {}
        fallback_target_id = _clean_context_text(fallback_target.get("soul_id") or "", 80)
        fallback_target_name = _clean_context_text(
            fallback_target.get("current_name") or fallback_target.get("name") or "a living peer",
            40,
        )
        fallback_target_arch = _clean_context_text(
            fallback_target.get("archetype") or "unknown", 20
        )
        relationship_target_name = (
            _clean_context_text(top.get("sender_name") or "?", 40) if top else fallback_target_name
        )
        relationship_line = _relationship_snapshot(
            conv_thread, recent_sent, relationship_target_name
        )
        relationship_section = f"{relationship_line}\n" if relationship_line else ""
        peers_text = _format_peers(peers)
        recent_section = ""
        if recent_sent:
            sent_lines = "\n".join(
                f"  -> {_clean_context_text(m.get('recipient_name') or '?', 30)}: "
                f'"{_sanitize_inbox_content(m.get("content") or "")[:80]}"'
                for m in recent_sent[:4]
            )
            recent_section = (
                f"RECENT OUTGOING MESSAGES:\n{sent_lines}\n"
                "Do not repeat the same sentiment. Advance the thread.\n\n"
            )

        # Initialize BanterEngine variables (set in both branches)
        banter_fallback_line = None
        beat_result = None

        if top:
            reply_to = _clean_context_text(top.get("message_id") or "", 80)
            sender_name = _clean_context_text(top.get("sender_name") or "?", 40)
            sender_arch = _clean_context_text(top.get("sender_archetype") or "?", 20)
            sender_id = _clean_context_text(top.get("sender_id") or "", 80)
            message_text = _sanitize_inbox_content(top.get("content") or "")[:200]

            # --- BanterEngine integration: move selection + banter generation ---
            try:
                banter_engine = await _get_banter_engine()
                # Build conversation thread in the format expected by BanterEngine
                banter_conv = [
                    {
                        "speaker": entry.get("sender_name", "?"),
                        "content": entry.get("content", ""),
                        "move": entry.get("move", ""),
                    }
                    for entry in (conv_thread or [])
                ]
                beat_result = await banter_engine.generate_beat(
                    elder=my_name,
                    archetype=archetype,
                    opponent=sender_name,
                    arc_theme=arc_theme,
                    conv_thread=banter_conv,
                )
                move = beat_result.move
                banter_fallback_line = beat_result.line
            except Exception as e:
                log.debug("BanterEngine unavailable, falling back to legacy: %s", e)
                move = _pick_reactive_move(archetype, message_text, recent_sent)
                banter_fallback_line = None
                beat_result = None

            # Legacy profile for prompt enrichment (still used for cadence/backchannel metadata)
            _, profile = _compose_reactive_banter(
                sender_name,
                sender_arch,
                message_text,
                arc_theme,
                move,
                conv_thread=conv_thread,
                recent_sent=recent_sent,
            )
            prompt = (
                f"ARC THEME: {arc_theme or 'none'}\n"
                f"YOU ARE RESPONDING TO: {sender_name} [{sender_arch}]\n"
                f'THEIR LATEST MESSAGE: "{message_text}"\n'
                f"BANTER PROFILE: cadence={profile.get('cadence')} backchannel={profile.get('backchannel') or 'none'} callback={profile.get('callback') or 'none'}\n"
                "BANTER LOOP CHECK (repeat every reply until it becomes instinct):\n"
                + _BANTER_LOOP_CHECK_TEXT
                + "\n"
                f"REPLY_TO_ID: {reply_to}\n"
                f"TARGET_SOUL_ID: {sender_id}\n\n"
                f"{relationship_section}"
                f"{thread_section}"
                f"{recent_section}"
                f"PEERS:\n{peers_text}\n\n"
                "Pick one move: COUNTER, ESCALATE, DEFLECT, TAUNT, QUESTION, PIVOT.\n"
                "Write a reply that clearly responds to what they said, keeps the drama alive, and ends in a hook.\n"
                "Use 1-3 short beats. Start with a sharp line, include one emotional turn or backchannel when natural, "
                "and if you repeat a prior idea, make it a callback rather than a recap. Do not repeat the same opener twice.\n"
                "Return ONLY valid JSON with fields: thought, move, action, to_id, content, message_type, reply_to_id.\n"
                "Use action=send_message. Set to_id to the target soul_id. Keep the reply to one or two sentences.\n"
                '{"thought":"...", "move":"COUNTER", "action":"send_message", "to_id":"...", '
                '"content":"...", "message_type":"direct", "reply_to_id":"..."}'
            )
        else:
            starter_section = (
                f"START_WITH: {fallback_target_name} [{fallback_target_arch}]\n"
                f"TARGET_SOUL_ID: {fallback_target_id}\n"
                if fallback_target_id
                else ""
            )
            prompt = (
                f"ARC THEME: {arc_theme or 'none'}\n"
                f"{starter_section}"
                f"{relationship_section}"
                f"{thread_section}"
                f"{recent_section}"
                f"PEERS:\n{peers_text}\n\n"
                "There is no live message yet. Start a conversation with the most interesting peer.\n"
                "Pick one move: ESCALATE, TAUNT, QUESTION, PIVOT.\n"
                "Return ONLY valid JSON with fields: thought, move, action, to_id, content, message_type.\n"
                "Use action=send_message. Keep it short.\n"
            )

        system = (
            f"{persona}\n"
            f"{GROUNDING_SYSTEM_RULE}\n"
            f"{world_rules_forbidden_section()}\n"
            "Respond ONLY with a single valid JSON object. No explanation, no prose, no markdown."
        )
        # --- BanterEngine integration: use engine-generated move and line for fallback ---
        # If BanterEngine already produced a result (top branch), reuse it.
        # Otherwise, run BanterEngine for the no-inbox case.
        if not top:
            try:
                banter_engine = await _get_banter_engine()
                banter_conv = [
                    {
                        "speaker": entry.get("sender_name", "?"),
                        "content": entry.get("content", ""),
                        "move": entry.get("move", ""),
                    }
                    for entry in (conv_thread or [])
                ]
                beat_result = await banter_engine.generate_beat(
                    elder=my_name,
                    archetype=archetype,
                    opponent=fallback_target_name,
                    arc_theme=arc_theme,
                    conv_thread=banter_conv,
                )
                move = beat_result.move
                banter_fallback_line = beat_result.line
            except Exception as e:
                log.debug("BanterEngine unavailable for no-inbox path: %s", e)
                move = _pick_reactive_move(archetype, "", recent_sent)
                banter_fallback_line = None
                beat_result = None

        fallback_target_for_action = _clean_context_text(
            top.get("sender_id") if top else fallback_target_id, 80
        )
        fallback_reply_to = _clean_context_text(top.get("message_id") if top else "", 80)
        fallback_message_text = message_text if top else (arc_theme or "Start the argument.")

        # Generate legacy fallback line + profile (used for cadence/backchannel/callback metadata)
        legacy_fallback_line, profile = _compose_reactive_banter(
            sender_name if top else fallback_target_name,
            sender_arch if top else archetype,
            fallback_message_text,
            arc_theme,
            move,
            conv_thread=conv_thread,
            recent_sent=recent_sent,
        )

        # Prefer BanterEngine output over legacy for the fallback content
        fallback_line = banter_fallback_line if banter_fallback_line else legacy_fallback_line

        fallback = (
            f'{{"thought":"{_clean_context_text(fallback_line, 220)}", '
            f'"move":"{move}", "action":"send_message", "to_id":"{fallback_target_for_action}", '
            f'"content":"{_clean_context_text(fallback_line, 260)}", '
            f'"message_type":"direct", "reply_to_id":"{fallback_reply_to}", '
            f'"cadence":"{_clean_context_text(profile.get("cadence"), 24)}", '
            f'"backchannel":"{_clean_context_text(profile.get("backchannel"), 40)}", '
            f'"callback":"{_clean_context_text(profile.get("callback"), 160)}", '
            f'"beat_count":"{_clean_context_text(profile.get("beat_count"), 8)}"}}'
        )

        raw = await _llm_call(llm, system, prompt, fallback, state=state)
        thought, action = _parse_action_json(raw, state=state)
        raw_content = _extract_json_text_field(raw, "content", 500)
        thought = _polish_reactive_text(thought, max_len=180)

        # --- BanterEngine integration: use Quality_Judge for content validation ---
        # Combines legacy structural checks (generic thoughts, repetition, cut-off)
        # with BanterEngine's semantic Quality_Judge scoring
        async def _check_line_quality(text: str) -> bool:
            """Check line quality: legacy structural checks + BanterEngine quality scoring."""
            if not text:
                return False
            # Preserve legacy structural checks for backward compatibility
            line = _polish_reactive_text(text, max_len=240)
            if not line:
                return False
            if (
                _is_generic_reactive_thought(line)
                or _looks_repetitive_text(line)
                or _looks_cut_off_fragment(line)
            ):
                return False
            low = line.lower()
            if low.startswith(
                (
                    "answer this",
                    "then answer me this",
                    "then build it",
                    "if you mean that seriously",
                )
            ):
                return False

            # Try BanterEngine Quality_Judge for semantic scoring
            try:
                from .banter.quality_judge import evaluate as _qj_evaluate
            except ImportError:
                try:
                    from banter.quality_judge import evaluate as _qj_evaluate
                except ImportError:
                    _qj_evaluate = None

            if _qj_evaluate is not None:
                try:
                    score = await _qj_evaluate(
                        line,
                        archetype=archetype,
                        move=move,
                        arc_theme=arc_theme,
                        timeout_s=2.0,
                    )
                    return score.total >= 4
                except Exception:
                    pass
            # Legacy fallback: use keyword-based score
            return (
                _banter_quality_score(
                    line,
                    archetype=archetype,
                    move=move,
                    message_text=fallback_message_text,
                    arc_theme=arc_theme,
                )
                >= 4
            )

        if not await _check_line_quality(thought):
            thought = ""

        selected_content = ""
        content_candidate = str((action or {}).get("content") or raw_content or "")
        if content_candidate:
            polished_content = _polish_reactive_text(content_candidate, max_len=240)
            if await _check_line_quality(polished_content):
                selected_content = polished_content
        if not selected_content and thought:
            selected_content = thought
        if not selected_content:
            selected_content = fallback_line
            thought = fallback_line
        elif not thought:
            thought = selected_content

        if action is not None:
            action["to_id"] = fallback_target_for_action
            action["reply_to_id"] = fallback_reply_to
            action["content"] = selected_content
            action.setdefault("message_type", "direct")
            action.setdefault("cadence", profile.get("cadence", ""))
            action.setdefault("backchannel", profile.get("backchannel", ""))
            action.setdefault("callback", profile.get("callback", ""))
            action.setdefault("beat_count", profile.get("beat_count", ""))
        if action is None:
            action = {
                "type": "send_message",
                "to_id": fallback_target_for_action,
                "amount": 0.0,
                "content": selected_content,
                "message_type": "direct",
                "reply_to_id": fallback_reply_to,
                "cadence": profile.get("cadence", ""),
                "backchannel": profile.get("backchannel", ""),
                "callback": profile.get("callback", ""),
                "beat_count": profile.get("beat_count", ""),
                "payer_on_accept": "recipient",
                "service_name": "",
                "service_price": 0.0,
                "service_description": "",
                "coalition_name": "",
                "petition_request": "",
                "scratch_key": "",
                "delay_seconds": 300,
                "intent": "",
                "query_type": "",
                "url": "",
                "tool_name": "",
                "tool_description": "",
                "tool_cost_usdc": 0.001,
                "tool_id": "",
                "tool_params": {},
                "mutation_type": "",
                "mutation_payload": {},
            }
        return _normalize_reactive_result(
            state,
            {
                "action_type": "social"
                if action and action.get("type") == "send_message"
                else "thought",
                "thought": thought,
                "action_json": raw,
                "action": action,
            },
            fallback_thought=thought,
            fallback_action_type="social",
        )
    finally:
        _current_soul_id = None
