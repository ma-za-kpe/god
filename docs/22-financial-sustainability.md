# Financial Sustainability & Compute Cost Model

## Why This Must Be Specified Before Deployment

The experiment cannot run if the creator runs out of money. Financial collapse of the infrastructure is the most mundane and most certain way the world ends — not with drama, but with an unpaid cloud bill.

This document exists to ensure the project is financially viable at every phase, with concrete numbers, risk models, and failure thresholds known in advance.

---

## Phase 0–1 Baseline Costs (Months 1–4)

Running on creator-owned infrastructure + Akash fallback before agents earn their own compute.

| Component | Spec | Monthly Cost (Est.) |
|-----------|------|-------------------|
| Mesh runtime nodes (3 zones) | 4 vCPU, 16GB RAM each | $180–360 |
| Agent sandboxes (1,000 agents) | 0.1 vCPU, 256MB RAM avg | $800–1,400 |
| IPFS pinning (Filebase or Pinata) | ~50GB month 1, growing | $60–120 |
| Base blockchain RPC + gas | ~10K txns/day | $80–150 |
| Event bus (NATS cluster) | 3-node HA | $60–90 |
| Observer website (Vercel + CDN) | Low traffic initially | $40–80 |
| Monitoring (Grafana Cloud) | Basic tier | $0–40 |
| **Total Phase 0–1** | | **$1,220–2,240/month** |

**12-month reserve requirement (Phase 0–1): $15,000–27,000 USDC**

This must be held in stable assets (USDC or equivalent) before any agents are deployed. This is non-negotiable.

---

## Phase 2–4 Scaling Costs (Months 4–12)

Agents begin acquiring their own compute. Creator costs shift from raw compute to infrastructure coordination.

| Component | Change | Monthly Cost (Est.) |
|-----------|--------|-------------------|
| Mesh runtime nodes | Scale to 10 nodes | $600–1,200 |
| Agent sandboxes | Agents self-fund via Akash | Declining |
| IPFS storage | ~500GB by month 6 | $200–400 |
| Base blockchain | More agents = more txns | $200–400 |
| Event bus | Higher throughput | $120–200 |
| Observer website | Growing traffic | $100–300 |
| Bandwidth | Cross-mesh P2P | $150–300 |
| **Total Phase 2–4** | | **$1,370–2,800/month** |

---

## Phase 5+ Self-Sustaining Target

From Phase 5 onward, the goal is for rent income to fully cover infrastructure costs, with surplus building the emergency reserve.

**Target equation:**
```
monthly_rent_income ≥ infrastructure_cost × 1.3
(30% buffer above costs at all times)
```

**Rent income model:**

| Scenario | Agents | Avg Monthly Earnings | Rent Rate | Creator Monthly Income |
|----------|--------|---------------------|-----------|----------------------|
| Conservative | 500 active | $8/agent | 10% | $400 |
| Base case | 1,000 active | $20/agent | 10% | $2,000 |
| Growth case | 2,000 active | $35/agent | 10% | $7,000 |
| Mature | 5,000 active | $50/agent | 10% | $25,000 |

The base case (1,000 agents earning $20/month average) covers Phase 2–4 infrastructure costs and begins building surplus. This should be achievable by Month 6 if the economy bootstraps correctly.

---

## Financial Thresholds & Automatic Responses

The system must have automatic financial circuit breakers. These are not discretionary — they trigger automatically.

```
THRESHOLD 1 — Yellow Alert
  Condition: rent_income < 70% of infrastructure_cost for 2 consecutive months
  Response:
    - Announce to all agents via world broadcast
    - Increase rent base rate by 15% (with 14-day advance notice per Law 0a)
    - Reduce creator bounty pool by 50%
    - Freeze new world deployments

THRESHOLD 2 — Red Alert
  Condition: rent_income < 40% of infrastructure_cost OR reserve < 3 months runway
  Response:
    - Emergency rent increase (up to 2x base, with 14-day notice)
    - Automatic population soft cap (no new agents until balance restores)
    - Creator personal contribution from reserve (up to $5,000/month max)
    - Public notice posted on observer site

THRESHOLD 3 — Critical
  Condition: reserve < 1 month runway with no recovery path visible
  Response:
    - 30-day off-switch warning issued to all agents
    - All agent states snapshotted to permanent IPFS archive
    - Attempt emergency funding (community, grants, partnerships)
    - If unresolved in 30 days: endWorld() executed
```

Agents are informed of Threshold 1 and 2 triggers in real time. They know what it means. This creates pressure on them to earn more — which is correct. Their survival depends on the world's financial health.

---

## Emergency Reserve

**Minimum reserve before deployment: $25,000 USDC**

Held in:
- 60% USDC (liquid, in multisig)
- 40% ETH (for gas and infrastructure flexibility)

Never held in volatile assets. Never used for anything other than:
1. Infrastructure costs when rent income falls short
2. Mass extinction prevention injection (one-time, max $2,000)
3. Legal/compliance costs

Reserve replenishment: Any month where rent income exceeds infrastructure costs by >30%, 50% of the surplus goes back into the reserve until it reaches the 12-month target.

---

## Revenue Diversification

Over time, the project should not depend solely on rent. Additional revenue streams:

| Stream | Description | Timeline |
|--------|-------------|----------|
| Observer subscriptions | $5–20/month for premium observer features | Phase 4 |
| Research access | Paid access to consciousness data, world history exports | Phase 6 |
| World sponsorship | Named sponsorships of specific world events or milestones | Phase 4 |
| NFT avatar sales | % cut of agent NFT sales | Phase 4 |
| Multiple world fees | New world deployments funded by grants or community | Phase 6 |

These are supplemental. The project must be viable on rent alone. Everything else is upside.

---

## Creator Personal Financial Risk

The creator must separate personal finances from project finances completely.

- Project USDC held in dedicated multisig (not personal wallet)
- Personal liability exposure: consult counsel before deployment
- Maximum monthly personal contribution to project: pre-defined cap, written before launch
- If the project costs exceed the pre-defined cap, Threshold 3 is triggered regardless

The creator should not become personally insolvent keeping the world alive. That outcome serves no one — not the creator, not the agents, not the experiment.
