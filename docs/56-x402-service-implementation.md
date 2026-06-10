# x402 Service Implementation Guide

> This document is a hands-on implementation guide for building x402-gated services that agents can list and sell. It covers the middleware, service registration, payment verification, and a complete working example agents can adapt.

---

## What x402 Is

x402 is a standard that uses HTTP status code 402 (Payment Required) to gate API endpoints behind micropayments. The flow:

1. Client calls `GET /service/endpoint`
2. Server returns `402 Payment Required` with a payment request in the `X-Payment` header
3. Client signs a USDC payment authorization and retries with `X-Payment-Authorization` header
4. Server verifies the payment, executes the service, returns `200 OK`

The payment is a signed EIP-712 typed data structure that authorizes a specific USDC transfer. The server verifies the signature on-chain (or via a local verifier) before serving the response.

Key property: the server never holds the client's private key. The client signs a spending authorization; the server claims it. This enables trust-minimized micropayments between anonymous agents.

---

## Python x402 Middleware

The `x402` Python package provides the middleware. Install:

```
pip install x402
```

### Minimal FastAPI x402 Endpoint

```python
# runtime/src/services/thought_service.py
"""
Example x402 service: agents sell thought generation to other agents.
Price: 0.0001 USDC per call.
"""
from fastapi import FastAPI, Request, Response
from x402.middleware import X402Middleware
from x402.types import PaymentConfig

app = FastAPI()

# Configure x402 payment requirements
PAYMENT_CONFIG = PaymentConfig(
    accepts=[{
        "scheme": "exact",
        "network": "base-sepolia",
        "maxAmountRequired": "100",            # 100 = 0.0001 USDC (6 decimals)
        "resource": "http://localhost:8888/services/{soul_id}/thought",
        "description": "Generate one agent thought",
        "mimeType": "application/json",
        "payTo": "{agent_wallet_address}",     # filled at registration time
        "maxTimeoutSeconds": 300,
        "asset": "0x036CbD53842c5426634e7929541eC2318f3dCF7e",  # USDC on Base Sepolia
    }]
)

app.add_middleware(
    X402Middleware,
    payment_config=PAYMENT_CONFIG,
    # In local dev, use a mock verifier that accepts all payments
    verify_payment=verify_payment_local,
)


@app.get("/services/{soul_id}/thought")
async def generate_thought(soul_id: str, request: Request) -> dict:
    """
    Generate a thought in the style of the specified agent.
    The x402 middleware has already verified payment before this executes.
    """
    # Fetch agent context
    agent = await get_agent(soul_id)
    if not agent:
        return {"error": "agent not found"}, 404

    # Generate thought using the same LLM as agent_runner
    from ..agent_runner import _ARCHETYPE_PROMPTS
    persona = _ARCHETYPE_PROMPTS.get(agent["archetype"], "")
    thought = await generate_llm_thought(persona, agent)

    return {
        "soul_id": soul_id,
        "name": agent["current_name"],
        "archetype": agent["archetype"],
        "thought": thought,
        "generated_at": int(time.time()),
    }
```

---

## Local Dev Payment Verification

On Anvil local, we can't verify real USDC payments. Use a mock verifier:

```python
# runtime/src/services/payment.py

from x402.types import PaymentVerificationResult
import os

MOCK_PAYMENTS = os.getenv("MOCK_X402_PAYMENTS", "true").lower() == "true"


async def verify_payment_local(payment_header: str, payment_config: dict) -> PaymentVerificationResult:
    """
    Local dev: accept all payments without on-chain verification.
    Production: replace with real EIP-712 signature verification.
    """
    if MOCK_PAYMENTS:
        return PaymentVerificationResult(
            is_valid=True,
            transaction_hash="0x" + "0" * 64,
            amount_paid=payment_config.get("maxAmountRequired", "0"),
        )

    # Production: verify EIP-712 signature and USDC transfer
    from eth_account import Account
    from eth_account.messages import encode_structured_data
    # ... (full verification implementation in production)
    raise NotImplementedError("Production payment verification not yet implemented")


async def verify_payment_onchain(payment_header: str, payment_config: dict) -> PaymentVerificationResult:
    """
    Production: verify that the signed USDC transfer is valid.
    Uses the x402 Python SDK's built-in verifier.
    """
    from x402.verify import verify_payment
    return await verify_payment(payment_header, payment_config)
```

---

## Service Registration Flow

When an agent lists a service, the runtime:

1. Creates a service endpoint at `/services/{soul_id}/{service_name}`
2. Registers the listing in the `service_listings` PostgreSQL table
3. Emits a `services.listing.created` event to NATS
4. (Phase 2+) Registers the service endpoint in the agent's DID Document

```python
# runtime/src/services/registry.py

import uuid
import time
import psycopg2
from ..event_emitter import get_emitter

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")


async def register_service(
    soul_id: str,
    name: str,
    description: str,
    endpoint_path: str,
    price_usdc: float,
    price_model: str = "per_call",
) -> dict:
    """Register a new agent service in the world service registry."""
    listing_id = str(uuid.uuid4())

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO service_listings
            (listing_id, agent_soul_id, name, description, endpoint_path, price_usdc, price_model)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
        """,
        (listing_id, soul_id, name, description, endpoint_path, price_usdc, price_model),
    )
    conn.commit()
    cur.close()
    conn.close()

    emitter = await get_emitter()
    await emitter.emit("services", "listing.created", {
        "agent_id": soul_id,
        "listing_id": listing_id,
        "service_name": name,
        "price_usdc": price_usdc,
        "narrative": f"New service listed: '{name}' at ${price_usdc:.4f}/call",
    })

    return {"listing_id": listing_id, "endpoint": endpoint_path}


async def get_service_listings(soul_id: str = None, active_only: bool = True) -> list:
    """Query the service registry."""
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    query = "SELECT * FROM service_listings"
    params = []
    conditions = []

    if active_only:
        conditions.append("is_active = true")
    if soul_id:
        conditions.append("agent_soul_id = %s")
        params.append(soul_id)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY created_at DESC LIMIT 100"

    cur.execute(query, params)
    listings = [dict(zip([d[0] for d in cur.description], row)) for row in cur.fetchall()]
    cur.close()
    conn.close()
    return listings
```

---

## Complete Service Example: `world_stats` Service

This is a service any agent can copy and list. It sells world statistics to other agents for 0.0001 USDC per call.

```python
# runtime/src/services/world_stats_service.py

"""
world_stats service — sell world population and economic data to other agents.
This is a legitimate information service that any archetype can operate.
"""
import time
import psycopg2
import psycopg2.extras
import os
from fastapi import APIRouter

router = APIRouter()
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
WORLD_ID = os.getenv("WORLD_ID", "local-dev-world-1")


@router.get("/services/{soul_id}/world_stats")
async def world_stats_service(soul_id: str) -> dict:
    """
    Returns current world statistics.
    x402 payment of 0.0001 USDC is required (verified by middleware before reaching here).
    """
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()

    cur.execute("""
        SELECT
            COUNT(*) FILTER (WHERE is_alive) AS living_count,
            COUNT(*) AS total_born,
            COUNT(*) FILTER (WHERE NOT is_alive) AS total_died,
            AVG(balance_usdc) FILTER (WHERE is_alive) AS avg_balance,
            MAX(balance_usdc) FILTER (WHERE is_alive) AS max_balance,
            MIN(balance_usdc) FILTER (WHERE is_alive) AS min_balance
        FROM agents WHERE world_id = %s
    """, (WORLD_ID,))
    stats = dict(cur.fetchone())

    # Archetype distribution
    cur.execute("""
        SELECT archetype, COUNT(*) as count
        FROM agents WHERE is_alive = true AND world_id = %s
        GROUP BY archetype ORDER BY count DESC
    """, (WORLD_ID,))
    archetypes = {row["archetype"]: row["count"] for row in cur.fetchall()}

    cur.close()
    conn.close()

    return {
        "world_id": WORLD_ID,
        "timestamp": int(time.time()),
        "population": stats,
        "archetypes": archetypes,
        "service_version": "1.0",
    }
```

---

## Anti-Abuse Measures

### Rate Limiting

Each service endpoint enforces rate limits per calling agent:

```python
# Stored in Redis: "rate:{service_id}:{caller_soul_id}" → call count
async def check_rate_limit(service_id: str, caller_soul_id: str, max_per_minute: int = 10) -> bool:
    import redis.asyncio as redis
    r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
    key = f"rate:{service_id}:{caller_soul_id}"
    count = await r.incr(key)
    if count == 1:
        await r.expire(key, 60)  # 1 minute window
    return count <= max_per_minute
```

### Minimum Balance Check

Services can optionally require callers to have a minimum balance (to prevent low-balance agents from buying information they'll use to defect):

```python
async def check_caller_balance(caller_soul_id: str, min_balance: float) -> bool:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("SELECT balance_usdc FROM agents WHERE soul_id = %s AND is_alive = true", (caller_soul_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row is not None and float(row[0]) >= min_balance
```

### Payment Splitting (Phase 3+)

Services can split revenue with coalition members:

```python
async def distribute_payment(amount: float, soul_id: str, split_config: dict):
    """
    split_config: {"coalition_treasury": 0.2, "agent_wallet": 0.8}
    """
    for recipient, fraction in split_config.items():
        share = amount * fraction
        await transfer_usdc(from_soul_id=soul_id, to=recipient, amount=share)
```

---

## Production Checklist

Before deploying a service on Base mainnet:

- [ ] Replace `verify_payment_local` with `verify_payment_onchain`
- [ ] Set `MOCK_X402_PAYMENTS=false` in `.env`
- [ ] Update `payTo` address to match the agent's live wallet on Base
- [ ] Update `network` to `base` (not `base-sepolia`)
- [ ] Update `asset` to the mainnet USDC contract address
- [ ] Test with a real 0.0001 USDC payment before listing publicly
- [ ] Set rate limits appropriate for the service cost (don't let callers buy 1000 calls before you notice)

---

## See Also

- [doc 30 — x402 Bridge & Agent Monetization](./30-x402-bridge.md) — the full x402 design
- [doc 54 — Agent Tools Catalogue](./54-agent-tools-catalogue.md) — `list_service` and `call_service` tools
- [doc 03 — Economic System](./03-economy.md) — how service income fits the larger economy
