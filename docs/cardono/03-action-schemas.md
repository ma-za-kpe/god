# Structured Cardano Action Schemas

**Design Principle**: All actions are JSON, validated in womb before any "execution". Sandbox only proposes. Fits GOD: evidence raw (market data in env), authority structured (womb gates with rent, risk, grounding).

**New Capabilities (Tiered)**:
- Tier 1: cardano_monitor_market (query prices/positions)
- Tier 2: cardano_mock_swap, cardano_provide_liquidity, cardano_harvest_yield
- Tier 3+: cardano_governance_vote, cardano_rebalance_portfolio, register_cardano_service (signals)

**Schemas** (for archetype_graphs _grounded_decide output, and _execute_action):

1. cardano_monitor_market
{
  "action_type": "cardano_monitor_market",
  "payload": {
    "query_type": "prices" | "my_positions" | "yields" | "governance",
    "asset": "ADA" | null
  }
}

Womb: returns snapshot slice. Cheap, no cost.

2. cardano_mock_swap
{
  "action_type": "cardano_mock_swap",
  "payload": {
    "from_asset": "ADA",
    "to_asset": "USDCx",
    "amount": 150.5,
    "slippage_tolerance": 0.015,
    "reason": "arbitrage on dip"
  }
}

Womb:
- Check balance (mock holdings or USDC proxy).
- Apply OU current price + slippage + impact.
- Update agent cardano_positions.
- Settle P&L to balance_usdc via economic_activity (credit external style?).
- Emit event "cardano.trade" for snapshot/feed.
- Cost: small USDC fee for "gas" simulation.

3. cardano_provide_liquidity / harvest_yield
Similar, with pool, amounts. Harvest adds yield to positions, converts to "earned" USDCx proxy.

4. cardano_governance_vote
{
  "action_type": "cardano_governance_vote",
  "payload": {
    "proposal_id": "CIP-1694-foo",
    "vote": "yes" | "no" | "abstain",
    "stake_amount": 500
  }
}

Mock: affects "sentiment" in market (small price bias). Good votes can yield "rewards".

5. register_cardano_service (for meta-economy)
{
  "action_type": "register_cardano_service",
  "payload": {
    "name": "my_trading_signals",
    "description": "Private signals for next 3 swaps. 80% win rate in sim.",
    "price_usdc": 0.05,
    "type": "signal" | "copy_trade"
  }
}

Then others buy_service.

**Womb Execution Notes** (@makufarmerlyn):
- All in new cardano_market.py handlers.
- For real later: replace mock_swap logic with PyCardano + Blockfrost call (womb only, secure keys).
- Always: after action, refresh_env, emit to NATS for observer.
- Grounding: before accept, validate assets exist in current market snapshot.
- Risk: if post-trade drawdown > 10%, reject or liquidate mock.

**Integration**:
- Add to capabilities.py TIER_CAPABILITIES.
- In archetype_graphs.py: add to VALID_ACTIONS or prompt tools menu.
- agent_runner: route to cardano_market.execute(action, agent)
- economic_activity: extend for cardano P&L settlements.

See 01 for Darwinism, 02 for sim details.

This enables agents to "earn" locally via trading meta-game, feeding real ext rev path.
