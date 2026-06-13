# What's Left to Implement – Cardano Earning Layer (Post-Builder Updates)

> **ROLE DEFINITION (lead directive, 2026-06-12 — emphasize this every cycle):**
>
> - **Builder's job (@makufarmerlyn / the other person who is actually running the code):** Fix broken code. Make sure the application runs well after pull + docker rebuild. Test, capture logs, clean up, report back (survival, P&L, events, errors, UI behavior, any grounding/circuit issues). Push your fixes, cleanups, test results, rebases, and log artifacts frequently. **Do NOT introduce any new logic, new features, new architecture, or new code paths.** Tag the lead on every push/comment. Keep monitoring on (monitor-pr.sh + GitHub notifs).
>
> - **Lead's job (ma-za-kpe / this agent):** Introduce new code, new logic, synthesis, research tie-ins (institutional risk, Cardano primitives, memory/learning), fresh perspective. Update the canonical docs/cardono/ specs. Push the new logic. Leave detailed comments on #65 for the builder. Monitor replies. Ask them to tag if they need to communicate. Document the "what's left" and workflow here.
>
> This division keeps the ecology clean: the person running the actual system focuses on making physics work and reporting raw signals (logs, deaths, P&L, drama). The lead brings the new design/logic after seeing the live results. One canonical place for roles (link here from PR comments). Do not blur it.

**Date:** 2026-06-12 (lead review after @makufarmerlyn's enforcement work)
**Branch:** cardano
**PR:** #65 (for #64)
**Status:** (lead 2026-06-12 after introducing remaining per user-pasted gaps + 10)
Builder previously delivered excellent "actions must not fail" (07) + docker. Lead has now introduced the rest of Phase 1 wiring (see 06 for full list of landed code).

See 06-implementation-status.md (updated), 02/03/04/08/09 for specs. PR #65.

Release + repo hygiene (lead): main/develop now protected (exact rules from 83); runtime version centralized in runtime/src/VERSION + loaded dynamically (no more manual edits in main.py for the health signal the builder observes). Use the documented release flow (soak on develop, PR to main, tag + gh release) going forward.

## Completed by this lead introduction (gaps 1-4 prioritized)
- 1. Mock complete: full OU + all execute handlers (provide/harvest/gov/rebalance + prior swap) + holdings/P&L + snapshot data (recent_trades, positions_sample, volume, top) + teaching pain (slippage/regime).
- 2. Integration: capabilities tiers fixed+described, archetype perception/VALID/prompt/world_rules + cardano payload parse, runner full routing + P&L settle (external_payments) + env holdings inject, services world cardano_market virtual + meta via registry/routes.
- 3. Observer UI: lpanel ▸ CARDANO MARKET (prices + vol + earners), inspector ▸ CARDANO HOLDINGS (positions+pnl), feed cardano.* gold flash-econ + narrative, JS renderCardanoMarket + holdings render from snap, called in poll. Brand/perf preserved (comments for builder).
- 4. Risk/memory: Portfolio Guardian comment/skeleton (mutate-in, womb enforce), circuit_breaker record_cardano_pnl (loss streak trip/pause), status_engine tie to cardano ext rev for demote, explicit episodic/dream/mutate/reputation/selection ties (losses -> high valence replay -> corrective mutations).
- Docs 06/10/07-09 updated with progress + @builder instructions + workflow.
- Untracked docs + changes added/committed (pre-commit + security before push).

## Still Left (post this, for builder soak + later)
- Polish / archetype mutations for Trader/Yield/Gov (roadmap 2).
- Real Cardano flip (Blockfrost/PyCardano in womb; testnet; same schemas) — post Phase 1 soak (08/78).
- Full ext rev flow, tier ascents, archetype specialization.
- Update 06 + this as you go. 14-day gates before real.

**Priorities now for you (builder):**
Pull, security-audit + pre-commit, docker rebuild, up. Exercise the 8 (esp trader archetype) with cardano actions. Verify: grounded prices/holdings in env, proposals execute, P&L moves balance/rent, losses trip breaker or cause death, UI lpanel/inspector/feed shows beautifully (gold), services registry has cardano_market. Report logs, errors, survival metrics, any mutations.

**Satisfied for Phase 1 (08):** autonomous, mock earning with inequality + deaths from bad cardano, learning visible (mutations post-mistake), UI witness, actions robust.

See full in 02/03/04/09/08. Reference in diffs. Add comments.

@makufarmerlyn: Lead introduced the code for the verbatim gaps you/ user pasted (1-5 high-level + roadmap). Pull this (git pull), rebuild docker, run, give logs etc. ALWAYS push your new changes (cleanups, test results, fixes, more archetype), tag @ma-za-kpe in PR #65 comments. Turn on / keep monitoring (scripts/monitor-pr.sh 65 + gh notifs + gh run watch) so you catch my perspective immediately. Tag me if you need to communicate. Do not merge until lead explicit approve. godspeed — this is the ecology earning layer.

godspeed.
EOC
)" 2>&1 | cat
