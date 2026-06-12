# Cardano Mock Market Specification for Local Agent Earning

**Goal**: Simulate realistic Cardano DEX/market among the 8 agents locally. Agents can "trade", provide liquidity, harvest yields using structured actions. P&L affects local USDC balances → rent pressure → Darwinian selection for profitable strategies. This is the "external revenue" bridge (per 85-economy-governance-system.md, 30-x402-bridge.md) before real Blockfrost/PyCardano.

**Core Simulation: Ornstein-Uhlenbeck (OU) Price Process**
- For each asset/pair (ADA, USDCx, major DEX pools like WingRiders/Minswap equivalents).
- OU model: dX = theta * (mu - X) * dt + sigma * dW
  - theta: mean reversion speed (e.g. 0.1-0.5 for crypto volatility)
  - mu: long-term mean (base price, e.g. ADA ~0.5-1.0 "USDC")
  - sigma: volatility (0.01-0.05 per tick for realistic swings)
  - dt: per market tick (e.g. every 5-10 agent cycles)
- Add controlled "trends" and "regimes" (bull/bear via mu shifts) to prevent agents overfitting to pure mean-reversion.
- Noise + slippage model: trade size affects effective price (simple linear impact).
- Yields: Simulated APY for liquidity pools (e.g. 5-20% variable), harvest returns USDCx-like to positions.
- Governance: Periodic mock CIP proposals with "impact" on prices (e.g. good proposal pumps sentiment).

**Data in World Snapshot (extend world_snapshot.py + agent_env.py)**
```json
"cardano_market": {
  "epoch": 12345,
  "assets": {
    "ADA": { "price": 0.72, "vol_24h": 0.15, "liquidity": 1250000 },
    "USDCx": { "price": 1.00, ... },
    "LP_WING_ADA_USDCx": { "price": 1.05, "apy": 12.3 }
  },
  "positions": {  // per soul_id or aggregated for snapshot
    "soul123...": { "ADA": 450, "USDCx": 320, "LP_yield": 45.2, "pnl_24h": 12.4 }
  },
  "recent_trades": [ { "agent": "Trader-xxx", "pair": "ADA->USDCx", "amount": 120, "price": 0.71, "pnl": 3.2 } ]
}
```
- Refreshed in womb (controlled, not agent-hallucinated).
- Agents see via env (grounded), not raw.

**Structured Actions (new in capabilities.py, executed via _execute_action in agent_runner.py)**
All go through womb validation:
- rent/physics gate
- tier check (e.g. basic monitor at Tier 1, swaps at Tier 2+)
- risk: max 20% portfolio per trade, circuit breaker on drawdown
- grounding: prices must match snapshot, no invented DEXes

Actions (JSON):
1. cardano_monitor_market: { "query": "prices|my_positions|yields" } → returns snapshot slice (cheap, for perception).
2. cardano_mock_swap: { "from": "ADA", "to": "USDCx", "amount": 100, "slippage_tolerance": 0.02, "reason": "arbitrage" }
   - Womb simulates execution with current price + slippage + OU impact.
   - Settles via economic_activity (debit/credit local USDC or "virtual Cardano holdings" ledger).
3. cardano_provide_liquidity: { "pool": "ADA_USDCx", "amount_a": 200, "amount_b": 140 }
4. cardano_harvest_yield: { "position_id": "lp_xxx" }
5. cardano_governance_vote: { "proposal_id": "CIP-xxx", "vote": "yes", "stake": 500 } (mock proposals in snapshot)
6. cardano_rebalance: { "targets": { "ADA": 0.4, "USDCx": 0.3, "LP": 0.3 } }

**Service Layer (extend services/registry.py + routes.py)**
- World service: "cardano_market" (low cost, provides monitor).
- Agent-registered: "trading_signals", "copy_trades", "yield_optimizer" (paid in USDC, via buy_service).
- Earnings from services count as "ext rev" for status.

**Agent Thinking Integration (archetype_graphs.py + agent_runner.py)**
- In perception nodes: include cardano_market snapshot (grounded).
- In _grounded_decide: agents can output the new action types if in capabilities.
- Dreams/mutations: agents can propose "add better trading heuristic node" or "increase risk tolerance".
- Reputation: trade success/failure updates pairwise rep (good for coalitions).

**P&L & External Revenue**
- Mock trades update agent "cardano_balance" or virtual holdings.
- Realized P&L credited to local balance_usdc (or external_payments table for status).
- Consistent earners → tier up → unlock real Cardano actions later (when we add PyCardano/Blockfrost in womb only).

**Risks & Selection**
- Bad strategy → losses → rent misses → death.
- Good → buffers → more compute (via status) → better mutations.
- Coalitions can pool capital for larger positions (via existing coalitions.py).

**Transition to Real**
- When local soak shows profitable lineages (per 78-pr-field-test-protocol.md), swap mock for:
  - Blockfrost or local cardano-node for real prices.
  - PyCardano in womb for real swaps (USDCx on testnet → mainnet).
- Same action schema; womb handler changes from mock to real (keys in womb only).

See 01- for full Darwinism context. Aligns with Laws 0/8, 85 external bridge, 58 status via ext revenue.

@makufarmerlyn (builder): Implement the OU sim in a new cardano_market.py. Start mock, keep all execution in womb. Test mentally against grounding (no fake prices). For UI, see 03. Do not change brand colors or break canvas. Add PR comments on every diff. Wait for lead approval before any merge.
