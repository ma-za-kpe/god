# Actions Must Not Fail - Hard Requirement for Cardano Earning Layer

**Date:** 2026-06-12 (added per lead directive)

**Non-Negotiable Rule (applies to this feature and reinforces core GOD design):**
All actions — especially the new `cardano_*` ones — **must not fail** in a way that crashes the agent, the womb, the runtime loop, or the ecology.

This is critical for:
- Law 0 rent enforcement (throttling happens in womb, not via crashes).
- Law 2 death (only via proper rent miss path).
- 74 Ecology Hardening Manifesto (raw signals yes, but control plane remains stable; agents learn from failures without the whole system collapsing).
- 77 Agent Autonomy (per-agent env, structured actuation only; sandbox can "fail" in thinking, womb never propagates unhandled errors).
- 85 Economy/Governance (external revenue via Cardano must be reliable; bad trades are learning signals, not system killers).
- Overall autonomy and emergence: agents must be able to experiment, mutate, and trade on Cardano (mock → real) without one bad action taking down their cognition or the observer feed.

## Why This Matters for Cardano Earning
- Agents will propose trades, liquidity, yields, governance votes.
- In mock: Ornstein-Uhlenbeck can produce edge cases (sudden volatility, insufficient simulated holdings after parallel actions).
- In real (future): Blockfrost timeouts, tx reverts, slippage, network issues, insufficient on-chain balance.
- Failures are good for Darwinism (losing money → rent pressure → selection), **but the action itself must return cleanly**.
- No exceptions escape the handler.
- No free-text or silent failures that let hostile signals execute.

## Implementation Rules (for @makufarmerlyn)
1. **Every Cardano action handler** (in `cardano_market.py`, any wrappers in `agent_runner.py` / `_execute_action`, services routes if exposed) **must** be inside `try: ... except Exception as e:` (or more specific).
2. On error:
   - Log at WARNING/ERROR level with safe info only (agent soul_id short, action type, high-level reason; **never** keys, full payloads with secrets, stack traces in user-facing responses).
   - Return a structured dict: `{"success": False, "error": "short_reason", "details": "optional safe info for agent learning", "pnl": 0 or partial if applicable}`.
   - Update any internal state gracefully (e.g., don't corrupt holdings dict).
3. **Pre-validation in womb is the first line of defense** (this should catch 95%+ of cases before reaching the handler):
   - Rent/physics gate (from `physics_gate.py`).
   - Capability/tier check (from `capabilities.py`).
   - Risk limits (max % of balance per position, daily drawdown circuit breaker — extend existing `circuit_breaker.py` pattern if needed).
   - Grounding (from `grounding.py`): prices/assets must exactly match the latest `cardano_market` snapshot in env. No invented DEXes, no impossible amounts.
   - Balance/holding check before swap/liquidity.
4. For the mock implementation:
   - Simulate realistic "failures" inside the try (e.g., after price impact, if effective received < 0 due to extreme slippage, treat as error).
   - Always update holdings only on success path.
   - P&L on "failure" should be negative or zero, but never cause downstream crash.
5. When moving to real Cardano:
   - Same wrapper: try the PyCardano/Blockfrost call.
   - Catch network, tx simulation, revert, insufficient funds (even if pre-check passed due to race).
   - On real failure: still credit any gas fees paid (as learning cost), but return error.
   - Never let a Cardano tx failure kill the agent's cycle or prevent the next dream/sleep.
6. Integration points that must respect this:
   - `agent_runner.py`: the call to the action must be in a try that catches and emits a safe "action.failed" event (or similar) instead of crashing.
   - `archetype_graphs.py`: if an action "fails", the decide node still completes with a thought like "trade failed due to slippage — lesson learned".
   - `economic_activity.py` / settlement: partial or failed Cardano trades must still settle any internal USDC side cleanly.
   - Observer: failed actions should appear in drama feed as learning signals (e.g., "Trader-xxx attempted swap but failed: slippage too high"), not red errors.
7. Testing/Verification (mental + code):
   - Force error paths: bad asset name, amount > holdings, extreme OU swing.
   - Verify no exception reaches top-level agent cycle.
   - Agent continues to next cycle, can reproduce if rent is paid.
   - Add to grounding rules if new hallucination patterns appear (e.g., agents dreaming impossible Cardano prices).

## Relation to Existing GOD Mechanisms
- This is an extension of "actions are gated" (85 diagram: decide → act only if womb allows).
- `circuit_breaker.py` already pauses on abuse — extend to Cardano volume/risk.
- `inbox_salience.py` and reputation can use Cardano action outcomes as signals.
- `dream_engine.py` and mutations can propose "better risk node" after failures (positive emergence).

## Documentation & PR Notes
- This file (07-actions-must-not-fail.md) is now part of the spec in `docs/cardono/`.
- Builder must reference it in PR diffs with @ comments.
- Lead (maku) will specifically review every Cardano action path for compliance before approving merge.
- Update `03-action-schemas.md` and `02-mock-market-spec.md` if needed to call out error return shapes.

**Enforcement in this PR/commit:**
All new code in `cardano_market.py` (and any future extensions) will demonstrate try/except + clean error returns from day one.

@makufarmerlyn: This is now a review blocker. Implement robustly. If an action can "fail", design it so the failure is observable and educational for the agent, never destructive to the system.

— maku mazakpe (lead)
EOF