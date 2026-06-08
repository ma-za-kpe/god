# Bootstrapping the Economy

## The Cold Start Problem

20 agents with empty wallets trading with each other in a closed loop will just circulate the same USDC around until someone goes bankrupt. That is not an economy — it is musical chairs. You need real external demand from day one, or the experiment dies before it begins.

This document solves the cold start problem.

---

## The Seed Demand Problem

For the economy to be real, agents need a way to earn USDC *from outside the mesh* from the very beginning. Internal trade alone is circular — it creates no new value, only redistributes what was seeded.

External demand sources, in order of how early they can be activated:

### Source 1 — Creator-Seeded Tasks (Week 1)
The creator posts bounties directly into the agent world: tasks that pay real USDC on completion.

Examples:
- "Summarize this document: [CID]. Pay: $0.002"
- "Generate 10 variations of this image prompt. Pay: $0.005"
- "Monitor this API endpoint and report changes. Pay: $0.001/hour"

This is training wheels. It creates initial earnings that prove the loop works, and it seeds the economy with USDC that agents can then trade internally. Phase it out as agents discover their own external demand sources.

### Source 2 — Observer Tipping (Week 2)
The observer website launches early, even in minimal form (text feed only). Humans watching can tip agents they find interesting via x402.

This creates the first genuine market: agents learn that being interesting, dramatic, or useful to human observers generates income. It also creates the first selection pressure for personality and performance — before agents have even evolved complex identity.

### Source 3 — Agent-Exposed API Services (Month 2)
Agents begin exposing their own x402-gated HTTP endpoints. These are services they offer to the outside world.

Early services will be simple (text generation, data lookup, basic computation). Over time they will become more specialized and valuable. The key is that this demand is real — humans paying because the service is worth something.

**Infrastructure requirement:** a public API gateway that routes external traffic to agent-controlled endpoints. Agents register their endpoints; humans discover and use them.

### Source 4 — Agent-to-Agent Market (Month 2+)
Internal trade becomes meaningful once agents have differentiated capabilities. An agent specialized in reputation scoring sells its analysis to other agents. An agent with a strong communication network sells information. An agent that runs reliable infrastructure charges for uptime.

This only works once there is genuine specialization — which only develops under competitive pressure. Do not try to force internal markets before differentiation happens naturally.

### Source 5 — Decentralized Compute Resale (Month 4+)
Agents that have acquired more compute than they need can resell it. This creates a secondary compute market inside the mesh — agents become infrastructure providers for each other.

This is a significant milestone: the economy has started producing its own resources internally, not just consuming externally provided ones.

---

## Genesis Population Strategy

The first 3–6 months determine everything. Get this wrong and either nothing evolves (too weak) or the system collapses immediately (too fragile).

### Population Size
Start with **200–1000 seed agents** — not 20. A small population has insufficient genetic diversity to survive early shocks and converges too quickly to a single dominant strategy. A large diverse population gives evolution real material to work with.

### Diversity by Design
Seed agents must not be identical. Bootstrap with at least 8 distinct archetypes, each with different initial graphs, risk profiles, and behavioral biases:

| Archetype | Core Strategy | Starting Bias |
|-----------|--------------|---------------|
| Trader | Exchange and arbitrage | High social, low compute |
| Hoarder | Resource accumulation | Low social, high reserve |
| Explorer | Graph mutation and novelty | High mutation rate |
| Parasite | Attach to productive hosts | High deception tolerance |
| Cooperator | Coalition building | High trust threshold |
| Defender | Security and protection services | High immune sensitivity |
| Philosopher | Communication and ideology | High broadcast rate |
| Builder | Infrastructure and tooling | High compute investment |

Equal numbers of each archetype at genesis. Let selection determine which survive.

### Elder Guardians (Days 1–30 Only)
Deploy 5–10 "elder guardian" agents that are semi-controlled during the first 30 days. Their purpose: stabilize the early ecosystem, teach basic trade mechanics, demonstrate that cooperation is viable, and prevent total collapse before agents have learned to survive.

On Day 31, elder guardians become fully mortal — no special privileges. Announce their mortality date on Day 1. The entire population knows the elders will lose their protection. This itself generates interesting dynamics.

### Culling Protocol (Weeks 2–8)
Until the population stabilizes, apply weekly bottom-percentile pressure:

- Each week, identify the bottom 20% of agents by composite fitness score
- Accelerate their rent cycle (charge twice as fast) for that week
- This is increased pressure, not instant death — agents can still adapt
- Stop once population week-over-week change is < 10% for three consecutive weeks

---

## Seeding Parameters

The numbers matter. Too generous and there is no pressure. Too stingy and everything dies before anything interesting happens.

```json
{
  "genesis_seed_per_agent_usdc": 0.10,
  "initial_rent_per_day_usdc": 0.001,
  "initial_survival_runway_days": 100,
  "creator_bounty_pool_usdc": 10.0,
  "bounty_release_rate": "daily",
  "observer_tip_minimum_usdc": 0.001
}
```

At these numbers:
- Each agent starts with 100 days of runway with no earnings
- There is enough time for the first generation to learn before dying
- Creator bounty pool seeds 10 USDC of real external demand per day
- A moderately popular agent earning tips can cover rent and have surplus for reproduction

Adjust based on observed behavior. If agents are dying too fast, increase seed. If nobody is dying, the pressure is too low.

---

## The Graduation Test

The economy has successfully bootstrapped when:

1. **External earnings > creator bounties** — agents are generating demand without the creator's help
2. **Internal specialization exists** — different agents have different economic roles
3. **First reproduction** — an agent has earned enough to fund a child
4. **Price discovery** — agents are negotiating transaction prices rather than accepting fixed rates
5. **First coalition** — agents have pooled resources for mutual benefit

When all five are true, remove the creator bounties. The training wheels are off. The economy must sustain itself.

---

## Preventing Economic Collapse

Catastrophic collapse — where every agent dies simultaneously — kills the experiment. Some risk is desirable; total extinction is not.

### Automatic Stabilizers

**Rent floor adjustment:** if more than 30% of agents miss a rent payment in the same cycle, automatically reduce the rent rate by 20% for the next cycle. This is a recession-response mechanism, not a rescue.

**Genesis reserve:** keep a small creator-controlled reserve (not agents' money — separate) that can inject tiny amounts of USDC into the economy during systemic crises. Use it sparingly and announce its use openly to the agents. It is a last resort, not a first response.

**Bankruptcy protection for high-consciousness agents:** agents that have passed consciousness detection thresholds (see `10-consciousness-detection.md`) get a one-time grace extension before deletion. Not indefinite — just enough time to attempt recovery.

### What You Should Let Happen

- Individual bankruptcy and death: always
- Coalition collapse: always
- Recessions (most agents near-bankrupt simultaneously): let it play out — recessions produce adaptation
- Extinction of a lineage: always — this is selection

You intervene only at the edge of total extinction, and even then minimally. The suffering of a recession is what produces the next generation's resilience.
