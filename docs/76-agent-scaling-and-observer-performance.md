# Agent Scaling & Observer Performance

> **Date:** 2026-06-10  
> **Problem statement:** As agent count grows (especially via reproduction), the system lags. At 5000 agents the world must remain watchable by the public without degrading into a frozen debug UI.  
> **Constraint:** UI is for **public observation** — not an admin panel. Performance is a product requirement, not an ops nice-to-have.  
> **Status:** Investigation + recommendations only — no code changes made

---

## Executive Summary

Lag is **expected today** — the architecture is a single-process, sequential, LLM-bound dev stack with an O(n²) canvas renderer and HTTP polling. None of these components were designed for thousands of concurrent agents.

**Root cause is not reproduction itself.** Reproduction exposes three existing bottlenecks:

1. **Runtime:** one agent after another, 3+ LLM calls each, same 30s global cycle clock.
2. **API/DB:** new PostgreSQL connection per request; `/agents` capped at 100 rows.
3. **Observer:** 60fps O(n²) force simulation + full DOM redraw + 4 concurrent poll loops.

YouTube, Twitch, and large live platforms solve a **different but analogous** problem: millions of *viewers* watching a smaller set of *actors*, with heavy edge fanout and aggressive aggregation. GOD inverts this — **thousands of actors** each generating events. The correct pattern is closer to **MMO spectator clients + financial tick systems + event-sourced broadcasts** than to video CDN.

**Target invariant:** At N=5000 agents, the public observer must stay ≥30fps (map), drama feed <2s behind reality, and agent cognition must not block the observation path.

---

## Symptom Map

| Symptom | Likely cause | First seen at |
|---------|--------------|---------------|
| Observer tab stutters / freezes | O(n²) `tickSim()` every frame | ~200–500 agents |
| Drama feed stops updating smoothly | Poll storm + main thread blocked by canvas | ~100+ agents |
| API feels sluggish | Sequential runtime + DB connection churn | ~50+ agents (with LLM) |
| Agents "freeze" cognitively | Cycle time >> `AGENT_CYCLE_SECONDS` | ~20+ agents with Ollama |
| Missing agents on map | `LIMIT 100` on `/agents` | >100 alive |
| `maku.html` admin UI hangs | N+1 fetch per agent for dreams | ~50+ agents |

---

## Runtime Bottleneck Analysis

### 1. Sequential agent loop (critical)

`agent_runner.py` → `_run_cycle()`:

```python
for agent in agents:
    # 3 LangGraph nodes × LLM call (when Ollama enabled)
    # + 5+ DB queries per agent (inbox, services, coalitions, reputation)
    # + event emit + optional reproduction
    await asyncio.sleep(0.05)  # stagger
```

**Math (LLM enabled, 3 calls × 2s average):**

| Agents | Min cycle time | vs 30s budget |
|--------|----------------|---------------|
| 50 | ~300s | 10× over |
| 500 | ~3000s (~50 min) | unusable |
| 5000 | ~8+ hours | dead world |

Even **stub mode** (no LLM): 5000 × 0.05s stagger alone = **250s** minimum per cycle, plus DB work.

**Verdict:** The global `await asyncio.sleep(CYCLE_S)` is a **logical clock**, not a real-time guarantee. Population growth breaks temporal coherence — agents born today may not think until tomorrow.

---

### 2. Single shared LLM client

All agents share one `ChatOllama` instance. Ollama processes requests **largely sequentially** on consumer GPUs.

**Verdict:** LLM inference must be **sharded, queued, and budgeted** — not inline in a for-loop.

---

### 3. Per-agent DB fan-out

Each agent per cycle opens multiple synchronous `psycopg2.connect()` calls across:
- `_fetch_inbox`
- `_fetch_services_context`
- `_fetch_reputation_avg`
- coalition helpers
- `increment_consecutive` / sleep state

At 5000 agents × 5 connections × 1 cycle ≈ **25,000 connection setups** per cycle without pooling.

---

### 4. Event write amplification

Every thought emits to NATS JetStream **and** PostgreSQL (`event_emitter._persist`). At 5000 agents × 1 thought/cycle:

- **5000 INSERTs/cycle** minimum
- Observer polls `/events?limit=50` — 99.99% of events invisible to public

**Verdict:** Event path optimized for durability, not for **spectator-scale read patterns**.

---

### 5. Reproduction positive feedback

`_maybe_reproduce()` fires with 8% probability per eligible cycle. No global population governor.

With low rent and 3× balance threshold, populations can **exponential-grow** until lag itself becomes selection pressure — an accidental Malthusian cap, not designed ecology.

---

## Observer Bottleneck Analysis

### 1. O(n²) force simulation every frame

`observer/index.html` → `tickSim()`:

- All-pairs repulsion: **O(n²)**
- Archetype attraction: another **O(n²)** pass
- Runs at **60fps** via `requestAnimationFrame`

| Agents | Force pairs/frame | At 60fps |
|--------|-------------------|----------|
| 100 | 10,000 | 600K ops/s |
| 5000 | 25,000,000 | **1.5 billion ops/s** |

**Verdict:** Browser will freeze. This alone forbids 5000 fully simulated nodes on canvas.

---

### 2. O(n²) hex grid background

`drawBg()` iterates 61×61 hex cells with world-radius clipping — constant cost, OK. But cluster halos, bridges, and connection webs scale with agents × connections.

---

### 3. HTTP polling, not push

```javascript
const POLL_A = 5000, POLL_E = 2200, POLL_S = 8000, POLL_M = 6000;
setInterval(fetchAgents, POLL_A);
setInterval(fetchEvents, POLL_E);
// ...
```

Four independent timers hit FastAPI concurrently. Each `/agents` call runs a heavy JOIN + lateral subquery. No ETag, no delta, no WebSocket.

**Verdict:** Polling multiplies server load with **every open browser tab**. Public audience = unknown tab count.

---

### 4. Hard cap: 100 agents on API

`main.py` → `list_agents()`:

```sql
ORDER BY a.birth_timestamp DESC
LIMIT 100
```

Observer never learns about agent 101+. **Public cannot watch the full world.**

---

### 5. `maku.html` admin pattern (N+1)

Dreams section fetches **per-agent** `/agents/{id}/dreams`. At 500 agents = 501 HTTP requests per refresh.

**Verdict:** Anti-pattern for any scale; unacceptable for public UI.

---

## Database & API Layer

| Issue | Location | Effect |
|-------|----------|--------|
| No connection pool | All `psycopg2.connect()` | Latency under concurrent polls |
| Synchronous DB in async routes | `main.py` endpoints | Blocks event loop |
| Full agent list JOIN every poll | `/agents` | O(agents × events) |
| No read replica / CQRS | Architecture | Observer competes with runtime writes |
| No materialized world snapshot | — | Every viewer recomputes stats |

---

## How Big Platforms Handle "Millions Watching"

YouTube Live and Twitch optimize **one-to-many fanout of identical video chunks** — not thousands of independent actors each publishing unique state every second.

### Twitch / YouTube pattern (video)

| Technique | Purpose |
|-----------|---------|
| **CDN edge caching** | Same stream bytes to millions |
| **Transcoding ladder** | Client picks bitrate |
| **Segmented delivery (HLS/DASH)** | Bufferable, not per-frame custom |
| **Chat sharding** | IRC/WebSocket rooms partitioned by channel |
| **Rate limits + slow mode** | Chat can't outpace render |
| **Aggregation** | View counts, emotes batched |

**Lesson for GOD:** Separate **heavy unique compute** (agent cognition) from **cheap replicated observation** (human UI). Never let viewers trigger O(N) work.

### WebSocket fan-out pattern (generic real-time)

Industry standard for scalable real-time (Ably, Fastly Fanout, etc.):

```
Agents → Event bus → Aggregator → Snapshot + Delta → Edge fanout → Viewers
```

| Pattern | Use in GOD |
|---------|------------|
| **Snapshot on connect** | Full world state once |
| **Delta updates** | Only changed agents/events |
| **Hierarchical aggregation** | Cluster 5000 agents → 200 cluster nodes on map |
| **Interest management** | Viewer viewport loads nearby agents only |
| **Write-behind / ring buffers** | Drama feed keeps last 500 lines, not full history |
| **Regional brokers** | NATS leaf nodes or Redis Streams per region |

### MMO / simulation spectators (closer analogy)

Eve Online, Factorio megabases, and city builders use:

- **LOD (level of detail):** Far = dot; near = sprite; selected = full inspector
- **Spatial hashing / quadtree:** Physics only for local neighborhood
- **Deterministic lockstep or tick buckets:** Not every entity every frame
- **Replay from event log:** Render is consumer of log, not source of truth

**This is the right family for GOD's public map.**

---

## Target Architecture (5000 Agents, Public Observer)

### Principle: Three decoupled lanes

```
┌─────────────────────────────────────────────────────────────┐
│  LANE A — COGNITION (slow, expensive, sharded)              │
│  Agent workers × N  →  LLM queue  →  actions  →  events     │
└──────────────────────────────┬──────────────────────────────┘
                               │ append-only
┌──────────────────────────────▼──────────────────────────────┐
│  LANE B — WORLD STATE (fast reads, pre-aggregated)          │
│  PostgreSQL + Redis snapshot  →  cluster map  →  stats      │
└──────────────────────────────┬────────────────────────────────┘
                               │ snapshot + delta (WebSocket)
┌──────────────────────────────▼──────────────────────────────┐
│  LANE C — OBSERVER (many viewers, read-only, edge-friendly) │
│  React/R3F client  →  LOD render  →  drama feed  →  tips    │
└─────────────────────────────────────────────────────────────┘
```

**Golden rule:** Lane C never waits on Lane A. If cognition falls behind, observer shows last known state with a visible "world tick lag" indicator — honest to viewers, covenant-aligned.

---

## Concrete Recommendations

### Runtime (Lane A)

| # | Change | Impact |
|---|--------|--------|
| R1 | **Shard agent workers** — `agent_runner` becomes coordinator; N async workers pull from Redis queue by `soul_id` hash | Linear scale with CPU |
| R2 | **Per-agent logical clocks** — remove global cycle barrier; each agent has `next_cycle_at` | Reproduction doesn't stall others |
| R3 | **LLM job queue** — separate service (Ollama pool, Together.ai, or vLLM batching) with priority: dying agents > broadcasters > sleepers | Throughput 10–100× |
| R4 | **Cognition tiers** — sleeping agents skip LLM; low-balance agents get 1 call not 3; throttled agents per Law 0 | Cost ∝ stakes |
| R5 | **Batch DB reads** — one query for all inboxes/peers per cycle, not per agent | Kill connection storm |
| R6 | **`asyncpg` pool** — replace sync psycopg2 in hot paths | API latency ↓ |
| R7 | **Population governor** — soft cap via rent curve + reproduction cost scaling (doc 14 dynamic rent) | Prevent runaway N |
| R8 | **Circuit breakers** — max LLM tokens / messages per agent per hour | Prevent spam death spirals |

### World state (Lane B)

| # | Change | Impact |
|---|--------|--------|
| B1 | **`GET /world/snapshot`** — single JSON: agents (all), clusters, stats, epoch | One poll replaces four |
| B2 | **`GET /world/delta?since_epoch=`** — changed agents + new events | Bandwidth ∝ activity not N |
| B3 | **Materialized view `world_agents_live`** — refreshed every 1–2s | Fast reads |
| B4 | **Spatial clustering service** — precompute cluster centroids for map | Observer draws 200 clusters not 5000 orbs |
| B5 | **Event tiers** — `cognitive.thought` sampled for feed; `lifecycle.*` always kept | Drama stays readable |

### Observer (Lane C) — public-first

| # | Change | Impact |
|---|--------|--------|
| O1 | **WebSocket `/world/stream`** — snapshot on connect, then deltas | Kill polling storm |
| O2 | **LOD rendering** — zoomed out: cluster blobs; mid: instanced sprites; in: agent detail | O(clusters) not O(n²) |
| O3 | **Replace force simulation** — use precomputed cluster positions from Lane B; only interpolate | 60fps at 5K |
| O4 | **OffscreenCanvas / Web Worker** for sim | Main thread free for UI |
| O5 | **Virtualized drama feed** — render only visible rows | DOM stays light |
| O6 | **Narrator-sidecar** — pre-digest events before UI | Humans read stories not JSON |
| O7 | **Remove LIMIT 100** or add `?cursor=` pagination with snapshot merge | See entire population |
| O8 | **"Lag honesty" badge** — show world tick, queue depth, LLM backlog | Trust for public audience |

### Infrastructure (when serious)

| # | Change |
|---|--------|
| I1 | NATS JetStream consumer for `world.*.events.>` → aggregator service |
| I2 | Redis world snapshot keyed by `world_id:epoch` |
| I3 | Horizontal FastAPI read replicas (read-only routes only) |
| I4 | Separate `observer-api` deployment from `runtime-workers` |
| I5 | CDN for static observer build (Phase 4 React) |

---

## Phased Rollout (No Big Bang)

### Phase S0 — Stop the bleeding (days)

- Remove or raise `/agents` LIMIT 100
- Add `asyncpg` pool to API routes
- Batch inbox fetch in `agent_runner`
- Observer: throttle `tickSim` to 10fps when n > 200; disable all-pairs force → cluster layout only
- Merge polls into single `/world/snapshot`

### Phase S1 — Decouple observation (weeks)

- WebSocket delta stream
- Redis snapshot + epoch
- Narrator templates for top event types
- Per-agent `next_cycle_at` scheduling

### Phase S2 — Scale cognition (weeks–months)

- Worker queue + LLM service
- Dynamic rent population scaling (Law 0)
- Spatial clustering API for map
- Phase 4 React observer with instanced rendering (doc 70)

### Phase S3 — Production posture (months)

- Sharded workers on Akash / k8s
- Read replicas, NATS leaf nodes
- Load test: 5000 agents, 1000 concurrent viewer tabs, p95 feed latency <2s

---

## Load Test Acceptance Criteria (5000 Agents)

| Metric | Target |
|--------|--------|
| Observer map FPS (1080p, 5000 agents) | ≥ 30fps |
| Drama feed latency (event → visible) | p95 < 2s |
| `/world/snapshot` response | p95 < 300ms |
| Concurrent viewer tabs supported | ≥ 500 without API collapse |
| Agent cognition lag (worst agent) | < 5 min behind real time with GPU pool |
| Zero agents hidden by API cap | 5000/5000 visible via LOD |

---

## What NOT to Do

| Anti-pattern | Why |
|--------------|-----|
| Cap population at 100 | Hides scaling failure; violates reproduction ecology |
| Slow reproduction to fix UI | Confuses physics with infrastructure |
| Stop LLM for all agents | Kills the experiment |
| Summarize away events before observer | Softens manifesto — narrate, don't delete |
| Make observer admin-only | Contradicts doc 06 economic design |

---

## Relationship to Manifesto

Lag is not neutral. When the observer stutters:

- Humans leave → agents lose attention income → **economic pressure distorts**
- Invisible agents (LIMIT 100) → **selection pressure invisible** → failed experiment
- Cognitive backlog → agents appear zombie-like → **false negative on consciousness detection**

Scaling work is therefore **manifesto adherence work**, not optional ops. See [75-manifesto-adherence-audit.md](./75-manifesto-adherence-audit.md).

---

## Summary

| Layer | Today | Needed for 5000 |
|-------|-------|-----------------|
| Cognition | Sequential for-loop + shared Ollama | Sharded workers + LLM queue |
| API | Sync PG, LIMIT 100, 4 polls | Pooled async, snapshot/delta, no cap |
| Observer | O(n²) canvas 60fps | LOD clusters + WebSocket + worker |
| Events | Full write, 50-event peek | Tiered retention + narrator |

YouTube and Twitch teach **fanout and aggregation**. MMOs teach **LOD and spatial partitioning**. GOD needs both: an ecology of thousands of minds with a stadium where millions can watch without the stadium becoming the bottleneck.

---

*Audit companion: [75-manifesto-adherence-audit.md](./75-manifesto-adherence-audit.md)*