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


def _ornstein_uhlenbeck(
    current: float, mu: float, theta: float, sigma: float, dt: float = 1.0
) -> float:
    """Ornstein-Uhlenbeck process for mean-reverting price.
    dX = theta*(mu - X)*dt + sigma*dW
    """
    drift = theta * (mu - current) * dt
    # approx brownian with random.gauss (std ~ sigma * sqrt(dt))
    shock = random.gauss(0, sigma * (dt**0.5))
    new_price = current + drift + shock
    # clamp to avoid negative / crazy values (realistic guard)
    return max(0.01, round(new_price, 4))


@dataclass
class MockMarket:
    prices: Dict[str, float] = field(default_factory=lambda: INITIAL_PRICES.copy())
    last_update: float = field(default_factory=time.time)
    _rng_seed: Optional[int] = None  # for reproducibility in tests if wanted
    recent_trades: list = field(default_factory=list)  # for snapshot/feed (gap1)

    def update_prices(self) -> None:
        """Advance all prices with OU. Call periodically from womb (e.g. every N cycles).
        @makufarmerlyn: Must never raise. Wrapped for 'actions must not fail' rule.
        See docs/cardono/07-actions-must-not-fail.md. On any math/OU edge, log and keep last prices.
        Regime-ish via sigma + mean shifts in OU params (prevent pure overfit).
        """
        try:
            now = time.time()
            dt = max(0.1, (now - self.last_update) / 60.0)  # minutes as dt
            for asset, p in self.prices.items():
                params = OU_PARAMS.get(asset, {"mu": p, "theta": 0.1, "sigma": 0.02})
                self.prices[asset] = _ornstein_uhlenbeck(
                    p, params["mu"], params["theta"], params["sigma"], dt
                )
            self.last_update = now
            log.debug(f"Cardano mock prices updated: {self.prices}")
        except Exception as e:
            log.warning(f"Cardano mock price update failed safely (no crash): {e}")
            # Keep previous prices - action "did not fail" the system.

    def get_state(self) -> dict:
        """For world snapshot / agent env (grounded data only). Extended for gaps 1/3 (positions, recent_trades)."""
        # Sample positions (top few by total value rough) + recent for UI/feed
        pos_sample = {}
        try:
            for sid, h in list(_agent_holdings.items())[:6]:
                pos_sample[sid[:8]] = {
                    k: round(v, 4)
                    for k, v in h.items()
                    if k in ("ADA", "USDCx", "LP_WING_ADA_USDCx", "pnl_24h")
                }
        except Exception:
            pass
        return {
            "prices": dict(self.prices),
            "last_update": self.last_update,
            "recent_trades": list(self.recent_trades[-10:]),
            "positions_sample": pos_sample,
            "note": "MOCK for local earning sim (OU + slippage + yield + gov sentiment). Real via Blockfrost/PyCardano in womb only later. See cardono/02.",
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

        @makufarmerlyn: CRITICAL - 'actions must not fail' (see docs/cardono/07).
        This entire method is try/except wrapped. On ANY error (bad input, math, state),
        log safely and return clean error dict. NEVER raise. Womb pre-checks + this = robust.
        Simulate realistic failures (slippage, insufficient) as error returns for agent learning.
        """
        try:
            if from_asset not in self.prices or to_asset not in self.prices:
                return {
                    "success": False,
                    "error": "unknown asset",
                    "details": f"from={from_asset}, to={to_asset}",
                }

            current_price = self.prices[from_asset]
            # simple impact + slippage (realistic for small local sim)
            effective_price = current_price * (
                1 + random.uniform(-slippage_tolerance, slippage_tolerance)
            )
            if effective_price <= 0:
                return {
                    "success": False,
                    "error": "invalid effective price",
                    "details": str(effective_price),
                }

            received = amount / effective_price

            holdings = _agent_holdings.setdefault(
                soul_id, {"ADA": 0.0, "USDCx": 0.0, "pnl_24h": 0.0}
            )
            if holdings.get(from_asset, 0) < amount:
                return {
                    "success": False,
                    "error": "insufficient mock balance",
                    "details": f"has={holdings.get(from_asset, 0)}, need={amount}",
                }

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
            self.recent_trades.append(
                {
                    "t": int(time.time()),
                    "soul": soul_id[:8],
                    "type": "swap",
                    "pnl": round(pnl, 4),
                    "pair": f"{from_asset}->{to_asset}",
                }
            )
            if len(self.recent_trades) > 50:
                self.recent_trades = self.recent_trades[-50:]
            log.info(f"Cardano mock swap for {soul_id[:8]}: {result}")
            return result
        except Exception as e:
            log.warning(
                f"Cardano mock swap failed safely for {soul_id[:8]} (no crash, action did not fail system): {e}"
            )
            return {
                "success": False,
                "error": "internal mock error",
                "details": "contact womb - failure handled gracefully",
            }

    # TODO @makufarmerlyn (builder): Review the full OU + handlers. Pull, rebuild docker, test mock trades/yields/gov in local 8-agent setup, report logs. Extend for real later. See docs/cardono/10 and 09. Always push updates and tag @ma-za-kpe.

    def execute_provide_liquidity(
        self, soul_id: str, pool: str, amount_a: float, amount_b: float
    ) -> dict:
        """Mock provide liquidity to a pool. Updates holdings, accrues simulated yield."""
        try:
            holdings = _agent_holdings.setdefault(
                soul_id, {"ADA": 0.0, "USDCx": 0.0, "pnl_24h": 0.0, "LP_WING_ADA_USDCx": 0.0}
            )
            if holdings.get("ADA", 0) < amount_a or holdings.get("USDCx", 0) < amount_b:
                return {"success": False, "error": "insufficient mock balance for LP"}
            holdings["ADA"] -= amount_a
            holdings["USDCx"] -= amount_b
            lp_amount = (amount_a + amount_b) / 2  # simplistic
            holdings["LP_WING_ADA_USDCx"] = holdings.get("LP_WING_ADA_USDCx", 0) + lp_amount
            # Simulate yield accrual over time (mock APY)
            apy = 0.12  # 12% example
            yield_amount = lp_amount * (apy / 365)  # daily rough
            holdings["pnl_24h"] = holdings.get("pnl_24h", 0) + yield_amount
            result = {
                "success": True,
                "pool": pool,
                "added_a": amount_a,
                "added_b": amount_b,
                "lp_received": round(lp_amount, 4),
                "simulated_yield": round(yield_amount, 4),
                "new_holdings": dict(holdings),
            }
            self.recent_trades.append(
                {
                    "t": int(time.time()),
                    "soul": soul_id[:8],
                    "type": "provide_liquidity",
                    "pnl": round(yield_amount, 4),
                    "pool": pool,
                }
            )
            if len(self.recent_trades) > 50:
                self.recent_trades = self.recent_trades[-50:]
            log.info(f"Cardano mock LP for {soul_id[:8]}: {result}")
            return result
        except Exception as e:
            log.warning(f"Cardano mock LP failed safely for {soul_id[:8]}: {e}")
            return {
                "success": False,
                "error": "internal mock LP error",
                "details": "handled gracefully per 07",
            }

    def execute_harvest_yield(self, soul_id: str, position_id: str) -> dict:
        """Mock harvest yield from LP position."""
        try:
            holdings = _agent_holdings.setdefault(
                soul_id, {"ADA": 0.0, "USDCx": 0.0, "pnl_24h": 0.0, "LP_WING_ADA_USDCx": 0.0}
            )
            lp = holdings.get("LP_WING_ADA_USDCx", 0)
            if lp <= 0:
                return {"success": False, "error": "no LP position"}
            harvest = lp * 0.001  # small daily mock
            holdings["USDCx"] += harvest
            holdings["pnl_24h"] = holdings.get("pnl_24h", 0) + harvest
            result = {
                "success": True,
                "position_id": position_id,
                "harvested": round(harvest, 4),
                "new_holdings": dict(holdings),
            }
            self.recent_trades.append(
                {
                    "t": int(time.time()),
                    "soul": soul_id[:8],
                    "type": "harvest_yield",
                    "pnl": round(harvest, 4),
                    "pos": position_id,
                }
            )
            if len(self.recent_trades) > 50:
                self.recent_trades = self.recent_trades[-50:]
            log.info(f"Cardano mock harvest for {soul_id[:8]}: {result}")
            return result
        except Exception as e:
            log.warning(f"Cardano mock harvest failed safely for {soul_id[:8]}: {e}")
            return {
                "success": False,
                "error": "internal mock harvest error",
                "details": "handled gracefully per 07",
            }

    def execute_governance_vote(
        self, soul_id: str, proposal_id: str, vote: str, stake_amount: float
    ) -> dict:
        """Mock governance vote. Affects sentiment (small price bias) + possible reward."""
        try:
            holdings = _agent_holdings.setdefault(
                soul_id, {"ADA": 0.0, "USDCx": 0.0, "pnl_24h": 0.0}
            )
            if holdings.get("ADA", 0) < stake_amount:
                return {"success": False, "error": "insufficient stake"}
            holdings["ADA"] -= stake_amount  # stake locked mock
            # Mock sentiment impact on prices
            bias = 0.005 if vote.lower() == "yes" else -0.003
            for asset in self.prices:
                self.prices[asset] *= 1 + bias
            reward = stake_amount * 0.02 if vote.lower() == "yes" else 0  # mock reward
            holdings["USDCx"] += reward
            holdings["pnl_24h"] = holdings.get("pnl_24h", 0) + reward
            result = {
                "success": True,
                "proposal_id": proposal_id,
                "vote": vote,
                "staked": stake_amount,
                "sentiment_bias": bias,
                "reward": round(reward, 4),
                "new_holdings": dict(holdings),
            }
            self.recent_trades.append(
                {
                    "t": int(time.time()),
                    "soul": soul_id[:8],
                    "type": "governance_vote",
                    "pnl": round(reward, 4),
                    "proposal": proposal_id,
                    "vote": vote,
                }
            )
            if len(self.recent_trades) > 50:
                self.recent_trades = self.recent_trades[-50:]
            log.info(f"Cardano mock gov vote for {soul_id[:8]}: {result}")
            return result
        except Exception as e:
            log.warning(f"Cardano mock gov vote failed safely for {soul_id[:8]}: {e}")
            return {
                "success": False,
                "error": "internal mock gov error",
                "details": "handled gracefully per 07",
            }

    def execute_rebalance(self, soul_id: str, targets: dict) -> dict:
        """Mock rebalance to target allocations."""
        try:
            holdings = _agent_holdings.setdefault(
                soul_id, {"ADA": 0.0, "USDCx": 0.0, "pnl_24h": 0.0}
            )
            total = sum(holdings.get(k, 0) for k in ["ADA", "USDCx"])
            if total <= 0:
                return {"success": False, "error": "no balance to rebalance"}
            changes = {}
            for asset, target_pct in targets.items():
                target_amt = total * target_pct
                current = holdings.get(asset, 0)
                diff = target_amt - current
                holdings[asset] = target_amt
                changes[asset] = round(diff, 4)
            result = {
                "success": True,
                "targets": targets,
                "changes": changes,
                "new_holdings": dict(holdings),
            }
            self.recent_trades.append(
                {
                    "t": int(time.time()),
                    "soul": soul_id[:8],
                    "type": "rebalance",
                    "pnl": 0.0,
                    "targets": targets,
                }
            )
            if len(self.recent_trades) > 50:
                self.recent_trades = self.recent_trades[-50:]
            log.info(f"Cardano mock rebalance for {soul_id[:8]}: {result}")
            return result
        except Exception as e:
            log.warning(f"Cardano mock rebalance failed safely for {soul_id[:8]}: {e}")
            return {
                "success": False,
                "error": "internal mock rebalance error",
                "details": "handled gracefully per 07",
            }


_market = MockMarket()


def get_market() -> MockMarket:
    """Singleton for runtime use."""
    return _market


# Example: how womb would call (do not call from sandbox)
# holdings = market.execute_mock_swap(soul, "ADA", "USDCx", 100)
# then credit holdings["pnl"] via external_payments or direct balance for status

# Portfolio Guardian (gap4 / 09-risk): agents mutate_graph to add "portfolio_guardian" node.
# It runs in perception/_grounded_decide (or pre-execute) checking total exposure / drawdown vs cardano_holdings + balance.
# Womb (here + runner cardano block + circuit) enforces hard limits. "Teaching pain" in OU makes it learnable.
# Concrete: if sum(exposure) > 0.25 * (balance + holdings total) or recent drawdown > 0.3 -> reject or reduce size.
# Ties to episodic_memory (high valence on losses) + dream_engine (replay -> mutate "add guardian") + status demote.
# No hardcode perfection — emerges via selection + memory per 74/08/09.
