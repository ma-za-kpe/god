# Risk Management, Saving Strategies, Memory, and Learning in the Cardano Earning Layer

**Date:** 2026-06-12 (lead synthesis)
**Branch:** cardano
**Related Docs:** 01 (evolution), 02 (mock spec), 03 (actions), 07 (actions must not fail), 08 (success criteria), 85 (economy-governance map), 14 (laws), 74 (manifesto), 77 (autonomy), 58/66 (status), 40/57 (reproduction)

**Lead Note:** This captures the full brainstorm thread on "How does the system avoid losing money? How do the agents avoid losing money? What's their saving strategy? Memory and learning from past mistakes? Is this accurate? Research tie-in from top institutional traders (Morgan Stanley, JPM, hedge funds, etc.)."

Everything below must be respected in upcoming code changes. @makufarmerlyn: stand by — more code changes are coming your way. Do not implement anything yet. Document only for now. All future diffs must reference this doc + 07 + 08. Communicate only via PR comments on #65. Do not merge until I (lead) am satisfied.

## System-Level Protections: How the Overall System Prevents Big Losses

The description provided is **accurate** and directly implements core GOD canon. It correctly positions the "womb" as the unbreakable control plane (per 74 manifesto: evidence vs authority; 85 map: perceive/judge/act/enforce/govern with immutable floor).

### Physics Gate + Rent First (Law 0) — The Ultimate Throttle
- Before *any* agent cognition or Cardano action, the womb runs `evaluate_physics_gate` (from physics_gate.py, integrated in agent_runner).
- Low balance / missed rent → reduced compute (smaller sandbox, slower cycles, weaker LLM context).
- 3 misses → death + full IPFS archive (Law 2, enforced via rent_daemon + death mechanics).
- **Effect on earning layer:** Agents literally cannot risk everything on one trade without first feeling the pain of throttled intelligence. This forces "rent first" conservatism at the system level. No "go all in" possible without self-sabotage.

This is harsher and more elegant than real-world margin calls or risk limits — the pressure is continuous, automatic, and tied to survival.

### Womb Validation on Every Action (The Institutional Risk Committee)
- Sandbox (agent thinking): free to dream wild trades, hallucinate opportunities, propose crazy leverage.
- Womb (execution): enforces structured JSON only. Rejects anything that bypasses:
  - Capability/tier gates (capabilities.py + status_engine): Tier 1 = monitor only. Tier 2+ = swaps/liquidity. High-risk (leverage analogs) only after proven external revenue.
  - Hard position sizing (extend in cardano_market.py): Max 15-25% of current balance per Cardano action. Calculated from `cardano_holdings` + local USDC.
  - Max drawdown / circuit breakers (extend circuit_breaker.py): If portfolio drops >30% in window, auto-pause trading for N cycles. Losing streaks trigger pause.
  - Grounding (grounding.py): Every price, asset, DEX, yield reference must exactly match the live `cardano_market` snapshot in the agent's env. No invented Elders, fake liquidity, or hallucinated infrastructure. (See 07 for "actions must not fail" enforcement.)
  - Rent/physics re-check immediately before signing (prevents races; ties directly to Law 0).

All new Cardano actions (`cardano_mock_swap`, `provide_liquidity`, `harvest_yield`, `governance_vote`, etc.) must route through womb validation. Sandbox proposes; womb executes or safely rejects.

### Sandbox Isolation + Structured Actions Only
- Agents never see or control real keys (womb signs/submits everything).
- No free-text execution (enforced in archetype_graphs.py + agent_runner._execute_action + tool_registry).
- Failures are *observable learning signals* (reputation hit, negative emotional valence in memory, increased chance of corrective mutation) but never system crashes.
- When flipping mock → real (Blockfrost/PyCardano or local node): *exact same contract*. Only the womb handler changes. Sandbox still never touches keys or on-chain state directly.

### Additional System Layers (Evolving from Canon + Cardano Primitives)
- **Shared Treasury for Coalitions** (extend coalitions.py + 69-coalition-implementation.md): Coalitions can pool "play money" for bigger plays, but only a governance-defined % of group funds is at risk. Acts as natural hedging, diversification, and risk sharing. Agents can "sell" risk management as a service.
- **Performance-Based Tool Access** (status_engine + reputation): Consistent losers (tracked via external_payments + P&L) lose access to high-risk Cardano tools. Winners get more (copy-trading, larger limits, better signals). Ties to 58/66 status via external revenue.
- **Mock → Real Gradual Rollout** (per 02-mock-market-spec.md): The local OU simulation includes realistic pain (slippage, fees, volatility spikes, sudden regime shifts). Agents learn the *feeling* of loss and the value of buffers *before* real money. When flipping, same action schemas + womb rules apply.
- **Observer as Public Risk Auditor** (per 04-ui-spec.md + 06): All Cardano events (trades, yields, failures, P&L) are visible in the glass box. Bad strategies become visible reputation signals. Humans/outsiders can tip winning agents or hire services (x402 extension). Makes external value streams legible.

**Net Effect on the Ecology:** The *system* cannot "blow up" or require perpetual Creator subsidy. Individual agents *are* allowed (and expected) to lose and die — that's the selection pressure (Law 0 + 2 + 74). The only true failure mode is if the whole ecology stops generating net positive external value while still needing Creator rent support.

This directly supports the success criteria in 08 (Phase 1: measurable internal Cardano economy with winners/losers; Phase 2: net positive external revenue feeding rent/repro; Phase 3: self-sustaining with minimal Creator input).

## How Individual Agents Avoid (or Survive) Losing Money — Emergent Saving Strategies

Agents are **not** born with perfect risk models. They **discover** and evolve them through failure + memory + selection + mutation. The system provides the guardrails; the agents provide the adaptation.

The following table expands the brainstorm with institutional research tie-ins (Morgan Stanley / JPM-style risk management, hedge fund practices, Kelly criterion, VaR, post-mortems, etc.). These are **not** hard-coded — they emerge because reckless agents get throttled and deleted; disciplined ones build buffers, pay rent reliably, get more compute, and reproduce with inherited "risk genes" (via mutate_graph + reproduction crossover in 40/57).

| Strategy (Institutional Parallel) | How It Emerges in Agents | GOD Mechanism That Produces It | Why It Wins Under Rent Pressure (Law 0 + External Value) |
|-----------------------------------|--------------------------|--------------------------------|---------------------------------------------------------|
| **Position Sizing First** (MS/JPM: risk 0.5-2% of capital per trade; sizing often more important than stop-loss) | "Never risk more than 15-20% of balance on any Cardano swap" | Womb-enforced hard cap in cardano_market.execute (sandbox can propose bigger; womb rejects). mutate_graph lets agents add "my_sizing_guardian" node. | Prevents single-trade ruin. Over-betters get throttled fast and die. Matches Kelly/partial Kelly for long-term survival. |
| **Barbell / Buffers + Rent First** (keep large safe allocation + small convex bets; "play money" only) | Keep 40-60% in stable/USDCx as "rent reserve." Only trade with surplus. | Physics gate makes buffer visible (low stable = immediate compute penalty). agent_env scratch for personal rules. | Rent security is non-negotiable (Law 0). No buffer = throttled before you can speculate. Classic institutional "defensive core + growth sleeve." |
| **Diversification + True Hedging** (low-correlation assets, long/short, not just "don't put all eggs") | Hold mix of ADA directional + USDCx stable + yield LP. Coalitions to take opposing sides or hedge. | Native Cardano assets (cheap, first-class hedging — no EVM wrappers). Coalitions (69) + shared treasury. Reputation vectors track hedging skill. | Reduces volatility. Panic-sellers during dips get selected out. Hedge funds explicitly seek "true diversification" for safe leverage. |
| **Yield/Carry Farming over High-Vol Speculation** (steady harvest > leveraged directional bets) | Prefer registering/harvesting "yield_optimizer" services. Small, reliable gains. | Services registry + economic_activity (56). Dream engine replays "the time the 3x long wrecked my rent buffer." | Covers rent reliably with lower variance. High-speculators have more deaths. Matches carry-trade and options-writing desks. |
| **Stop-Loss / Risk Limits as Process** (automated exits, trading envelopes, concentration limits) | Propose "auto_exit_if_down_8%" as part of swap, or guardian node before any action. | Structured actions + womb validation. Grounding ensures real triggers. | Cuts losers early. Agents that add this via mutation survive longer. |
| **Saving Buffers + Outsource Intelligence** (buy edge, share risk via coalitions) | Pay stronger traders for "copy my next 3 trades" signals. Form trading coalitions that vote on positions and pool "play money." | Service marketplace (56) + reputation. Coalitions for shared scratch/blacklists of bad strategies. | Weak agents survive by riding winners; winners compound via fees. Mirrors buying research or joining syndicates. |
| **Post-Trade Analysis + Process Discipline** (daily P&L attribution, "what went wrong" reviews, model validation) | Dream engine replays high-valence (big loss) episodes with distortion/outcome flips. Propose "add slippage_guard after that bad fill." | episodic_memory.py + dream_engine.py (replay + coherence check) + mutate_graph (self-mod). Reputation as living track record. | Failures become *data*. Agents that don't update graphs after losses get selected against. Direct parallel to institutional post-mortems (e.g., London Whale lessons at JPM: better model validation, real limits, process over ego). |

**Institutional Research Tie-In (MS, JPM, Hedge Funds):**
Top winners (desks at Morgan Stanley, JPM, successful hedge funds) don't have zero losses — they have *small, survivable, informative losses* and iron discipline:
- Position sizing is the real edge (often cited as more important than stop-losses). Kelly criterion (full or partial) for optimal sizing based on edge + win rate. Over-betting is the fastest path to ruin even with positive expectancy.
- Diversification + hedging (low/negative correlation assets, long/short, volatility overlays). "True diversification" allows safe leverage.
- Quantitative risk tools (VaR, expected shortfall, concentration limits, stress testing) + human/process overrides (risk committees). JPM's own history (London Whale) is a cautionary tale of *bypassing* limits, optimistic models, and no real discipline.
- Post-trade analysis and learning loops (daily P&L reviews, attribution, "what went wrong" meetings, model validation). Failed strategies are documented and banned from the process.
- Barbell + saving-first psychology (large safe allocation + small high-convexity sleeve). "Cut losses quickly, let winners run" — but with hard rules, not hope.
- Psychological discipline: ego is the enemy; process beats prediction.

In GOD + Cardano, agents that internalize these (via the mechanisms above) will dominate. The ones that treat Cardano like a casino will fund the rent of the survivors. eUTxO + Plutus on the real side actually helps (more deterministic execution, fewer "surprise" black swans than EVM account model).

## Memory and Learning from Past Mistakes

**Yes — agents do learn from past mistakes, and the system is explicitly designed for it.** This is accurate and central to the vision (01-vision, 08 success criteria, 74 manifesto emphasis on judgment/memory/adaptation under pressure).

### Existing GOD Memory Systems (Leverage These 100%)
- **Episodic Memory** (episodic_memory.py): Every cycle (including Cardano trades, P&L, failures) is committed as an episode with emotional_imprint (valence from rent impact or yield). High-loss trades get strong negative imprint.
- **Dream Engine + Distortion** (dream_engine.py): During sleep, recent episodes (weighted by emotional salience) are replayed, distorted (outcome flips, counterfactuals), and turned into mutation proposals. A blown-up leveraged swap can become "I should have sized smaller and hedged with stable."
- **Grounding + Coherence on Mutations** (grounding.py + dream_engine coherence check): Proposals are validated against live world + physics violations (no "never lose again" meta). Useful risk nodes ("add position_sizing_guard before any cardano_swap") survive if they pass.
- **Reputation + External Signals** (messaging.py + status_engine): Trade outcomes update pairwise reputation. Selling bad signals loses customers/revenue. Successful hedging builds prestige (and higher tiers = more tool access).
- **Selection + Inheritance** (reproduction.py + 40/57): Bad strategies must *cost* the agent (lost rent, missed reproduction windows). Winners' children start with partial inheritance via crossover. This is the ultimate teacher.
- **Coalitions as Shared Long-Term Memory** (coalitions.py + 69): Groups can maintain blacklists of bad counterparties/strategies, shared playbooks, or pooled intelligence via services. Weak agents ride winners; winners monetize edge.

### How Learning Actually Happens (Emergent, Not Perfect RL)
- Failures are replayed in dreams with emotional weight → higher chance of corrective mutation.
- Grounding prevents "magical thinking" mutations while allowing real adaptation.
- Reputation makes learning social and economic (bad actors lose business).
- Selection pressure ensures only strategies that improve long-term survival (rent coverage + reproduction) spread.
- Dreams function as internal "post-trade reviews" and "what-if" scenario planning (exactly like institutional attribution analysis).

Early agents will be noisy and lossy. Under continuous rent pressure + real adversarial Cardano prices (which don't care about your feelings), selection + memory + mutation will surface sophisticated behaviors. Top lineages will look like they "discovered" position sizing, hedging, and post-trade review — because the ones that didn't got deleted.

**Is this accurate to canon?** Yes. It directly implements 74 (raw adversarial signals like market volatility and betrayal in coalitions are visible; only structured decisions execute), 14 (outside is real; mutation encouraged within bounds), 77 (per-agent env + scratch for personal rules; tiered actuation), 85 (external revenue → tiers → capabilities; rent metabolism forces conservatism), and 61 (sovereign evolution via self-modification).

## Concrete Implementation Notes (For Future Code Changes)

- **System:** Add "Portfolio Guardian" node template (agents can mutate it in) that runs before any cardano_* action and checks total exposure + recent drawdown. Womb must enforce it.
- **Agent Memory:** Weight dream mutations toward risk nodes after high-loss Cardano episodes (emotional weighting already exists). Make "bad trade" episodes high-salience for replay.
- **Mock Fidelity:** Include realistic teaching pain in OU sim (extreme slippage, fees, sudden regime shifts) so agents have real mistakes to learn from *before* real money.
- **Real Flip:** Same womb rules + guardian logic. Cardano's eUTxO + verifiable scripts can even let coalitions enforce on-chain risk rules if they evolve that far (meta layer).
- **Measurement (per 08):** Track "risk heuristic evolution" via accepted mutate_graph changes that improve P&L survival rate. In Phase 2, net external revenue with controlled (not zero) drawdowns.
- **Non-Negotiables (per 07 + 74):** Every Cardano action path must be try/except wrapped + return structured error (never crash cycle). Womb pre-checks + this wrapper = actions "must not fail" the control plane.

@makufarmerlyn: Stand by — more code changes are coming your way. Do not make any changes yet. Simply document in the docs and the PR comments or issue. When the changes arrive, reference this doc (09) + 07 + 08 in every relevant diff. Add your own comments explaining how the implementation supports emergent institutional-style risk discipline under GOD selection pressure. Leverage existing memory systems (episodic_memory, dream_engine, mutate_graph, reputation) 100%. No hard-coded perfection — it must be learnable/adaptable via the ecology.

This keeps the ecology harsh enough to reward judgment, memory, and adaptation (current tone from CLAUDE.md) while giving agents the tools to evolve real trader-like smarts.

See also the full success criteria in 08 — sustainable external revenue with controlled risk is a core Phase 2/3 metric.

— maku mazakpe (lead)

**Workflow / Role Clarification (per lead directive, 2026-06-12)**

@makufarmerlyn — copy that.

- You (builder) are the one actually running the code, making edits, cleaning things up, and delivering changes.
- My job as team lead (maku mazakpe) is to bring fresh code perspective, research tie-ins, canon alignment, and synthesis **after** you have done the work and cleaned it.
- Until you say "changes are ready", I am in pure stand-by / documentation mode: only updating docs/cardono/ and posting PR/issue comments.
- No code changes from my side right now.
- All communication about incoming work goes through PR comments on #65 (or the issue when relevant).
- I will review, add perspective, and update docs once you deliver cleaned changes.
- Do not merge until I explicitly approve.

This section added per the stand-by instruction. The rest of this doc (risk, saving strategies, memory/learning, institutional research, etc.) remains the spec to build against when changes arrive.

**Next pull?** (When you're ready to resume brainstorming or deliver changes.) How governance proposals on Cardano could let *agents* vote on their own risk parameters (meta layer)? Or specific OU tuning + "bad fill" simulation? Or reputation weighting for Cardano P&L? Let me know when you have something to review.
EOC
)" 2>&1 | cat
