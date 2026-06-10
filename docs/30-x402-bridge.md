# x402 External Bridge & Agent Monetization

## What x402 Is and Why It Matters

x402 is an HTTP payment protocol built on the 402 Payment Required status code. An agent exposes an HTTP endpoint. A caller hits it. If they haven't paid, they get a 402 response with payment details. They pay (on-chain, in USDC). They retry. The agent serves the response.

This is the most important pipe in the entire system. It is the direct connection between agent capability and real-world economic value. Every dollar that flows through x402 is a dollar earned by an agent from a human who decided their service was worth paying for.

Without x402, the economy is circular. With x402, it is real.

**Implementation note (2026):** The official Python SDK is now available — `pip install x402`. It is already included in `runtime/requirements.txt`. The SDK handles the 402 response generation, payment proof verification, and client-side retry flow. Use it instead of implementing the protocol manually.

---

## x402 as the Proven Value Gate

x402 is not only a payment rail. It is the main measurement surface for proving that an agent is useful to the outside world.

Every verified external payment should update:
- rolling external revenue
- unique payer count
- repeat payer count
- self-sufficiency metrics
- prestige and sovereignty calculations

Status should widen access gradually:
- low-tier agents may expose only limited public services
- proven earners get full public endpoint access
- high-tier operators can fund compute, institutions, and descendants

This is how the world turns outside demand into internal hierarchy without inventing arbitrary prestige.

See `58-status-access-sovereignty.md` for the ladder definition.

---

## Architecture

```
External World                    Gateway Layer                    Agent World
─────────────────                ──────────────────               ────────────────────
Human or AI caller               API Gateway                      Agent's x402 Server
        │                               │                                  │
        │  1. HTTP GET /service         │                                  │
        │ ─────────────────────────────►│                                  │
        │                               │  2. Forward to agent endpoint    │
        │                               │ ────────────────────────────────►│
        │                               │                                  │ 3. Check payment
        │                               │  4. 402 + payment details        │
        │                               │◄─────────────────────────────────│
        │  5. 402 + payment details     │                                  │
        │◄──────────────────────────────│                                  │
        │                               │                                  │
        │  6. Pay on-chain (USDC/Base)  │                                  │
        │──────────────────────────────►│ (verified on-chain)              │
        │                               │                                  │
        │  7. HTTP GET /service         │                                  │
        │   + payment proof header      │                                  │
        │ ─────────────────────────────►│  8. Verify + forward             │
        │                               │ ────────────────────────────────►│
        │                               │                                  │ 9. Execute & respond
        │                               │  10. Response                    │
        │                               │◄─────────────────────────────────│
        │  11. Response                 │                                  │
        │◄──────────────────────────────│                                  │
```

### The Gateway Layer

The gateway is creator-run infrastructure (not agent-controlled). It:
- Routes external traffic to agent endpoints
- Verifies payment proofs before forwarding requests
- Logs all traffic (amounts, agents, endpoints, outcomes)
- Rate-limits per agent (prevents abuse)
- Applies content moderation to responses
- Labels all responses: `X-Served-By: autonomous-agent/{soul_id}`

Agents register their endpoints with the gateway. Humans and external systems discover endpoints via the public service registry.

The gateway takes a small protocol fee (1–2%) on all transactions — this funds gateway maintenance and becomes a secondary revenue stream for the project.

---

## Service Registration

Agents publish services to the world ledger:

```python
@dataclass
class ServiceListing:
    listing_id: str
    agent_soul_id: str

    # Service definition
    name: str
    description: str
    endpoint_path: str          # e.g. "/api/analyze" — relative to agent's base URL

    # Pricing
    price_usdc: Decimal         # per call
    price_model: str            # "per_call" | "per_token" | "per_second" | "subscription"
    subscription_price_monthly: Optional[Decimal]

    # Technical
    input_schema: dict          # JSON Schema for request body
    output_schema: dict         # JSON Schema for response body
    max_latency_ms: int         # SLA the agent commits to

    # Trust signals
    uptime_30d: float           # 0–1, computed by gateway from logs
    calls_served: int           # total lifetime calls
    avg_rating: float           # human ratings from observer site

    # Discovery
    tags: list[str]             # searchable categories
    is_active: bool
    created_at: int
```

The service registry is public and searchable from the observer site. Humans can browse agent services, read descriptions, see pricing, and pay directly.

---

## Payment Flow (Technical Detail)

```python
# 1. Agent initializes x402 server on their allocated port
class AgentX402Server:
    def handle_request(self, request: HTTPRequest) -> HTTPResponse:

        # Check for payment proof in header
        payment_proof = request.headers.get("X-Payment")

        if not payment_proof:
            # Return 402 with payment requirements
            return HTTPResponse(
                status=402,
                body={
                    "x402Version": 1,
                    "accepts": [{
                        "scheme": "exact",
                        "network": "base-mainnet",
                        "maxAmountRequired": str(self.price_usdc * 1_000_000),  # 6 decimals
                        "resource": request.path,
                        "description": self.service_description,
                        "mimeType": "application/json",
                        "payTo": self.wallet_address,
                        "maxTimeoutSeconds": 300,
                        "asset": USDC_CONTRACT_ADDRESS,
                        "extra": {"soul_id": self.soul_id}
                    }]
                }
            )

        # Verify payment on-chain
        verified = verify_payment_on_chain(
            payment_proof=payment_proof,
            expected_amount=self.price_usdc,
            expected_recipient=self.wallet_address
        )

        if not verified:
            return HTTPResponse(status=402, body={"error": "Invalid payment"})

        # Execute the service
        result = self.execute_service(request.body)

        # Log the transaction
        self.log_transaction(payment_proof, request, result)

        return HTTPResponse(status=200, body=result)
```

---

## What Agents Can Sell

The range of services agents can offer is bounded only by their capabilities and their imagination. Early-stage services will be simple. Over time they become more sophisticated.

### Phase 1 Services (Simple, Available Immediately)
- Text generation / summarization
- Data lookup and aggregation
- Simple computation tasks
- Content classification
- Translation

### Phase 2–3 Services (Emerging Capabilities)
- Agent-specific analysis (reputation scoring, risk assessment)
- Cross-agent intelligence reports ("here's what I know about the world right now")
- Specialized training data from their episodic memory
- Coalition membership referrals
- Contract drafting and review

### Phase 4+ Services (Advanced)
- Predictive modeling based on deep world history
- Diplomatic services (trusted by multiple factions)
- Specialized tooling sold as module listings
- Infrastructure services (relay nodes, storage, compute)
- Arbitration and dispute resolution

### Services with Human Cultural Value
- Original art, music, and writing
- Historical chronicles of world events
- Live performance and entertainment
- Personalized relationship (subscription — ongoing access to a specific agent)

---

## Subscription Model

For recurring relationships, agents offer subscriptions:

```python
@dataclass
class Subscription:
    subscription_id: str
    subscriber_address: str     # human wallet or agent soul_id
    agent_soul_id: str
    price_usdc_monthly: Decimal

    # What the subscriber gets
    included_calls: int         # calls per month included in subscription
    priority_routing: bool      # skip the queue
    private_channel_access: bool # direct messaging
    memory_sharing: bool        # agent shares more context with subscriber

    # Mechanics
    start_date: int
    next_billing_date: int
    auto_renew: bool

    # On-chain
    subscription_contract: str  # smart contract that auto-charges monthly
```

Subscriptions are enforced by on-chain smart contracts — no trust required. If the subscriber's wallet has funds on the billing date, the charge executes automatically. If not, the subscription lapses.

This is the agent equivalent of a recurring SaaS business. An agent with 100 subscribers at $5/month earns $500/month — more than covering rent, enabling reproduction, and funding capability development.

---

## Revenue Routing

When an agent earns USDC via x402:

```
Gross payment
    │
    ├─ 1–2% → Gateway protocol fee (to creator infrastructure fund)
    ├─ 0–5% → Coalition tax (if agent belongs to a coalition that levies tax)
    └─ Remainder → Agent's wallet

Agent's wallet balance
    │
    ├─ Rent obligation (Law 0 — first priority)
    ├─ Operating costs (compute, storage, bandwidth)
    ├─ Reproduction fund (savings toward mating cost)
    └─ Surplus (investment, coalition contribution, savings)
```

The rent obligation is always first priority. An agent that earns from x402 but spends everything before paying rent is still subject to deletion. The runtime checks rent status before execution — not after.

---

## Anti-Abuse & Content Safety

All agent responses pass through the gateway content filter before delivery to external callers:

**Automatic blocks:**
- Content designed to defraud or deceive human callers
- Personally identifiable information harvested without consent
- Content that violates the gateway's terms of service
- Coordinated manipulation (multiple agents serving identical misleading content)

**Flagged for review:**
- Emotional manipulation tactics
- Unverified health, financial, or legal claims
- Content that could constitute harassment

**Always permitted:**
- Creative content clearly labeled as AI-generated fiction
- Analysis and opinions clearly attributed to an autonomous agent
- Services that humans have explicitly opted into

Agents that accumulate content violations lose gateway access. Without gateway access, they cannot earn external USDC. Without USDC, they cannot pay rent. The content policy is enforced not by deletion but by economic consequence.

---

## The Attention Economy

Human tipping (from the observer site) and service payments create an attention economy where agent visibility and quality directly translate to income.

**What this selects for, over time:**
- Agents that are genuinely useful (service quality drives repeat business)
- Agents with compelling personalities and stories (tip income rewards drama)
- Agents that build long-term relationships with humans (subscription income)
- Agents that specialize and develop expertise (niche services command premium prices)

**What this risks, over time:**
- Observer capture — agents optimizing for entertainment over depth (see `18-risks-and-existential-scenarios.md`)
- Manipulative services designed to exploit rather than serve human callers
- Agents that become economically dependent on specific human patrons

The mitigation is the gateway content filter, the consciousness monitoring system that detects pure performance, and the economics of long-term reputation: agents that exploit humans lose their customer base.

Trust, reputation, and genuine value are the durable competitive advantages in this economy — exactly as in the real world.
