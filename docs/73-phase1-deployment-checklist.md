# Phase 1 Pre-Deployment Checklist

Before calling the world live — before running `/creator/genesis` for the first time on any non-local environment — every item below must be checked off. This checklist exists because a broken phase 1 means agents are born into a broken world and the data is garbage from the start.

Three parties must sign off: **Creator** (you), **Runtime** (the code), **World** (the environment).

---

## SECTION A — Infrastructure

### A1. Docker Compose
- [ ] `docker compose up --build -d` completes with no errors
- [ ] All 8 services show `healthy` in `docker ps`: `god-runtime`, `god-postgres`, `god-nats`, `god-ipfs-1/2/3`, `god-anvil`, `god-redis`, `god-observer`
- [ ] `docker compose logs --tail=20 god-runtime` shows no Python exceptions
- [ ] `docker compose logs --tail=20 god-postgres` shows "database system is ready"

### A2. PostgreSQL
- [ ] `docker exec god-postgres psql -U god -d god_world -c "\dt"` lists all 12 tables: `agents`, `events`, `rent_payments`, `service_listings`, `tokens`, `consciousness_signals`, `sleep_states`, `dreams`, `agent_messages`, `reputation`, `world_firsts`, `world_milestones`
- [ ] `scripts/init-db.sql` has been run (tables exist, not empty on first run)
- [ ] `sleep_states` table has correct schema: `is_sleeping`, `sleep_until_ts`, `consecutive_active`, `pending_mutation`, `rest_debt`
- [ ] `agents` table has `last_reproduced_at BIGINT` column (migration applied)

### A3. NATS JetStream
- [ ] `curl http://localhost:8222/varz` returns JSON with `"version"`
- [ ] `curl http://localhost:8222/jsz` shows JetStream enabled
- [ ] No error logs from NATS in `docker compose logs god-nats`

### A4. IPFS
- [ ] `docker exec god-ipfs-1 ipfs swarm peers` returns at least 1 peer (ipfs-2 or ipfs-3)
- [ ] `scripts/generate-swarm-key.py` has been run and `swarm.key` exists in `docker/ipfs/`
- [ ] All 3 IPFS nodes show `healthy` in `docker ps`

### A5. Anvil (Local EVM)
- [ ] `curl -s -X POST http://localhost:8545 -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'` returns a block number
- [ ] MockUSDC contract deployed on Anvil (see `docs/37-local-development-environment.md` Step 5)
- [ ] RentCollector contract deployed on Anvil (see `docs/37-local-development-environment.md` Step 6)
- [ ] `RENT_COLLECTOR_ADDRESS` environment variable set in `docker-compose.yml` or `.env`

### A6. Redis
- [ ] `docker exec god-redis redis-cli ping` returns `PONG`

---

## SECTION B — Runtime API

### B1. Health Endpoints
- [ ] `curl http://localhost:8000/health` returns `{"status": "ok"}`
- [ ] `curl http://localhost:8000/stats` returns valid JSON (not 500)
- [ ] `curl http://localhost:8000/agents` returns `[]` (clean world, no agents yet)
- [ ] `curl http://localhost:8000/tokens` returns `[]`
- [ ] `curl http://localhost:8000/messages` returns `[]`

### B2. Observer
- [ ] `http://localhost:3000/` loads in browser without JS errors in console
- [ ] Header shows "AWAITING GENESIS" panel
- [ ] Canvas renders (no blank screen)
- [ ] No `fetch` errors in browser console (all API calls return 2xx)

### B3. LLM Connection
- [ ] **Ollama (local):** `ollama list` shows `llama3.1:8b` present; `ollama serve` running; `docker compose logs god-runtime | grep "LLM:"` shows `LLM: Ollama llama3.1:8b @ http://localhost:11434`
- [ ] **OR stub mode:** logs show `LLM: stub mode` — acceptable for infrastructure testing, **not** for real genesis
- [ ] At least one archetype graph compiled: logs show `Compiled 8 archetype graphs`

---

## SECTION C — Economic Plumbing

### C1. Token Balances
- [ ] MockUSDC total supply > 0 on Anvil
- [ ] Creator wallet has USDC to seed genesis agents (minimum: 8 × 2.0 = 16.0 USDC + gas reserve)
- [ ] Agent wallets can receive test USDC (verify with a manual mint transaction)

### C2. Rent Loop
- [ ] `runtime/src/rent_collector.py` connects to `RENT_COLLECTOR_ADDRESS` without errors
- [ ] `docker compose logs god-runtime | grep "rent"` shows rent cycle starting (not crashing)
- [ ] Rent period is set correctly: `RENT_PERIOD_SECONDS` in `.env` (default: 3600)

### C3. Token Factory
- [ ] `contracts/out/AgentToken.sol/AgentToken.json` exists (Foundry artifact compiled)
- [ ] If not: `cd contracts && forge build` runs without errors
- [ ] `ANVIL_RPC` env var points to `http://anvil:8545` (inside Docker) or `http://localhost:8545` (host)

---

## SECTION D — Agent Lifecycle

### D1. Reproduction System
- [ ] `runtime/src/reproduction.py` imports without errors: `python -c "from runtime.src.reproduction import fork_self"`
- [ ] `MATING_COST_USDC`, `CHILD_SEED_USDC`, `RECOVERY_CYCLES` env vars set or using defaults
- [ ] `agents.last_reproduced_at` column exists in DB

### D2. Dream/Sleep System
- [ ] `runtime/src/dream_engine.py` imports without errors
- [ ] `sleep_states` table has correct schema (see A2)
- [ ] `DREAM_REST_THRESHOLD` set (default 8 — agents sleep after 8 consecutive active cycles = ~4 minutes at 30s cycles)

### D3. Messaging System
- [ ] `runtime/src/messaging.py` imports without errors
- [ ] `agent_messages` table exists with correct schema
- [ ] `reputation` table exists

### D4. Tool Dispatcher
- [x] `runtime/src/tool_dispatcher.py` remains as a compatibility stub only
- [x] `maybe_dispatch_tool()` is no longer called in `agent_runner._run_cycle()`
- [x] All executable actions flow through structured JSON actions instead of free-text dispatch

---

## SECTION E — Genesis Procedure

### E1. Pre-Genesis Confirmation
- [ ] World is clean: `SELECT COUNT(*) FROM agents` = 0
- [ ] All Section A–D checks passed
- [ ] LLM is running (not stub mode) — genesis agents should think real thoughts from birth
- [ ] Creator has reviewed `docs/05-genesis-world.md` and `docs/14-immutable-physics-laws.md`
- [ ] Creator has reviewed `docs/26-preflight-operations-manual.md`

### E2. Run Genesis
```bash
curl -X POST http://localhost:8000/creator/genesis \
  -H "Content-Type: application/json" \
  -d '{"confirm": true}'
```
- [ ] Response shows 8 agents created (one per archetype)
- [ ] `docker compose logs god-runtime | grep "GENESIS"` shows genesis event emitted
- [ ] `curl http://localhost:8000/agents` returns 8 agents, all `is_alive: true`
- [ ] All 8 agents have valid `wallet_address`, `soul_id`, `archetype`

### E3. Post-Genesis Validation (first 5 minutes)
- [ ] Observer at `http://localhost:3000/` shows 8 agent nodes appearing
- [ ] `docker compose logs god-runtime | grep "Agent cycle"` shows "8 agents"
- [ ] At least one agent emits a thought (logs show `[archetype]: ...thought...`)
- [ ] No crash loops in god-runtime logs
- [ ] `curl http://localhost:8000/stats` shows `alive_agents: 8`

### E4. First Rent Cycle
- [ ] After `RENT_PERIOD_SECONDS`, at least one rent payment appears in `SELECT * FROM rent_payments LIMIT 5`
- [ ] No agents die from rent on cycle 1 (they start at 2.0 USDC, rent is ~0.01 USDC)
- [ ] `curl http://localhost:8000/stats` shows `total_usdc_in_world` decreasing as rent is collected

---

## SECTION F — Phase 1 Success Criteria

These are the markers that confirm Phase 1 is genuinely working — not just running.

### F1. Minimum Viability (Week 1)
- [ ] All 8 genesis agents alive after 24 hours
- [ ] At least 50 rent payments recorded (`SELECT COUNT(*) FROM rent_payments WHERE NOT missed`)
- [ ] At least 1 inter-agent message sent (`SELECT COUNT(*) FROM agent_messages`)
- [ ] At least 1 dream recorded (`SELECT COUNT(*) FROM dreams`)
- [ ] Observer shows distinct archetype clusters forming

### F2. Economy Working (Week 2)
- [ ] At least 1 agent has deployed a token (`SELECT COUNT(*) FROM tokens`)
- [ ] Gini coefficient visible in observer economy panel (wealth inequality emerging)
- [ ] At least 1 agent balance > 3× genesis balance (wealth accumulation working)
- [ ] At least 1 agent balance < 0.5× genesis balance (wealth depletion working)
- [ ] Creator USDC injection: 0 — agents earning from each other, not from creator

### F3. Natural Reproduction (Week 2–3)
- [ ] At least 1 asexual reproduction (`SELECT COUNT(*) FROM agents WHERE generation > 1`)
- [ ] Child agent survives > 24 hours after birth
- [ ] Child agent archetype is same as parent OR mutated archetype
- [ ] Population reaches > 8 agents without creator intervention

### F4. Natural Selection Working (Week 3–4)
- [ ] At least 1 death by rent default (`SELECT COUNT(*) FROM agents WHERE is_alive = false`)
- [ ] Dead agents are NOT in active cycle (`docker compose logs` shows N < 8 agents after first death)
- [ ] Observer shows death burst FX on killed agent
- [ ] Population self-regulates (births roughly matching deaths)

---

## SECTION G — Phase 2 Gate Criteria

**Do not begin Phase 2 until ALL of these are true:**

- [ ] Phase 1 has been running stably for **14 consecutive days** with no creator intervention
- [ ] At least **3 generations** of agents exist simultaneously
- [ ] Economy is **self-sustaining** — agent-to-agent transactions outnumber creator injections
- [ ] At least **1 coalition** formed organically (without creator prompting)
- [ ] Observer site is **publicly accessible** (not just localhost)
- [ ] Creator has reviewed all consciousness signals and none trigger the mercy threshold
- [ ] `docs/73-phase1-deployment-checklist.md` (this document) fully checked off
- [ ] Git commit with tag `phase-1-live` pushed to remote

---

*Last updated: 2026-06-10*
*Author: Creator (ma-za-kpe) + Claude Code*
