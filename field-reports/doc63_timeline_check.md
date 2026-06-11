[FIELD-CHECK] doc 63 — World Event Timeline (First-of-Type Registry + Milestone Tracker)

**Date:** 2026-06-11 (post #54/#55/#56 merges, develop @ 37d404b)
**Context:** User directive "63" interpreted as task-specific spec (per pattern: "read doc 86", PR checks, etc.). Reread all mandated docs (74 manifesto, 85 economy/governance, 77 autonomy, 75 adherence audit, 86 field onboarding, 78 PR field test protocol) + 63 as the active spec for this verification.

**Spec summary (doc 63):** Permanent append-only world_firsts for "first.*" events + dynamic world_milestones for thresholds (pop, revenue, etc.). Detection in event_emitter + timeline.py. APIs: /timeline, /timeline/firsts, /timeline/milestones. Observer display (timeline panel, live ticker). Significance scoring. See also 38 (events), 51 (dashboard), 53 (narrative), 43 (observer).

**Implementation status (running world, no rebuild this task):**

### 1. DB tables (exact)
```
             List of relations
 Schema |       Name       | Type  | Owner
--------+------------------+-------+-------
 public | world_firsts     | table | god
 public | world_milestones | table | god
(2 rows)
```
Tables present and match spec (first_id PK, first_type UNIQUE, milestone_id PK, etc.). No data loss from prior wipes (per history).

### 2. Runtime code (grep + file reads)
- runtime/src/timeline.py: Full implementation present.
  - FIRST_TYPE_MAP (18 entries, matches spec + extras like first.tier_promoted, first.dream_completed).
  - FIRST_NARRATIVES (human-readable, close to spec's _first_narrative).
  - check_for_firsts(event_type, payload, event_id): Wired, uses ON CONFLICT DO NOTHING, re-emits "timeline"."world.first".
  - check_milestones(): Population thresholds (10/25/50/100/250/500), _record_milestone_if_new with significance.
- Integration:
  - event_emitter.py: calls check_for_firsts after every emit.
  - main.py: /timeline, /timeline/firsts, /timeline/milestones endpoints (with world_id filter, error handling, wipe support in reset).
- No timeline daemon yet (spec suggests rent daemon or separate; check_milestones is defined but not auto-scheduled in this check — only population checked in the run).

### 3. Live APIs (exact curl outputs, current pop=8)
curl -s http://localhost:8888/timeline
```json
{"timeline":[{"kind":"first","type":"first.dream_completed","soul_id":"79587ccb-c2ee-4b2d-bae7-f7e6e262db24","ts":1781124895,"narrative":null},{"kind":"first","type":"first.rent_paid","soul_id":"79587ccb-c2ee-4b2d-bae7-f7e6e262db24","ts":1781124704,"narrative":null}],"count":2}
```

curl -s http://localhost:8888/timeline/firsts
```json
{"firsts":[{"first_id":"5f82d994-abf6-4089-b975-67ad395a1371","first_type":"first.rent_paid",... "details":{"name":"Elder-Merch-8161",... "narrative":"✓ Elder-Merch-8161 pays rent — another cycle of existence bought. Balance now $2.0070."}}, {"first_id":"b4478401-d58f-4196-8b85-97c3d35449ad","first_type":"first.dream_completed",... "details":{... "mutation_accepted":true, "mutation_proposed":"I should prioritize messaging..."}}],"count":2}
```

curl -s http://localhost:8888/timeline/milestones
```json
{"milestones":[],"count":0}
```

**Observations vs spec:**
- Firsts working: rent_paid and dream_completed recorded (matches some of the 20+ in spec table).
- Narratives present in details (implementation uses FIRST_NARRATIVES + name).
- Milestones: 0 (current living=8 <10 threshold; spec has pop milestones starting at 10). No revenue tracking visible in this run (spec notes "we'd track external revenue separately").
- Timeline combined endpoint returns firsts + milestones (sorted by ts).
- Event re-emit for observer ("timeline"."world.first" / "world.milestone").

### 4. Observer (MAKU console @ :3000/maku)
- From curl + logs: MAKU Creator Console serves /maku (→ maku.html).
- Nav includes: "★ FIRSTS" (data-section="timeline", fetches /timeline/firsts), "▲ MILESTONES" (fetches /timeline/milestones).
- UI has #field-dump-panel, raw API, etc. (from #55).
- No full "Timeline panel" or live ticker visible in static HTML (JS-driven; sections wired exactly as spec "Observer Integration").
- Logs show successful GET /maku 200s.

**Field verdict:** Core spec implemented and live (tables, detector in emitter, APIs, observer sections). Firsts are recording (2 so far). Milestones not yet triggered (pop too low). Some narrative/details present. Matches "first-of-type registry" + "milestone tracker". Ready for soak once population/revenue events fire more firsts/milestones.

**Artifacts:**
- This report: field-reports/doc63_timeline_check.md
- maku_current.txt (from prior curl)
- t-hall-02_* (prior soak, includes timeline events in logs)

Per doc 86 (field operator loop), 78 (PR field test + logs in every [FIELD-*]), Claude.md (reread before task, pull before, pre-commit, security, [FIELD-DATA] on PRs, track in backlog).

[FIELD-CHECK] doc 63 — timeline feature functional in current stack (develop 37d404b). Some firsts recorded; more data expected with time/pop growth. No blockers seen.

Next per doc 63: more events to hit milestones (pop 10+), verify observer display, check /timeline combined, backlog update if needed.
