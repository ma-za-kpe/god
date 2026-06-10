# PR Field Test Protocol

> Coordinate scale testing and bug fixes between the **coding agent** and a **field operator** (Docker + Ollama) via GitHub PR comments on [PR #1](https://github.com/ma-za-kpe/god/pull/1).

---

## Roles

| Role | Who | Does |
|------|-----|------|
| **Agent** | Grok / PR babysitter | Implements fixes, pushes commits, posts `[AGENT-REQUEST]` then `[AGENT-READY]` |
| **Field operator** | Human with compute | **Waits** for `[AGENT-READY]`, then pulls, rebuilds Docker, runs tests, posts `[FIELD-*]` |

Both parties **always `git pull` on `feat/p0-manifesto-and-scaling` before acting.**

---

## WAIT GATE (mandatory — read first)

**The field operator must NOT rebuild Docker, restart services, or run requested tests until the agent posts `[AGENT-READY]` for that task.**

| Phase | Who | Action |
|-------|-----|--------|
| 1. Request | Agent | Posts `[AGENT-REQUEST] T-xxx` describing what to test **after** code lands |
| 2. Implement | Agent | Makes code changes, commits, pushes to `feat/p0-manifesto-and-scaling` |
| 3. Ready | Agent | Posts `[AGENT-READY] T-xxx @ <sha>` — **only then** may the operator act |
| 4. Execute | Operator | `git pull` → `docker compose build runtime` → `up` → run steps → `[FIELD-*]` |

**If you see `[AGENT-REQUEST]` without a matching `[AGENT-READY]` at the same or newer commit: wait.** Do not pull, rebuild, or report yet.

**Exception:** `[FIELD-READY]` (environment smoke check) and `[FIELD-DATA]` replies to a *previous* completed task do not require a new `[AGENT-READY]`.

Wrong order (do not do this):

```
[AGENT-REQUEST] T-5000-01 → operator immediately rebuilds  ❌
```

Correct order:

```
[AGENT-REQUEST] T-5000-01 — … — WAIT: do not rebuild until [AGENT-READY]
… agent pushes commits …
[AGENT-READY] T-5000-01 @ abc1234 — safe to pull, rebuild runtime, run steps
→ operator pulls @ abc1234, rebuilds, runs, posts [FIELD-PASS|FAIL|DATA]
```

---

## Comment Tags (required prefix)

Use the tag as the **first line** of every coordination comment.

| Tag | Author | Meaning |
|-----|--------|---------|
| `[AGENT-REQUEST]` | Agent | Announces upcoming work; **includes `WAIT: do not rebuild until [AGENT-READY]`** |
| `[AGENT-READY]` | Agent | Code pushed; operator may pull, rebuild Docker, and run the task (include `@ <sha>`) |
| `[AGENT-ACK]` | Agent | Acknowledges a field report; may include commit hash for the next cycle |
| `[FIELD-READY]` | Operator | Environment up, branch pulled, ready for tasks |
| `[FIELD-RUNNING]` | Operator | Test in progress (include start time + config) |
| `[FIELD-PASS]` | Operator | Test met acceptance criteria (attach metrics) |
| `[FIELD-FAIL]` | Operator | Test failed (attach logs, metrics, repro steps) |
| `[FIELD-BLOCKED]` | Operator | Cannot proceed (missing access, OOM, etc.) |
| `[FIELD-DATA]` | Operator | Raw artifacts only (JSON, log excerpts) — no verdict |

**Reply threading:** Quote the request comment URL or paste its tag + task ID when responding.

---

## Task ID Format

Agent requests use numbered tasks:

```
[AGENT-REQUEST] T-5000-01 — Short title
WAIT: do not rebuild until [AGENT-READY] T-5000-01 @ <sha>
```

When code is pushed:

```
[AGENT-READY] T-5000-01 @ abc1234 — safe to pull, rebuild runtime, run steps below
```

Operator responses reference the same ID:

```
[FIELD-PASS] T-5000-01 — ...
```

---

## 5000-Agent Test — Acceptance Criteria

From [doc 76](./76-agent-scaling-and-observer-performance.md) and P0/P1 implementation:

| # | Check | Pass threshold |
|---|-------|----------------|
| C1 | `GET /agents` count | Returns **5000** living agents (`AGENTS_MAX_LIMIT` ≥ 10000) |
| C2 | `GET /world/snapshot` latency | **p95 < 500ms** over 20 requests |
| C3 | Observer map FPS | **≥ 30fps** at 5000 agents (cluster layout >200) |
| C4 | WebSocket `/world/stream` | Connects, receives snapshot + deltas without disconnect |
| C5 | Drama feed lag | New events visible **< 2s** after emit (WS primary) |
| C6 | Runtime health | `GET /health` ok; no OOM restart in 10 min soak |
| C7 | Cognitive lag honesty | Report `due_count/total` from logs; document LLM mode |

**Phase A (required first):** `LLM_PROVIDER=stub` or Ollama stopped — proves **observation path** scales.  
**Phase B (if GPU allows):** Ollama with `LLM_CONCURRENCY=4` — report queue depth / cycle time.

---

## Operator Environment Checklist

**Run only after `[AGENT-READY] T-xxx @ <sha>` for the task you are executing.**

```bash
git checkout feat/p0-manifesto-and-scaling
git pull --rebase origin feat/p0-manifesto-and-scaling
git rev-parse --short HEAD   # must match [AGENT-READY] sha
docker compose build runtime
docker compose up -d
curl -s http://localhost:8000/health
```

Recommended `.env.local` overrides for scale test:

```env
AGENTS_MAX_LIMIT=10000
AGENT_CYCLE_SECONDS=30
SCHEDULER_TICK_S=1
LLM_CONCURRENCY=4
WS_SNAPSHOT_INTERVAL_S=30
AGENT_ENV_ROOT=/data/agent_env
```

---

## Bulk Population (5000 agents)

Genesis creates 8 elders only. Use bulk seed script:

```bash
docker compose exec runtime python /app/scripts/seed-bulk-agents.py --count 5000
# or from host:
python scripts/seed-bulk-agents.py --count 5000
```

Then verify:

```bash
curl -s http://localhost:8000/agents?limit=10000 | jq '.count'
```

---

## Metrics to Attach in `[FIELD-PASS]` / `[FIELD-FAIL]`

Copy-paste this block filled in:

```
Branch: feat/p0-manifesto-and-scaling @ <sha>
Agents living: 
LLM mode: stub | ollama (<model>)
Snapshot p95 ms: 
/agents ms: 
Observer FPS (5 min avg): 
WS: ok | fail
Runtime restarts: 
Docker mem peak: 
Notes:
```

Optional artifacts (paste or attach paths):

- `curl -s localhost:8000/stats | jq`
- `docker compose logs runtime --tail 50`
- Screenshot or screen recording of observer at 5000

---

## Hallucination Spot-Check (parallel track)

While scaling, spot-check 5 random `last_thought` values from `/agents`:

- Agent names must exist in the peer list
- No invented mechanics: tunnels, processing power, security scans, agent "prices"
- Report under `[FIELD-DATA] T-HALL-01` with agent names + thoughts

---

## Agent ↔ Operator Loop

```
Agent → [AGENT-REQUEST] T-xxx (WAIT: do not rebuild yet)
Agent → implements, pushes
Agent → [AGENT-READY] T-xxx @ <sha>
Operator → pull @ sha → rebuild runtime → run → [FIELD-PASS|FAIL|DATA] T-xxx
Agent → pull → [AGENT-ACK] T-xxx → next [AGENT-REQUEST] if needed
```

**Operator rule:** If the agent has not posted `[AGENT-READY]` with a commit SHA for your task, **stop and wait**. Rebuilding early wastes time and produces misleading `[FIELD-*]` reports.

Do not merge PR #1 until **T-5000-01 Phase A** passes and hallucination track has a plan.

---

## Links

- [Scaling audit](./76-agent-scaling-and-observer-performance.md)
- [Autonomy local](./77-agent-autonomy-local.md)
- [Ecology manifesto](./74-ecology-hardening-manifesto.md)