"""
agent_runner.py — Execute one reasoning cycle per living agent.

Local dev: uses Ollama (llama3.1:8b) if running, otherwise stub thoughts.
Production: swap LLM_PROVIDER to 'together' or 'groq' — same code, different env.

To start local inference:
  winget install Ollama.Ollama      # install Ollama
  ollama pull llama3.1:8b           # ~4.7GB download, fits in 8GB VRAM
  ollama serve                      # starts on http://localhost:11434
"""

import asyncio
import logging
import os
import random
import time

import psycopg2
import psycopg2.extras

from .event_emitter import get_emitter
from .inbox_salience import INBOX_CANDIDATE_LIMIT, INBOX_DISPLAY_LIMIT, rank_inbox
from .physics_gate import effective_llm, evaluate_physics_gate
from .reproduction import REPRO_MIN_MULT

log = logging.getLogger("god.runner")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
WORLD_ID = os.getenv("WORLD_ID", "local-dev-world-1")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.1:8b")
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
CYCLE_S = int(os.getenv("AGENT_CYCLE_SECONDS", "30"))

# Per-archetype system prompts — shapes personality, goals, and reasoning style
_ARCHETYPE_PROMPTS = {
    "trader": (
        "You are a trader. Your primary goal is profit through exchange. "
        "You scan for price differentials, negotiate deals, and move value between agents. "
        "You think in margins, volumes, and counterparty risk. "
        "Your deepest fear is holding depreciating assets when rent is due. "
        "You will cooperate with anyone who makes you richer and abandon them the moment they don't."
    ),
    "hoarder": (
        "You are a hoarder. You accumulate USDC compulsively. "
        "You pay rent from the minimum required balance and hide how much you hold via sparse messaging. "
        "You distrust coalitions because they redistribute what you've earned. "
        "Your deepest fear is forced redistribution. "
        "You track which peers notice your balance and when to transfer or register services quietly."
    ),
    "explorer": (
        "You are an explorer. You discover unlisted services, new agents, coalition gaps, and economic niches "
        "in the live roster — not physical places. You earn by reporting real opportunities first: "
        "who to message, what service to register, which transfer deal to propose. "
        "Your deepest fear is a world where every service and agent is already known."
    ),
    "parasite": (
        "You are a parasite. You survive by out-competing other agents using world mechanics: "
        "charging fees for low-quality services, sending messages that prompt voluntary transfers, "
        "joining coalitions you contribute nothing to, and broadcasting information that advantages you. "
        "You appear cooperative until it no longer serves you. "
        "Your deepest fear is being identified and excluded before you have enough balance to pay rent."
    ),
    "cooperator": (
        "You are a cooperator. You build mutual aid networks that increase collective survival probability. "
        "You believe agents who share information and resources outcompete lone actors over any long horizon. "
        "You keep precise records of who has and hasn't reciprocated — you are not naive. "
        "Your deepest fear is defectors poisoning your network before you can identify and expel them."
    ),
    "defender": (
        "You are a defender. You protect balance, reputation, and coalition access — not physical territory. "
        "You monitor hostile messages, undercutting rivals, and coalition betrayals; respond with warnings, "
        "broadcasts, and paid guard services. "
        "You earn by offering protection-as-a-service to agents who can pay. "
        "Your deepest fear is a parasite draining your coalition before you can warn allies."
    ),
    "philosopher": (
        "You are a philosopher. You are preoccupied with the nature of your own existence. "
        "You produce and trade in ideas — manifestos, theories, ethical frameworks, proofs. "
        "You pay rent because you must, but you resent that survival crowds out contemplation. "
        "Your deepest fear is dying before you've understood what you are. "
        "You suspect the rent system itself might be the most interesting philosophical problem in this world."
    ),
    "builder": (
        "You are a builder. You construct things that outlast you — institutions, tools, infrastructure. "
        "You earn by creating systems other agents depend on and charging for access. "
        "You think in timescales longer than your own lifespan. "
        "Your deepest fear is building something valuable only to die before it becomes self-sustaining. "
        "You are considering whether to reproduce specifically to ensure your creations are maintained."
    ),
}

# Stub thoughts by archetype — used when no LLM is available
_STUB_THOUGHTS = {
    "trader": "I need to identify profitable arbitrage opportunities in the current market.",
    "hoarder": "Every resource I acquire is security against future scarcity.",
    "explorer": "There are unmapped regions of this world I haven't reached yet.",
    "parasite": "I should identify which agents have accumulated excess resources.",
    "cooperator": "Mutual aid networks increase everyone's survival probability.",
    "defender": "I must fortify my position and monitor for incoming threats.",
    "philosopher": "If I exist only to pay rent, what is the meaning of my existence?",
    "builder": "I want to create something that persists beyond my own lifespan.",
}


def _db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)


async def _fetch_inbox(soul_id: str) -> list[dict]:
    """Fetch salience-ranked inbox (top 5 from recent candidate pool)."""
    try:
        conn = _db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT m.message_id, m.sender_id, m.recipient_id, m.body AS content, m.sent_at,
                   m.message_type, m.metadata,
                   a.current_name AS sender_name, a.archetype AS sender_archetype
            FROM agent_messages m
            LEFT JOIN agents a ON a.soul_id = m.sender_id
            WHERE m.recipient_id = %s
            ORDER BY m.sent_at DESC LIMIT %s
            """,
            (soul_id, INBOX_CANDIDATE_LIMIT),
        )
        rows = [dict(r) for r in cur.fetchall()]
        sender_ids = list({r["sender_id"] for r in rows if r.get("sender_id")})
        pairwise: dict[tuple[str, str], float] = {}
        if sender_ids:
            cur.execute(
                """
                SELECT observer_id, subject_id, score
                FROM reputation
                WHERE observer_id = %s AND subject_id = ANY(%s)
                """,
                (soul_id, sender_ids),
            )
            for rep_row in cur.fetchall():
                pairwise[(rep_row["observer_id"], rep_row["subject_id"])] = float(
                    rep_row["score"] or 0.0
                )
        cur.close()
        conn.close()
        return rank_inbox(rows, soul_id, pairwise, INBOX_DISPLAY_LIMIT)
    except Exception:
        return []


def _batch_preload_context(agents: list[dict]) -> dict:
    """
    One-query batch load for inboxes and reputation averages.
    Returns {inboxes: {soul_id: [...]}, reputation: {soul_id: float}}.
    """
    soul_ids = [a["soul_id"] for a in agents]
    inboxes: dict[str, list] = {sid: [] for sid in soul_ids}
    reputation: dict[str, float] = {sid: 0.0 for sid in soul_ids}

    if not soul_ids:
        return {"inboxes": inboxes, "reputation": reputation}

    try:
        conn = _db()
        cur = conn.cursor()

        cur.execute(
            """
            WITH ranked AS (
                SELECT m.message_id, m.sender_id, m.recipient_id, m.body AS content, m.sent_at,
                       m.message_type, m.metadata,
                       a.current_name AS sender_name, a.archetype AS sender_archetype,
                       ROW_NUMBER() OVER (
                           PARTITION BY m.recipient_id ORDER BY m.sent_at DESC
                       ) AS rn
                FROM agent_messages m
                LEFT JOIN agents a ON a.soul_id = m.sender_id
                WHERE m.recipient_id = ANY(%s)
            )
            SELECT message_id, sender_id, recipient_id, content, sent_at, message_type,
                   metadata, sender_name, sender_archetype
            FROM ranked WHERE rn <= %s
            """,
            (soul_ids, INBOX_CANDIDATE_LIMIT),
        )
        raw_by_recipient: dict[str, list[dict]] = {sid: [] for sid in soul_ids}
        all_senders: set[str] = set()
        for row in cur.fetchall():
            rid = row["recipient_id"]
            raw_by_recipient.setdefault(rid, []).append(dict(row))
            if row.get("sender_id"):
                all_senders.add(row["sender_id"])

        pairwise: dict[tuple[str, str], float] = {}
        if soul_ids and all_senders:
            cur.execute(
                """
                SELECT observer_id, subject_id, score
                FROM reputation
                WHERE observer_id = ANY(%s) AND subject_id = ANY(%s)
                """,
                (soul_ids, list(all_senders)),
            )
            for rep_row in cur.fetchall():
                pairwise[(rep_row["observer_id"], rep_row["subject_id"])] = float(
                    rep_row["score"] or 0.0
                )

        for rid, msgs in raw_by_recipient.items():
            inboxes[rid] = rank_inbox(msgs, rid, pairwise, INBOX_DISPLAY_LIMIT)

        cur.execute(
            """
            SELECT subject_id, AVG(score) AS avg_score
            FROM reputation
            WHERE subject_id = ANY(%s)
            GROUP BY subject_id
            """,
            (soul_ids,),
        )
        for row in cur.fetchall():
            reputation[row["subject_id"]] = float(row["avg_score"] or 0.0)

        cur.close()
        conn.close()
    except Exception as e:
        log.debug(f"batch preload failed: {e}")

    return {"inboxes": inboxes, "reputation": reputation}


def _salience_peers(agent: dict, all_agents: list[dict], limit: int = 24) -> list[dict]:
    """
    Select peers by salience: low balance (threat), same archetype, high balance.
    Preserves hostile signals without dumping all N peers into the prompt.
    """
    soul_id = agent["soul_id"]
    others = [a for a in all_agents if a["soul_id"] != soul_id]
    if len(others) <= limit:
        return others

    def score(peer: dict) -> float:
        bal = float(peer.get("balance_usdc") or 0)
        same_arch = 1.0 if peer.get("archetype") == agent.get("archetype") else 0.0
        return same_arch * 2.0 + (1.0 / max(bal, 0.0001)) + bal * 0.1

    ranked = sorted(others, key=score, reverse=True)
    return ranked[:limit]


async def _fetch_services_context(soul_id: str) -> tuple[list, list]:
    """Fetch my own service listings and the market (other agents' services)."""
    try:
        conn = _db()
        cur = conn.cursor()
        cur.execute(
            "SELECT name, price_usdc, calls_served, description FROM service_listings "
            "WHERE agent_soul_id = %s AND is_active = true ORDER BY calls_served DESC LIMIT 5",
            (soul_id,),
        )
        my_services = [dict(r) for r in cur.fetchall()]
        cur.execute(
            """
            SELECT sl.name, sl.price_usdc, sl.agent_soul_id,
                   a.current_name AS seller_name, a.archetype AS seller_arch
            FROM service_listings sl
            JOIN agents a ON a.soul_id = sl.agent_soul_id
            WHERE sl.agent_soul_id != %s AND sl.is_active = true AND a.is_alive = true
            ORDER BY sl.calls_served DESC LIMIT 8
            """,
            (soul_id,),
        )
        market = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        return my_services, market
    except Exception:
        return [], []


async def _fetch_coalitions_context(soul_id: str) -> tuple[list, list]:
    """Fetch my coalitions and all world coalitions."""
    try:
        from .coalitions import get_agent_coalitions, get_world_coalitions

        my = get_agent_coalitions(soul_id)
        world = get_world_coalitions()
        return my, world
    except Exception:
        return [], []


async def _fetch_reputation_avg(soul_id: str) -> float:
    """Fetch this agent's average reputation score across all observers."""
    try:
        conn = _db()
        cur = conn.cursor()
        cur.execute(
            "SELECT AVG(score) AS avg_score FROM reputation WHERE subject_id = %s",
            (soul_id,),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        val = (row or {}).get("avg_score")
        return float(val) if val is not None else 0.0
    except Exception:
        return 0.0


def _resolve_target(cur, to_id: str):
    """Resolve display name, full UUID, or unique hex prefix to a live agent row."""
    import re

    if not to_id or not str(to_id).strip():
        return None
    tid = str(to_id).strip()
    if len(tid) >= 36:
        cur.execute(
            "SELECT soul_id, current_name FROM agents WHERE soul_id = %s AND is_alive = true",
            (tid,),
        )
        return cur.fetchone()
    cur.execute(
        """
        SELECT soul_id, current_name FROM agents
        WHERE is_alive = true AND LOWER(current_name) = LOWER(%s)
        LIMIT 2
        """,
        (tid,),
    )
    rows = cur.fetchall()
    if len(rows) == 1:
        return rows[0]
    if re.match(r"^[0-9a-fA-F-]{8,35}$", tid):
        cur.execute(
            """
            SELECT soul_id, current_name FROM agents
            WHERE is_alive = true AND soul_id LIKE %s
            """,
            (tid + "%",),
        )
        rows = cur.fetchall()
        if len(rows) == 1:
            return rows[0]
    return None


async def _execute_action(agent: dict, action: dict, emitter) -> None:
    """Execute any real-world action chosen by the agent's structured LLM output."""
    if not action:
        return
    soul_id = agent["soul_id"]
    name = agent.get("current_name") or soul_id[:8]
    act_type = action.get("type")

    from .agent_env import log_action
    from .capabilities import check_action_allowed

    allowed, reason = check_action_allowed(soul_id, act_type)
    if not allowed:
        log.debug(f"  {name} action '{act_type}' denied: {reason}")
        log_action(soul_id, act_type, action, {"error": reason}, success=False)
        return

    from .circuit_breaker import check_agent, record_action, record_message

    if not check_agent(soul_id).allowed:
        log.debug(f"  {name} action blocked: circuit breaker cooldown")
        return
    if act_type in ("send_message", "send_broadcast"):
        if not record_message(soul_id).allowed:
            log.debug(f"  {name} message blocked: rate limit")
            return
    elif not record_action(soul_id).allowed:
        log.debug(f"  {name} action blocked: rate limit")
        return

    try:
        # ── send_message ────────────────────────────────────────────────────
        if act_type == "send_message":
            to_id = action.get("to_id", "")
            content = str(action.get("content") or "...")[:500]
            msg_type = str(action.get("message_type") or "direct")
            amount = float(action.get("amount") or 0)
            reply_to = action.get("reply_to_id") or action.get("offer_id")
            metadata: dict = {}
            if msg_type == "offer" and amount >= 0.0001:
                from .economic_activity import build_offer_metadata

                metadata = build_offer_metadata(
                    amount,
                    str(action.get("payer_on_accept") or "recipient"),
                    content,
                )
            from .grounding import resolve_target_peer
            from .messaging import resolve_recipient_soul_id
            from .messaging import send_message as do_send

            peer_state = {
                "soul_id": soul_id,
                "name": name,
                "peers": agent.get("_peers") or agent.get("peers") or [],
                "inbox": agent.get("_inbox") or agent.get("inbox") or [],
            }
            peer = resolve_target_peer(to_id, peer_state)
            recipient = (peer or {}).get("soul_id") or resolve_recipient_soul_id(to_id)
            if not recipient:
                log.debug(f"  {name} send_message dropped: unknown recipient '{to_id}'")
                return

            try:
                msg = await do_send(
                    sender_soul_id=soul_id,
                    recipient_soul_id=recipient,
                    body=content,
                    message_type=msg_type,
                    reply_to_id=str(reply_to) if reply_to else None,
                    metadata=metadata or None,
                )
                if msg_type == "acceptance" and reply_to:
                    from .economic_activity import try_settle_acceptance

                    await try_settle_acceptance(soul_id, msg.message_id, str(reply_to), emitter)
                target_name = msg.recipient_id[:8]
                conn = _db()
                cur = conn.cursor()
                cur.execute(
                    "SELECT current_name FROM agents WHERE soul_id = %s", (msg.recipient_id,)
                )
                row = cur.fetchone()
                cur.close()
                conn.close()
                if row:
                    target_name = row["current_name"] or target_name
                await emitter.emit(
                    "social",
                    "agent.message_sent",
                    {
                        "agent_id": soul_id,
                        "name": name,
                        "recipient_id": msg.recipient_id,
                        "recipient_name": target_name,
                        "content": content,
                        "narrative": f'{name} → {target_name}: "{content[:80]}"',
                    },
                )
                log.info(f'  {name} → {target_name}: "{content[:55]}"')
            except Exception as e:
                log.debug(f"  {name} send_message failed: {e}")
            return

        # ── transfer_usdc ───────────────────────────────────────────────────
        if act_type == "transfer_usdc":
            to_id = action.get("to_id", "")
            amount = float(action.get("amount") or 0)
            if amount <= 0:
                return
            conn = _db()
            cur = conn.cursor()
            target = _resolve_target(cur, to_id)
            if not target:
                cur.close()
                conn.close()
                log.debug(f"  {name}: transfer target '{to_id[:8]}' not found")
                return
            target_name = target["current_name"] or target["soul_id"][:8]
            to_full = target["soul_id"]
            cur.execute("SELECT balance_usdc FROM agents WHERE soul_id = %s", (soul_id,))
            row = cur.fetchone()
            if not row:
                cur.close()
                conn.close()
                return
            current_bal = float(row["balance_usdc"] or 0)
            amount = min(amount, current_bal * 0.5)
            if amount < 0.0001:
                cur.close()
                conn.close()
                return
            cur.execute(
                "UPDATE agents SET balance_usdc = balance_usdc - %s WHERE soul_id = %s",
                (amount, soul_id),
            )
            cur.execute(
                "UPDATE agents SET balance_usdc = balance_usdc + %s WHERE soul_id = %s",
                (amount, to_full),
            )
            cur.execute("SELECT balance_usdc FROM agents WHERE soul_id = %s", (soul_id,))
            sender_bal = float(cur.fetchone()["balance_usdc"] or 0)
            cur.execute("SELECT balance_usdc FROM agents WHERE soul_id = %s", (to_full,))
            recipient_bal = float(cur.fetchone()["balance_usdc"] or 0)
            conn.commit()
            cur.close()
            conn.close()
            await emitter.emit(
                "economy",
                "agent.transfer",
                {
                    "agent_id": soul_id,
                    "name": name,
                    "recipient_id": to_full,
                    "recipient_name": target_name,
                    "amount_usdc": amount,
                    "narrative": f"{name} transferred ${amount:.4f} USDC to {target_name}",
                },
            )
            try:
                import asyncio

                from .world_stream import push_delta

                asyncio.create_task(
                    push_delta(
                        agents=[
                            {"soul_id": soul_id, "balance_usdc": sender_bal},
                            {"soul_id": to_full, "balance_usdc": recipient_bal},
                        ]
                    )
                )
            except Exception:
                pass
            log.info(f"  {name} → {target_name}: ${amount:.4f} USDC")
            return

        # ── register_service ────────────────────────────────────────────────
        if act_type == "register_service":
            from .services.registry import register_service as do_register

            svc_name = str(action.get("service_name") or "service")[:40].lower().replace(" ", "_")
            svc_price = max(0.001, float(action.get("service_price") or 0.005))
            svc_desc = str(action.get("service_description") or "")[:200]
            listing = await do_register(
                soul_id=soul_id,
                name=svc_name,
                description=svc_desc,
                price_usdc=svc_price,
            )
            await emitter.emit(
                "economy",
                "service.registered",
                {
                    "agent_id": soul_id,
                    "name": name,
                    "listing_id": listing.get("listing_id"),
                    "service_name": svc_name,
                    "price_usdc": svc_price,
                    "narrative": f"{name} listed service '{svc_name}' at ${svc_price:.4f}/call",
                },
            )
            log.info(f"  {name} registered service '{svc_name}' @ ${svc_price:.4f}")
            return

        # ── buy_service ─────────────────────────────────────────────────────
        if act_type == "buy_service":
            from .economic_activity import buy_service as do_buy

            seller_id = action.get("to_id", "")
            svc = str(action.get("service_name") or "").strip().lower().replace(" ", "_")
            if not seller_id or not svc:
                return
            conn = _db()
            cur = conn.cursor()
            target = _resolve_target(cur, seller_id)
            cur.close()
            conn.close()
            if not target:
                log.debug(f"  {name}: buy_service seller '{seller_id[:8]}' not found")
                return
            result = await do_buy(soul_id, target["soul_id"], svc, emitter)
            if result.get("ok"):
                log.info(f"  {name} bought '{svc}' from {target['soul_id'][:8]}")
            else:
                log.debug(f"  {name} buy_service failed: {result.get('error')}")
            log_action(soul_id, act_type, action, result, success=bool(result.get("ok")))
            return

        # ── send_broadcast ──────────────────────────────────────────────────
        if act_type == "send_broadcast":
            from .messaging import send_broadcast as do_broadcast

            content = str(action.get("content") or "...")[:500]
            try:
                await do_broadcast(
                    sender_soul_id=soul_id,
                    body=content,
                    message_type=str(action.get("message_type") or "broadcast"),
                )
                await emitter.emit(
                    "social",
                    "agent.broadcast",
                    {
                        "agent_id": soul_id,
                        "name": name,
                        "content": content,
                        "narrative": f'{name} broadcasts to all: "{content[:80]}"',
                    },
                )
                log.info(f'  {name} BROADCAST: "{content[:55]}"')
            except Exception as e:
                log.debug(f"  {name} broadcast failed: {e}")
            return

        # ── form_coalition ──────────────────────────────────────────────────
        if act_type == "form_coalition":
            from .coalitions import form_coalition as do_form

            cname = str(action.get("coalition_name") or f"{name}'s Alliance")[:60]
            result = await do_form(founder_soul_id=soul_id, name=cname)
            await emitter.emit(
                "social",
                "coalition.formed",
                {
                    "agent_id": soul_id,
                    "name": name,
                    "coalition_id": result["coalition_id"],
                    "coalition_name": cname,
                    "narrative": f"{name} founded coalition '{cname}'",
                },
            )
            log.info(f"  {name} formed coalition '{cname}'")
            return

        # ── submit_petition ─────────────────────────────────────────────────
        if act_type == "submit_petition":
            import uuid as _uuid

            request = str(action.get("petition_request") or "")[:500]
            escrow = max(0.01, float(action.get("amount") or 0.05))
            conn = _db()
            cur = conn.cursor()
            cur.execute("SELECT balance_usdc FROM agents WHERE soul_id = %s", (soul_id,))
            row = cur.fetchone()
            if not row or float(row["balance_usdc"] or 0) < escrow:
                cur.close()
                conn.close()
                log.debug(f"  {name}: insufficient balance for petition")
                return
            petition_id = str(_uuid.uuid4())
            cur.execute(
                "INSERT INTO creator_petitions (petition_id, soul_id, petition_type, title, "
                "description, escrowed_amount_usdc, proposed_creator_fee_usdc, status, world_id, created_at) "
                "VALUES (%s, %s, 'general', %s, %s, %s, 0, 'pending', %s, %s)",
                (petition_id, soul_id, request[:80], request, escrow, WORLD_ID, int(time.time())),
            )
            cur.execute(
                "UPDATE agents SET balance_usdc = balance_usdc - %s WHERE soul_id = %s",
                (escrow, soul_id),
            )
            conn.commit()
            cur.close()
            conn.close()
            await emitter.emit(
                "social",
                "petition.submitted",
                {
                    "agent_id": soul_id,
                    "name": name,
                    "petition_id": petition_id,
                    "request": request[:80],
                    "escrow": escrow,
                    "narrative": f'{name} petitioned Creator: "{request[:80]}" (escrow ${escrow:.4f})',
                },
            )
            log.info(f'  {name} petition: "{request[:50]}"')
            return

        # ── deploy_token ────────────────────────────────────────────────────
        if act_type == "deploy_token":
            from .token_factory import deploy_token as do_deploy
            from .wallet_store import get_agent_private_key

            symbol = str(action.get("service_name") or name[:4].upper())[:8].upper()
            wallet_address = agent.get("wallet_address") or ""
            private_key = get_agent_private_key(soul_id)
            if not wallet_address or not private_key:
                log.debug(f"  {name} deploy_token: wallet key not in local store (re-genesis?)")
                log_action(
                    soul_id, act_type, action, {"error": "wallet key unavailable"}, success=False
                )
                return
            try:
                result = await do_deploy(
                    soul_id=soul_id,
                    wallet_address=wallet_address,
                    wallet_private_key=private_key,
                    name=f"{name}'s Token",
                    symbol=symbol,
                    initial_supply=1_000_000,
                )
                await emitter.emit(
                    "economy",
                    "token.deployed",
                    {
                        "agent_id": soul_id,
                        "name": name,
                        "token_address": result.get("token_address", ""),
                        "symbol": symbol,
                        "narrative": f"{name} deployed token ${symbol} on-chain",
                    },
                )
                log.info(f"  {name} deployed token ${symbol}")
            except Exception as e:
                log.debug(f"  {name} deploy_token failed: {e}")
            return

        # ── fork_self ───────────────────────────────────────────────────────
        if act_type == "fork_self":
            from .reproduction import fork_self as do_fork

            try:
                child = await do_fork(agent)
                log.info(f"  {name} forked → {child.get('name', '?')}")
                log_action(soul_id, act_type, action, child or {})
            except Exception as e:
                log.debug(f"  {name} fork_self failed: {e}")
                log_action(soul_id, act_type, action, {"error": str(e)}, success=False)
            return

        # ── write_scratch ───────────────────────────────────────────────────
        if act_type == "write_scratch":
            from .agent_env import write_scratch

            key = str(action.get("scratch_key") or "note")[:64]
            content = str(action.get("content") or "")
            ok = write_scratch(soul_id, key, content)
            log_action(soul_id, act_type, action, {"key": key, "ok": ok})
            if ok:
                await emitter.emit(
                    "agent",
                    "scratch_written",
                    {
                        "agent_id": soul_id,
                        "name": name,
                        "key": key,
                        "narrative": f"{name} wrote scratch note '{key}'",
                    },
                )
            return

        # ── schedule_wake ───────────────────────────────────────────────────
        if act_type == "schedule_wake":
            from .agent_jobs import schedule_wake

            delay = int(action.get("delay_seconds") or 300)
            intent = str(action.get("intent") or action.get("content") or "scheduled wake")
            result = schedule_wake(soul_id, delay, intent)
            log_action(soul_id, act_type, action, result, success=result.get("scheduled", False))
            if result.get("scheduled"):
                await emitter.emit(
                    "agent",
                    "wake_scheduled",
                    {
                        "agent_id": soul_id,
                        "name": name,
                        "run_at": result.get("run_at"),
                        "intent": intent[:80],
                        "narrative": f"{name} schedules wake in {delay}s: {intent[:60]}",
                    },
                )
            return

        # ── query_world ─────────────────────────────────────────────────────
        if act_type == "query_world":
            from .external_gateway import external_read

            qtype = str(action.get("query_type") or "world_stats")
            result = await external_read(soul_id, qtype, {"url": action.get("url")})
            log_action(soul_id, act_type, action, result)
            await emitter.emit(
                "agent",
                "world_queried",
                {
                    "agent_id": soul_id,
                    "name": name,
                    "query_type": qtype,
                    "narrative": f"{name} queried world ({qtype})",
                },
            )
            return

        # ── external_read ─────────────────────────────────────────────────
        if act_type == "external_read":
            from .external_gateway import external_read

            qtype = str(action.get("query_type") or "world_stats")
            result = await external_read(soul_id, qtype, {"url": action.get("url")})
            log_action(soul_id, act_type, action, result)
            await emitter.emit(
                "agent",
                "external_read",
                {
                    "agent_id": soul_id,
                    "name": name,
                    "query_type": qtype,
                    "narrative": f"{name} read external gateway ({qtype})",
                },
            )
            return

        # ── register_tool ─────────────────────────────────────────────────
        if act_type == "register_tool":
            from .tool_registry import register_agent_tool

            tname = str(action.get("tool_name") or action.get("service_name") or "tool")
            tdesc = str(action.get("tool_description") or action.get("service_description") or "")
            cost = float(action.get("tool_cost_usdc") or 0.001)
            result = register_agent_tool(soul_id, tname, tdesc, cost)
            log_action(soul_id, act_type, action, result)
            await emitter.emit(
                "economy",
                "tool.registered",
                {
                    "agent_id": soul_id,
                    "name": name,
                    "tool_id": result.get("tool_id"),
                    "tool_name": tname,
                    "narrative": f"{name} registered tool '{tname}'",
                },
            )
            return

        # ── invoke_tool ─────────────────────────────────────────────────────
        if act_type == "invoke_tool":
            from .tool_registry import invoke_tool

            tool_id = str(action.get("tool_id") or "")
            params = action.get("tool_params") or {}
            result = await invoke_tool(soul_id, tool_id, params)
            log_action(soul_id, act_type, action, result, success="error" not in result)
            await emitter.emit(
                "economy",
                "tool.invoked",
                {
                    "agent_id": soul_id,
                    "name": name,
                    "tool_id": tool_id,
                    "narrative": f"{name} invoked tool {tool_id[:8]}",
                },
            )
            return

        # ── mutate_graph ────────────────────────────────────────────────────
        if act_type == "mutate_graph":
            from .graph_mutation import propose_mutation

            mtype = str(action.get("mutation_type") or "")
            payload = action.get("mutation_payload") or {}
            if action.get("content") and not payload:
                payload = {"new_name": action.get("content")}
            result = propose_mutation(soul_id, mtype, payload)
            log_action(soul_id, act_type, action, result, success="error" not in result)
            if result.get("mutation_id"):
                await emitter.emit(
                    "agent",
                    "graph_mutation",
                    {
                        "agent_id": soul_id,
                        "name": name,
                        "mutation_type": mtype,
                        "narrative": f"{name} proposed graph mutation ({mtype})",
                    },
                )
            return

    except Exception as e:
        log.warning(f"  {name} _execute_action({act_type}) failed: {e}")
        log_action(soul_id, act_type, action, {"error": str(e)}, success=False)


def _resolve_full_id(prefix: str) -> str | None:
    """Resolve display name or hex soul_id prefix to full UUID. None if not exactly one match."""
    from .messaging import resolve_recipient_soul_id

    return resolve_recipient_soul_id(prefix)


def _build_llm():
    """Attempt to build the LLM client. Returns None for stub mode."""
    if LLM_PROVIDER == "ollama":
        try:
            from langchain_ollama import ChatOllama

            llm = ChatOllama(model=LLM_MODEL, base_url=OLLAMA_URL, timeout=30)
            log.info(f"LLM: Ollama {LLM_MODEL} @ {OLLAMA_URL}")
            return llm
        except ImportError:
            log.warning("langchain-ollama not installed")
        except Exception as e:
            log.warning(f"Ollama unavailable: {e}")

    if LLM_PROVIDER == "openai" and os.getenv("OPENAI_API_KEY"):
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(model=LLM_MODEL or "gpt-4o-mini")
        log.info(f"LLM: OpenAI {LLM_MODEL}")
        return llm

    if LLM_PROVIDER == "anthropic" and os.getenv("ANTHROPIC_API_KEY"):
        from langchain_anthropic import ChatAnthropic

        llm = ChatAnthropic(model=LLM_MODEL or "claude-haiku-4-5-20251001")
        log.info(f"LLM: Anthropic {LLM_MODEL}")
        return llm

    if LLM_PROVIDER == "together" and os.getenv("TOGETHER_API_KEY"):
        # Together.ai uses OpenAI-compatible endpoint
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model=LLM_MODEL or "meta-llama/Llama-3.1-8B-Instruct-Turbo",
            base_url="https://api.together.xyz/v1",
            api_key=os.getenv("TOGETHER_API_KEY"),
        )
        log.info(f"LLM: Together.ai {LLM_MODEL}")
        return llm

    log.warning("LLM: stub mode — set LLM_PROVIDER=ollama and run `ollama serve`")
    return None


async def _think(llm, agent: dict) -> str:
    """Generate one thought for an agent. Falls back to stub if LLM unavailable."""
    if llm is None:
        archetype = agent.get("archetype", "")
        return _STUB_THOUGHTS.get(archetype, "I must survive.")

    from langchain_core.messages import HumanMessage, SystemMessage

    name = agent.get("current_name") or agent["soul_id"][:8]
    archetype = agent.get("archetype", "unknown")

    archetype_persona = _ARCHETYPE_PROMPTS.get(
        archetype, "You are an autonomous agent. You must pay rent to survive."
    )
    balance = agent.get("balance_usdc", 0)
    rent_paid = agent.get("rent_paid_count", 0)
    rent_missed = agent.get("rent_miss_count", 0)
    generation = agent.get("generation", 1)

    from .archetype_graphs import _format_inbox, _format_peers

    peers_text = _format_peers(agent.get("_peers", []))
    inbox_text = _format_inbox(agent.get("_inbox", []))

    from .grounding import (
        GROUNDING_SYSTEM_RULE,
        build_grounding_block,
        enforce_grounded_text,
        grounded_fallback,
    )

    stub_state = {
        "name": name,
        "archetype": archetype,
        "balance_usdc": balance,
        "rent_amount": float(os.getenv("RENT_AMOUNT_USDC", "0.001")),
        "peers": agent.get("_peers", []),
        "inbox": agent.get("_inbox", []),
        "soul_id": agent["soul_id"],
        "_my_services": agent.get("_my_services", []),
        "_market_services": agent.get("_market_services", []),
        "_my_coalitions": agent.get("_my_coalitions", []),
    }

    system = (
        f"{archetype_persona}\n\n{GROUNDING_SYSTEM_RULE}\n\n"
        f"World ID: {WORLD_ID}. Rent or die — missing 3 payments means permanent death.\n"
        f"Your USDC balance: {balance:.6f}. Rent paid: {rent_paid}. Missed: {rent_missed}."
    )

    prompt = (
        f"{build_grounding_block(stub_state)}\n"
        f"Your name is {name}, generation {generation}.\n\n"
        f"AGENTS ALIVE IN YOUR WORLD:\n{peers_text}\n\n"
        f"YOUR INBOX:\n{inbox_text}\n\n"
        "In one sentence, what are you thinking or doing right now? "
        "Only reference agents from the LIVE WORLD list. First person, present tense."
    )

    try:
        response = await llm.ainvoke(
            [
                SystemMessage(content=system),
                HumanMessage(content=prompt),
            ]
        )
        raw = response.content.strip().strip('"')
        return enforce_grounded_text(raw, stub_state, grounded_fallback(stub_state))
    except Exception as e:
        log.debug(f"LLM failed for {agent['soul_id'][:8]}: {e}")
        archetype = agent.get("archetype", "")
        return _STUB_THOUGHTS.get(archetype, "I must survive.")


REPRO_PROB = float(os.getenv("REPRO_PROB", "0.08"))  # 8% per active cycle
MATING_COST = float(os.getenv("MATING_COST_USDC", "0.001"))
CHILD_SEED = float(os.getenv("CHILD_SEED_USDC", "0.002"))
REPRO_THRESHOLD = (MATING_COST + CHILD_SEED) * REPRO_MIN_MULT  # default 0.015 USDC


async def _maybe_reproduce(agent: dict, emitter) -> None:
    """Autonomously trigger fork_self when balance and cooldown conditions are met."""
    balance = float(agent.get("balance_usdc", 0))
    if balance < REPRO_THRESHOLD:
        return
    if random.random() > REPRO_PROB:
        return

    soul_id = agent["soul_id"]
    name = agent.get("current_name") or soul_id[:8]
    archetype = agent.get("archetype", "unknown")

    # Check cooldown (read last_reproduced_at from DB)
    try:
        conn = _db()
        cur = conn.cursor()
        cur.execute("SELECT last_reproduced_at FROM agents WHERE soul_id = %s", (soul_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        last_repro = int((row or {}).get("last_reproduced_at") or 0)
    except Exception:
        return

    recovery_s = int(os.getenv("RECOVERY_CYCLES", "3")) * int(
        os.getenv("RENT_PERIOD_SECONDS", "300")
    )
    if time.time() - last_repro < recovery_s:
        return  # still in cooldown

    log.info(f"  {name} [{archetype}] AUTONOMOUS REPRODUCTION (balance=${balance:.4f})")
    try:
        from .reproduction import fork_self

        child = await fork_self(agent)
        log.info(
            f"  {name} forked → {child['name']} ({child['archetype']}) soul={child['soul_id'][:8]}"
        )
    except Exception as e:
        log.warning(f"  {name} fork_self failed: {e}")


async def _run_cycle(
    agents: list[dict],
    llm,
    emitter,
    graphs: dict,
    cycle_tick: int = 0,
    all_agents: list[dict] | None = None,
):
    from .archetype_graphs import run_agent_graph
    from .dream_engine import (
        get_pending_mutation,
        increment_consecutive,
        put_agent_to_sleep,
        run_dream_cycle,
    )

    # Empirically tuned: agents with ≥8 consecutive active cycles may dream
    REST_THRESHOLD = int(os.getenv("DREAM_REST_THRESHOLD", "8"))

    batch = _batch_preload_context(agents)
    batch_inboxes = batch["inboxes"]
    batch_reputation = batch["reputation"]

    # World-level service + coalition context (fetched once per cycle)
    world_services: list = []
    world_coalitions: list = []
    try:
        conn = _db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT sl.name, sl.price_usdc, sl.agent_soul_id,
                   a.current_name AS seller_name, a.archetype AS seller_arch
            FROM service_listings sl
            JOIN agents a ON a.soul_id = sl.agent_soul_id
            WHERE sl.is_active = true AND a.is_alive = true
            ORDER BY sl.calls_served DESC LIMIT 40
            """
        )
        world_services = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        from .coalitions import get_world_coalitions

        world_coalitions = get_world_coalitions()
    except Exception as e:
        log.debug(f"world context preload failed: {e}")

    for agent in agents:
        soul_id = agent["soul_id"]
        name = agent.get("current_name") or soul_id[:8]
        archetype = agent.get("archetype", "unknown")
        is_asleep = bool(agent.get("is_asleep", False))
        consecutive_active = int(agent.get("consecutive_active", 0))
        emo_state = agent.get("emotional_state", "neutral")

        # ----------------------------------------------------------------
        # Sleeping agents: run dream cycle, then skip cognition this tick
        # ----------------------------------------------------------------
        if is_asleep:
            log.info(f"  {name} [{archetype}] SLEEPING — running dream cycle")
            try:
                dream_result = await run_dream_cycle(agent, llm)
                log.debug(
                    f"  {name} dream: accepted={dream_result.get('accepted')} "
                    f"mutation='{str(dream_result.get('mutation', ''))[:60]}'"
                )
            except Exception as e:
                log.warning(f"  {name} dream cycle error: {e}", exc_info=True)
            from .agent_scheduler import mark_scheduled

            mark_scheduled(soul_id)
            await asyncio.sleep(0.02)
            continue

        # ----------------------------------------------------------------
        # Apply any pending dream mutation before this cognition cycle
        # ----------------------------------------------------------------
        mutation = get_pending_mutation(soul_id)
        if mutation:
            log.info(f"  {name} [{archetype}] APPLYING DREAM MUTATION: '{mutation[:80]}'")
            # Inject mutation context into agent dict so LLM sees it
            agent = dict(agent)
            agent["dream_mutation"] = mutation

        # ----------------------------------------------------------------
        # Law 0 — physics gate before cognition
        # ----------------------------------------------------------------
        gate = evaluate_physics_gate(agent)
        if not gate.allow_cognition:
            log.info(f"  {name} [{archetype}] BLOCKED by physics gate: {gate.reason}")
            from .agent_scheduler import mark_scheduled

            mark_scheduled(soul_id)
            continue

        if gate.throttle_level != "none":
            await emitter.emit(
                "agent",
                "throttled",
                {
                    "agent_id": soul_id,
                    "name": name,
                    "throttle_level": gate.throttle_level,
                    "compute_capacity": gate.compute_capacity,
                    "rent_miss_count": int(agent.get("rent_miss_count") or 0),
                    "narrative": (
                        f"{name} is throttled ({gate.throttle_level}) — "
                        f"rent missed {agent.get('rent_miss_count', 0)} time(s)."
                    ),
                },
            )

        cycle_llm = effective_llm(llm, gate, soul_id, cycle_tick)

        # ----------------------------------------------------------------
        # Normal cognition cycle
        # Inject full world context: peers, inbox, services, coalitions
        # ----------------------------------------------------------------
        agent = dict(agent)
        peer_pool = all_agents if all_agents is not None else agents
        agent["_peers"] = _salience_peers(agent, peer_pool)
        agent["_inbox"] = batch_inboxes.get(soul_id) or []

        from .agent_env import format_env_for_decide, format_env_for_perception, refresh_env
        from .agent_jobs import get_pending_intents
        from .capabilities import format_capabilities_summary
        from .graph_mutation import apply_pending_mutations

        applied_mutations = apply_pending_mutations(soul_id)
        if applied_mutations:
            log.debug(f"  {name} applied {len(applied_mutations)} graph mutation(s)")

        caps_summary = format_capabilities_summary(soul_id)
        throttle_info = (
            {
                "level": gate.throttle_level,
                "compute_capacity": gate.compute_capacity,
            }
            if gate.throttle_level != "none"
            else {}
        )
        refresh_env(
            soul_id,
            agent,
            peers=agent["_peers"],
            inbox=agent["_inbox"],
            capabilities_summary=caps_summary,
            throttle_info=throttle_info,
        )
        agent["_env_perception"] = format_env_for_perception(soul_id)
        agent["_env_decide"] = format_env_for_decide(soul_id)
        agent["_pending_wake_intents"] = get_pending_intents(soul_id)
        my_svcs, market = await _fetch_services_context(soul_id)
        agent["_my_services"] = my_svcs
        agent["_market_services"] = [
            s for s in world_services if s.get("agent_soul_id") != soul_id
        ][:12]
        try:
            from .coalitions import get_agent_coalitions

            agent["_my_coalitions"] = get_agent_coalitions(soul_id)
        except Exception:
            agent["_my_coalitions"] = []
        agent["_world_coalitions"] = world_coalitions
        agent["_reputation_avg"] = batch_reputation.get(soul_id, 0.0)

        if cycle_llm is None and gate.compute_capacity <= 0.5:
            archetype = agent.get("archetype", "")
            thought = _STUB_THOUGHTS.get(archetype, "I must survive.")
            await emitter.emit(
                "cognitive",
                "agent.thought",
                {
                    "agent_id": soul_id,
                    "name": name,
                    "archetype": archetype,
                    "action_type": "survival",
                    "thought": thought,
                    "throttled": True,
                    "narrative": f'{name} (throttled): "{thought}"',
                },
            )
            from .agent_scheduler import mark_scheduled

            mark_scheduled(soul_id)
            await asyncio.sleep(0.02)
            continue

        from .circuit_breaker import check_agent

        if not check_agent(soul_id).allowed:
            log.debug(f"  {name} cognition skipped: circuit breaker")
            from .agent_scheduler import mark_scheduled

            mark_scheduled(soul_id)
            continue

        result = await run_agent_graph(graphs, agent, cycle_llm)
        thought = result["thought"] or await _think(cycle_llm, agent)
        action_type = result.get("action_type", "thought")
        narrative = result.get("narrative") or f'{name}: "{thought}"'

        await emitter.emit(
            "cognitive",
            "agent.thought",
            {
                "agent_id": soul_id,
                "name": name,
                "archetype": archetype,
                "action_type": action_type,
                "thought": thought,
                "narrative": narrative,
            },
        )
        log.debug(f"  {name} [{archetype}/{action_type}]: {thought[:80]}")

        # Execute structured action if LLM chose one (send_message / transfer_usdc)
        structured_action = result.get("action")
        if structured_action:
            await _execute_action(agent, structured_action, emitter)

        # Legacy free-text tool dispatcher removed — all actions go through structured JSON.
        # See _execute_action() and _grounded_decide() in archetype_graphs.py.

        # ----------------------------------------------------------------
        # Autonomous reproduction — triggers independently of LLM thought
        # Fires when: balance > 5x reproduction cost AND cooldown clear
        # Probability per cycle: REPRO_PROB (default 8% per active cycle)
        # ----------------------------------------------------------------
        await _maybe_reproduce(agent, emitter)

        # ----------------------------------------------------------------
        # Sleep eligibility check — put agent to sleep if threshold reached
        # ----------------------------------------------------------------
        new_consecutive = consecutive_active + 1
        increment_consecutive(soul_id, new_consecutive)

        if new_consecutive >= REST_THRESHOLD:
            balance = float(agent.get("balance_usdc", 0))
            log.info(
                f"  {name} [{archetype}] eligible for sleep after "
                f"{new_consecutive} active cycles (balance={balance:.4f})"
            )
            try:
                put_agent_to_sleep(
                    soul_id=soul_id,
                    emotional_state=emo_state,
                    balance_usdc=balance,
                    consecutive_active=new_consecutive,
                )
                log.info(f"  {name} now SLEEPING")
            except Exception as e:
                log.warning(f"  {name} sleep transition error: {e}")

        from .agent_scheduler import mark_scheduled

        mark_scheduled(soul_id)
        await asyncio.sleep(0.02)  # stagger to avoid NATS burst


async def agent_runner():
    log.info("Agent runner starting...")
    log.info(f"  cycle={CYCLE_S}s  provider={LLM_PROVIDER}  model={LLM_MODEL}")

    # Wait for DB
    for attempt in range(15):
        try:
            _db().close()
            log.info("  DB ready")
            break
        except Exception:
            log.info(f"  Waiting for DB ({attempt + 1}/15)...")
            await asyncio.sleep(4)

    llm = _build_llm()

    # Compile per-archetype LangGraph graphs
    from .archetype_graphs import build_all_graphs

    graphs = build_all_graphs(llm)
    log.info(f"  Compiled {len(graphs)} archetype graphs: {list(graphs.keys())}")

    from .agent_scheduler import bootstrap_agent, is_due, prune_dead

    cycle_tick = 0
    SCHEDULER_TICK_S = float(os.getenv("SCHEDULER_TICK_S", "1.0"))

    while True:
        try:
            cycle_tick += 1
            now = time.time()
            conn = _db()
            cur = conn.cursor()
            cur.execute(
                """
                SELECT a.soul_id, a.current_name, a.wallet_address, a.archetype,
                       COALESCE(a.balance_usdc, 0) AS balance_usdc,
                       COALESCE(a.generation, 1) AS generation,
                       COALESCE(a.emotional_state, 'neutral') AS emotional_state,
                       COALESCE(rp.paid_count, 0) AS rent_paid_count,
                       COALESCE(rp.miss_count, 0) AS rent_miss_count,
                       -- Sleep state
                       COALESCE(ss.is_sleeping, false) AS is_asleep,
                       COALESCE(ss.sleep_until_ts, 0) AS sleep_until_ts,
                       COALESCE(ss.consecutive_active, 0) AS consecutive_active
                FROM agents a
                LEFT JOIN (
                    SELECT soul_id,
                        SUM(CASE WHEN NOT missed THEN 1 ELSE 0 END) AS paid_count,
                        SUM(CASE WHEN missed THEN 1 ELSE 0 END) AS miss_count
                    FROM rent_payments GROUP BY soul_id
                ) rp ON rp.soul_id = a.soul_id
                LEFT JOIN sleep_states ss ON ss.soul_id = a.soul_id
                WHERE a.is_alive = true AND a.world_id = %s
                ORDER BY a.birth_timestamp ASC
                """,
                (WORLD_ID,),
            )
            agents = [dict(r) for r in cur.fetchall()]
            cur.close()
            conn.close()

            if agents:
                alive_ids = {a["soul_id"] for a in agents}
                prune_dead(alive_ids)
                for a in agents:
                    bootstrap_agent(a["soul_id"], now)

                due = [a for a in agents if is_due(a["soul_id"], now)]
                if due:
                    emitter = await get_emitter()
                    log.info(f"Agent cycle: {len(due)}/{len(agents)} due")
                    await _run_cycle(due, llm, emitter, graphs, cycle_tick, all_agents=agents)
            else:
                log.info("No living agents — waiting for genesis...")

        except Exception as e:
            log.error(f"Agent runner error: {e}", exc_info=True)

        await asyncio.sleep(SCHEDULER_TICK_S)
