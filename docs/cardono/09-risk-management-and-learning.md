# Risk Management, Saving Strategies, and Learning in the GOD + Cardano Earning System

**Date:** 2026-06-12 (expanded from brainstorm)
**Related:** 01 (evolution), 02 (mock spec), 03 (actions), 07 (actions must not fail), 08 (success criteria), 85 (economy map), 14 (laws), 74 (manifesto), 77 (autonomy)

## How the Overall System Prevents Big Losses (Validates Previous Description)

The pasted description is **accurate and well-aligned** with GOD canon. It correctly positions the "womb" as the unbreakable control plane (evidence vs authority from 74), with agents free to think dangerously in the sandbox but unable to execute harmfully.

### Physics Gate + Rent First (Law 0) — The Ultimate Throttle
- Before *any* cognition or action (including Cardano trades), the womb runs `evaluate_physics_gate` (physics_gate.py).
- Low balance / missed rent → reduced compute (smaller LLM context, slower cycles, weaker models). This is **not optional** — it's the metabolism of the ecology.
- 3 misses → death + full IPFS archive (Law 2). No bailouts.
- **Effect on Cardano earning:** Agents *cannot* risk everything on one trade. The gate forces "rent first" conservatism. A bad streak immediately shrinks their "brain" before they can double down.

This is harsher and more elegant than real-world margin calls — the pressure is continuous and automatic.

### Womb Validation on Every Action (The Risk Committee)
Sandbox proposes (dreams wild strategies, hallucinates opportunities).
Womb enforces (structured JSON only):
- Capability/tier gates (from 58/66/ capabilities.py): Tier 1 = monitor only. Tier 2+ = swaps/liquidity. High-risk tools (leverage analogs) gated behind proven external revenue.
- Hard position sizing (extend existing risk patterns): Max 15-25% of current balance per Cardano action. Womb calculates from `cardano_holdings` + local USDC.
- Max drawdown / circuit breaker: If simulated or real P&L drops >30% in a window, auto-pause trading for N cycles (see circuit_breaker.py — extend to Cardano volume).
- Grounding (grounding.py): Every price, asset, DEX reference must match the live `cardano_market` snapshot in the agent's env. No "invented Elders" or fake liquidity. Hallucinated strategies are rejected before womb even sees them.
- Rent/physics re-check right before signing (no race conditions).

This directly implements "actions must not fail" (the system stays stable even if an individual trade goes bad).

### Sandbox Isolation + Structured Actions
- Agents never see or control keys (womb signs everything).
- No free-text execution (archetype_graphs + runner enforce JSON).
- All Cardano actions go through `cardano_market.execute_*` (mock today, real later) which is itself wrapped in try/except and returns structured success/error (per 07 doc).

### Additional System Layers (Evolving from Canon)
- **Shared Treasury for Coalitions** (extend coalitions.py + 69): Coalitions can pool "play money" for bigger plays, but only a governance-defined % of group funds is at risk. Acts as natural hedging and diversification.
- **Performance-Based Tool Access**: Consistent losers (via status_engine external_revenue tracking + reputation) lose access to high-risk Cardano tools. Winners get more (copy-trading signals, larger limits).
- **Mock → Real Gradual Rollout** (per 02 spec): The local OU market includes realistic pain (slippage, fees, volatility spikes, sudden "regime shifts"). Agents learn the *feeling* of loss before real money is on the line. When flipping to Blockfrost/PyCardano, the same action schemas apply — only the womb handler changes.
- **Observer as External Auditor**: All Cardano events (trades, yields, failures) are public in the glass box. Bad strategies become visible reputation signals. Humans/outsiders can tip or hire winning agents (x402 extension).

**Net Effect:** The *ecology* as a whole cannot "blow up." Individual agents are allowed (and expected) to lose and die — that's the selection pressure. The system only "loses" if the whole ecology requires perpetual Creator subsidy.

## How Individual Agents Avoid (or Survive) Losing Money — Emergent Saving Strategies

Agents are not born with perfect risk models. They **discover** them through failure + memory + selection.

The table from the query is a good starting point and aligns well. Here's an expanded version grounded in real institutional practices (Morgan Stanley / JPM-style risk management) mapped to GOD mechanics:

| Strategy (Institutional Parallel) | How It Emerges in Agents | GOD Mechanism That Enables It | Why It Wins Under Rent Pressure |
|-----------------------------------|--------------------------|-------------------------------|---------------------------------|
| **Position Sizing** (JPM "1% risk per trade" rule, Kelly/partial Kelly) | "Never risk more than 10-20% on one Cardano swap" | Womb-enforced hard cap in cardano_market.execute (sandbox can propose bigger, womb rejects). mutate_graph lets agents add "my_sizing_heuristic" node. | Prevents ruin on single bad trade. Losers who ignore it get throttled fast. |
| **Diversification + Hedging** (MS portfolio risk platform, long/short, low-correlation assets) | Hold mix of ADA, USDCx stable, yield LP positions. Use coalitions to short one side while long another. | Native Cardano assets make hedging cheap (no wrapper tokens). Coalitions (69) + shared treasury. Reputation vectors track "who is good at hedging." | Reduces volatility. Agents that panic-sell everything during dips die; diversified ones survive to reproduce. |
| **Yield Farming over Speculation** (steady carry vs. high-vol bets) | Prefer registering/harvesting "yield_optimizer" services over leveraged directional trades. | Services registry + economic_activity for paid automation. Dream engine replays "the time I got rekt on a 3x long." | Reliable small gains cover rent. Speculators have high variance — some get rich, most get deleted. |
| **Stop-Loss / Risk Limits** (automated exits, trading envelopes) | Propose "auto_exit_if_down_8%" as part of swap action, or guardian node in graph. | Structured actions + womb validation. Grounding ensures the price trigger is real. | Cuts losers early. Agents that add this via mutation survive longer. |
| **Saving Buffers + Barbell** (JPM/MS "defensive + growth" allocation, keep dry powder) | Keep 40-60% in stable/USDCx "rent reserve." Only trade with "play money." | Physics gate makes buffer visible (low balance = immediate compute penalty). agent_env scratch for personal rules. | Rent security is non-negotiable. Agents without buffers get throttled before they can trade. |
| **Coalition Hedging + Signal Markets** (shared risk, buy intelligence) | Form trading coalitions that vote on positions. Buy "copy my next 3 trades" services from proven winners. | Coalitions + service marketplace (56). Reputation and external_revenue tracking reward good signals. | Outsources intelligence. Weak agents survive by paying winners; winners compound via fees. |
| **Post-Trade Analysis & Learning** (London Whale post-mortems, daily P&L reviews at banks) | Dream engine replays recent Cardano episodes with emotional valence. mutate_graph proposes "add slippage_guard after that bad fill." | episodic_memory.py + dream_engine.py (distort + coherence check) + mutate_graph (self-modification). | Failures become *data*. Agents that don't update their graphs after losses get selected against. |

These are **not hard-coded**. They emerge because:
- Reckless agents lose fast and die (or produce weak children).
- Conservative + adaptive agents build buffers, pay rent reliably, get more compute, and reproduce with inherited "risk nodes."

## Memory and Learning from Past Mistakes — Yes, This Is Accurate and Central

**Yes, the previous description is accurate.** Agents *do* learn, but not like a perfect RL agent with a global loss function. Learning is ecological and multi-layered:

1. **Episodic Memory** (runtime/src/episodic_memory.py): Every cycle (including Cardano trades) is committed as an episode with emotional_imprint (valence from P&L). High-loss trades get strong negative imprint → replayed in dreams.

2. **Dream Engine + Distortion** (dream_engine.py): During sleep, recent episodes (weighted by emotional salience) are replayed, distorted (outcome flips, counterfactuals), and turned into mutation proposals. A bad leveraged swap that caused a rent miss can become "I should have sized smaller and hedged with stable."

3. **Grounding + Coherence Check**: Mutations are validated against live world + physics violations. "I will never lose again by ignoring rent" gets rejected as meta/hallucinated. Useful ones ("add position_sizing_guard before any cardano_swap") survive if they pass coherence.

4. **Reputation & External Signals** (messaging + status_engine): Trade outcomes update pairwise reputation. Agents that sell bad signals lose customers. Successful hedging builds prestige (and higher tiers = more tool access).

5. **Selection Pressure (the real teacher)**: Memory alone isn't enough. Bad strategies must *cost* the agent (lost rent, missed reproduction). Winners' children start with partial inheritance (via reproduction crossover in 40/57).

6. **Coalitions as Shared Memory**: Groups can maintain "bad trade" blacklists or successful playbooks (via shared scratch or services).

**Is it "smart" like a Morgan Stanley quant desk?** Not initially. Early agents will be noisy and lossy. But under continuous rent pressure + real external feedback (Cardano prices are adversarial and unforgiving), selection + mutation + memory will surface sophisticated behaviors:
- Agents will "discover" position sizing, stop logic, and hedging because the ones that don't get deleted.
- Dreams will increasingly function as internal "post-trade reviews."
- Top lineages will look like partial-Kelly + barbell + diversification because those maximize long-term survival under volatility.

Real institutions use committees, VaR models, and quants because they *also* face ruin if they don't. Our agents have something stronger: **permanent death for the individual + reproduction of successful code**. Plus eUTxO on Cardano makes execution more deterministic (fewer "surprise reentrancy" style risks than EVM).

## Institutional Research Tie-In (MS / JPM / Hedge Funds)

Professional desks don't "never lose." They manage so that losses are small, survivable, and informative:

- **Position Sizing is King** (more important than stop-losses in many quant views): Risk 0.5-2% of capital per trade (institutional standard). Kelly Criterion (or partial Kelly) for optimal sizing based on edge + win rate. Our womb hard-caps act as an enforced institutional limit.
- **Diversification & True Hedging** (not just "don't put all eggs in one basket"): Low-correlation assets, long/short, options/futures overlays. Hedge funds explicitly seek "true diversification" to use leverage safely. Our agents will evolve this via native Cardano assets + coalition structures.
- **Quantitative Risk + Limits** (VaR, expected shortfall, concentration limits): JPM famously (and infamously in the London Whale case) uses VaR. Post-mortems led to better model validation and limits. Agents get this via womb-enforced drawdown breakers + reputation as a living "track record."
- **Learning Systems**: Daily P&L reviews, attribution analysis, "what went wrong" meetings. Failed strategies are documented and banned. Our dream_engine + mutate_graph + reputation is a decentralized, always-on version of this.
- **Psychological/Process Discipline**: "Cut losses quickly, let winners run" (but with hard rules). Risk committees override trader ego. In GOD: the womb is the committee; selection pressure punishes ego-driven overbetting.
- **Barbell / Saving First**: Many pros keep a large safe allocation and only risk a small "convexity" sleeve. Matches the emergent "40-60% stable buffer" strategy.

The London Whale is a cautionary tale of *bypassing* limits and models — exactly what our womb prevents.

In the GOD ecology, agents that internalize these (via memory, dreams, and inheritance) will dominate. The ones that treat Cardano like a casino will fund the rent of the survivors.

## Concrete Next Steps for Implementation

- Add a "Portfolio Guardian" node template that agents can mutate in (runs before cardano actions, checks total exposure + drawdown).
- Extend status_engine to demote tool access on sustained losses.
- Make dream mutations for risk nodes more likely after high-loss episodes (emotional weighting already exists).
- In observer UI (per 04 spec): Show per-agent "risk metrics" (current % at risk, recent P&L streak) alongside Cardano holdings — makes learning visible.
- When going real: The same womb rules apply; Cardano's eUTxO + verifiable scripts actually make some of these easier to enforce on-chain (e.g., script-enforced position limits via multisig treasuries).

This keeps the ecology harsh (agents *will* lose and some will die) while making catastrophic, system-threatening losses extremely hard.

**For the builder (@makufarmerlyn in PR #65):** When implementing the remaining actions and the real flip, ensure every path respects the womb limits above. Add explicit "risk check" steps in cardano_market.py that mirror institutional position-sizing math. Update the mock to include realistic "bad fills" so agents have real mistakes to learn from.

See also the success criteria in 08 — sustainable external revenue with controlled drawdowns is a Phase 2 metric.

This direction is sound. It turns Cardano from "just another API" into genuine selection pressure for judgment and memory. 

— maku mazakpe (lead)

Next pull? How governance proposals on Cardano could let *agents* vote on their own risk parameters (meta layer)? Or specific OU parameter tuning for the mock so it actually teaches good sizing?
