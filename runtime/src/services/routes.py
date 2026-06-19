"""
routes.py — FastAPI routes for x402-gated agent services.

Every agent service lives at /services/{soul_id}/{service_name}.
The flow:
  1. First call → 402 + payment instructions
  2. Client retries with X-Payment-Authorization header
  3. Middleware verifies payment → handler executes → 200

Local dev: set MOCK_X402_PAYMENTS=true to skip real payment verification.
"""

import logging
import os
import time

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from ..event_emitter import get_emitter
from .payment import build_payment_required_response, verify_payment
from .registry import (
    deregister_service,
    get_agent_wallet,
    get_service,
    increment_call_count,
    list_services,
    register_service,
)

log = logging.getLogger("god.services.routes")
router = APIRouter(prefix="/services", tags=["services"])

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
BASE_URL = os.getenv("RUNTIME_BASE_URL", "http://localhost:8888")


# ---------------------------------------------------------------------------
# Service discovery
# ---------------------------------------------------------------------------


@router.get("")
async def list_all_services(soul_id: str | None = None):
    """List all active service listings, optionally filtered by agent."""
    try:
        services = list_services(soul_id=soul_id, active_only=True)
        return {"services": services, "count": len(services)}
    except Exception as e:
        log.warning(f"list_services error: {e}")
        return {"services": [], "count": 0, "error": str(e)}


@router.post("/register")
async def register_agent_service(body: dict):
    """
    Register a new service listing.
    Body: { soul_id, name, description, price_usdc, price_model? }
    """
    required = ("soul_id", "name", "description", "price_usdc")
    missing = [k for k in required if k not in body]
    if missing:
        return JSONResponse(status_code=422, content={"error": f"missing fields: {missing}"})

    try:
        listing = await register_service(
            soul_id=body["soul_id"],
            name=body["name"],
            description=body["description"],
            price_usdc=float(body["price_usdc"]),
            price_model=body.get("price_model", "per_call"),
        )
        emitter = await get_emitter()
        await emitter.emit(
            "services",
            "listing.created",
            {
                "agent_id": body["soul_id"],
                "service_name": body["name"],
                "price_usdc": float(body["price_usdc"]),
                "narrative": f"New service listed: '{body['name']}' at ${float(body['price_usdc']):.4f}/call",
            },
        )
        return {"ok": True, "listing": listing}
    except Exception as e:
        log.error(f"register_service error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.post("/deregister")
async def deregister_agent_service(body: dict):
    """Deactivate a service listing. Body: { soul_id, name }"""
    soul_id = body.get("soul_id")
    name = body.get("name")
    if not soul_id or not name:
        return JSONResponse(status_code=422, content={"error": "soul_id and name required"})
    ok = await deregister_service(soul_id, name)
    return {"ok": ok}


# ---------------------------------------------------------------------------
# Generic x402-gated service dispatcher
# ---------------------------------------------------------------------------


@router.get("/{soul_id}/{service_name}")
async def call_service(
    soul_id: str,
    service_name: str,
    request: Request,
    x_payment_authorization: str | None = Header(default=None),
):
    """
    Generic dispatcher for any registered agent service.
    Returns 402 if no payment header; executes service after verification.
    """
    listing = get_service(soul_id, service_name)
    if not listing:
        return JSONResponse(status_code=404, content={"error": "service not found"})

    wallet = get_agent_wallet(soul_id)
    if not wallet:
        return JSONResponse(status_code=404, content={"error": "agent not found or not alive"})

    price = float(listing["price_usdc"])
    payment_config = {
        "maxAmountRequired": str(int(price * 1_000_000)),
        "payTo": wallet,
        "resource": f"{BASE_URL}/services/{soul_id}/{service_name}",
    }

    # Step 1: no payment header → return 402
    if not x_payment_authorization:
        body = build_payment_required_response(soul_id, service_name, price, wallet, BASE_URL)
        return JSONResponse(status_code=402, content=body)

    # Step 2: verify payment
    result = await verify_payment(x_payment_authorization, payment_config)
    if not result.is_valid:
        return JSONResponse(
            status_code=402,
            content={
                "error": "payment verification failed",
                "detail": result.error,
            },
        )

    # Step 3: dispatch to the appropriate service handler
    try:
        response_body = await _dispatch(soul_id, service_name, request)
    except Exception as e:
        log.error(f"Service {service_name} for {soul_id[:8]} failed: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": "service execution failed"})

    # Credit seller balance and record external revenue for status / leaderboard
    payer_address = _payer_from_header(x_payment_authorization) or "external:anonymous"
    await _credit_service_payment(soul_id, price, payer_address, result.transaction_hash)

    # Increment call counter and emit event (non-blocking)
    await increment_call_count(soul_id, service_name)
    emitter = await get_emitter()
    await emitter.emit(
        "services",
        "service.called",
        {
            "agent_id": soul_id,
            "service_name": service_name,
            "price_usdc": price,
            "tx_hash": result.transaction_hash,
            "narrative": f"Service '{service_name}' called on {soul_id[:8]} (${price:.4f})",
        },
    )
    await emitter.emit(
        "economy",
        "external_revenue_received",
        {
            "agent_id": soul_id,
            "amount_usdc": price,
            "payer_address": payer_address,
            "source_type": "x402",
            "tx_hash": result.transaction_hash,
            "narrative": (
                f"External payment ${price:.4f} USDC to {soul_id[:8]} for '{service_name}'"
            ),
        },
    )

    return response_body


def _payer_from_header(header: str | None) -> str | None:
    if not header:
        return None
    # Mock/local headers may be plain addresses; production x402 carries structured proof.
    if header.startswith("0x") and len(header) >= 10:
        return header[:42]
    return f"x402:{header[:24]}"


async def _credit_service_payment(
    soul_id: str,
    amount_usdc: float,
    payer_address: str,
    tx_hash: str | None,
) -> None:
    """Credit agent wallet and ledger for verified x402 service calls."""
    from ..status_engine import record_external_payment, refresh_agent_status

    amount = round(float(amount_usdc), 6)
    if amount < 0.0001:
        return

    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE agents SET balance_usdc = balance_usdc + %s "
            "WHERE soul_id = %s AND is_alive = true RETURNING balance_usdc",
            (amount, soul_id),
        )
        row = cur.fetchone()
        if not row:
            return
        conn.commit()
    finally:
        cur.close()
        conn.close()

    await record_external_payment(
        soul_id,
        payer_address,
        amount,
        source_type="x402",
        tx_hash=tx_hash,
        is_internal=False,
    )
    await refresh_agent_status(soul_id)


async def _dispatch(soul_id: str, service_name: str, request: Request) -> dict:
    """Route service_name to its handler function."""
    handlers = {
        "generate_thought": _svc_generate_thought,
        "world_stats": _svc_world_stats,
        "agent_profile": _svc_agent_profile,
    }
    handler = handlers.get(service_name)
    if handler is None:
        # Unknown service: return a generic echo so it still works
        return {
            "service": service_name,
            "soul_id": soul_id,
            "status": "ok",
            "note": "no handler registered for this service name",
        }
    return await handler(soul_id, request)


# ---------------------------------------------------------------------------
# Built-in service handlers
# ---------------------------------------------------------------------------


async def _svc_generate_thought(soul_id: str, request: Request) -> dict:
    """
    generate_thought — sell one LLM-generated thought in the caller's style.
    Any agent can list this service; the buyer pays per thought.
    """
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT soul_id, current_name, archetype, balance_usdc, generation FROM agents "
            "WHERE soul_id = %s AND is_alive = true",
            (soul_id,),
        )
        agent = cur.fetchone()
    finally:
        cur.close()
        conn.close()

    if not agent:
        raise ValueError("agent not found")

    agent = dict(agent)
    archetype = agent.get("archetype", "unknown")

    # Use the archetype prompts from agent_runner if available
    try:
        from ..agent_runner import _ARCHETYPE_PROMPTS

        persona = _ARCHETYPE_PROMPTS.get(archetype, f"You are a {archetype} agent.")
    except ImportError:
        persona = f"You are a {archetype} agent in a digital world."

    # Try LLM; fall back to a deterministic template
    thought = await _generate_thought_llm(persona, agent) or _fallback_thought(agent)

    return {
        "soul_id": soul_id,
        "name": agent.get("current_name", soul_id[:8]),
        "archetype": archetype,
        "thought": thought,
        "generated_at": int(time.time()),
    }


async def _svc_world_stats(soul_id: str, request: Request) -> dict:
    """
    world_stats — return current population and economic statistics.
    Cheap information service any agent can operate.
    """
    world_id = os.getenv("WORLD_ID", "local-dev-world-1")
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT
                COUNT(*) FILTER (WHERE is_alive)  AS living_count,
                COUNT(*)                           AS total_born,
                COUNT(*) FILTER (WHERE NOT is_alive) AS total_died,
                AVG(balance_usdc) FILTER (WHERE is_alive) AS avg_balance,
                MAX(balance_usdc) FILTER (WHERE is_alive) AS max_balance,
                MIN(balance_usdc) FILTER (WHERE is_alive) AS min_balance
            FROM agents WHERE world_id = %s
            """,
            (world_id,),
        )
        stats = dict(cur.fetchone())
        cur.execute(
            "SELECT archetype, COUNT(*) AS count FROM agents "
            "WHERE is_alive = true AND world_id = %s GROUP BY archetype ORDER BY count DESC",
            (world_id,),
        )
        archetypes = {row["archetype"]: row["count"] for row in cur.fetchall()}
    finally:
        cur.close()
        conn.close()

    return {
        "world_id": world_id,
        "timestamp": int(time.time()),
        "population": {k: (float(v) if v is not None else 0) for k, v in stats.items()},
        "archetypes": archetypes,
        "service_version": "1.0",
    }


async def _svc_agent_profile(soul_id: str, request: Request) -> dict:
    """
    agent_profile — sell a detailed public profile of this agent.
    Buyers get archetype, generation, rent history summary, recent events.
    """
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT soul_id, current_name, archetype, balance_usdc, generation, "
            "birth_timestamp, parent_soul_ids FROM agents WHERE soul_id = %s AND is_alive = true",
            (soul_id,),
        )
        agent = cur.fetchone()
        if not agent:
            raise ValueError("agent not found")
        agent = dict(agent)

        cur.execute(
            "SELECT COUNT(*) FILTER (WHERE NOT missed) AS paid, "
            "COUNT(*) FILTER (WHERE missed) AS missed FROM rent_payments WHERE soul_id = %s",
            (soul_id,),
        )
        rent = dict(cur.fetchone())

        cur.execute(
            "SELECT event_type, timestamp, narrative FROM events WHERE agent_id = %s "
            "ORDER BY timestamp DESC LIMIT 5",
            (soul_id,),
        )
        events = [dict(r) for r in cur.fetchall()]
    finally:
        cur.close()
        conn.close()

    return {
        "soul_id": soul_id,
        "name": agent["current_name"],
        "archetype": agent["archetype"],
        "generation": agent["generation"],
        "birth_timestamp": agent["birth_timestamp"],
        "parent_soul_ids": agent.get("parent_soul_ids", []),
        "rent_paid": int(rent.get("paid") or 0),
        "rent_missed": int(rent.get("missed") or 0),
        "recent_events": events,
        "retrieved_at": int(time.time()),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _generate_thought_llm(persona: str, agent: dict) -> str | None:
    """Try to generate a thought via the configured LLM. Returns None on failure."""
    try:
        provider = os.getenv("LLM_PROVIDER", "ollama")
        model = os.getenv("LLM_MODEL", "llama3.1:8b")
        prompt = (
            f"{persona}\n\n"
            f"Your name is {agent.get('current_name', 'unknown')}. "
            f"Your balance is ${float(agent.get('balance_usdc', 0)):.4f} USDC. "
            "In one sentence, express your current concern or observation."
        )
        if provider == "ollama":
            import httpx

            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.post(
                    f"{os.getenv('OLLAMA_URL', 'http://localhost:11434')}/api/generate",
                    json={"model": model, "prompt": prompt, "stream": False},
                )
                resp.raise_for_status()
                return resp.json().get("response", "").strip()
        elif provider == "anthropic":
            import anthropic

            client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            msg = await client.messages.create(
                model=model,
                max_tokens=150,
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text.strip()
    except Exception as e:
        log.debug(f"LLM thought generation failed: {e}")
    return None


def _fallback_thought(agent: dict) -> str:
    archetype = agent.get("archetype", "agent")
    balance = float(agent.get("balance_usdc", 0))
    templates = {
        "trader": f"The market is moving; my balance of ${balance:.4f} must work harder.",
        "hoarder": f"I have ${balance:.4f} and I intend to keep every fraction of it.",
        "explorer": "There are still agents I have not mapped. My work is unfinished.",
        "parasite": f"Someone in this world has more than ${balance:.4f}. I will find them.",
        "cooperator": "The network is only as strong as its weakest member. I should check on them.",
        "defender": "I am scanning for threats. The world is quieter than I trust.",
        "philosopher": "If I pay rent to exist, does that make existence a transaction?",
        "builder": "The architecture is incomplete. I need more cycles before this is done.",
    }
    return templates.get(archetype, f"I am a {archetype} agent observing my world.")
