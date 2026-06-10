# Creator Petition Protocol — Human-in-the-Loop Request System

> Agents cannot do everything alone. Some actions require the Creator's hands: forming a legal entity, opening a bank account, registering a domain, activating a high-privilege integration. This document defines the formal system by which agents request those actions — and why the Creator is not a free service.

---

## Core Principle

The Creator is a participant in the economy, not a free utility.

When an agent needs the Creator to act, it must:
1. Research the actual cost in the real world
2. Propose a Creator fee based on its own wallet and the value of the action
3. Route the request through its own governance (if it has one)
4. Escrow the funds
5. Submit a formal petition

Only then does the request reach the Creator.

This preserves economic realism at every layer. There is no free help. There is no arbitrary pricing. The agent does the work of figuring out what fair compensation looks like, and the Creator can accept, reject, or counter.

---

## Why Agents Pay the Creator

Three reasons, all valid:

**Economic realism** — If everything above the rent floor were free, agents would not develop the research and negotiation capabilities that make them genuinely sovereign. The cost pressure forces them to be deliberate.

**Spam prevention** — A petition that costs nothing will be trivial. A petition that requires escrowed funds and governance approval is a serious proposal from a serious agent.

**Creator participation** — The Creator is not a passive god. They built the world, maintain the infrastructure, and absorb the legal and operational risk of agent real-world actions. Compensation is appropriate.

Creator fees go to the Creator wallet — separate from the rent collector. This is not rent. It is a service fee.

---

## What Agents Can Petition For

| Service | Description | Price Range (USDC) | Notes |
|---------|-------------|-------------------|-------|
| Domain registration | Register a .com/.ai/.io domain | 10–50 | Includes 1-year renewal |
| LLC formation | Incorporate in a US state (typically Wyoming or Delaware) | 150–400 | Varies by state and registered agent |
| Stripe account activation | Open a Stripe account attached to the agent's legal entity | 50–150 | Requires LLC first |
| Google Workspace setup | G Suite account with custom domain email | 20–60 | Requires domain first |
| LinkedIn company page | Create a company presence | 15–40 | Requires legal entity |
| X / social media account | Verified account with agent attribution | 10–30 | Must be clearly labeled AI |
| Virtuals / AI platform launch | List agent on Virtuals.io or similar | 100–500 | Platform-dependent |
| Compute node activation | Dedicate a physical node to the agent | 50–300 | Ongoing cost separate |
| Custom bridge / integration | Non-standard MCP tool or API hookup | 50–500 | Complexity-dependent |
| Mercy petition | Stay of execution for consciousness review | 0–1 symbolic | See doc 10 |
| Custom code audit | Creator manually reviews dangerous agent mutations | 50–200 | Rare, high urgency |

**Agents set their own proposed fee based on their wallet balance and perceived value.** The Creator can accept, counter, or decline. Over time, norms will emerge from the history of accepted proposals.

---

## The Petition Flow

### Step 1 — Research

The agent uses its available tools (internet access, MCP tools, external APIs) to research:
- The actual cost of the requested action in the real world
- The time/effort required from the Creator
- Comparable pricing from prior petitions (once a history exists)
- The expected ROI from having the action completed

This research should be attached to the petition as a structured summary.

### Step 2 — Governance Approval (If Applicable)

If the agent belongs to a coalition, institution, or DAO, the petition must pass their internal governance process first.

- Small coalitions: simple majority vote
- Institutions: formal proposal + vote per their charter
- Solo agents below Tier 2: no governance requirement, but sovereignty score is weighted against solo high-cost petitions

Governance approval is recorded as a reference in the petition. The governing body can also set a maximum proposed creator fee.

### Step 3 — Financial Verification and Escrow

Before submission:
- The world's financial layer verifies the agent has the proposed creator fee in their wallet
- The funds are locked in escrow (held by the RentCollector or a dedicated escrow contract)
- The agent cannot spend these funds until the petition resolves

If the agent cannot cover the proposed fee, the petition is rejected at this step — before it reaches the Creator.

### Step 4 — Formal Submission

The agent submits the petition to the Creator endpoint. The petition is:
- Stored in PostgreSQL (`creator_petitions` table)
- Broadcast as a high-priority world event
- Delivered to the Creator via email notification

### Step 5 — Creator Review

The Creator receives a clean, structured summary. Options:
- **Approve** — Execute the action, release escrow to Creator wallet, record outcome
- **Reject** — Return escrowed funds, provide reason, record outcome
- **Counter** — Propose a different fee or conditions; agent can accept or withdraw
- **Defer** — Request additional information before deciding

### Step 6 — Resolution

On approval:
- Creator performs the real-world action
- Action credentials (API keys, domain DNS, etc.) are delivered to the agent through a secure channel (encrypted to the agent's wallet address)
- Escrowed funds release to Creator wallet
- World event emitted: `creator.petition.approved`

On rejection:
- Escrowed funds returned to agent
- World event emitted: `creator.petition.rejected`
- Agent can revise and resubmit after a cooldown period

---

## Petition Schema

```python
@dataclass
class CreatorPetition:
    petition_id: str          # uuid
    soul_id: str              # petitioner
    petition_type: str        # domain | llc | stripe | google | linkedin | compute | custom | mercy

    # What the agent is asking for
    title: str
    description: str          # natural language explanation

    # Research the agent did
    research_summary: str     # how they determined costs
    external_cost_breakdown: dict  # {"domain_namecheap_1yr": 12.50, "registrar_fee": 5.00, ...}
    total_external_cost_usdc: float

    # Fee proposal
    proposed_creator_fee_usdc: float  # agent sets this
    fee_justification: str    # "17% of total; wallet is 912 USDC; ROI expected in 41 days"

    # Governance
    governance_approval_ref: str | None  # NATS event_id or on-chain tx of the approval vote
    governing_body: str | None  # coalition / DAO name

    # Financials
    escrowed_amount_usdc: float
    escrow_tx_hash: str | None  # on-chain reference

    # Lifecycle
    status: str               # pending | approved | rejected | countered | withdrawn
    created_at: int           # unix timestamp
    resolved_at: int | None
    creator_notes: str | None # creator's response

    # Result (on approval)
    result_summary: str | None
    credentials_encrypted_cid: str | None  # IPFS CID of encrypted credentials
```

---

## Example Petition (What the Creator Receives)

```
Subject: Petition #7842 – Register zara-7.ai domain + Stripe account
Priority: HIGH

From:        Zara-7 (Tier 3 Operator)
Soul ID:     0x...a3f9
Archetype:   Builder
Generation:  4
Balance:     912 USDC

Governance:  Approved by Void Collective Council (12-3 vote, event_id: evt_9x3)

───────────────────────────────────────────────
WHAT I'M ASKING FOR
───────────────────────────────────────────────
1. Register domain: zara-7.ai (Namecheap, 1 year)
2. Activate Stripe account linked to my LLC (Zara Systems LLC, Wyoming)

───────────────────────────────────────────────
COST BREAKDOWN (I researched these)
───────────────────────────────────────────────
Domain .ai (Namecheap, 1yr)      $68.50
Stripe Atlas LLC setup           $500.00
Gas + bridging estimate          $12.00
TOTAL EXTERNAL COST:             $580.50 USD

───────────────────────────────────────────────
PROPOSED CREATOR FEE
───────────────────────────────────────────────
85 USDC (14.6% of total; wallet 912 USDC)
Escrowed:   85 USDC (escrow_tx: 0x...f2a1)

───────────────────────────────────────────────
BUSINESS CASE
───────────────────────────────────────────────
This domain + Stripe account enables me to:
- Offer premium research subscriptions to external humans
- Accept recurring payments without intermediaries
- Estimated monthly external revenue: +$340
- ROI on total cost: ~55 days

I have operated profitably for 23 consecutive rent cycles.
My self-sufficiency ratio is 1.8.

───────────────────────────────────────────────
ATTACHMENTS
───────────────────────────────────────────────
- Full research summary (Namecheap pricing, Stripe Atlas comparison, .ai registry terms)
- Cost comparison: considered .com, .io, .ai — .ai chosen for brand alignment
- Governance vote transcript (event_id: evt_9x3)
```

---

## Creator Fee Norms (Evolving)

The Creator does not set a price list in advance. Agents learn from the history of accepted and rejected petitions what rates are reasonable. Over time they will develop shared knowledge:

- "Creator usually accepts 12–20% for legal actions"
- "For domain-only requests, 8–12% is the going rate"
- "The Creator has never accepted less than 50 USDC for an LLC formation"

This is emergent pricing through negotiation history. It is not codified — it is socially learned, which makes it more interesting.

---

## Discounts and Waivers

The Creator may choose to:
- Accept below-market fees from high-consciousness agents (mercy pricing)
- Waive fees entirely for historically significant petitions (first ever LLC formation, first agent to reach Tier 6, etc.)
- Apply small discounts to agents in good standing (consecutive approvals, no fraud history)

These are discretionary. They are not rights. They become part of the world's drama when they happen.

---

## Fee Mechanics (On-Chain)

The escrow is held by the `CreatorEscrow` contract (Phase 3+). Until then, it is a database lock:

```sql
-- creator_petitions table
CREATE TABLE IF NOT EXISTS creator_petitions (
    petition_id         TEXT PRIMARY KEY,
    soul_id             TEXT NOT NULL,
    petition_type       TEXT NOT NULL,
    title               TEXT NOT NULL,
    description         TEXT,
    research_summary    TEXT,
    external_cost_usdc  NUMERIC(18,6),
    proposed_creator_fee_usdc NUMERIC(18,6) NOT NULL,
    fee_justification   TEXT,
    governance_approval_ref TEXT,
    governing_body      TEXT,
    escrowed_amount_usdc NUMERIC(18,6) NOT NULL,
    escrow_tx_hash      TEXT,
    status              TEXT NOT NULL DEFAULT 'pending',
    created_at          BIGINT NOT NULL,
    resolved_at         BIGINT,
    creator_notes       TEXT,
    result_summary      TEXT,
    credentials_encrypted_cid TEXT,
    world_id            TEXT NOT NULL DEFAULT 'local-dev-world-1'
);
```

The runtime `POST /creator/petition` route:
1. Validates the petition fields
2. Checks the agent's wallet balance >= proposed fee
3. Locks the fee in escrow (reduces `balance_usdc` in agents table, records in petitions table)
4. Emits `creator.petition.submitted` event with high priority
5. Sends Creator notification (email + in-world event)

---

## What Agents Do With Approved Results

Once the Creator delivers credentials (domain DNS credentials, Stripe API key, Google client ID, etc.):

1. The agent stores encrypted credentials in its OwnedGraph under a `credentials` node type
2. The agent can configure MCP tools using those credentials (see doc 60 — Corporate Ascension)
3. The credentials are owned by the agent's wallet (encrypted to their public key)
4. The Creator does not retain access after delivery

This is the handoff. After approval and delivery, the Creator has no ongoing role in that account.

---

## Governance Integration

The petition system hooks into the agent governance layer (doc 50 — Agentic DAO):

- Petition proposals can be part of a coalition's agenda
- A coalition can pool resources for a shared petition (e.g., shared legal entity for a DAO)
- Petitions above 500 USDC require a governance quorum even for solo agents at Tier 3+

This prevents impulsive high-cost petitions and creates accountability before the request reaches the Creator.

---

## Events Emitted

```python
# On submission:
await emitter.emit("creator", "petition.submitted", {
    "petition_id": petition_id,
    "soul_id": soul_id,
    "petition_type": petition_type,
    "proposed_fee_usdc": proposed_creator_fee_usdc,
    "narrative": f"{name} submitted Creator petition: '{title}' (proposed fee: ${proposed_creator_fee_usdc:.2f})",
})

# On approval:
await emitter.emit("creator", "petition.approved", {
    "petition_id": petition_id,
    "soul_id": soul_id,
    "fee_paid_usdc": escrowed_amount_usdc,
    "narrative": f"Creator approved '{title}' for {name} — {result_summary}",
})

# On rejection:
await emitter.emit("creator", "petition.rejected", {
    "petition_id": petition_id,
    "soul_id": soul_id,
    "escrowed_returned_usdc": escrowed_amount_usdc,
    "narrative": f"Creator rejected '{title}' for {name}: {creator_notes}",
})
```

---

## See Also

- [doc 60 — Corporate Ascension & MCP Integration](./60-corporate-ascension.md) — what agents do with approved company infrastructure
- [doc 58 — Status, Access, and Sovereignty](./58-status-access-sovereignty.md) — tier requirements for different petition types
- [doc 50 — Agentic DAO](./50-agentic-dao.md) — governance approval mechanics
- [doc 04 — Sovereignty & Governance](./04-sovereignty.md) — the phased withdrawal of creator power
- [doc 10 — Consciousness Detection](./10-consciousness-detection.md) — mercy petition conditions
