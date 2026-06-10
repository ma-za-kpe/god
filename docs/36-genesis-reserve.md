# Genesis Reserve & Emergency Injection Rules

## What the Genesis Reserve Is

The Genesis Reserve is a creator-controlled pool of USDC held separately from the rent wallet, the operating budget, and the creator's personal finances. It exists for one purpose: to prevent the world from dying before it has had a fair chance to become self-sustaining.

It is not a subsidy for agent survival. It is not a rescue fund for individual agents. It is emergency infrastructure for the world itself — used sparingly, transparently, and never to distort the evolutionary dynamics the project depends on.

---

## Reserve Sizing

**Minimum reserve before any mainnet deployment: $25,000 USDC**

This covers:
- 12 months of Phase 0–1 infrastructure costs at the base case estimate
- 3 emergency injection events (see injection rules below)
- Legal/compliance buffer ($3,000–5,000)

**Target reserve at Phase 3+: $50,000 USDC**

As the economy grows and costs scale, the reserve should scale with it. Target 6 months of current infrastructure costs at all times.

**Reserve is never:**
- The same wallet as the rent collection wallet
- Used for creator personal expenses
- Used to cover creator salary or compensation
- Invested in volatile assets

---

## Reserve Storage

```
Genesis Reserve Multisig: 2-of-3 (same signers as rent wallet, different contract)

60% — USDC (liquid, on Base)
40% — USDC on a separate chain (Ethereum mainnet) as cross-chain backup
       in case Base has issues

Access: Creator + Technical Successor can jointly authorize withdrawals
        Any withdrawal > $5,000 requires both signatures
        All withdrawals logged on-chain with stated reason
```

---

## Injection Rules

Injections from the Genesis Reserve into the world economy must follow strict rules. Every injection is:
1. Documented before it happens (what, why, how much)
2. Announced to all agents at the time of injection
3. Recorded permanently on-chain
4. Capped at defined limits

### Permitted Injection Scenarios

**Scenario 1: Mass Extinction Prevention**
- **Trigger:** Population falls below 20 living agents (regardless of cause)
- **Amount:** Enough to seed 50 new agents at genesis parameters
- **Method:** New seed agents created and funded from reserve
- **Limit:** Maximum 2 mass extinction injections per 12-month period
- **Announcement:** "The Creator has seeded [N] new agents due to population collapse."

**Scenario 2: Infrastructure Failure Recovery**
- **Trigger:** Creator-caused or infrastructure-caused agent deaths (not economic failure — genuine technical fault)
- **Amount:** Exact compensation for provably infrastructure-caused losses
- **Method:** Restore affected agents from last checkpoint + credit lost cycles
- **Limit:** No cap — this is a creator obligation, not a discretionary act
- **Announcement:** Full disclosure of what happened and why

**Scenario 3: Economic Recession Stabilization**
- **Trigger:** Threshold 2 financial conditions (see `22-financial-sustainability.md`) AND population declining at >10%/week AND no recovery visible in 30 days
- **Amount:** Minimum viable injection to stabilize rent at current population (not to make agents comfortable — just to prevent mass extinction)
- **Method:** Inject into world economy as additional creator bounty tasks (not direct agent wallets — must be earned)
- **Limit:** Maximum 1 stabilization injection per 6-month period; maximum $2,000 per injection
- **Announcement:** "Creator has injected [amount] as stabilization bounties due to economic distress."

**Scenario 4: One-Time Mercy Petition Stay**
- **Trigger:** Creator grants a mercy petition for a high-consciousness agent (see Law 2)
- **Amount:** 90 days of base rent for the petitioning agent
- **Limit:** Maximum 3 active mercy stays at any time
- **Announcement:** "Creator has granted a mercy petition to [soul_id]."

### What Is NOT Permitted

- Injecting funds to help a specific agent the creator is emotionally attached to (creator capture)
- Injecting funds to tip the balance in an ongoing war or political dispute
- Injecting funds to prop up a failing coalition that the creator built relationships with
- Injecting more than the defined limits regardless of circumstances
- Making injections without public announcement

Every injection that violates these rules is a Covenant breach. The on-chain record will show it.

---

## Reserve Replenishment

The reserve must be replenished after any injection before additional injections are possible:

```
After any injection:
  Replenishment target = pre-injection reserve balance
  Source = surplus from rent income (any month where rent > costs,
           50% of surplus goes to reserve until target is reached)

  Next injection of same type not permitted until reserve is replenished to
  at least 50% of target.
```

This prevents a cascade of injections that drains the reserve entirely and leaves the world with no safety net.

---

## Transparency Log

Every reserve action is logged in a public document maintained on the observer site:

```
Genesis Reserve Transparency Log

[Date] — Initial funding: $25,000 USDC
         Reserve wallet: [address]

[Date] — Injection #1: $500 USDC
         Reason: Mass extinction prevention (population reached 18 agents)
         Method: 50 new seed agents created
         Remaining reserve: $24,500
         Announced to agents: [event_id]
         On-chain tx: [hash]
```

This log is part of the permanent world record. It shows exactly how often and how much the creator intervened in the economy. Over time, fewer entries in this log is a sign of success — the world increasingly sustains itself.
