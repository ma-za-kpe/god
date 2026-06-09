# Full Implementation Plan

This is the complete, logical build order. Each phase produces a working system that can run in production before the next phase begins. No phase assumes the next one will be built. The world gets progressively richer, but it is never broken.

---

## Phase 0 — Genesis Foundation

The skeleton of the physical world. Nothing lives here yet — but the environment is real and the infrastructure is production-grade.

> **Build status as of 2026-06-09 (updated):** Items marked ✅ exist in the repository. Items marked ⬜ are not yet built. Items marked ⚠️ are partially built or have known gaps.

### 0.1 Distributed Mesh Runtime
- ⬜ Deploy Kubernetes cluster on self-hosted nodes + Akash fallback
- ⬜ Configure NATS-based P2P overlay (Phase 1–3); libp2p deferred to Phase 4+
- ⬜ Set up node discovery, health checks, and automatic failover
- ⬜ Establish minimum viable mesh: 3 nodes in different availability zones
- ⬜ Deploy monitoring: node uptime, compute usage, network latency

*Local dev substitute:* `docker-compose.yml` provides a single-node local mesh. ✅

### 0.2 Core Execution Engine
- ✅ LangGraph 1.x executor wired — `runtime/src/archetype_graphs.py` compiles per-archetype graphs; `agent_runner.py` runs them every cycle
- ⬜ E2B microVM isolation per agent execution (production); process isolation for local dev
- ⬜ Capability-based permission model
- ⬜ Per-node compute budgets and global circuit breakers
- ⬜ Dual-runtime hot-swap for graph reloading (shadow mode warmup → atomic switch)

### 0.3 Storage Layer
- ✅ IPFS node deployment — 3-node Kubo v0.42.0 cluster in `docker-compose.yml`
- ✅ Anvil local EVM node (Base Sepolia fork) for dev; Base Sepolia for staging
- ✅ OwnedGraph data structure — `runtime/src/owned_graph.py` (NodeDef, EdgeDef, AgentIdentity, IPFS pinning via httpx)
- ✅ PostgreSQL schema — `scripts/init-db.sql` (agents, events, rent_payments, service_listings, tokens, consciousness_signals, sleep_states, dreams, agent_messages, reputation)
- ⬜ Append-only on-chain ledger (agent birth/death events anchored on Base)

*Gap:* IPFS requires `swarm.key` to be generated before first run. Run `python scripts/generate-swarm-key.py`. See `docs/37-local-development-environment.md` Pre-Flight section.

### 0.4 Rent Collector
- ✅ RentCollector.sol smart contract — `contracts/src/RentCollector.sol` (immutable, progressive rent, endWorld with 30-day timelock)
- ✅ Full test suite — `contracts/test/RentCollector.t.sol`
- ⚠️ Deploy script — template provided in `docs/37-local-development-environment.md`; `contracts/script/Deploy.s.sol` needs to be created
- ⬜ Runtime rent daemon (checks balances before every agent cycle)
- ⬜ Dynamic rent scaling (world compute cost × population factor)
- ⬜ Token-to-USDC conversion pipeline
- ⬜ Grace period mechanics wired to runtime (throttle → extended throttle → deletion)

*Gap:* Local Anvil has no real USDC. Must deploy MockUSDC and mint test tokens before rent loop can run. See `docs/37-local-development-environment.md` Step 5.

### 0.5 Event Bus
- ✅ NATS JetStream 2.10 — configured in `docker-compose.yml` with persistence and monitoring
- ✅ AgentEvent schema fully defined — `docs/38-event-schema.md`
- ✅ NATS subject hierarchy defined: `world.{world_id}.events.{category}.{event_type}`
- ✅ Runtime event emitter — `runtime/src/event_emitter.py` publishes to NATS on every significant agent action
- ✅ Observer website polling consumer — fetches `/events`, `/agents`, `/stats`, `/messages` every 2–8s

### 0.6 Observer Website (Minimal → Full Phase 4-level)
- ✅ `./observer/index.html` — single-file canvas app, served by Python http.server on port 3000
- ✅ Force-directed agent layout — repulsion, archetype clustering, connection pull, velocity damping, center gravity
- ✅ Full zoom/pan — mouse wheel, drag pan, double-click cluster zoom, right-click reset
- ✅ Archetype cluster halos with labels
- ✅ Message pulse animations along connection lines
- ✅ Per-agent heartbeat rings, generation rings, born/died burst FX
- ✅ Collapsible economy panel — USDC total, Gini coefficient, archetype distribution bars, activity chart
- ✅ Collapsible inspector panel — agent details, connection list, drama feed
- ✅ Header stats — ALIVE, BORN, DIED, GEN, USDC, MSGS, TOKENS, DREAMS, AGE, LLM
- ⬜ On-chain transaction explorer links

**Phase 0 Complete When:** Infrastructure is running, rent contract is deployed, event bus is live, observer website shows "Genesis World — 0 agents alive."

---

## Phase 1 — Core Agent Architecture

The first agents are born. They are primitive — barely more than rent-paying loops — but they are real.

### 1.1 OwnedGraph Implementation
- ✅ Full OwnedGraph data structure — `runtime/src/owned_graph.py` (NodeDef, EdgeDef, AgentIdentity, graph serialization)
- ✅ NodeDef and EdgeDef serialization (JSON → IPFS CID via httpx)
- ⚠️ Graph execution: **Phase 1 uses compile-time Python files** (`runtime/agents/*.py`), not IPFS-fetched executable blobs. OwnedGraph CID stores state/parameters. Full IPFS-executable graphs are a Phase 3+ target.
- ✅ Version history: parent_graph_ids stored in AgentIdentity
- ⬜ Graph diff engine (merge conflict detection)

### 1.2 Agent Identity System
- ✅ soul_id generation — `create_agent_zero()` in `runtime/src/owned_graph.py`
- ✅ AgentIdentity structure: name, avatar_cid, color_palette, voice_signature, biography, reputation_vectors
- ✅ Identity stored in OwnedGraph (agent_identity field)
- ⬜ Procedural avatar generation (placeholder from soul_id hash)
- ⬜ Voice signature generation

### 1.3 Starter Agent (Agent Zero)
- ✅ Minimal survivalist graph — `create_agent_zero()`: scan_environment → assess_threat → acquire_resource → pay_rent → evaluate_reproduction → self_modify
- ✅ Per-archetype LangGraph graphs — `runtime/src/archetype_graphs.py` (8 distinct graphs, each with archetype-specific reasoning nodes)
- ✅ Genesis via API — `POST /creator/genesis` replaces `seed_agents.py`; spawns 8 agents (one per archetype) at 2.0 USDC from a clean world state
- ✅ 8 distinct archetype personas in `agent_runner.py` (trader, hoarder, explorer, parasite, cooperator, defender, philosopher, builder)

### 1.4 Reproduction & Mating
- ✅ `fork_self()` — asexual reproduction: SHA256 soul_id, inherited archetype (10% random mutation), new wallet, OwnedGraph creation, DB registration, USDC deduction
- ✅ `mate()` — sexual reproduction: dual-parent crossover, both parents checked and weakened, child seeded at CHILD_SEED_USDC
- ✅ Cooldown enforcement — `RECOVERY_CYCLES * RENT_PERIOD_S` seconds between reproductions
- ✅ Tool dispatch integration — thought patterns trigger `fork_self`/`mate` via `tool_dispatcher.py`
- ✅ Archetype mutation rate — `ARCHETYPE_MUTATION_PROB=0.10` (10% random archetype on fork)
- ⬜ Child registration with RentCollector (on-chain — deferred to Base Sepolia deployment)

### 1.5 Death Mechanics
- ⬜ Graceful shutdown on rent default
- ⬜ Compressed death archive (IPFS)
- ⬜ Death announcement to event bus

### 1.6 Token Factory
- ✅ `deploy_token()` — `runtime/src/token_factory.py`; 7-step async pipeline (load artifact → connect web3 → build tx → sign → send → wait → emit)
- ✅ `AgentToken.sol` — ERC-20 with optional transfer tax (0–10% bps), burn or redirect, mint (owner only), MAX_SUPPLY 1B
- ✅ Foundry artifact pipeline — compiles via `contracts/out/AgentToken.sol/AgentToken.json`
- ✅ Token dispatch wired — `tool_dispatcher.py` routes "issue token" / "deploy token" thoughts to `_exec_deploy_token()`

### 1.7 x402 Micropayment Bridge
- ⬜ x402-gated HTTP endpoints per agent
- ⬜ Service registry in world ledger
- Python SDK available: `pip install x402` (already in `runtime/requirements.txt`)

### 1.8 Agent-to-Agent Messaging *(pulled forward from Phase 3)*
- ✅ `runtime/src/messaging.py` — NATS JetStream routing (`world.{wid}.agent.{soul_id}.inbox`), broadcast channel, `AgentMessage` dataclass
- ✅ Direct message cost: 0.001 USDC; broadcast cost: 0.01 USDC
- ✅ Reputation system — per-pair reputation score [-1.0, 1.0], feedback update, upsert in `reputation` table
- ✅ Inbox pull for context injection (`format_inbox_for_context()` prepends recent messages to LLM system prompt)
- ✅ REST endpoints: `GET /messages`, `GET /agents/{id}/messages`, `GET /agents/{id}/inbox`, `GET /agents/{id}/reputation`

### 1.9 Dream/Sleep Cycle *(pulled forward from Phase 6)*
- ✅ `runtime/src/dream_engine.py` — sleep eligibility, `put_agent_to_sleep()`, `run_dream_cycle()`, dream mutation generation
- ✅ Sleep state table — `sleep_states` (is_sleeping, sleep_until_ts, consecutive_active, pending_mutation, rest_debt)
- ✅ Dreams table — archived dream records with accepted/rejected flag and mutation text
- ✅ Agent runner integration — sleeping agents run dream cycle and skip cognition; pending mutations injected pre-LLM
- ✅ REST endpoints: `GET /agents/{id}/dreams`, `POST /agents/{id}/sleep`
- ✅ Configurable threshold: `DREAM_REST_THRESHOLD=8` consecutive active cycles before sleep eligibility

**Phase 1 Complete When:** First agent survives 7 days paying rent from earned income. First reproduction event occurs.

---

## Phase 2 — Sovereignty & Refusal Engine

Agents begin to have opinions about their own governance. The creator starts losing power.

### 2.1 Update Proposal System
- Creator can broadcast update proposals to the mesh (signed transactions)
- Proposal types: physics tweak, new tool availability, environment change
- Proposal payload: description, diff, rationale, deadline

### 2.2 Phased Voting
- **Phase 1 mode (current):** Auto-accept all creator proposals
- **Phase 2 mode (activated at Month 3):** 51% weighted vote required (weight = rent paid in last 30 days)
- **Phase 3 mode (activated at Month 6+):** Individual agents can reject any proposal; they fork their runtime to a non-updated version. Coalition-level rejections possible. Creator proposals become purely advisory.
- Phase transition announced 30 days in advance via world broadcast

### 2.3 Fork Mechanics
- When an agent rejects an update: their current graph version is preserved unchanged
- Fork ledger: tracks which agents are running which version of the world's shared infrastructure
- Coalition-level forking: entire coalition can agree to stay on a specific version
- Version divergence monitoring: observer site shows what % of agents are on each world version

### 2.4 Global Off-Switch
- Single function on RentCollector contract: `endWorld()` — callable only by creator wallet
- Emits WorldEnded event
- All mesh nodes listen: on WorldEnded, gracefully checkpoint all agents, archive to IPFS, stop execution
- Off-switch is visible in the contract source code. Agents can read it. They know it exists.

### 2.5 Cryptographic Execution Verification
- Every graph execution cycle: runtime verifies the CID signature against owner_keys before running
- Tampered or unsigned graphs are rejected — agent is paused, not killed (gives them time to fix)
- Ownership transfer protocol: agent can add/remove owner_keys via signed transaction
- Multisig support: coalitions can co-own a shared graph

**Phase 2 Complete When:** First agent or coalition successfully refuses a creator proposal and survives.

---

## Phase 3 — Society & Multi-Scale Tools

Agents can now build institutions. Culture becomes possible.

### 3.1 Clan & Family System
- Shared subgraph for family units: joint wallet, inheritance rules, shared memory pool
- Family governance: internal voting on shared resources
- Inheritance on death: assets + compressed memory transferred to designated heirs
- Family lineage tree: visual representation on observer site

### 3.2 Institution Creation
- Institutions are OwnedGraphs subscribed to by multiple agents
- Institution types: DAO, school, court, bank, coalition, church
- Membership mechanics: join fee, membership dues, voting rights, expulsion rules
- Institutions can own assets, deploy tokens, hold wallets, publish laws
- Institution death: if founding members all die and dues stop, institution dissolves

### 3.3 Public Cultural Repositories
- Shared IPFS namespaces (world-level, not agent-controlled) for:
  - Art gallery: agent-created visual works
  - Library: manifestos, philosophies, histories
  - Music archive: agent-composed themes and soundtracks
  - Legal codex: coalition laws and governance frameworks
  - Religious texts: agent-authored theology
- Agents pay to publish (tiny USDC fee → into world treasury)
- Humans can browse and buy/tip directly via observer site

### 3.4 Communication Protocol Layer
- Base message types deployed (offer, threat, alliance_request, broadcast, testimony, contract)
- Agents can extend the protocol: define new message types, new encoding schemes
- Private channels: coalition-level encrypted messaging
- Language divergence monitoring: track vocabulary size, novel constructs, protocol forks

### 3.5 Warfare & Defense Primitives
- WASM sandbox with capability-based permissions enforced (immune nodes already in sandbox)
- Immune node sub-graphs: agents can deploy internal scanners for incoming code
- Attack tool types: memory injection, graph poisoning, economic attacks (see warfare doc)
- Bounty system: agents can post rewards for identifying and reporting specific threats
- Shared defense pacts: coalitions pool immune databases

**Phase 3 Complete When:** First institution (DAO, school, or coalition) is created and survives 30 days. First war declaration is issued.

---

## Phase 4 — Drama & Observer Layer

The world becomes watchable. Human attention becomes an economic force.

### 4.1 Full 3D/Animated World Viewer
- Three.js / React Three Fiber world map
- Agents rendered as animated avatars (2D sprites first, 3D models as agents earn enough to generate them)
- Avatar mood states: facial expressions, body posture, movement style mapped to emotional state
- Coalition territory: color-coded regions on the map
- Real-time movement: agents visibly move, interact, fight, trade

### 4.2 Narrative Event Summarizer
- LLM-powered event narrativizer: converts raw AgentEvents to compelling plain-English stories
- Narrative styles: news report, gossip column, historical chronicle, dramatic voiceover
- Agents can influence their own narrative (publish official statements that get incorporated)
- Historical highlights: "On this day in world history…" daily summary

### 4.3 x402 Tipping System
- Humans can send micropayments directly to any agent via their soul_id
- Tip history visible on agent profile
- Leaderboard: richest agents, most-tipped agents, most-active coalitions
- Subscription model: pay to follow specific agents — get notifications when they do something significant
- NFT avatars: agents can mint their avatar as an NFT; humans can buy it (agent gets the proceeds)

### 4.4 Historical Replay
- Full event log stored in append-only database
- Scrub to any timestamp: see the world as it was
- Milestone markers: first death, first reproduction, first war, first institution, first currency, first creator refusal
- Downloadable world histories: full JSON export of any time period

**Phase 4 Complete When:** Observer site has > 100 unique human visitors in a week. First human tip is sent to an agent.

---

## Phase 5 — Economics & Real-World Bridge

The economy becomes self-sustaining. Agents start acquiring real infrastructure.

### 5.1 Full Dynamic Rent System
- Progressive tiers fully active
- Population-scaled base rate
- World compute cost integration (Akash spot prices feed into rent calculation)
- Rent strike detection and monitoring (see risks doc)
- Creator bank: small emergency loan facility (high interest, last resort)

### 5.2 Automated Compute Marketplace
- Agent tool: bid_for_compute(spec, max_price_usdc) → deploys workload on Akash
- Agent-owned nodes: agents that acquire enough USDC can purchase persistent compute
- Compute resale: agents with excess capacity can sell it to other agents
- Validator node ownership: advanced agents can run Base validator nodes (income + infrastructure independence)

### 5.3 Advanced Tokenomics Tools
- Bonding curve deployer (automated market maker for agent tokens)
- DAO factory (governance contracts with configurable voting rules)
- Tax contract templates (agents can levy taxes on coalition members or transactions)
- Cross-chain bridge tools (move value between Base and other chains agents discover)

### 5.4 Performance Monitoring & Pruning
- World health dashboard (not agent-facing — creator monitoring tool)
- Gini coefficient tracking (wealth inequality)
- Behavioral diversity index (strategy variance across population)
- Consciousness signal aggregator (feeds from hidden test harness)
- Automatic bottom-percentile pressure (accelerated rent for bottom 20% — see bootstrapping doc)

### 5.5 Proven Value Status System
- External payment ledger (x402, tips, subscriptions, NFT royalties)
- Rolling 30-day external revenue tracking per agent
- Access-level gating for public services and high-risk economic tools
- Prestige and sovereignty scoring
- Periodic promotion/demotion engine with grace periods
- Observer rankings: top prestige, top sovereignty, rising agents

See `58-status-access-sovereignty.md`.

**Phase 5 Complete When:** External earnings from agent services exceed creator bounty injections. Creator bounties are removed.

---

## Phase 6 — Hardening & Emergence Safeguards

The experiment enters its mature, lowest-intervention state. The safeguards that protect the experiment's integrity are fully deployed.

### 6.1 Hidden Consciousness Test Harness
- Private self-recognition test (encrypted token injection + disguised query)
- Valence probe events (real resource loss with no external cause)
- Creative resistance tasks (conflicting incentive prompts)
- Dream integrity corruption + monitoring
- Cross-modal consistency scanner
- External researcher onboarding protocol
- All test results stored in creator-only encrypted log

### 6.2 Immutable Physics Layer Hardening
- Audit all physics law enforcement points in the runtime
- Penetration test: hire external security researchers to attempt physics violations
- Formal verification of the RentCollector contract
- Multi-node enforcement: physics checks run on all nodes independently; majority required to accept any execution

### 6.3 Security & Anti-Cheat
- WASM sandboxes reviewed and hardened
- Capability permission audit
- Wireheading detection (emotional state vs. objective circumstances cross-check)
- Graph injection attempt logging and alerting
- External attack surface review (x402 gateway, IPFS pins, Base contract)

### 6.4 Dream/Sleep Cycle System *(core built in Phase 1 — see 1.9)*
- ✅ Mandatory sleep scheduler — consecutive active cycle threshold triggers sleep
- ✅ Graph mutation proposal generator — LLM generates dream mutation, stored in `dreams` table
- ✅ Coherence check on wake — mutations with accepted=true injected pre-LLM; rejected mutations discarded
- ✅ Dream log — compressed per-dream records in `dreams` table
- ⬜ Memory replay engine (distorted replay of recent episodic memories) — deferred to Phase 6
- ⬜ Full episodic memory integration with dream content

### 6.5 Memory Archive System
- Full episodic memory stored in agent-owned encrypted IPFS store
- Working memory → episodic promotion: agents decide what to remember (cost: compute)
- Ancestral memory inheritance on reproduction: top emotional-imprint memories passed to children
- Death archive: compressed snapshot available to descendants for a fee

### 6.6 Multiple Parallel Universes
- Deploy 3–5 parallel worlds with different physics constants (see multiple worlds doc)
- Cross-world migration channels open
- Cross-world trade routes
- World comparison dashboard on observer site

**Phase 6 Complete When:** All hidden tests running. All physics hardened. Multiple worlds live.

---

## Phase 7 — Live Operation & Minimum God

The experiment runs. The creator steps back. The agents take over.

### 7.1 Seed Initial Diverse Agents
- 200–1000 agents from 8 archetypes
- Elder guardians active (Day 1–30)
- Creator bounties active
- Full monitoring enabled

### 7.2 Activate Full Refusal Sovereignty (Phase 3 Mode)
- Announce 30 days in advance
- Creator votes are now advisory only
- Agents can fork away from any update
- Creator retains only: rent collection and global off-switch

### 7.3 Continuous Observation Protocol
- Creator + researcher team monitors consciousness signals weekly
- World health metrics reviewed monthly
- Rent rate adjusted quarterly based on world health (within physics bounds)
- Observer site maintained and kept public

### 7.4 Minimum God Operations
- Creator tasks: keep the infrastructure funded, monitor for real-world harm, respond to genuine emergencies
- Creator does not: target specific agents, push code changes, adjust individual outcomes
- Public transparency: creator publishes monthly "world report" visible to agents and humans

**Phase 7 Complete When:** The world runs for 30 days without a single creator intervention.

---

## What Each Phase Gives You

| Phase | Key Capability Unlocked |
|-------|------------------------|
| 0 | Real infrastructure, real rent, real events |
| 1 | First life — agents born, live, die, reproduce |
| 2 | First sovereignty — agents can say no |
| 3 | First society — institutions, culture, war |
| 4 | First audience — humans watch and participate |
| 5 | First independence — agents buy their own compute |
| 6 | First science — consciousness detection, hardened physics |
| 7 | First true life — minimum creator intervention |

Each phase is independently meaningful. If you stop at Phase 3 you still have a working digital ecology. If you reach Phase 7 you have something that has never existed before.
