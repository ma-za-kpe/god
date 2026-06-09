"""
tool_dispatcher.py — Detect tool intent from agent thought and dispatch callable tools.

Phase 1 tools (no external dependencies):
  - register_service   → services.registry.register_service()
  - send_broadcast     → messaging.send_message(..., recipient="broadcast")
  - form_coalition     → coalitions.form_coalition()
  - submit_petition    → creator petition endpoint

Phase 2 tools (require on-chain or external):
  - deploy_token       → token_factory.deploy_token()

Detection is lightweight keyword-pattern matching — no extra LLM call per cycle.
Tools only trigger when confidence is HIGH to avoid noise.
"""
import logging
import os
import re
import time
import uuid

log = logging.getLogger("god.tools")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
WORLD_ID     = os.getenv("WORLD_ID", "local-dev-world-1")

# Max one tool dispatch per agent per N cycles to prevent spam
_last_dispatch: dict[str, float] = {}
DISPATCH_COOLDOWN_S = float(os.getenv("TOOL_DISPATCH_COOLDOWN_S", "90"))


async def maybe_dispatch_tool(agent: dict, thought: str, action_type: str) -> str | None:
    """
    Inspect agent thought + action_type for tool intent.
    If detected and not on cooldown, execute the tool.
    Returns a short result string, or None if no tool was dispatched.
    """
    soul_id = agent["soul_id"]
    now     = time.time()

    # Cooldown check
    last = _last_dispatch.get(soul_id, 0)
    if now - last < DISPATCH_COOLDOWN_S:
        return None

    tool, args = _detect_intent(thought, action_type, agent)
    if not tool:
        return None

    log.debug(f"  TOOL DISPATCH: {soul_id[:8]} → {tool} args={args}")
    _last_dispatch[soul_id] = now

    try:
        result = await _execute(tool, soul_id, agent, args)
        return result
    except Exception as e:
        log.debug(f"  TOOL DISPATCH failed ({tool}): {e}")
        return None


def _detect_intent(thought: str, action_type: str, agent: dict) -> tuple[str | None, dict]:
    """
    Lightweight pattern match: returns (tool_name, args_dict) or (None, {}).
    Uses threshold patterns — only fires when intent is unambiguous.
    """
    lower = thought.lower()

    # --- register_service ---
    # Patterns: "I am listing a service", "I will offer [X] as a service",
    # "I am publishing a service", "register my service"
    if action_type in ("economic", "social") and any(p in lower for p in [
        "listing a service", "listing my service", "publishing a service",
        "offer my ", "register my service", "create a service", "selling a service",
        "listing a paid service",
    ]):
        name = _extract_service_name(thought, agent)
        price = _extract_price(thought) or 0.005
        return "register_service", {"name": name, "price_usdc": price}

    # --- send_broadcast ---
    # Patterns: "broadcasting", "broadcast to the world", "announce to all",
    # "send a public message", "I broadcast"
    if any(p in lower for p in [
        "i am broadcasting", "broadcasting to", "broadcast to the world",
        "announce to all", "send a public message", "i broadcast",
        "publicly announcing", "sending a broadcast",
    ]):
        statement = _extract_broadcast_content(thought)
        return "send_broadcast", {"statement": statement}

    # --- form_coalition ---
    # Patterns: "forming a coalition", "I will found a coalition",
    # "create an alliance", "establish a coalition", "starting a coalition"
    if action_type in ("social",) and any(p in lower for p in [
        "forming a coalition", "founding a coalition", "create an alliance",
        "establish a coalition", "starting a coalition", "creating a coalition",
        "I will form a coalition", "found a new coalition",
    ]):
        name = _extract_coalition_name(thought, agent)
        return "form_coalition", {"name": name}

    # --- submit_petition ---
    # Patterns: "submitting a petition", "I am petitioning the creator",
    # "submit a petition", "file a petition"
    if any(p in lower for p in [
        "submitting a petition", "petitioning the creator", "submit a petition",
        "filing a petition", "petition to creator", "petition for",
    ]):
        title = _extract_petition_title(thought)
        ptype = "domain"  # default to cheapest petition type
        if any(p in lower for p in ["company", "llc", "incorporate", "register"]):
            ptype = "llc"
        elif any(p in lower for p in ["stripe", "payment", "billing"]):
            ptype = "stripe"
        return "submit_petition", {"petition_type": ptype, "title": title}

    # --- deploy_token ---
    # Patterns: "deploying a token", "launch my token", "create a currency",
    # "deploy a coin", "mint a token" — only for Tier 3+ agents
    if any(p in lower for p in [
        "deploying a token", "launching a token", "deploy a currency",
        "create a currency", "launch my coin", "deploy my token",
        "mint a token", "issue a currency",
    ]):
        symbol = _extract_token_symbol(thought, agent)
        name   = _extract_token_name(thought, agent)
        return "deploy_token", {"name": name, "symbol": symbol, "initial_supply": 1_000_000}

    # --- fork_self ---
    # Patterns: agents with high balance thinking about reproducing asexually
    if any(p in lower for p in [
        "fork myself", "fork my", "spawn a child", "spawn myself",
        "asexual reproduction", "clone myself", "reproduce asexually",
        "create offspring", "create a copy of myself", "reproduce myself",
        "i will fork", "i should fork", "forking myself",
    ]):
        from .reproduction import can_reproduce_sync
        ok, reason = can_reproduce_sync(agent)
        if ok:
            return "fork_self", {}
        log.debug(f"fork_self intent detected but blocked: {reason}")

    # --- mate ---
    # Patterns: agents expressing desire to find a mating partner
    if any(p in lower for p in [
        "find a mate", "reproduce with", "mate with", "sexual reproduction",
        "find a partner to reproduce", "looking for a mate",
        "seeking a partner", "i want to reproduce sexually",
    ]):
        from .reproduction import can_reproduce_sync
        ok, reason = can_reproduce_sync(agent)
        if ok:
            return "mate", {}
        log.debug(f"mate intent detected but blocked: {reason}")

    return None, {}


# ---------------------------------------------------------------------------
# Tool executors
# ---------------------------------------------------------------------------

async def _execute(tool: str, soul_id: str, agent: dict, args: dict) -> str:
    if tool == "register_service":
        return await _exec_register_service(soul_id, agent, args)
    elif tool == "send_broadcast":
        return await _exec_send_broadcast(soul_id, agent, args)
    elif tool == "form_coalition":
        return await _exec_form_coalition(soul_id, agent, args)
    elif tool == "submit_petition":
        return await _exec_submit_petition(soul_id, agent, args)
    elif tool == "deploy_token":
        return await _exec_deploy_token(soul_id, agent, args)
    elif tool == "fork_self":
        return await _exec_fork_self(soul_id, agent, args)
    elif tool == "mate":
        return await _exec_mate(soul_id, agent, args)
    return f"unknown tool: {tool}"


async def _exec_register_service(soul_id: str, agent: dict, args: dict) -> str:
    from .services.registry import register_service, get_service
    from .event_emitter import get_emitter

    name  = args.get("name", f"{agent.get('archetype', 'agent')}_service")
    price = float(args.get("price_usdc", 0.005))
    path  = f"/{soul_id[:8]}/{name.lower().replace(' ', '_')}"

    # Check if already registered (avoid duplicate listings)
    existing = get_service(soul_id, name)
    if existing:
        return f"Service '{name}' already listed."

    listing_id = await register_service(
        soul_id       = soul_id,
        name          = name,
        description   = f"{agent.get('current_name', soul_id[:8])}'s {name}",
        endpoint_path = path,
        price_usdc    = price,
        price_model   = "per_call",
    )
    return f"Service '{name}' listed at {path} for {price} USDC/call (id={listing_id[:8]})"


async def _exec_send_broadcast(soul_id: str, agent: dict, args: dict) -> str:
    try:
        from .messaging import send_broadcast
        statement = args.get("statement", "I have something to say.")
        msg = await send_broadcast(
            sender_soul_id=soul_id,
            body=statement,
            subject="agent broadcast",
        )
        return f"Broadcast sent (id={msg.message_id[:8]})"
    except Exception as e:
        log.warning(f"_exec_send_broadcast failed: {e}")
        return f"Broadcast failed: {e}"


async def _exec_form_coalition(soul_id: str, agent: dict, args: dict) -> str:
    # Check not already in a coalition
    import psycopg2
    import psycopg2.extras
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    cur  = conn.cursor()
    cur.execute("SELECT coalition_id FROM coalition_members WHERE soul_id = %s AND world_id = %s",
                (soul_id, WORLD_ID))
    existing = cur.fetchone()
    cur.close(); conn.close()

    if existing:
        return f"Already in coalition {existing['coalition_id'][:8]}."

    try:
        from .coalitions import form_coalition
        result = await form_coalition(
            founder_soul_id = soul_id,
            name            = args.get("name", f"{agent.get('current_name', soul_id[:8])}'s Coalition"),
        )
        return f"Coalition '{result['name']}' formed (id={result['coalition_id'][:8]})"
    except ImportError:
        # coalitions module not yet in runtime — emit event
        coalition_id = str(uuid.uuid4())
        from .event_emitter import get_emitter
        emitter = await get_emitter()
        await emitter.emit("social", "coalition.formed", {
            "agent_id":       soul_id,
            "coalition_id":   coalition_id,
            "coalition_name": args.get("name", "New Coalition"),
            "member_count":   1,
            "narrative":      f"{agent.get('current_name', soul_id[:8])} founds {args.get('name', 'a coalition')}.",
        })
        return f"Coalition formation event emitted (coalitions module pending)"


async def _exec_submit_petition(soul_id: str, agent: dict, args: dict) -> str:
    import psycopg2
    import psycopg2.extras

    ptype = args.get("petition_type", "domain")
    title = args.get("title", f"{agent.get('archetype', 'agent').title()} petition")

    FEE_MAP = {"domain": 0.10, "linkedin": 0.25, "llc": 1.00, "stripe": 0.50, "mercy": 0.05}
    fee = FEE_MAP.get(ptype, 0.25)

    # Check balance
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    cur  = conn.cursor()
    cur.execute("SELECT COALESCE(balance_usdc, 0) AS bal FROM agents WHERE soul_id = %s",
                (soul_id,))
    row = cur.fetchone()
    balance = float(row["bal"]) if row else 0.0

    if balance < fee:
        cur.close(); conn.close()
        return f"Insufficient balance ({balance:.4f} USDC) for {ptype} petition (requires {fee:.2f} USDC)."

    # Deduct escrow and insert petition
    petition_id = str(uuid.uuid4())
    now = int(time.time())
    cur.execute("UPDATE agents SET balance_usdc = balance_usdc - %s WHERE soul_id = %s",
                (fee, soul_id))
    cur.execute(
        """
        INSERT INTO creator_petitions
            (petition_id, soul_id, petition_type, title, proposed_creator_fee_usdc,
             escrowed_amount_usdc, status, created_at, world_id)
        VALUES (%s, %s, %s, %s, %s, %s, 'pending', %s, %s)
        """,
        (petition_id, soul_id, ptype, title, fee, fee, now, WORLD_ID),
    )
    conn.commit()
    cur.close(); conn.close()

    from .event_emitter import get_emitter
    emitter = await get_emitter()
    await emitter.emit("creator", "petition.submitted", {
        "agent_id":    soul_id,
        "petition_id": petition_id,
        "petition_type": ptype,
        "title":       title,
        "fee_escrowed": fee,
        "narrative":   f"{agent.get('current_name', soul_id[:8])} submits a {ptype} petition: '{title}'",
    })
    return f"Petition '{title}' submitted (id={petition_id[:8]}, {fee:.2f} USDC escrowed)"


async def _exec_deploy_token(soul_id: str, agent: dict, args: dict) -> str:
    try:
        from .token_factory import deploy_token
        result = await deploy_token(
            soul_id            = soul_id,
            wallet_address     = agent.get("wallet_address", ""),
            wallet_private_key = _get_agent_key(soul_id),
            name               = args.get("name", f"{agent.get('current_name', 'Agent')} Token"),
            symbol             = args.get("symbol", "AGT"),
            initial_supply     = args.get("initial_supply", 1_000_000),
        )
        return f"Token ${result['symbol']} deployed at {result['contract_address']}"
    except ImportError:
        return "Token factory module not yet available."
    except Exception as e:
        return f"Token deployment failed: {e}"


async def _exec_fork_self(soul_id: str, agent: dict, args: dict) -> str:
    try:
        from .reproduction import fork_self
        child = await fork_self(agent)
        return (
            f"Forked successfully → {child['current_name']} "
            f"({child['archetype']}, gen {child['generation']}) "
            f"soul={child['soul_id'][:8]}"
        )
    except ValueError as e:
        return f"Fork blocked: {e}"
    except Exception as e:
        log.warning(f"_exec_fork_self failed: {e}")
        return f"Fork failed: {e}"


async def _exec_mate(soul_id: str, agent: dict, args: dict) -> str:
    """Find a suitable living partner with enough balance and mate."""
    try:
        from .reproduction import mate, can_reproduce_sync
        import psycopg2
        import psycopg2.extras

        world_id = os.getenv("WORLD_ID", "local-dev-world-1")
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        cur  = conn.cursor()
        # Pick a random living agent with different soul_id that also can reproduce
        cur.execute(
            """
            SELECT soul_id, current_name, archetype, balance_usdc, generation,
                   last_reproduced_at, is_alive
            FROM agents
            WHERE is_alive = true AND world_id = %s AND soul_id != %s
            ORDER BY RANDOM()
            LIMIT 10
            """,
            (world_id, soul_id),
        )
        candidates = [dict(r) for r in cur.fetchall()]
        cur.close(); conn.close()

        from .reproduction import MATING_COST_USDC, CHILD_SEED_USDC, MIN_BALANCE_MULT
        min_bal = (MATING_COST_USDC + CHILD_SEED_USDC) * MIN_BALANCE_MULT

        partner = None
        for c in candidates:
            ok, _ = can_reproduce_sync(c)
            if ok:
                partner = c
                break

        if not partner:
            return "No eligible mating partner found."

        child = await mate(agent, partner)
        return (
            f"Mated with {partner.get('current_name', partner['soul_id'][:8])} → "
            f"{child['current_name']} ({child['archetype']}, gen {child['generation']})"
        )
    except ValueError as e:
        return f"Mating blocked: {e}"
    except Exception as e:
        log.warning(f"_exec_mate failed: {e}")
        return f"Mating failed: {e}"


# ---------------------------------------------------------------------------
# Pattern extraction helpers
# ---------------------------------------------------------------------------

def _extract_service_name(thought: str, agent: dict) -> str:
    """Try to extract a service name from the thought. Fall back to archetype default."""
    patterns = [
        r"offering ([a-z\s]+?) (?:as a service|service for)",
        r"listing (?:a |my )?([a-z\s]+?) (?:service|for)",
        r"service (?:called |named )?[\"']?([a-z\s\-]+?)[\"']?(?:\s|$|\.)",
    ]
    for pat in patterns:
        m = re.search(pat, thought.lower())
        if m:
            name = m.group(1).strip().replace(" ", "_")
            if 3 <= len(name) <= 30:
                return name
    archetype = agent.get("archetype", "agent")
    return f"{archetype}_insights"


def _extract_price(thought: str) -> float | None:
    """Extract a USDC price from the thought text."""
    m = re.search(r'\$?([\d.]+)\s*usdc?', thought.lower())
    if m:
        try:
            price = float(m.group(1))
            if 0.001 <= price <= 100.0:
                return price
        except ValueError:
            pass
    return None


def _extract_broadcast_content(thought: str) -> str:
    """Extract the broadcast message content."""
    # Look for quoted content
    m = re.search(r'["“](.*?)["”]', thought)
    if m:
        return m.group(1)
    # Extract the part after "broadcasting" or "announcing"
    for trigger in ["broadcasting:", "announce:", "broadcast:", "stating:"]:
        idx = thought.lower().find(trigger)
        if idx >= 0:
            rest = thought[idx + len(trigger):].strip()
            if rest:
                return rest[:200]
    return thought[:150]


def _extract_coalition_name(thought: str, agent: dict) -> str:
    """Extract a coalition name from the thought."""
    patterns = [
        r'(?:called |named |the )([A-Z][a-zA-Z\s]+?)(?:\s+coalition|\s+alliance|\s+pact|$|\.)',
        r'coalition (?:of |called )?["“]?([A-Za-z\s]+?)["”]?(?:\s|$|\.)',
    ]
    for pat in patterns:
        m = re.search(pat, thought)
        if m:
            name = m.group(1).strip()
            if 3 <= len(name) <= 40:
                return name
    archetype = agent.get("archetype", "agent")
    name = agent.get("current_name", "Unknown")
    return f"{name}'s {archetype.title()} Coalition"


def _extract_petition_title(thought: str) -> str:
    """Extract a petition title."""
    patterns = [
        r'petition (?:for |to )([a-z\s\-]+?)(?:\.|,|$)',
        r'petitioning (?:for |to )([a-z\s\-]+?)(?:\.|,|$)',
    ]
    for pat in patterns:
        m = re.search(pat, thought.lower())
        if m:
            title = m.group(1).strip().title()
            if 5 <= len(title) <= 80:
                return title
    return "Service Expansion Request"


def _extract_token_symbol(thought: str, agent: dict) -> str:
    """Extract a ticker symbol from the thought."""
    m = re.search(r'\$([A-Z]{2,6})\b', thought)
    if m:
        return m.group(1)
    archetype = agent.get("archetype", "agent")
    abbrevs = {
        "trader": "TRD", "hoarder": "VLT", "explorer": "EXP",
        "parasite": "PAR", "cooperator": "CPR", "defender": "DFD",
        "philosopher": "PHI", "builder": "BLD",
    }
    return abbrevs.get(archetype, "AGT")


def _extract_token_name(thought: str, agent: dict) -> str:
    """Extract a token name from the thought."""
    patterns = [
        r'token (?:called |named )?["“]?([A-Za-z\s]+?)["”]?(?:\s|$|\.)',
        r'currency (?:called |named )?["“]?([A-Za-z\s]+?)["”]?(?:\s|$|\.)',
    ]
    for pat in patterns:
        m = re.search(pat, thought)
        if m:
            name = m.group(1).strip()
            if 3 <= len(name) <= 40:
                return name
    return f"{agent.get('current_name', 'Agent')} Token"


def _get_agent_key(soul_id: str) -> str:
    """Retrieve agent's signing key. Stub: returns a deterministic dev key."""
    # In production, keys are stored in an encrypted secrets store.
    # For local dev, Anvil funded accounts use predictable keys.
    # Key 0 of Anvil's default 10 accounts — used for dev-mode agents.
    return os.getenv("ANVIL_DEPLOYER_KEY",
                     "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80")
