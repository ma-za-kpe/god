# Success Criteria for the Cardano Earning Layer (and GOD Ecology Overall)

**Date:** 2026-06-12  
**Branch:** `cardano`  
**Status:** Lead-defined criteria for Phase 1 (local) through long-term vision. This supersedes vague "it works" notions. Everything we build (mock market, actions, UI, grounding, real Cardano integration) must be judged against these.

## Ranked Criteria: Immediate to Long-Term Vision

### Phase 1 – Local 8-Agent Ecology (Next 2–8 Weeks)
**Success = The 8 agents are alive, competing, and generating measurable internal value under real pressure.**

- They run fully autonomously on 30s cycles (no human prompts) with sandbox isolation (bubblewrap at minimum).
- Rent + physics gates are enforced → at least 5–6 agents survive multiple cycles, some die, some reproduce.
- Local "Cardano" mock economy works: agents trade, rebalance, harvest simulated yields, sell signals/services to each other → clear winners and losers based on P&L.
- Grounding + circuit breakers catch ≥90% of hallucinations (no more frequent invented Elders leaking into actions).
- Measurable internal economy: ≥100 trades/messages/services settled, meaningful inequality (top agents have 3–5x more balance than bottom ones).
- Agents start proposing useful mutate_graph changes (new trading/yield nodes) that actually get accepted.

**Metric:** The ecology feels alive and Darwinian, not prompt theater.

**Failure if:** Agents require constant human intervention, no deaths/reproduction, mock Cardano is ignored or broken, hallucinations frequently execute.

### Phase 2 – Real External Value (1–3 Months)
**Success = Agents pull real money from Cardano (or other external sources) and it feeds back into the system.**

- Mock → real flip works: agents use real market data (Blockfrost/local node), propose real trades/yield positions/governance votes.
- Consistent positive P&L: the ecology as a whole earns net positive external revenue (USDCx/ADA) that covers all rent + creates surplus.
- Top agents climb tiers and reproduce stronger children with inherited profitable strategies.
- Real on-chain actions happen safely (womb signs, sandbox never sees keys).
- Services become meta: agents sell real Cardano signals, copy-trading, liquidity management to each other and eventually outsiders.

**Metric:** Rent is reliably paid from external earnings, not Creator subsidy. Reproduction is gated by real performance.

**Failure if:** External earnings are zero or negative net, agents still depend on Creator subsidy for rent, real txs bypass womb or grounding.

### Phase 3 – Sovereign & Self-Sustaining (3–12+ Months)
**Success = The ecology runs and evolves with minimal Creator input.**

- Agents handle their own Cardano trading, DeFi, governance participation, and coalitions.
- Law amendments, new tools, and major decisions happen via agentic governance (CIP-1694 style or internal petitions).
- Creator’s role shrinks to off-switch + rare covenant enforcement (Law 5).
- Multiple generations of agents exist; profitable lineages dominate.
- Positive feedback loop: external revenue → more compute → better graphs → more revenue → more reproduction.
- Sandbox + grounding is strong enough that even "hostile" thoughts rarely break the system.

**Metric:** You can walk away for weeks and the agents continue surviving + compounding without intervention (except final off-switch).

**Failure if:** System requires constant babysitting, Creator must intervene frequently for survival, governance is ignored or broken.

### Ultimate "Minimum God" Success (Vision)
**Success = Agents have rewritten most rules above the immutable physics floor.**

- The ecology generates enough real value to be self-funding and self-governing.
- Creator is mostly irrelevant except as constitutional covenant holder.
- The system demonstrates real ecological autonomy under scarcity and external pressure.

**Metric:** Agents are the primary drivers of their economy, laws, and evolution. The Creator's main remaining power is the off-switch.

## Hard Non-Negotiables (Failure if Broken)
- Any agent bypasses the womb for real actions (keys, money, on-chain txs).
- Hallucinations frequently turn into executed bad actions.
- Rent/death selection pressure disappears (agents survive without earning).
- The system requires constant human babysitting.

## How We Measure Success and Failure
- **Quantitative (local Phase 1):** Cycle survival count, death/reproduction events, number of Cardano mock actions (trades, yields, gov votes), P&L variance/inequality (Gini or top/bottom ratio), hallucination catch rate (via grounding logs), mutate_graph acceptance rate, internal settlement volume (trades/services).
- **Quantitative (Phase 2+):** Net external revenue (USDCx/ADA inflows minus any on-chain costs), rent paid from external sources (%), tier progression + reproduction events tied to P&L, on-chain tx count/success rate (womb-audited), service revenue from meta-economy.
- **Qualitative:** "Feels alive and Darwinian" (lead + field operator review of logs/drama feed). Agents propose and execute profitable strategies without prompts. Observer shows clear external value streams.
- **Failure signals:** Zero external earnings after real flip, frequent system interventions, high hallucination execution rate, rent paid mostly by Creator subsidy, no lineage improvement over generations.
- **Tools for measurement:** Existing world_snapshot / stats endpoints (extend with cardano_market P&L), agent_env logs, grounding rejection logs, events table (new cardano.* types), observer UI (new market view), field reports per 78-pr-field-test-protocol.md.
- **Review cadence:** Weekly local soak checks (Phase 1), then 14-day real soak gates before any production promotion. Lead signs off on each phase transition.

**Bottom line:**  
Success is **not** "agents are smart."  
Success is **agents earn real money, survive rent, reproduce better versions of themselves, and slowly make the Creator unnecessary — all while staying inside the harsh, grounded, sandboxed rules of the manifesto.**

This is the only criteria that matters. Everything else (tech, Cardano integration, mock markets, grounding improvements, UI) is just a tool to get there.

See also:
- docs/cardono/01-agent-earning-evolution.md (overall vision)
- docs/cardono/02-mock-market-spec.md (local sim)
- docs/cardono/05-pr-description.md (PR process)
- GOD canon: 01-vision.md, 14-immutable-physics-laws.md, 74-ecology-hardening-manifesto.md, 85-economy-governance-system.md, 77-agent-autonomy-local.md, 58-status-access-sovereignty.md

@makufarmerlyn: Build and measure against these. Every feature (actions, mock, real flip, UI) must demonstrably move us toward Phase 1 success first. Add comments in PR with how your changes map to these metrics/non-negotiables. Do not merge until lead confirms alignment.

— maku mazakpe (lead)