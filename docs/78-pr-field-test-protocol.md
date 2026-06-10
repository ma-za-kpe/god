# PR Field Test Protocol

> Coordinate scale testing and bug fixes between the **coding agent** and a **field operator** (Docker + Ollama) via GitHub PR comments on [PR #1](https://github.com/ma-za-kpe/god/pull/1).

---

## Roles

| Role | Who | Does |
|------|-----|------|
| **Agent** | Grok / PR babysitter | Implements fixes, pushes commits, posts `[AGENT-REQUEST]` |
| **Field operator** | Human with compute | Runs Docker, Ollama, load tests, posts `[FIELD-*]` replies |

Both parties **always `git pull` on `feat/p0-manifesto-and-scaling` before acting.**

---

## Comment Tags (required prefix)

Use the tag as the **first line** of every coordination comment.

| Tag | Author | Meaning |
|-----|--------|---------|
| `[AGENT-REQUEST]` | Agent | Asks operator to run a specific test or gather data |
| `[AGENT-ACK]` | Agent | Acknowledges a field report; may include commit hash |
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

```bash
git checkout feat/p0-manifesto-and-scaling
git pull --rebase origin feat/p0-manifesto-and-scaling
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
Agent pushes fix → [AGENT-REQUEST] T-xxx
Operator pulls → runs test → [FIELD-PASS|FAIL] T-xxx
Agent pulls → reads comment → implements → [AGENT-ACK] + new request
```

Do not merge PR #1 until **T-5000-01 Phase A** passes and hallucination track has a plan.

---

## Links

- [Scaling audit](./76-agent-scaling-and-observer-performance.md)
- [Autonomy local](./77-agent-autonomy-local.md)
- [Ecology manifesto](./74-ecology-hardening-manifesto.md)