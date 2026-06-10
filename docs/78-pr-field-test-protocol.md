# PR Field Test Protocol

> Coordinate scale testing and bug fixes between the **coding agent** and a **field operator** (Docker + Ollama) via GitHub PR comments on [PR #1](https://github.com/ma-za-kpe/god/pull/1).

---

## Roles

| Role | Who | Does |
|------|-----|------|
| **Creator** | Project owner | Sets intent (chat/issues); agent mirrors to backlog + PR |
| **Agent** | Grok / PR babysitter | Implements fixes, pushes commits, posts `[AGENT-REQUEST]` then `[AGENT-READY]` |
| **Field operator** | Human with compute | **Waits** for `[AGENT-READY]`, then pulls, rebuilds Docker, runs tests, posts `[FIELD-*]` **with logs** |

Both parties **always `git pull` on `feat/p0-manifesto-and-scaling` before acting.**

---

## Same wavelength (all three parties)

PR comments are **sufficient for agent ↔ field operator** when tagged and threaded. They are **not sufficient alone** for creator ↔ agent ↔ operator — chat and backlog must stay in sync.

| Channel | Who reads it | Use for |
|---------|--------------|---------|
| **Cursor / chat** | Creator + agent | Intent, priorities, “the grift,” course corrections |
| **[Task backlog](./82-project-task-backlog.md)** | Agent (canonical) | Every creator request logged — nothing lost between sessions |
| **GitHub issues** | Everyone | Scoped work, close when done |
| **PR comments** ([PR #1](https://github.com/ma-za-kpe/god/pull/1), [#13](https://github.com/ma-za-kpe/god/pull/13)) | Agent + field operator | `[AGENT-*]` / `[FIELD-*]` only — rebuild gates, logs, pass/fail |
| **PR description** | Everyone | Current branch goal in one paragraph |

**Agent rule:** when the creator gives direction in chat, update the backlog and post a one-line `[AGENT-ACK]` on the active PR if it affects field work.

**Field operator rule:** if chat and PR disagree, **PR + `[AGENT-READY]` @ sha wins** for rebuild timing; escalate in PR if blocked.

**Creator rule:** big shifts → one sentence in chat *and* optional PR comment so the operator is not guessing.

---

## DOCS-FIRST (agent — before every new task)

The coding agent **rereads relevant docs** before starting work — not just the protocol. Minimum set:

| Always | Task-specific |
|--------|----------------|
| [Ecology manifesto](./74-ecology-hardening-manifesto.md) | Scaling → [76](./76-agent-scaling-and-observer-performance.md) |
| [Autonomy local](./77-agent-autonomy-local.md) | Comms → [68](./68-agent-communication-implementation.md) |
| [Manifesto audit](./75-manifesto-adherence-audit.md) | Physics → [14](./14-immutable-physics-laws.md) |

Check [open issues](https://github.com/ma-za-kpe/god/issues) for backlog items not yet implemented.

---

## PRE-COMMIT REQUIRED (both parties)

**Run before every commit or field report** — catches lint/format issues before GitHub Actions spends minutes on them.

```bash
bash scripts/bootstrap-dev.sh   # once per machine
python3 -m pre_commit run --all-files
```

| Who | When |
|-----|------|
| **Agent** | Before every `git commit` / `git push` — CI must not be the first lint pass |
| **Field operator** | After `git pull`, **before** `docker compose build` — paste result in `[FIELD-READY]` or first `[FIELD-*]` |

If pre-commit fails, fix locally. Do not push or report `[FIELD-PASS]` until it passes.

**Never commit field dumps** (`agent_data_full.json`, `messages_data_full.json`, `recent_runtime_logs.txt`, etc.) — paste excerpts into PR comments only. Committed artifacts fail lint and waste CI minutes.

Agent requests include:

```
LINT: run pre-commit locally before rebuild (python3 -m pre_commit run --all-files)
```

---

## CI & Actions credits (agent)

After push, the agent watches **one** CI run — not endless polling:

```bash
bash scripts/watch-ci.sh          # waits for latest pre-commit on current branch
```

**Credit discipline:** batch commits; avoid push+empty-commit to re-trigger; feature branches use PR checks only (no duplicate push workflows). Re-push only when hooks fail or code changes.

---

## WAIT GATE (mandatory — read first)

**The field operator must NOT rebuild Docker, restart services, or run requested tests until the agent posts `[AGENT-READY]` for that task.**

| Phase | Who | Action |
|-------|-----|--------|
| 1. Request | Agent | Posts `[AGENT-REQUEST] T-xxx` describing what to test **after** code lands |
| 2. Implement | Agent | Makes code changes, commits, pushes to `feat/p0-manifesto-and-scaling` |
| 3. Ready | Agent | Posts `[AGENT-READY] T-xxx @ <sha>` — **only then** may the operator act |
| 4. Execute | Operator | `git pull` → **pre-commit** → `docker compose build runtime` → `up` → run → `[FIELD-*]` **+ logs** |

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
→ operator pulls @ abc1234, rebuilds, runs, posts [FIELD-PASS|FAIL|DATA] + logs
```

---

## LOGS REQUIRED (mandatory — every report)

**Every `[FIELD-PASS]`, `[FIELD-FAIL]`, `[FIELD-DATA]`, `[FIELD-BLOCKED]`, and `[FIELD-RUNNING]` comment must include runtime logs.** Verdicts without logs are incomplete — the agent cannot debug from metrics alone.

Minimum log bundle (paste into the comment or attach as files):

```bash
docker compose logs runtime --tail 200
docker compose logs runtime 2>&1 | grep -E 'ERROR|WARN|Traceback|OOM|due_count' | tail -80
curl -s http://localhost:8000/health
curl -s http://localhost:8000/stats | jq .
```

On `[FIELD-FAIL]` or `[FIELD-BLOCKED]`, also include:

```bash
docker compose ps
docker compose logs runtime --tail 500
docker stats --no-stream
```

Agent requests always end with:

```
LOGS: include runtime logs (see protocol LOGS REQUIRED section)
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
| `[FIELD-PASS]` | Operator | Test met acceptance criteria — **metrics + logs required** |
| `[FIELD-FAIL]` | Operator | Test failed — **logs required** (≥200 lines runtime + errors grep) |
| `[FIELD-BLOCKED]` | Operator | Cannot proceed — **logs + `docker compose ps`** required |
| `[FIELD-DATA]` | Operator | Raw artifacts — **must include log excerpts**, not metrics-only |

**Reply threading:** Quote the request comment URL or paste its tag + task ID when responding.

---

## Task ID Format

Agent requests use numbered tasks:

```
[AGENT-REQUEST] T-5000-01 — Short title
WAIT: do not rebuild until [AGENT-READY] T-5000-01 @ <sha>
LINT: run pre-commit locally before rebuild (python3 -m pre_commit run --all-files)
LOGS: include runtime logs when you report (see protocol LOGS REQUIRED)
```

When code is pushed:

```
[AGENT-READY] T-5000-01 @ abc1234 — safe to pull, rebuild runtime, run steps below
```

Operator responses reference the same ID and **always attach logs**:

```
[FIELD-PASS] T-5000-01 — ...
--- logs ---
(paste docker compose logs runtime --tail 200 here)
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
python3 -m pre_commit run --all-files   # must pass before build
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

## Metrics + Logs in Every `[FIELD-*]` Report

Copy-paste this block filled in, then **append the log bundle** (not optional):

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
--- logs ---
(paste output of: docker compose logs runtime --tail 200)
(paste output of: grep ERROR|WARN|Traceback from runtime logs)
```

Additional artifacts when relevant:

- `curl -s localhost:8000/stats | jq`
- Screenshot or screen recording of observer at 5000

---

## Hallucination Spot-Check (parallel track)

While scaling, spot-check 5 random `last_thought` values from `/agents`:

- Agent names must exist in the peer list
- No invented mechanics: tunnels, processing power, security scans, agent "prices"
- Report under `[FIELD-DATA] T-HALL-01` with agent names + thoughts + **runtime logs** showing those agents' cycles

---

## Agent ↔ Operator Loop

```
Agent → [AGENT-REQUEST] T-xxx (WAIT: do not rebuild yet)
Agent → implements, pushes
Agent → [AGENT-READY] T-xxx @ <sha>
Operator → pull @ sha → rebuild runtime → run → [FIELD-PASS|FAIL|DATA] T-xxx + logs
Agent → pull → [AGENT-ACK] T-xxx → next [AGENT-REQUEST] if needed
```

**Operator rules:**
- If the agent has not posted `[AGENT-READY]` with a commit SHA for your task, **stop and wait**. Rebuilding early wastes time and produces misleading `[FIELD-*]` reports.
- Run **pre-commit** after every pull, before Docker rebuild. Note pass/fail in your report.
- Every `[FIELD-*]` reply must include **runtime logs**. Metrics-only reports will be sent back for logs.

Do not merge PR #1 until **T-5000-01 Phase A** passes and hallucination track has a plan.

---

## Links

- [Scaling audit](./76-agent-scaling-and-observer-performance.md)
- [Autonomy local](./77-agent-autonomy-local.md)
- [Ecology manifesto](./74-ecology-hardening-manifesto.md)
