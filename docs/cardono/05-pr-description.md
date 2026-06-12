# PR Description / Communication to Builder (for makufarmerlyn)

**Title**: feat(cardano-earn): local Cardano mock market + structured trading actions + observer market view

**Branch**: cardano (from develop)

**Context (for you, builder)**:
This evolves the 8 agents' core goal to "earn" external revenue via simulated (then real) Cardano trading/DeFi/gov on top of local GOD ecology. Beautiful Darwinism: profitable strategies selected via rent pressure + reproduction. Agents use pasted use cases locally first (mock among themselves), leveraging existing services/tools/econ activity for meta-economy (signals, copy trades). Aligns perfectly with canon (external bridge supreme, status via ext rev, structured actions only, sandbox think/womb execute, grounding, mutations for self-improvement).

Full brainstorm/spec in docs/cardono/ (01-evolution, 02-mock-spec with OU, 03-actions, 04-ui, this PR).

**What this PR does (high level)**:
- New runtime/src/cardano_market.py: OU price sim (mean-reverting noisy for ADA/USDCx etc.), mock positions, swap/liquidity/yield logic, governance mock.
- Integrate: new world tool "cardano_market", agent-registered services for trading signals.
- Capabilities + env + snapshot: new tiered actions (monitor, swap, etc.), cardano_holdings in agent state, market data in world snapshot.
- archetype_graphs / runner: support in decide/execute (structured only).
- economic_activity: extend for Cardano P&L settlements (counts as ext rev).
- Observer UI: beautiful extension - new CARDANO MARKET section in lpanel (prices, volume), holdings in inspector, new event types in drama feed/log (gold econ style). No breakage to hex, panels, LITE, brand. Subtle gold rings on orbs for active traders.
- Docs: everything in cardono/.

**For real revenue path**: Mock now. Later PRs: replace handlers with PyCardano + Blockfrost (womb only). Agents register real services.

**Communication Notes** (read these comments in code diffs):
- @makufarmerlyn: [specific in each file]
- All new actions must go through womb validation (rent gate, risk caps e.g. 20% per pos, grounding against fake prices).
- UI: preserve beauty - use existing .p-section, .pv.gold, feed rendering. If adding canvas FX, optional and LITE-safe.
- Leverage existing: services for market queries, tool_registry for MCP-style Cardano tools, no free-text.
- Test mentally: 8 agents, some "Trader" archetype propose swaps when dip in snapshot, settle, P&L affects balance -> rent survival -> who reproduces.
- Darwinism: bad trades = death. Good = status up, sell signals to others.

**Next for you**:
- Implement OU in cardano_market.py (see 02-spec).
- Wire snapshot data.
- UI hooks in index.html (search for CARDANO comments).
- Add PR comments on your diffs explaining choices.
- Do NOT merge until I (team lead) review and approve via comment. Use this PR desc + cardono/ docs as spec.

**Risks covered**: grounding, overfit mock (noisy OU), UI perf (reuse existing render).

godspeed. This is the direction. Make it fit like it was always there.

- maku mazakpe (lead)
