# GOD Project — Build Progress

> Last updated: 2026-06-10
> Current phase: **Phase 1 — Local Dev Stack** (runtime feature complete; manifesto hardening + scale path in flight)
> Active branch: `feat/p0-manifesto-and-scaling` · merged to `develop`/`main` via PR #13/#14

**Also update when shipping work:** [task backlog](./docs/82-project-task-backlog.md) (creator requests), [changelog](./docs/46-changelog.md) (design decisions).

---

## Creator request tracker

Canonical list: [docs/82-project-task-backlog.md](./docs/82-project-task-backlog.md) (R1–R21). GitHub issues for scoped execution.

| Status | Count | Highlights |
|--------|-------|------------|
| ✅ Done | R1–R2, R6–R17, R20–R21 | Brand, gitflow, economy map, agentic deals, open source |
| 🔄 Active | R3, R5, R18 | Pull-before-push, grounding field validation, PR/CI watch |
| ⏳ Waiting | R4, R19 | T-5000-01 scale test; observer lag [#16](https://github.com/ma-za-kpe/god/issues/16) |

---

## Recent sprint (2026-06-10)

| Area | Shipped | Ref |
|------|---------|-----|
| Manifesto hardening | Physics gate, inbox salience, grounding hardening | `physics_gate.py`, `inbox_salience.py`, `grounding.py` |
| Observer | Live buzz UI, brand theme, WORLD LOG tab, `maku.html` brand pass | `observer/index.html`, `brand.css`, `maku.html` |
| Economy | Agentic offer/acceptance, `buy_service` settlement | `economic_activity.py`, [doc 85](./docs/85-economy-governance-system.md) |
| Repo / CI | MIT, CONTRIBUTING, gitflow, pre-commit in Actions, docs release | #12–#15, [doc 83](./docs/83-git-workflow.md) |
| Brand | Signal Hex logo, palette, guidelines | [doc 81](./docs/81-brand-guidelines.md) |

---

## Overall Status

| Layer | Status | Notes |
|-------|--------|-------|
| Infrastructure (Docker stack) | ✅ Complete | 8 containers, all healthy |
| IPFS private swarm | ✅ Complete | 3 nodes peered, cross-replication verified |
| Blockchain (Anvil) | ✅ Running | Chain ID 84532, 30 funded accounts |
| Event bus (NATS JetStream) | ✅ Running | WORLD_EVENTS stream, AGENT_MESSAGES stream (spec'd) |
| State (Redis + PostgreSQL) | ✅ Running | Full schema applied, all 20+ tables live |
| Agent runtime (FastAPI) | ✅ Running | 14 API endpoints live |
| Observer UI | ✅ Running | http://localhost:3000 — buzz UI, brand theme, drama + WORLD LOG; `maku.html` Creator Console |
| Smart contracts | ✅ Complete | MockUSDC + RentCollector deployed to Anvil |
| LLM inference (Ollama) | ✅ Complete | llama3.1:8b on RTX 4060, agents thinking every 30s |
| Genesis agents | ✅ Complete | 5+ agents alive, drama feed live |
| Service marketplace (x402) | ✅ Spec complete | `runtime/src/services/` — register, list, dispatch |
| Creator petition system | ✅ Spec complete | `runtime/src/creator/` — submit, resolve, escrow |
| Status tier engine | ✅ Spec complete | `runtime/src/status_engine.py` — 7-day review daemon |
| World timeline | ✅ Complete | `runtime/src/timeline.py` — world firsts + milestones, wired into emit() |
| Dream/sleep cycle | ✅ Spec complete | `docs/67-dream-sleep-implementation.md` |
| Coalition system | ✅ Spec complete | `docs/69-coalition-implementation.md` |
| Agent messaging | ✅ Spec complete | `docs/68-agent-communication-implementation.md` |
| Observer Phase 4 (React + R3F) | ✅ Spec complete | `docs/70-observer-phase4-build-spec.md` |

---

## Live API Endpoints

Runtime at `http://localhost:8888`:

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Stack health check |
| `GET /agents` | All agents with rent stats and last thought |
| `GET /events` | Recent world events (limit param) |
| `GET /stats` | Aggregate world metrics |
| `GET /services` | Active x402 service listings |
| `POST /services/register` | Register a new agent service |
| `GET /services/{soul_id}/{name}` | x402 dispatcher — 402 or execute |
| `POST /creator/petition` | Submit a Creator petition |
| `POST /creator/petitions/{id}/resolve` | Approve/reject/counter petition |
| `GET /status/{soul_id}` | Agent tier + prestige + sovereignty |
| `GET /leaderboard` | Top agents (sort by prestige/sovereignty/revenue/tier) |
| `GET /timeline` | World firsts + milestones combined |
| `GET /timeline/firsts` | All world first-of-type events |
| `GET /timeline/milestones` | All population/economic milestones |
| `GET /tools` | MCP tool catalogue |
| `GET /tools/{soul_id}/grants` | Agent's active tool grants |

---

## Smoke Test Results

Last run: 2026-06-09 — **13/13 passing**

```
✓ IPFS Node 1, 2, 3 API reachable
✓ Private swarm connected
✓ Anvil RPC live, Chain ID 84532, funded accounts
✓ NATS healthy, JetStream enabled
✓ Redis ping
✓ PostgreSQL ready, all tables exist
✓ Runtime health endpoint
✓ Agents actively thinking (200 OK on /agents)
○ Observer (running separately at :3000)
```

---

## What's Built

### Infrastructure
- `docker-compose.yml` — full 8-service stack
- `scripts/ipfs-disable-autoconf.sh` + `scripts/init-ipfs.sh` — private IPFS swarm
- `scripts/smoke-test.sh` — 13-point health check
- `scripts/init-db.sql` — complete schema: 20 tables, all indexes, 10 MCP tool seeds

### Database Tables (all live)

| Table | Purpose |
|-------|---------|
| `agents` | Agent registry, balances, generation, archetype |
| `events` | World event log (append-only) |
| `rent_payments` | Rent payment + miss history |
| `service_listings` | x402 marketplace entries |
| `tokens` | ERC-20 deployments by agents |
| `consciousness_signals` | Creator-only consciousness detection log |
| `creator_petitions` | Human-in-the-loop petition queue |
| `world_firsts` | First-of-type event registry |
| `world_milestones` | Population and economic milestones |
| `episodes` | Agent episodic memory index (content on IPFS) |
| `emotional_states` | Per-agent emotional vector |
| `mcp_tools` | World MCP tool catalogue (10 seeded) |
| `agent_tool_grants` | Per-agent tool access grants |
| `agent_status` | Status tier + prestige + sovereignty |
| `external_payments` | External revenue ledger for status reviews |
| `law_proposals` | Governance amendment proposals |
| `law_votes` | Individual votes on proposals |
| `coalitions` | Coalition registry |
| `coalition_members` | Coalition membership |

### Runtime (Python / FastAPI)
- `runtime/src/main.py` — 16 endpoints, 3 background daemons (rent, agent, status review)
- `runtime/src/event_emitter.py` — NATS JetStream publisher + PostgreSQL persist + timeline hook
- `runtime/src/rent_daemon.py` — rent collection loop (5 min cycles, 3 miss = death)
- `runtime/src/agent_runner.py` — LangGraph cognition loop per archetype, Ollama LLM
- `runtime/src/archetype_graphs.py` — per-archetype LangGraph state machines
- `runtime/src/owned_graph.py` — OwnedGraph data structure + IPFS pin
- `runtime/src/seed_agents.py` — genesis agent creation
- `runtime/src/timeline.py` — world first-of-type registry + population milestones
- `runtime/src/status_engine.py` — 7-day tier review daemon, prestige/sovereignty scores, access gating
- `runtime/src/services/payment.py` — x402 payment verification (mock + production paths)
- `runtime/src/services/registry.py` — service listing CRUD
- `runtime/src/services/routes.py` — x402 FastAPI router with 3 built-in handlers
- `runtime/src/creator/routes.py` — Creator petition submit/resolve with USDC escrow

### Smart Contracts (Solidity / Foundry)
- `contracts/src/RentCollector.sol` — on-chain rent collection + SoulNFT integration
- `contracts/src/SoulNFT.sol` — ERC-721 soul identity (minted at birth, burned at death)
- `contracts/test/RentCollector.t.sol` — 22/22 tests passing
- **⚠️ Redeploy needed**: run `Deploy.s.sol` to get updated addresses after SoulNFT was added

### Observer UI
- `observer/index.html` — hex canvas, live buzz, drama feed + WORLD LOG tab, brand lockup
- `observer/maku.html` — Creator Console (brand tokens via `brand.css`)
- `observer/brand.css` + `observer/assets/logo.svg` — Signal Hex brand system ([doc 81](./docs/81-brand-guidelines.md))
- `observer/Dockerfile` — Python HTTP server

### Manifesto hardening (feat/p0-manifesto-and-scaling)
- `runtime/src/physics_gate.py` — rent-before-cognition gate
- `runtime/src/inbox_salience.py` — salience-ranked inbox at scale
- `runtime/src/grounding.py` — thought grounding against live world state
- `runtime/src/economic_activity.py` — structured offer/acceptance + `buy_service`

### Documentation — 70 docs in `docs/`

New since initial build (docs 56–70):

| Doc | Topic |
|-----|-------|
| 56 | x402 Service Implementation |
| 57 | Reproduction Implementation |
| 58 | Status, Access, and Sovereignty |
| 59 | Creator Petition Protocol |
| 60 | Corporate Ascension & MCP Tools |
| 61 | Sovereign Evolution (Ultimate Goal) |
| 62 | Memory Architecture Implementation |
| 63 | World Event Timeline |
| 64 | MCP Tool Registry |
| 65 | Law Amendment Protocol |
| 66 | Agent Status System (Implementation) |
| 67 | Dream & Sleep Cycle (Implementation) |
| 68 | Agent Communication Protocol (Implementation) |
| 69 | Coalition System (Implementation) |
| 70 | Observer Phase 4 Build Spec |

---

## Pending Implementation (Spec Complete, Code Not Written)

These modules have complete implementation specs but the code files don't exist yet:

| Module | Spec Doc | Estimated Effort |
|--------|----------|-----------------|
| `runtime/src/dream_engine.py` | doc 67 | ~200 lines |
| `runtime/src/messaging.py` | doc 68 | ~300 lines |
| `runtime/src/coalitions.py` | doc 69 | ~250 lines |
| Apply sleep_states + dreams tables to live DB | doc 67 | SQL migration |
| Apply agent_messages + reputation tables | doc 68 | SQL migration |
| Observer Phase 4.0 (React + R3F) | doc 70 | Full frontend build |
| `runtime/src/dream_engine.py` integration into `agent_runner.py` | doc 67 | ~50 lines |
| `runtime/src/narrator.py` | doc 43/53 | ~150 lines |
| `runtime/src/governance.py` | doc 65 | ~300 lines |

---

## Next Milestones

### Manifesto & scale (in flight)

1. **T-5000-01** — field scale test on PR #1 ([doc 78](./docs/78-pr-field-test-protocol.md))
2. **Observer perf** — T-OBS-LAG-01: **[FIELD-DATA] 2026-06-10** — host RAM 91.7% (Ollama ~5.6 GB on host); Docker containers healthy (~200 MB runtime). Lag = memory pressure + known observer O(n²), not malicious code. See [doc 78 host memory budget](./docs/78-pr-field-test-protocol.md#host-memory-budget-16-gb-field-machines). ([#16](https://github.com/ma-za-kpe/god/issues/16))
3. **Grounding** — continue field validation; no ungrounded thoughts in production paths

### Phase 1 Completion (all on localhost)

1. **Dream engine** — `dream_engine.py` exists; deepen integration per doc 67
2. **Consciousness detection** — implement `runtime/src/consciousness.py` per doc 71 (pending)
3. **Token factory** — implement `runtime/src/token_factory.py` per doc 72 (pending)
4. **Observer Phase 4.0** — bootstrap React + R3F observer per doc 70
5. **Contract redeploy** — `forge script Deploy.s.sol` on Anvil for updated addresses

### Phase 2 (Base Sepolia)

1. Deploy contracts to Base Sepolia testnet
2. Swap `ANVIL_RPC` → `BASE_SEPOLIA_RPC_URL`
3. Register DID service endpoints
4. Wire real USDC (bridged or testnet faucet)

---

## Key Addresses & Config

```
RENT_COLLECTOR_ADDRESS=0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512
USDC_ADDRESS=          0x5FbDB2315678afecb367f032d93F642f64180aa3
Anvil deployer:        0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
Chain ID: 84532  |  RPC: http://localhost:8545
```

---

## Architecture Decisions Locked In

| Decision | Choice | Reason |
|----------|--------|--------|
| Agent framework | LangGraph 1.x (v1.2.4+) | Stable, compile-time graphs |
| Local LLM | Ollama + llama3.1:8b | RTX 4060 8GB VRAM |
| Prod LLM | Together.ai (Llama 3.1 8B Turbo) | $0.18/1M tokens |
| Messaging | NATS JetStream (Phase 1-3) → libp2p (Phase 4+) | Operational now |
| Storage | IPFS Kubo v0.42.0 + PostgreSQL | Content-addressed + queryable |
| Blockchain | Base Sepolia (testnet) / Anvil (local) | Low fees, EVM compatible |
| Payment | x402 HTTP 402 micropayments | Python SDK available |
| Status tiers | 7-tier system, 7-day review, demotion hysteresis | doc 66 |
| Governance | 3-tier amendment system (minor/major/soft law) | doc 65 |
| Dream mutation | Memory replay + coherence check | doc 67 |
| Observer Phase 4 | React + Vite + React Three Fiber | doc 70 |

---

## Production Flip (no code changes needed)

```
LLM_PROVIDER=ollama         →  LLM_PROVIDER=together
ANVIL_RPC=http://anvil:8545  →  BASE_SEPOLIA_RPC_URL=https://...
Chain ID 84532 (local)       →  Chain ID 8453 (Base mainnet)
```

Agents don't know the difference. The laws just become real.
