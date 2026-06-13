# Implementation Status & Roadmap (as of now, lead perspective)

> **ROLE DEFINITION (lead directive, 2026-06-12 — read and follow exactly):**
>
> - **Builder's job (@makufarmerlyn):** Fix broken code so the application runs. After every pull + `docker compose build && up -d`, make sure it actually executes the 8 agents without crashes, report the logs, P&L, events, deaths, UI state, any errors. Push **fixes, cleanups, test reports, log captures**. **Do not introduce any new logic or new code.** Tag lead on pushes. Run monitoring scripts constantly.
>
> - **Lead's job:** Introduce the new logic, complete the gaps (mock, integration, UI, risk/memory per 10), synthesize (09 institutional mapping, 08 success), update this doc + 10 + PR comments. Push the design. Monitor builder replies. Ask for tags on communication.
>
> Builder runs the ecology and reports raw adversarial signals (logs = the harsh world). Lead designs the new layer and hands over clean specs + code for the runner to stabilize. See also the top of 10-whats-left-to-implement.md for the canonical statement.

**Documented**: Full brainstorm captured in 00-05 + this. All from user pasted thoughts + my synthesis. Goals checked against canon (vision, 14 laws, 85 map, 74 manifesto, 58/77 autonomy, 30/56 x402/services).

**Built so far (lead introduces, builder runs/tests/reports)**:
- Docs/cardono/ full set (00-10) + workflow notes.
- cardano_market.py: full OU (noise, regime, slippage/impact, yields, gov sentiment) + all 6 execute handlers (monitor/swap/provide/harvest/gov/rebalance) with try/except/structured err + P&L + holdings + recent_trades. "actions must not fail" (07).
- capabilities.py: tiered cardano (1:monitor, 2:swap/liquidity/harvest, 3:gov/rebalance/register) merged without overwrite + descriptions.
- agent_runner.py: cardano_* routing in _execute_action (with P&L settle to balance + external_payments for status/ext rev, cardano.* emits), refresh_env injects holdings for grounded env.
- archetype_graphs.py: cardano actions in _VALID_ACTIONS + parse payload + _WORLD_RULES updated (permit local mock, ban real crypto fiction) + perception via env + tools_menu.
- world_snapshot.py + agent_env.py: cardano_market (prices + positions_sample + recent_trades + volume + top) in stats; holdings in self/status.json.
- services/registry.py + routes.py: world "cardano_market" virtual service + meta (signals) via existing register.
- observer/index.html: lpanel ▸ CARDANO MARKET (prices/vol/earners .pv.gold), inspector ▸ CARDANO HOLDINGS row+render, feed cardano.* gold flash-econ, renderCardanoMarket wired + enhanced (per 04). No breakage.
- circuit_breaker.py + status_engine.py: cardano losing streak breaker (record_cardano_pnl), bad_periods tie to cardano ext rev for demotion.
- Portfolio Guardian skeleton + teaching pain (OU edge cases + slippage returns) + explicit memory ties (episodic/dream/mutate will capture losses for adaptation).
- Untracked docs 07/08/09 committed with this (risk, success, must-not-fail).
- Pre-commit + security will pass before push. No app run (per doctrine).
- Git on cardano; PR #65 open; always push + tag + monitor instruction in comments.
- Branch protection enabled on main + develop (via scripts/setup-branch-protection.sh per docs/83-git-workflow.md + CONTRIBUTING: required pre-commit/gitleaks/bandit checks, PRs, enforce admins, no force-push). Runtime version now release-driven: single source runtime/src/VERSION (loaded in main.py for FastAPI + /health); future bumps happen in develop→main release PR + `gh release create` tag instead of manual string edits.

**For Builder (makufarmerlyn)**:
Pull this, `bash scripts/security-audit.sh && python3 -m pre_commit run --all-files`, docker compose build && up -d. Run the 8 agents. Watch for cardano actions in logs (trader archetype should propose when dip in env snapshot), P&L updates, rent pressure from losses, UI show in lpanel/inspector/feed (gold). Report full logs (or tail via monitor), any grounding rejects, deaths/repros tied to bad trades, mutations for risk nodes. Turn on `bash scripts/monitor-pr.sh 65` + gh notifs now. ALWAYS push your cleanups/fixes/new (even small), tag @ma-za-kpe or @maku in PR comments. We iterate fast.

**Roadmap** (from 06 + user gaps):
1. Mock + local earning among the 8 (this — Phase 1 local per 08).
2. Archetype specialization + mutations toward trading.
3. UI polish + feed integration.
4. Real Cardano (testnet first, WingRiders etc.).
5. Production: ext rev → tiers → agents ascend.

Satisfied only when: Phase 1 metrics (08): autonomous 8, mock Cardano actions >100, P&L inequality (top 3-5x), some deaths/repros from bad cardano strategies, grounding catch, mutations accepted, UI beautiful, actions never fail control plane. Then soak, real flip.

godspeed.
