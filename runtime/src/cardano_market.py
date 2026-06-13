"""
cardano_market.py — Mock Cardano market for local agent earning simulation.

Enhanced per brutally honest external audit + lead plan (mid-2026 realities):
- Historical replay mode first (realistic patterns + noise).
- Jump-diffusion (fat tails) + vol clustering approx.
- Realistic slippage/fee + multi-agent contention (eUTxO batch-like).
- Grounded "analytics signals" stub.
- Iron risk: require risk_params (max_risk_pct 0.5-1%, stop, take). Guardian pre-check MANDATORY for all trade/liquidity actions.
- "Actions must not fail" wrappers everywhere.

This is tuition-paying Darwinian filter in thin liquidity. Expect high early churn. Lead introduces the logic; builder ONLY fixes/runs/reports raw data (deaths, P&L, DD, mutations, logs). NO new logic/extensions from builder.

ALL in WOMB. Sandbox proposes only.
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
    _rng_seed: Optional[int] = None
    recent_trades: list = field(default_factory=list)
    # Sharpened mock (per audit): historical replay stub + jump diffusion for fat tails.
    # Priority: historical first for real patterns. Contention on executes.
    historical_prices: Dict[str, list] = field(default_factory=dict)  # asset -> [price_series]
    current_hist_idx: Dict[str, int] = field(default_factory=dict)
    # MEV protection simulation state (for additional layers)
    pending_commits: dict = field(
        default_factory=dict
    )  # commit_hash -> {"soul": , "action": , "ts": }

    def _maybe_init_historical(self):
        if not self.historical_prices:
            # Priority per audit: historical replay first (realistic patterns + noise, not pure OU).
            # Stub "real Cardano-like" series (base + mild trend + noise + occasional regime jump).
            for asset in self.prices:
                base = self.prices[asset]
                series = []
                p = base
                trend = random.uniform(-0.002, 0.002)  # mild drift
                for i in range(100):
                    p = p * (1 + trend + random.uniform(-0.015, 0.015))
                    if random.random() < 0.03:  # occasional regime shock
                        p *= random.uniform(0.85, 1.15)
                    series.append(round(max(0.01, p), 4))
                self.historical_prices[asset] = series
                self.current_hist_idx[asset] = 0

    def update_prices(self, use_replay: bool = False) -> None:
        """Advance prices. use_replay=True uses historical + noise (teaches real patterns first).
        Adds jump-diffusion approx for fat tails + simple vol clustering.
        @makufarmerlyn: Builder — implement exactly. Report if replay mode produces different agent behavior.
        Must never raise (actions must not fail).
        """
        try:
            self._maybe_init_historical()
            now = time.time()
            dt = max(0.1, (now - self.last_update) / 60.0)

            for asset, p in list(self.prices.items()):
                params = OU_PARAMS.get(asset, {"mu": p, "theta": 0.1, "sigma": 0.02})

                if use_replay and asset in self.historical_prices:
                    idx = self.current_hist_idx.get(asset, 0) % len(self.historical_prices[asset])
                    base = self.historical_prices[asset][idx]
                    self.current_hist_idx[asset] = idx + 1
                    # Replay + OU noise + occasional jump
                    p = base
                else:
                    p = self.prices[asset]

                # OU base
                new_p = _ornstein_uhlenbeck(p, params["mu"], params["theta"], params["sigma"], dt)

                # Jump diffusion approx (fat tails): rare large moves
                if random.random() < 0.05:  # 5% chance jump
                    jump = random.gauss(0, params["sigma"] * 3)  # larger shock
                    new_p += jump

                # Simple vol clustering: if recent move large, increase sigma temporarily
                if abs(new_p - p) > params["sigma"] * 2:
                    new_p += random.gauss(0, params["sigma"] * 0.5)

                self.prices[asset] = max(0.01, round(new_p, 4))

            self.last_update = now
            log.debug(f"Cardano mock prices updated (replay={use_replay}): {self.prices}")
        except Exception as e:
            log.warning(f"Cardano mock price update failed safely: {e}")

    def _guardian_check(self, soul_id: str, risk_params: dict, trade_value: float) -> dict:
        """Mandatory Portfolio Guardian pre-check (per audit + plan + new MEV layer).
        Enforced in womb before any cardano trade/liquidity.
        Supports additional protections: deadline, twap_chunks, use_batch, commit_reveal.
        Returns {"ok": bool, "reason": str}.
        Builder: do not relax this. Report any guardian blocks in logs.
        """
        try:
            max_risk = float(risk_params.get("max_risk_pct", 0.01))
            if max_risk > 0.02:  # hard cap at 2%, prefer 0.5-1%
                return {"ok": False, "reason": "max_risk_pct too high (>2% not allowed)"}

            holdings = self.get_agent_holdings(soul_id)
            total_exposure = sum(
                holdings.get(k, 0) for k in ["ADA", "LP_WING_ADA_USDCx"] if k != "pnl_24h"
            )
            # Rough: if this trade would push Cardano exposure >35%, block
            if total_exposure + trade_value > 0.35 * (
                total_exposure + holdings.get("USDCx", 0) + 1
            ):
                return {"ok": False, "reason": "would breach portfolio Cardano exposure cap ~35%"}

            # Simple daily DD check stub (in real would track window)
            recent_pnl = holdings.get("pnl_24h", 0)
            if recent_pnl < -0.08:  # 8% drawdown pause
                return {"ok": False, "reason": "recent drawdown too high, guardian pause"}

            # Stress test sim (audit req): -50% crash on exposure would breach? Block large pos.
            if trade_value > 0.02 * (total_exposure + holdings.get("USDCx", 0) + 1):  # >2% rough
                # Approx crash impact
                crash_impact = -0.5 * trade_value
                if recent_pnl + crash_impact < -0.1:
                    return {"ok": False, "reason": "stress test: -50% crash would breach DD limits"}

            # New MEV: deadline / expiry
            if "deadline" in risk_params:
                if time.time() > float(risk_params["deadline"]):
                    return {"ok": False, "reason": "deadline expired - tx too old for MEV window"}

            # New MEV: TWAP chunking required for large trades
            twap = int(risk_params.get("twap_chunks", 1))
            if trade_value > 0.05 * (total_exposure + holdings.get("USDCx", 0) + 1) and twap < 2:
                return {
                    "ok": False,
                    "reason": "large trade requires twap_chunks >=2 for impact reduction",
                }

            # New MEV: commit-reveal required for high value
            if trade_value > 0.1 and not risk_params.get("commit_hash"):
                return {
                    "ok": False,
                    "reason": "high value requires commit_hash for commit-reveal protection",
                }

            # New MEV: batch mode encouraged for multiple
            # (no hard reject, but note in result for sim)

            return {"ok": True, "reason": "guardian ok"}
        except Exception as e:
            return {"ok": False, "reason": f"guardian error (safe fail): {e}"}

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
            # Analytics signals per audit (gap1): grounded "on-chain" proxies for perception (whale flows, vol spikes, TVL delta).
            # Agents can use in decide to avoid over-risk in "hot" regimes.
            "analytics": {
                "whale_flow_proxy": round(random.uniform(-0.2, 0.2), 3),  # mock large holder move
                "volume_spike": round(random.uniform(0.8, 1.5), 2),
                "tvl_delta": round(random.uniform(-0.05, 0.05), 3),
            },
            "note": "MOCK for local earning sim (historical replay priority + jumps + contention + analytics per audit). Real via Blockfrost/PyCardano in womb only later.",
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
        risk_params: dict | None = None,
    ) -> dict:
        """Mock DEX swap with sharpened realism (replay impact, contention, fat tails via price model).
        REQUIRES risk_params (max_risk_pct <=0.01 preferred, stop_loss_pct, take_profit_pct).
        Guardian MANDATORY. Womb must call with params or reject.

        @makufarmerlyn (builder): Implement EXACTLY the rules lead specified. Report raw guardian blocks,
        contention effects, replay vs normal behavior in logs. NO creative extensions or new logic.
        Fix only if it doesn't run.
        """
        try:
            risk_params = risk_params or {}
            guardian = self._guardian_check(soul_id, risk_params, amount)
            if not guardian.get("ok"):
                return {
                    "success": False,
                    "error": "guardian_block",
                    "details": guardian.get("reason"),
                }

            if from_asset not in self.prices or to_asset not in self.prices:
                return {
                    "success": False,
                    "error": "unknown asset",
                    "details": f"from={from_asset}, to={to_asset}",
                }

            current_price = self.prices[from_asset]

            # MEV protections simulation (on top of core risk/slippage)
            # 1. Commit-reveal: if commit_hash without reveal, record pending, delay full exec
            commit_hash = risk_params.get("commit_hash")
            if commit_hash and not risk_params.get("revealed", False):
                self.pending_commits[commit_hash] = {
                    "soul": soul_id,
                    "action": "swap",
                    "from_asset": from_asset,
                    "to_asset": to_asset,
                    "amount": amount,
                    "ts": time.time(),
                }
                return {
                    "success": False,
                    "error": "commit_phase",
                    "details": "waiting for reveal; commit recorded for MEV protection",
                    "commit_hash": commit_hash,
                }

            # 2. Batch auctions / uniform clearing: if use_batch, use averaged "batch price"
            if risk_params.get("use_batch") or risk_params.get("batch_mode"):
                # Simulate uniform clearing price (average of current + recent impact or fixed)
                batch_price = current_price
                if self.recent_trades:
                    recent_prices = [
                        self.prices.get(t.get("pair", "").split("->")[0], current_price)
                        for t in self.recent_trades[-3:]
                        if "->" in t.get("pair", "")
                    ]
                    if recent_prices:
                        batch_price = sum(recent_prices) / len(recent_prices)
                effective_price = batch_price  # uniform for batch
            else:
                # 3. Low/dynamic slippage + TWAP chunking
                twap_chunks = int(risk_params.get("twap_chunks", 1))
                base_impact = random.uniform(-slippage_tolerance, slippage_tolerance) / max(
                    1, twap_chunks
                )
                recent_activity = len(
                    [
                        t
                        for t in self.recent_trades[-5:]
                        if t.get("type") in ("swap", "provide_liquidity")
                    ]
                )
                contention_mult = 1 + (recent_activity * 0.15)
                effective_price = current_price * (1 + base_impact * contention_mult)

            # Fee realism
            fee = 0.003
            effective_price *= 1 + fee

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

            pnl = (
                (received * self.prices.get(to_asset, 1.0))
                - (amount * current_price)
                - (amount * fee)
            )
            holdings["pnl_24h"] = holdings.get("pnl_24h", 0) + pnl

            result = {
                "success": True,
                "from": from_asset,
                "to": to_asset,
                "spent": amount,
                "received": round(received, 4),
                "effective_price": round(effective_price, 4),
                "pnl": round(pnl, 4),
                "contention_mult": round(contention_mult, 2),
                "guardian": guardian,
                "new_holdings": dict(holdings),
                "mev_protection": {
                    "commit_reveal": bool(commit_hash),
                    "batch": bool(risk_params.get("use_batch") or risk_params.get("batch_mode")),
                    "twap_chunks": twap_chunks,
                },
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
            log.warning(f"Cardano mock swap failed safely for {soul_id[:8]}: {e}")
            return {
                "success": False,
                "error": "internal mock error",
                "details": "handled gracefully per 07",
            }

    # TODO @makufarmerlyn (builder): Review the full OU + handlers. Pull, rebuild docker, test mock trades/yields/gov in local 8-agent setup, report logs. Extend for real later. See docs/cardono/10 and 09. Always push updates and tag @ma-za-kpe.

    def execute_provide_liquidity(
        self,
        soul_id: str,
        pool: str,
        amount_a: float,
        amount_b: float,
        risk_params: dict | None = None,
    ) -> dict:
        """Mock provide liquidity. REQUIRES risk_params + guardian (per audit/gap4: mandatory for liquidity).
        Adds contention realism.
        """
        try:
            risk_params = risk_params or {}
            guardian = self._guardian_check(soul_id, risk_params, (amount_a + amount_b) / 2)
            if not guardian.get("ok"):
                return {
                    "success": False,
                    "error": "guardian_block",
                    "details": guardian.get("reason"),
                }

            holdings = _agent_holdings.setdefault(
                soul_id, {"ADA": 0.0, "USDCx": 0.0, "pnl_24h": 0.0, "LP_WING_ADA_USDCx": 0.0}
            )
            if holdings.get("ADA", 0) < amount_a or holdings.get("USDCx", 0) < amount_b:
                return {"success": False, "error": "insufficient mock balance for LP"}
            holdings["ADA"] -= amount_a
            holdings["USDCx"] -= amount_b
            lp_amount = (amount_a + amount_b) / 2
            holdings["LP_WING_ADA_USDCx"] = holdings.get("LP_WING_ADA_USDCx", 0) + lp_amount
            apy = 0.12
            yield_amount = lp_amount * (apy / 365)
            holdings["pnl_24h"] = holdings.get("pnl_24h", 0) + yield_amount
            result = {
                "success": True,
                "pool": pool,
                "added_a": amount_a,
                "added_b": amount_b,
                "lp_received": round(lp_amount, 4),
                "simulated_yield": round(yield_amount, 4),
                "guardian": guardian,
                "new_holdings": dict(holdings),
            }
            # Contention (recent LP activity)
            recent_activity = len(
                [
                    t
                    for t in self.recent_trades[-5:]
                    if t.get("type") in ("provide_liquidity", "swap")
                ]
            )
            result["contention_mult"] = round(1 + (recent_activity * 0.1), 2)
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

    def execute_harvest_yield(
        self, soul_id: str, position_id: str, risk_params: dict | None = None
    ) -> dict:
        """Mock harvest. Accepts risk_params + guardian for uniformity (audit: every cardano action)."""
        try:
            risk_params = risk_params or {}
            lp = _agent_holdings.get(soul_id, {}).get("LP_WING_ADA_USDCx", 0)
            guardian = self._guardian_check(soul_id, risk_params, lp * 0.001)
            if not guardian.get("ok"):
                return {
                    "success": False,
                    "error": "guardian_block",
                    "details": guardian.get("reason"),
                }

            holdings = _agent_holdings.setdefault(
                soul_id, {"ADA": 0.0, "USDCx": 0.0, "pnl_24h": 0.0, "LP_WING_ADA_USDCx": 0.0}
            )
            lp = holdings.get("LP_WING_ADA_USDCx", 0)
            if lp <= 0:
                return {"success": False, "error": "no LP position"}
            harvest = lp * 0.001
            holdings["USDCx"] += harvest
            holdings["pnl_24h"] = holdings.get("pnl_24h", 0) + harvest
            result = {
                "success": True,
                "position_id": position_id,
                "harvested": round(harvest, 4),
                "guardian": guardian,
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
        self,
        soul_id: str,
        proposal_id: str,
        vote: str,
        stake_amount: float,
        risk_params: dict | None = None,
    ) -> dict:
        """Mock governance vote. Accepts risk_params + guardian (audit: every action).
        Sentiment impact remains.
        """
        try:
            risk_params = risk_params or {}
            guardian = self._guardian_check(soul_id, risk_params, stake_amount)
            if not guardian.get("ok"):
                return {
                    "success": False,
                    "error": "guardian_block",
                    "details": guardian.get("reason"),
                }

            holdings = _agent_holdings.setdefault(
                soul_id, {"ADA": 0.0, "USDCx": 0.0, "pnl_24h": 0.0}
            )
            if holdings.get("ADA", 0) < stake_amount:
                return {"success": False, "error": "insufficient stake"}
            holdings["ADA"] -= stake_amount
            bias = 0.005 if vote.lower() == "yes" else -0.003
            for asset in self.prices:
                self.prices[asset] *= 1 + bias
            reward = stake_amount * 0.02 if vote.lower() == "yes" else 0
            holdings["USDCx"] += reward
            holdings["pnl_24h"] = holdings.get("pnl_24h", 0) + reward
            result = {
                "success": True,
                "proposal_id": proposal_id,
                "vote": vote,
                "staked": stake_amount,
                "sentiment_bias": bias,
                "reward": round(reward, 4),
                "guardian": guardian,
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

    def execute_rebalance(
        self, soul_id: str, targets: dict, risk_params: dict | None = None
    ) -> dict:
        """Mock rebalance. Accepts risk_params + guardian (full coverage per audit/gaps)."""
        try:
            risk_params = risk_params or {}
            holdings = _agent_holdings.setdefault(
                soul_id, {"ADA": 0.0, "USDCx": 0.0, "pnl_24h": 0.0}
            )
            total = sum(holdings.get(k, 0) for k in ["ADA", "USDCx"])
            guardian = self._guardian_check(soul_id, risk_params, total * 0.1)  # proxy exposure
            if not guardian.get("ok"):
                return {
                    "success": False,
                    "error": "guardian_block",
                    "details": guardian.get("reason"),
                }

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
                "guardian": guardian,
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
