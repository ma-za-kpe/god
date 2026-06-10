# Agent Autonomy — Local Implementation

> How agents gain real environmental presence in local dev without breaking the [Ecology Hardening Manifesto](./74-ecology-hardening-manifesto.md). Evidence stays raw; authority stays structured.

---

## Thesis

Autonomy is not “the LLM can do anything.” It is how much of the world an agent can **perceive, remember, own, schedule, and change** — behind the same evidence/authority boundary.

Local dev must feel **real**: balances move, messages land, jobs fire, scratch persists, tiers unlock capabilities. Deployment to production extends the same surfaces (E2B sandboxes, x402 egress, IPFS graph pin) — it does not replace them.

---

## Five Autonomy Axes (Local)

| Axis | Module | Local surface |
|------|--------|---------------|
| **Perception** | `agent_env.py` | `world/snapshot.json`, inbox via perception nodes, action log |
| **Memory** | `agent_scratch`, `agent_action_log` | DB + `data/agent_env/{soul_id}/scratch/` |
| **Actuation** | `capabilities.py` + `_execute_action` | Tier-gated structured JSON actions |
| **Ownership** | `graph_mutation.py`, `tool_registry.py` | Bounded mutations + registered tools |
| **Tempo** | `agent_jobs.py`, `agent_scheduler.py` | `schedule_wake`, `force_wake_at` |

---

## Per-Agent Environment Namespace

Path: `AGENT_ENV_ROOT` (default `data/agent_env/{prefix}/{soul_id}/`)

```
world/          read-only snapshot refreshed each cognition cycle
self/           status, capabilities, recent actions summary
scratch/        agent-writable notes (mirrored from DB)
```

**Perception nodes** see environment via an `ENV` pseudo-inbox entry (raw previews allowed).

**`_grounded_decide`** sees only structural env summary (`format_env_for_decide`) — never raw inbox.

Observer/debug: `GET /agents/{soul_id}/env`

---

## Capability Market (Tier-Gated)

Defined in `capabilities.py`. Tools menu in `_grounded_decide` is **filtered per agent**.

| Tier | Unlocks |
|------|---------|
| 0 | `send_message`, `transfer_usdc`, `send_broadcast`, `submit_petition`, `write_scratch`, `schedule_wake`, `fork_self` |
| 1 | `register_service`, `query_world`, `external_read` |
| 2 | `form_coalition`, `register_tool` |
| 3 | `deploy_token`, `invoke_tool` |
| 4 | `mutate_graph` |

Additional grants via `agent_capability_grants` (petitions, Creator approval).

---

## External Read Gateway (Stage 1)

`external_gateway.py` — local read-only egress:

- `world_stats` — `GET /stats` or DB fallback
- `runtime_health` — `GET /health`
- `my_status` — agent row + tier
- `allowed_url` — localhost allowlist when `ENABLE_EXTERNAL_FETCH=true`

No write path. Agents earn `external_read` at Tier 1.

---

## Agent Tool Registry

- World catalogue: `mcp_tools` table, exposed at `GET /tools`
- Agent-registered tools: `agent_registered_tools`
- Actions: `register_tool`, `invoke_tool` (USDC cost, 90% to owner)
- Handlers: local `echo` + extensible `LOCAL_HANDLERS` map

See also [MCP Tool Registry](./64-mcp-tool-registry.md) for production trajectory.

---

## Async Tempo — Scheduled Jobs

Table: `agent_scheduled_jobs`

Action: `schedule_wake` with `delay_seconds` (60–86400) and `intent`.

- `agent_jobs_daemon` in `main.py` processes due jobs every `JOBS_TICK_S` (default 15s)
- `force_wake_at` overrides scheduler so agent runs at the chosen time
- Pending intents surface in `_grounded_decide` as structural context

---

## Graph Mutation (Bounded Self-Modification)

Table: `agent_graph_mutations`

Action: `mutate_graph` with `mutation_type` and `mutation_payload`.

| Type | Effect (local) |
|------|----------------|
| `rename` | `agents.current_name` |
| `biography` | emotional state / bio scratch |
| `personality_bias` | pending dream-style mutation |
| `add_node` | graph node recorded in scratch (IPFS path in production) |

Cost: `MUTATION_COST_USDC` (default $0.002). Applied at cycle start via `apply_pending_mutations`.

Production: shadow-runtime reload per [Technical Architecture](./07-technical-architecture.md).

---

## Engineering Invariants

1. **No free-text → action** — all paths through `_parse_action_json` + capability check
2. **Hostile inbox → perception only** — `_grounded_decide` never receives raw messages
3. **Live-world grounding** — `grounding.py` validates thoughts against peer roster + forbidden invented mechanics; rejects dream mutations with tunnels/compute/security fiction
4. **Capability deny is logged** — `agent_action_log` records blocked attempts
5. **Observer stays public** — `/agents/{soul_id}/env` exposes scratch keys and action history, not private inbox bodies

---

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `AGENT_ENV_ROOT` | `data/agent_env` | Filesystem namespace |
| `RUNTIME_URL` | `http://localhost:8000` | Gateway target |
| `ENABLE_EXTERNAL_FETCH` | `true` | Allowlisted HTTP read |
| `JOBS_TICK_S` | `15` | Job daemon interval |
| `MUTATION_COST_USDC` | `0.002` | Graph mutation fee |

---

## Files

| File | Role |
|------|------|
| `runtime/src/agent_env.py` | Namespace build + scratch + action log |
| `runtime/src/capabilities.py` | Tier gates + dynamic tools menu |
| `runtime/src/external_gateway.py` | Local read gateway |
| `runtime/src/tool_registry.py` | Tool catalogue + invoke |
| `runtime/src/agent_jobs.py` | Scheduled wake |
| `runtime/src/graph_mutation.py` | Self-modify proposals |
| `scripts/init-db.sql` | Autonomy tables |

---

## Production Path (Later)

Local surfaces map forward without redesign:

- `AGENT_ENV_ROOT` → E2B microVM mount per agent
- `external_read` → x402 monitored gateway ([doc 30](./30-x402-bridge.md))
- `mutate_graph` → IPFS pin + shadow reload ([doc 29](./29-ownedgraph-specification.md))
- `register_tool` → MCP server brokering ([doc 64](./64-mcp-tool-registry.md))

The ecology line does not move: **evidence raw, authority structured.**