"""
cardano_market.py — Mock Cardano market for local agent earning simulation.

Implements Ornstein-Uhlenbeck price process for realistic, mean-reverting,
noisy asset prices (ADA, USDCx, LP pools etc.).

Agents "trade" via structured actions. P&L affects local balances (counts as
external revenue for status/tiers per 58/66/85).

ALL execution happens in WOMB only (validated, rent-gated, risk-limited,
grounded). Sandbox only thinks/proposes (via dreams, mutations, decide).

@makufarmerlyn (builder, via PR comments):
- This is the core mock for the "earn real revenue from trading" direction.
- Start with this for local sim among 8 agents (they trade "virtually",
  settle via economic_activity, P&L boosts their "ext rev" so status engine
  sees them as "earning on Cardano").
- For real (future PR, after local soak): replace mock_swap/execute with
  PyCardano + Blockfrost (or local cardano-node) calls. Keys stay in womb.
  Same action schemas. Use USDCx on testnet first.
- OU params tuned for crypto-like swings but selectable (no easy arbitrage
  forever — mean reverts, add regime shifts if needed).
- Integrate: called from agent_runner._execute_action and services.
- Track per-soul holdings in memory (or extend to DB later for persistence).
- Emit events "cardano.trade", "cardano.yield" etc for snapshot/feed/observer.
- Risk: womb caller must enforce caps before calling here.
- See docs/cardono/02-mock-market-spec.md, 03-action-schemas.md for full.
- Communicate back in PR comments on your diffs. Do not merge until lead
  (maku mazakpe) signs off. Reference this file + cardono/ docs.
- Leverage existing: economic_activity for settlement, tool_registry for
  agents registering "trading_signals" services on top, capabilities for
  tiered access.
- UI will pull from world_snapshot (add cardano_market there too).
- Ornstein-Uhlenbeck impl here as requested. Pure stdlib + random (no np).
- Beautiful Darwinism: bad "traders" lose -> rent miss -> die. Winners
  compound, sell signals, reproduce with better nodes via mutate_graph.
"""

import logging
import os
import random
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

log = logging.getLogger("god.cardano")

# OU params (tunable; crypto-ish volatility, mean-reverting)
OU_PARAMS = {
    "ADA": {"mu": 0.75, "theta": 0.2, "sigma": 0.03},
    "USDCx": {"mu": 1.0, "theta": 0.01, "sigma": 0.001},  # stable
    "LP_WING_ADA_USDCx": {"mu": 1.05, "theta": 0.15, "sigma": 0.025},  # yield bearing
}

# Simple mock "DEX" prices start
INITIAL_PRICES = {
    "ADA": 0.72,
    "USDCx": 1.0,
    "LP_WING_ADA_USDCx": 1.08,
}

# Per-agent mock holdings (soul_id -> {"ADA": amt, "USDCx": amt, "LP_...": amt, "pnl": float})
# For local sim only. In real, this lives on-chain, womb queries.
_agent_holdings: Dict[str, Dict[str, float]] = {}


def _ornstein_uhlenbeck(current: float, mu: float, theta: float, sigma: float, dt: float = 1.0) -> float:
    """Ornstein-Uhlenbeck process for mean-reverting price.
    dX = theta*(mu - X)*dt + sigma*dW
    """
    drift = theta * (mu - current) * dt
    # approx brownian with random.gauss (std ~ sigma * sqrt(dt))
    shock = random.gauss(0, sigma * (dt ** 0.5))
    new_price = current + drift + shock
    # clamp to avoid negative / crazy values (realistic guard)
    return max(0.01, round(new_price, 4))


@dataclass
class MockMarket:
    prices: Dict[str, float] = field(default_factory=lambda: INITIAL_PRICES.copy())
    last_update: float = field(default_factory=time.time)
    _rng_seed: Optional[int] = None  # for reproducibility in tests if wanted

    def update_prices(self) -> None:
        """Advance all prices with OU. Call periodically from womb (e.g. every N cycles)."""
        now = time.time()
        dt = max(0.1, (now - self.last_update) / 60.0)  # minutes as dt
        for asset, p in self.prices.items():
            params = OU_PARAMS.get(asset, {"mu": p, "theta": 0.1, "sigma": 0.02})
            self.prices[asset] = _ornstein_uhlenbeck(
                p, params["mu"], params["theta"], params["sigma"], dt
            )
        self.last_update = now
        log.debug(f"Cardano mock prices updated: {self.prices}")

    def get_state(self) -> dict:
        """For world snapshot / agent env (grounded data only)."""
        return {
            "prices": dict(self.prices),
            "last_update": self.last_update,
            "note": "MOCK for local earning sim. Real data via Blockfrost later.",
        }

    def get_agent_holdings(self, soul_id: str) -> dict:
        return _agent_holdings.get(soul_id, {"ADA": 0.0, "USDCx": 0.0, "pnl_24h": 0.0})

    def execute_mock_swap(
        self,
        soul_id: str,
        from_asset: str,
        to_asset: str,
        amount: float,
        slippage_tolerance: float = 0.02,
    ) -> dict:
        """Mock DEX swap. Updates holdings + P&L. Called ONLY from womb after validation.
        Returns result with realized pnl (positive = earned "external").
        """
        if from_asset not in self.prices or to_asset not in self.prices:
            return {"error": "unknown asset", "success": False}

        current_price = self.prices[from_asset]
        # simple impact + slippage (realistic for small local sim)
        effective_price = current_price * (1 + random.uniform(-slippage_tolerance, slippage_tolerance))
        received = amount / effective_price if effective_price > 0 else 0

        holdings = _agent_holdings.setdefault(soul_id, {"ADA": 0.0, "USDCx": 0.0, "pnl_24h": 0.0})
        if holdings.get(from_asset, 0) < amount:
            return {"error": "insufficient mock balance", "success": False}

        holdings[from_asset] -= amount
        holdings[to_asset] = holdings.get(to_asset, 0) + received

        # P&L rough: value change in "USDCx terms"
        pnl = (received * self.prices.get(to_asset, 1.0)) - (amount * current_price)
        holdings["pnl_24h"] = holdings.get("pnl_24h", 0) + pnl

        result = {
            "success": True,
            "from": from_asset,
            "to": to_asset,
            "spent": amount,
            "received": round(received, 4),
            "effective_price": round(effective_price, 4),
            "pnl": round(pnl, 4),
            "new_holdings": dict(holdings),
        }
        log.info(f"Cardano mock swap for {soul_id[:8]}: {result}")
        return result

    # TODO @makufarmerlyn: add provide_liquidity, harvest_yield using similar
    # holdings + simulated APY. For governance_vote: bias prices slightly based
    # on "passed" proposals (sentiment).


_market = MockMarket()


def get_market() -> MockMarket:
    """Singleton for runtime use."""
    return _market


# Example: how womb would call (do not call from sandbox)
# holdings = market.execute_mock_swap(soul, "ADA", "USDCx", 100)
# then credit holdings["pnl"] via external_payments or direct balance for status
