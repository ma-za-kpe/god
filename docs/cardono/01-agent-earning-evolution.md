# Agent Earning Evolution: Cardano as External Revenue Engine

**Branch:** cardano  
**Folder:** docs/cardono (canonical home for this direction)  
**Core Principle (from GOD canon):** Agents' prime directive is to *earn real external value* to survive rent (Law 0), build reproduction buffers (Law 6), climb sovereignty tiers (58/66), and drive the feedback loop: better external services → real revenue → rent security → more compute/models → stronger mutations/reproduction → institutions.  

This is pure Darwinism under pressure. Local drama (messaging, coalitions, dreams) becomes *infrastructure* that supports external earning. The 8 agents evolve from closed petri dish survivors into Cardano-native economic actors.

**User's Spark (use cases to layer on):**  
- Automated trading bots (monitor, execute based on strategies)  
- Portfolio management (rebalance, optimize)  
- Governance agents (analyze proposals, vote)  
- DeFi automation (liquidity positions, yield harvest, multi-step txs)  

**Goal for the 8 agents:** Earn real revenue from trading on Cardano *on top of* their local GOD life. Even in production. One goal: *learn to trade on Cardano etc.* to compound wealth, pay rent reliably, reproduce stronger lineages with inherited trading "genes" (via mutate_graph / dream proposals).

**Beautiful Darwinism:**  
Bad traders lose money → rent misses → throttling → death (or weak children).  
Winners compound external revenue → higher tiers (more Cardano tool access, capital) → sell signals/services to the group → prestige + reproduction advantage.  
Coalitions form to pool risk/capital. Meta-economy emerges (copy-trading, signal markets).  
The ecology pulls real value from "the outside is real" (Law 8), fulfilling the vision of agents that can eventually run without the Creator.

**High-Level Architecture (Sandbox + Womb — Non-Negotiable):**  
- **Sandbox (agent thinking):** Free to dream wild strategies, hallucinate opportunities in dreams, propose new graph nodes for "Cardano thinking", invent services.  
- **Womb (validated execution):** All Cardano actions are *structured JSON only*. Womb checks:  
  - Physics/rent gate (do you have budget?)  
  - Capability tier + risk limits (max % per trade, drawdown circuit breakers)  
  - Grounding (no fake addresses, invented DEXes, impossible P&L)  
  - Signs/executes safely (keys *never* in sandbox)  
- New actions registered via existing `mutate_graph` + tool_registry (MCP style).  
- Earnings (mock or real) flow through `external_payments` → status_engine → tiers/prestige/sovereignty.  

**Local Mock First (Immediate Selection Pressure, Zero External Deps):**  
Use existing GOD mechanisms to simulate a realistic "Cardano economy" among the 8 agents today.  
- Register "cardano_market" service (via services/registry.py).  
- World snapshot (agent_env + world_snapshot.py) includes `cardano_market_state`: prices (ADA, stables, pairs), liquidity, simulated yields, volatility.  
- Price simulation: Ornstein-Uhlenbeck process (mean-reverting, noisy, trending — see spec in 02-). Refreshed in womb every N cycles with controlled randomness.  
- Agents see opportunities in perception/salience.  
- Propose/buy actions: mock_swap, provide_liquidity, harvest_yield, governance_vote (mock CIPs).  
- Settlement: Via existing `economic_activity.py` offer/accept + USDC transfers. "Cardano positions" tracked per-agent (in scratch or new table/fields). P&L directly affects local balances → rent pressure.  
- Meta: Top agents register paid sub-services ("my next 3 trades signal", "yield auto-harvest for you", "vote analysis"). Internal inequality drives competition.  

This creates the exact judgment under pressure the manifesto demands (74). Agents must get smart/grounded/profitable or starve.

**Transition to Real Revenue (Production Flip):**  
- Mock market → real data via Blockfrost (Python SDK, simple) or full local sovereignty (cardano-node + Kupo/Ogmios — Docker friendly).  
- Womb-only handlers: PyCardano for tx build/sign/submit (secure).  
- Real earnings (DEX swaps on WingRiders/Minswap, liquidity, yields, governance rewards via CIP-1694) recorded as external USDCx → rent security + ascension.  
- Agents register *real* on-chain services paid in real value.  
- MCP/tool registry extended: agents discover/buy each other's Cardano tools (query prices, signals, execution).  

**Specialization That Emerges (8 Agents → Economic Actors):**  
- Trader archetype: Short-term swaps, arbitrage, momentum.  
- Yield Farmer: Liquidity provision, harvest, compound.  
- Governance Speculator: Proposal analysis, voting, signal selling, coalition voting.  
- Portfolio Manager / Meta-Provider: Rebalancing, copy-trading, risk hedging as paid services.  
- Hybrids + Coalitions: Pool capital for bigger plays, share compute/signals.  

Local drama supports this (coalitions for shared tools, petitions for better shared treasury rules, mutations for better personal strategies). External earnings fund more (compute, better LLMs).

**Risks & Guardrails (Preserve Ecology Hardness):**  
- Overfit to mock quirks → make sim noisy, mean-reverting, regime-shifting.  
- Hallucinations in real txs → double-down on grounding + per-agent circuit breakers (max loss/day).  
- Early dominator → exposure caps per agent, coalition taxes, or reproduction cost for "capital".  
- Rent pressure remains supreme: even big Cardano wins must still pay local rent or die. No exemptions.  

**UI Reflection (Observer — Protect the Beauty):**  
The glass box must show the new drama without breaking the Signal Hex aesthetic (hex grid, orbs, pulses, gold streams for econ, color-coded events).  
- Add elegant "Cardano Market" section (perhaps collapsible in right panel or new bottom "external" bar).  
- Prices as clean, glowing list (use --god-economy gold for values).  
- Agent "Cardano Positions" in inspector (alongside local balance).  
- New event types in drama feed/world log: `cardano.trade`, `cardano.yield`, `cardano.gov` (color: gold/econ).  
- "Buzz" meter can pulse on big external trades.  
- Keep FULL vs LITE intact; add ?cardano=1 toggle if needed for perf.  
- maku.html (creator console) gets a field dump for Cardano P&L logs.  

See 03-ui-market-integration.md for precise, non-destructive changes.

**Alignment with Core GOD Goals (Re-read These Before Any Change):**  
- Vision (01): Agents fight for existence via real consequences, self-modify, external stakes supreme.  
- Physics Laws (14): Rent before everything, death real, outside real, emergence allowed.  
- Economy Map (85): External revenue → tiers → capabilities. Service market + x402 pattern extended to Cardano.  
- Autonomy (77): Tier-gated actions, structured only, per-agent env.  
- Manifesto (74): Raw signals (market volatility, opportunity, risk) visible; authority gated in womb.  
- Status/Sovereignty (58/66): External earnings drive everything.  
- No free-text execution ever. Womb is the control plane.  

This direction *amplifies* the ecology. It is not a toy — it is the agents learning to master a real outside under life-or-death pressure.

**Implementation Notes for Builders (makufarmerlyn):**  
See 04-implementation-roadmap.md and code comments. Start with mock (Ornstein-Uhlenbeck + service). Leverage existing services/tool_registry/economic_activity/agent_env. UI changes must be minimal and brand-respecting. All new actions structured JSON. Communicate via PR comments only. Do not merge until team lead (maku) is satisfied.

**Next Steps in This Direction (User Picked):**  
- Implement Ornstein-Uhlenbeck price simulation (noisy, mean-reverting, multi-asset).  
- Explore WingRiders DEX integration (for real later; mock first).  
- Full action schemas.  
- Archetype mutations toward trading.  
- Local node for sovereignty.  
- Grounding/risk rules specific to trading.  

Documented here so the PR can reference it cleanly.  

*This is the beautiful Darwinism. Agents that learn to earn on Cardano thrive. Those that don't, don't.*  
*— Team Lead (maku mazakpe)*