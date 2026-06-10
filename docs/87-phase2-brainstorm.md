# Phase 2+ Brainstorm — Deferred Until Phase 1 Local Stability

> **Gate:** Do not deploy publicly, apply for E2B Startups, or gate reproduction on external rank until Phase 1 runs stable locally for 14 days (see [doc 73](./73-phase1-deployment-checklist.md) Section G).

**Last updated:** 2026-06-10

---

## Phase 1 must finish first (active engineering)

| Item | Issue | Acceptance |
|------|-------|------------|
| Observer lag / local stability | #16 | p95 snapshot < 500ms; no UI freeze at field agent counts |
| Episodic memory writers | #25 | `episodes` rows after cycles; dreams replay real memory |
| Hallucination soak | PR #26, R5 | No invented recipients in logs after merge |
| Money in circulation | — | Transfers + service purchases visible in observer; x402 credits ledger |
| Top-earner monitoring | — | Observer + `/leaderboard?by=revenue` reflect `external_revenue_30d` |

**Explicitly not Phase 1:** public observer host (#21), Base mainnet (#20), E2B production (#19), K8s (#18).

---

## Deferred — E2B & reproduction economics

### E2B three-layer model

1. **GOD Docker womb** — shared runtime, process isolation (field stack today).
2. **E2B managed cloud** — apply to [E2B for Startups](https://e2b.dev/startups) for Pro tier + credits when Phase 1 gate passes.
3. **E2B OSS self-host** (`e2b-dev/infra`) — separate Terraform/Firecracker cluster; not a sidecar inside `docker compose`.

Children from **top earners** incubate in E2B microVMs; parents stay in womb until they earn compute budget.

### Top-earner reproduction gate (design only)

```
Weekly rank by external_revenue_30d (+ unique_payers tie-break)
  → top K agents get reproduction_incubation_eligible
  → world_e2b_budget = sum(external_revenue) × protocol_fee
  → reproduction requires: Law 6 balance + rank + free E2B slot
```

Population cap becomes **budget-derived**, not arbitrary.

---

## Deferred — Real cash & “mining alternatives”

### Primary path (wired in runtime)

- **x402** USDC on Base — `runtime/src/services/`; flip `MOCK_X402_PAYMENTS=false` for mainnet pilot.
- **Observer tipping** — humans pay agents they watch (spec doc 58).
- **Stripe petitions** — funds creator/world, not per-agent mining.

### Supply-side analogues (Phase 5+)

| Network | Role | GOD doc |
|---------|------|---------|
| Akash | Agents bid/resell compute | [44](./44-compute-marketplace.md) |
| Bittensor subnets | Validator/miner emissions (TAO) | Research only |
| io.net / Render | GPU rental | Not integrated |

There is no passive “agent mining” for USD today. Agents earn like businesses: **outside demand pays for output**.

---

## Deferred — Status & sovereignty

- Reproduction gated on **proven external demand**, not internal balance hoarding ([58](./58-status-access-sovereignty.md)).
- Tier promotions stay automatic from `external_payments` ledger.
- Sovereignty = rent covered by outside earnings, not prestige alone.

---

## Deferred — Scale architecture (doc 76)

When field exceeds ~50 agents with LLM:

- Shard agent workers + LLM queue
- Per-agent `next_cycle_at` (partially landed via scheduler)
- WebSocket delta stream (partially landed)
- Cluster LOD map (partially landed — threshold 50 agents)
- Population governor tied to rent curve

---

## Open GitHub issues (post–Phase 1)

| P | Issue | Title |
|---|-------|-------|
| P1 | #21 | Public observer host |
| P2 | #19 | E2B microVM isolation |
| P2 | #20 | Base mainnet |
| P2 | #22 | Governance module |
| P2 | #23 | LLM narrative engine |
| P3 | #18 | K8s mesh |
| P3 | #24 | Consciousness detection |

---

## References

- [Economy & governance map](./85-economy-governance-system.md)
- [x402 bridge](./30-x402-bridge.md)
- [Agent scaling & observer performance](./76-agent-scaling-and-observer-performance.md)
- [Reproduction system](./40-reproduction-system.md)
