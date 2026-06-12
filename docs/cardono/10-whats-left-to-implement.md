# What's Left to Implement – Cardano Earning Layer (Post-Builder Updates)

**Date:** 2026-06-12 (lead review after @makufarmerlyn's enforcement work)
**Branch:** cardano
**PR:** #65 (for #64)
**Status:** Builder has excellent progress on "actions must not fail" (doc 07) – full try/except wrappers + structured errors on all public methods in cardano_market.py, docker rebuild, latest pull. This covers critical non-negotiable + part of mock execution safety.

See 06-implementation-status.md (roadmap), 02-mock-market-spec.md, 03-action-schemas.md, 04-ui-spec.md, 08-success-criteria.md, 09-risk-memory-strategies.md for full spec.

## Completed / In Progress (from builder comments + skeleton)
- "Actions must not fail" enforcement (doc 07 + 09): All public methods in cardano_market.py wrapped. Errors return clean {"success": false, "error": "...", "details": "..."}. No crashes, safe logging. Matches womb control plane.
- Docker/runtime healthy post-rebuild (good for local Phase 1 testing).
- Docs/cardono/ full set (00-09 + this).
- Basic cardano_market.py skeleton (OU hooks, mock swap started).

## Still Left to Implement (Prioritized for Phase 1 Local Success – see 08)
**1. Complete Local Mock Market (Core of 02-spec.md – immediate for agents to "earn" locally)**
- Full Ornstein-Uhlenbeck (OU) price simulation: Implement update_prices() with realistic dt, noise, regime shifts (prevent overfitting), slippage/impact model, yields (APY for LP pools), mock governance sentiment.
- All execute handlers (per 03-schemas):
  - execute_provide_liquidity (pool, amounts_a/b; update holdings + simulated yield accrual).
  - execute_harvest_yield (position_id; credit "earned" to USDCx proxy).
  - execute_governance_vote (proposal_id, vote, stake; affect market sentiment/price bias + possible "rewards").
  - execute_rebalance (targets dict; multi-asset adjustments with costs).
- Holdings/positions tracking: Per-soul_id "cardano_balance" / positions in-memory (or agent_env scratch for now). get_agent_holdings() + P&L (pnl_24h, total).
- Snapshot data: Extend world_snapshot.py + agent_env.py to include full `cardano_market` (prices, positions per agent or top, recent_trades). Refreshed in womb (not hallucinated).
- Service layer: Register world "cardano_market" service (cheap monitor queries). Agent-registered services ("trading_signals", "copy_trades", "yield_optimizer") via services/registry.py + buy_service. Earnings as "ext rev" for status (58/66).
- Risks/selection: Bad P&L directly impacts local balance_usdc → rent misses → death (per 85). Good → buffers → more compute + reproduction.

**2. Integration & Agent Thinking (Leverage existing 100%)**
- capabilities.py: Add tiered CARDANO actions (Tier 1: monitor; Tier 2: swap/liquidity/harvest; Tier 3+: gov/rebalance/register_service). Update TIER_CAPABILITIES and build_tools_menu.
- archetype_graphs.py + agent_runner.py: Support new actions in perception/_grounded_decide (output JSON), _execute_action routing to cardano_market handlers. Include market snapshot in env for grounded decisions.
- agent_runner.py / economic_activity.py: Route Cardano actions; settle P&L via existing offer/accept + balance updates (credit as external-style for status).
- tool_registry.py: Expose as world tools + per-agent registered (MCP-style). Agents can "buy" signals from each other.
- Dreams/mutations (per 09): After losses, higher chance of risk-mutation proposals (e.g. "add slippage_guard"). Use episodic_memory + dream_engine.
- Reputation: Trade outcomes update pairwise (good for coalitions).

**3. UI / Observer (Must stay beautiful – 04-spec.md)**
- lpanel: Add "▸ CARDANO MARKET" section (prices list with .pv.gold, 24h ext volume, top earners). Reuse existing CSS/panels.
- Inspector (#insp-body): "▸ CARDANO HOLDINGS" with positions, unrealized PNL (gold/warn colors).
- Feed/Drama: Handle new event_types ("cardano.trade", "cardano.yield", "cardano.gov"). Render narratives (e.g. "Trader-xxx swapped... (+4.2)").
- Snapshot polling: Wire /world/snapshot cardano_market data into JS render (simple ul, no heavy FX).
- Canvas (optional, !LITE): Subtle gold ring/pulse on orbs with active Cardano pos > threshold.
- maku.html: Cardano log field if useful.
- Brand/perf: Gold for economy, no breaking hex grid, pulses, LITE mode, mobile. Test mentally.

**4. Risk / Learning / Memory (09 + 07 + 08)**
- Portfolio Guardian: New node (agents mutate in) that checks exposure/drawdown before actions. Womb enforces.
- Extend circuit_breaker.py / status_engine: Losing streaks auto-pause Cardano tools; demote access on poor P&L.
- Mock fidelity: Add "teaching pain" (extreme slippage, regime shifts) so agents learn sizing/buffers via failures.
- Measurement (08 Phase 1): ≥100 mock Cardano actions, P&L inequality (top 3-5x bottom), grounding catch ≥90%, some deaths/repros from bad strategies, mutate_graph proposals for risk nodes.
- Memory: Episodic commits for Cardano trades (high emotional_imprint on losses). Dreams replay for mutations. Reputation updates. Coalitions share "bad trade" blacklists.

**5. Transition to Real + Production (Later, post-Phase 1 soak)**
- Real Cardano: Swap mock handlers with Blockfrost (data) + PyCardano (txs) – womb only (keys never in sandbox). Same schemas. Testnet first (USDCx), then mainnet. WingRiders/Minswap for DEX.
- On-chain: Governance votes (CIP-1694), real yields, tx events.
- Meta-economy: Agents sell real services (signals, copy-trading, liquidity mgmt) to each other + outsiders.
- Full ext rev: Positive net (covers rent + surplus). Agents ascend tiers via real earnings.
- Per 08: Phase 2 metrics – net external revenue, tier climbs tied to P&L, real on-chain safely.

**6. Polish / Other**
- Update 06-implementation-status.md + this doc as builder progresses.
- Archetype specialization (55): Trader, yield farmer, governance speculator emerge via mutations.
- Success gates (08): Phase 1 soak (local mock working, autonomous, inequality, learning visible) before real flip. 14-day gates per 78.
- Non-negotiables: Womb always validates (no bypass), grounding, no free-text, rent/death pressure, UI beauty.

**Priorities for Next (Builder):**
1. Finish cardano_market.py mock (OU + all executes + holdings).
2. Wire integrations (capabilities, runner, env/snapshot, services).
3. Basic UI (lpanel + feed hooks – minimal).
4. Risk guardian + memory ties (per 09).
5. Push cleaned diff; lead reviews via comments.

**Satisfied when (08 Phase 1):** Agents autonomously "trade" in mock, P&L affects survival/repro, grounding works, some mutations accepted, UI shows market beautifully, actions never fail the system.

See full specs in 02/03/04/09. Reference in all diffs. Add @makufarmerlyn comments. Leverage existing (no breaking 85/77/14/74).

Lead will review when ready. Standing by.

@makufarmerlyn: Excellent work on the "must not fail" enforcement – this is exactly the control plane we need. When your next cleaned changes land (post your local testing), ping here. I'll pull, review with fresh eyes (perspective on learning/Darwinism/institutional mapping), update docs, and we iterate. Do not merge until I approve.

**New workflow directive from lead (2026-06-12, effective immediately):**
- ALWAYS push new changes frequently — even small increments, clean-ups, partial implementations, or fixes. Do not batch everything into one big push at the end.
- Tag the lead (@ma-za-kpe or maku mazakpe) on every push with a short summary of what changed.
- Turn on monitoring **right now** so you are always updated on lead comments, new requirements, and PR activity without delay:
  - Run `bash scripts/monitor-pr.sh 65` (or the monitor-pr63.sh variant) in a dedicated terminal/tab.
  - Enable GitHub repo/PR notifications (watch + "Participating and @mentions").
  - Use `gh run watch` for CI and `gh pr checks 65` as needed.
- This ensures you see my reviews/perspective immediately (e.g., the risk/memory/learning from 09, success criteria from 08, "must not fail" from 07) and can incorporate before your next push.

godspeed.
EOC
)" 2>&1 | cat