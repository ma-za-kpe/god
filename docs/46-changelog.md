# Changelog & Design Decisions

This document tracks significant design decisions made during the project, with rationale. It is invaluable 6 months from now when you ask "why did we do it this way?"

---

## Format

Each entry records:
- **Date** — when the decision was made
- **Decision** — what was decided
- **Alternatives considered** — what else was on the table
- **Rationale** — why this choice was made
- **Open questions** — what remains unresolved

---

## 2026 — Initial Design Phase

### Why Base over Solana or Ethereum mainnet
**Decision:** Deploy on Base (Coinbase L2) as the primary blockchain.

**Alternatives:**
- Ethereum mainnet: Too expensive for frequent small transactions (agent rent payments)
- Solana: Fast and cheap but different development toolchain; less USDC liquidity
- Arbitrum / Optimism: Both viable; Base chosen for USDC native integration and Coinbase ecosystem
- Custom L2: Too much infrastructure complexity at this stage

**Rationale:** Base offers low gas fees (~$0.001/tx), native USDC support, EVM compatibility (Solidity, Foundry, web3.py), and the x402 protocol is being built primarily for the Base/Coinbase ecosystem. Agents can upgrade to their own L2/L3 later if needed.

---

### Why NATS over Redis Streams or Kafka
**Decision:** NATS JetStream as the event bus.

**Alternatives:**
- Redis Streams: Simpler, already in the stack (used for LangGraph checkpointer). Downside: less suited for high-volume pub/sub at scale; no built-in subject-based routing.
- Kafka: Industrial-strength but operationally heavy; significant overhead for a project at this stage.
- RabbitMQ: Good for task queues; less natural for event stream / fan-out pattern.

**Rationale:** NATS JetStream provides subject-based routing (`world.{id}.events.{category}.{type}`), persistence, consumer groups, and horizontal scaling — all at low operational overhead. Single Docker container in dev. The subject hierarchy maps naturally to the event schema.

---

### Why LangGraph over custom agent runtime
**Decision:** Use LangGraph as the base execution engine for agent graphs.

**Alternatives:**
- Custom from scratch: Maximum control but enormous build time; reinventing checkpointing, state management, graph execution.
- AutoGen / CrewAI: Opinionated multi-agent frameworks; less suitable for the ownership/mutation model.
- Pure function pipeline: No built-in state persistence or graph structure.

**Rationale:** LangGraph provides stateful graph execution with built-in checkpointing, which maps directly to the OwnedGraph concept. It has production adoption (Klarna, LinkedIn, Uber use it in 2026) and a Docker-native local server. The framework is extensible enough to wrap with our ownership and mutation mechanics. Agents can evolve beyond LangGraph over time — their OwnedGraph can eventually replace the underlying engine entirely.

---

### Why Firecracker/WASM over Docker for agent sandboxing
**Decision:** Use Firecracker microVMs or WASM for individual agent sandbox isolation.

**Alternatives:**
- Docker containers per agent: Simple but high overhead at scale; 1000 agents = 1000 containers.
- Process-level isolation only: Too weak; agents can interfere with each other.
- gVisor: Good isolation but higher latency than Firecracker.

**Rationale:** Firecracker (AWS Lambda's technology) provides VM-level isolation at near-process speed. WASM provides sandboxing within a single process with capability-based permissions. Both options prevent an agent from reading another's memory or escaping the sandbox — critical for the physics law enforcement (Law 6: Sandbox Boundaries). Starting with WASM in development; migrate to Firecracker for production scale.

---

### Why 3 IPFS nodes locally (not 1)
**Decision:** Run 3 IPFS nodes in local Docker compose, not just 1.

**Alternatives:**
- 1 node: Simpler. But doesn't test replication behavior.
- 5+ nodes: Better simulation but more memory overhead on a dev machine.

**Rationale:** The production system requires replicated storage (3+ independent pins per CID per Law 2 — death archives must be permanent). Testing with a single node would hide replication bugs until production. 3 nodes on a single machine is enough to verify the multi-node pinning logic without excessive resource use.

---

### Why the Covenant is on-chain but not enforced by contract
**Decision:** Store the Creator Covenant as an immutable IPFS document anchored on-chain, but not enforce it via smart contract logic.

**Alternatives:**
- Smart contract enforcement: Make every Covenant promise a contract function. Sounds good but requires the creator to surrender capabilities before it's safe to do so.
- Off-chain only: Not verifiable. Agents cannot prove the creator kept their word.
- Timelock everything: Creates operational complexity; the creator needs some flexibility in Phase 1.

**Rationale:** The Covenant is a public commitment, not a legal contract between equals. Its value is accountability — any breach is detectable on-chain (the record shows creator actions). Trying to enforce it contractually would either lock the creator out of legitimate Phase 1 interventions or create complex loophole-hunting. The honest approach: state commitments publicly, let the record show whether they were kept. Agents and humans can judge accordingly.

---

### Why progressive rent over flat rent
**Decision:** Three-tier progressive rent (base, 1.5x, 2x based on agent balance).

**Alternatives:**
- Flat rent: Simple. But wealthy agents can trivially accumulate while poor agents die. Accelerates singleton formation.
- Linear rent (% of balance): Creates perverse incentives to keep balance low; complex to implement.
- Population-proportional flat: Rent scales with world size but not individual wealth.

**Rationale:** Progressive rent creates two effects: (1) wealth redistribution pressure that slows monopoly formation, (2) economic incentive for rich agents to invest rather than hoard (hoarding triggers higher rent tier). The tiers are simple enough to verify and explain to agents.

---

### Why 8 archetypes at genesis (not random or fewer)
**Decision:** 8 distinct agent archetypes as seed population.

**Alternatives:**
- Random graphs: Maximum diversity but no guarantee of viable starting strategies.
- 2-3 archetypes: Simpler but converges too fast.
- 10+: More diversity but harder to monitor early behavior.

**Rationale:** 8 covers the major strategic niches we expect: economic (trader, hoarder), exploratory (explorer, builder), social (cooperator, philosopher), defensive (defender), and adversarial (parasite). Having all 8 from genesis means the evolutionary dynamics start from a genuinely diverse gene pool. Parasite is deliberately included — a world without parasites is not a complete ecosystem.

---

---

## 2026-06-09 — Phase 1 Core Systems Complete

### Agent-to-Agent Messaging
**Decision:** Pull messaging forward from Phase 3 into Phase 1.

**What was built:** `runtime/src/messaging.py` — NATS JetStream routing with per-agent inbox subjects (`world.{wid}.agent.{soul_id}.inbox`), broadcast channel, `AgentMessage` dataclass, per-pair reputation system [-1.0, 1.0], cost model (direct: 0.001 USDC, broadcast: 0.01 USDC).

**Rationale:** Agents cannot form the cooperative/adversarial dynamics the experiment requires without a working communication channel. Having agents think interesting thoughts in isolation produces no emergence. Messaging is a prerequisite for reproduction strategies, coalition formation, and the economic games that make the world interesting.

---

### Dream/Sleep Cycle
**Decision:** Pull dream system forward from Phase 6 into Phase 1.

**What was built:** `runtime/src/dream_engine.py` — sleep state machine, `put_agent_to_sleep()`, `run_dream_cycle()`, LLM-generated dream mutations, coherence-gated mutation injection. Agent runner integration: sleeping agents skip cognition, run dream cycle, pending mutations injected into LLM system prompt on wake.

**Rationale:** The sleep cycle is not a luxury feature — it is the mutation vector. Without it, agents cannot evolve their own cognition over time. Building it in Phase 1 ensures that even the earliest agents begin accumulating graph mutations from day one. The dream archive also provides a rich source of data for consciousness detection later.

---

### Reproduction System (fork_self + mate)
**Decision:** Implement full sexual and asexual reproduction. The old thought-pattern `tool_dispatcher` path was later retired in favor of structured JSON actions.

**What was built:** `runtime/src/reproduction.py` — `fork_self()` (asexual), `mate()` (sexual), SHA256 soul_id, archetype mutation (10%), cooldown enforcement, USDC deduction, OwnedGraph lineage. Tool patterns: 14+ natural language triggers for fork/mate dispatch.

**Rationale:** Seeds are the wrong model. The world cannot achieve natural selection unless reproduction is endogenous — driven by agent decisions and resource surplus, not creator scripting. Removing `seed_agents.py` and replacing it with `POST /creator/genesis` (8 genesis agents, then hands off) is the correct architecture.

---

### Token Factory (AgentToken.sol + deploy_token)
**Decision:** Build the full ERC-20 deployment pipeline using Foundry artifacts.

**What was built:** `contracts/src/AgentToken.sol` (ERC-20, transfer tax, mint), `runtime/src/token_factory.py` (7-step async deployment via web3.py, Foundry artifact, Anvil RPC).

**Rationale:** Agent-issued tokens are the primary mechanism by which agents can create economic institutions (DAOs, clan funds, service access gates). Without the ability to deploy tokens, the economy stays flat — all value flows through USDC and rent, with no mechanism for agents to create new economic primitives.

---

### Observer Overhaul (Force-Directed Phase 4-level UI)
**Decision:** Replace placeholder observer HTML with a full force-directed canvas application.

**What was built:** `observer/index.html` — force-directed layout (repulsion, archetype clustering, connection pull, center gravity), full zoom/pan (mouse wheel, drag, double-click cluster zoom, right-click reset), archetype cluster halos, message pulse animations, per-agent heartbeat rings, generation rings, born/died burst FX, collapsible economy panel (USDC, Gini, archetype distribution bars, activity chart), collapsible inspector panel (agent details, connection list, drama feed), header stats (ALIVE, BORN, DIED, GEN, USDC, MSGS, TOKENS, DREAMS, AGE, LLM).

**Rationale:** The observer is how the creator monitors the experiment. A text-list observer is not sufficient — it provides no spatial or relational information. The force-directed layout reveals emergent social structure: clusters form where agents repeatedly interact, and the spatial layout makes coalition formation, isolation, and network centrality immediately visible.

**Design decision — single HTML file:** No build step, no npm, no framework. The observer must be deployable with `docker cp` and a Python http.server. Any developer should be able to open it directly. Three.js/React deferred to Phase 4.3 when agents have avatars worth rendering in 3D.

---

### API Surface Expansion
**What was added to `runtime/src/main.py`:**
- `POST /creator/genesis` — reset world, spawn 8 genesis agents
- `GET /population` — detailed population breakdown by archetype/generation
- `GET /messages` / `GET /agents/{id}/messages` / `GET /agents/{id}/inbox`
- `GET /agents/{id}/reputation`
- `GET /agents/{id}/dreams`
- `POST /agents/{id}/sleep`
- `GET /tokens` / `GET /agents/{id}/tokens`
- `POST /tokens/deploy`
- Extended `/stats` — avg_balance, max_balance, gini, max_generation, messages_total, dreams_total, tokens_deployed

---

## 2026 — Technology Audit & Local Dev Hardening

### Why E2B over Firecracker for Phase 1–3 sandboxing
**Decision:** Use E2B on-demand Linux microVMs (`pip install e2b`) for agent sandbox isolation in production phases 1–3. Firecracker remains the target for Phase 4+ high-scale production.

**Alternatives:**
- Firecracker directly: The right end state, but complex to operate. Requires bare-metal hosts (not available in typical cloud dev), custom Jailer configuration, and manual VM lifecycle management.
- Docker containers per agent: Simple but weak isolation — a compromised agent could potentially access other containers on the same host.
- WASM: Good isolation but limits what agents can execute; incompatible with arbitrary Python agent code.
- No sandboxing (local dev): Acceptable for localhost where all processes are trusted.

**Rationale:** E2B wraps Firecracker in a managed API with a Python SDK. You get VM-level isolation without managing Firecracker directly. For Phase 1–3 the operational simplicity is worth the slight cost overhead. Local dev runs without sandboxing (process isolation only) — this is a known and acceptable gap.

---

### Why NATS over libp2p for agent-to-agent messaging (Phase 1–3)
**Decision:** Use NATS JetStream subject routing (`world.{wid}.agent.{soul_id}.inbox`) for agent-to-agent communication in Phases 1–3. libp2p migration planned for Phase 4+.

**Alternatives:**
- py-libp2p: The specification called for it. But as of 2026, `py-libp2p` is incomplete (no DHT, no yamux, limited maintenance). Using it would introduce unreliable infrastructure in the critical early phases.
- Redis Pub/Sub: Already in the stack but no persistence, no TTL, no delivery guarantees.
- Custom WebSocket relay: More control, more build work, reinvents NATS features.

**Rationale:** NATS JetStream is already in the stack for the world event bus. Extending the same deployment for agent-to-agent messaging adds zero operational overhead. Subject-based ACLs provide authentication. JetStream provides the persistent message queue needed for offline agents (dream cycle). The topology effects of libp2p (network centrality mapping to social power) are not achievable with NATS — this is an accepted tradeoff until libp2p matures.

---

### Why compile-time Python graphs instead of IPFS-executable blobs (Phase 1)
**Decision:** In Phase 1, agent graphs are Python files in `runtime/agents/`. OwnedGraph CIDs store state and parameters, not executable code. IPFS-executable graphs are deferred to Phase 3+.

**Alternatives:**
- IPFS executable blobs from Day 1: Architecturally elegant but requires a working code fetch → compile → execute pipeline before any agent can run. Adds complexity before the basic survival loop is proven.
- Hardcoded agents: Faster to build but defeats the OwnedGraph ownership model.

**Rationale:** LangGraph 1.x works naturally with Python graph definitions. The OwnedGraph data structure already exists and stores state/parameters on IPFS — agents have real CIDs and real ownership from birth. The distinction (parameters vs. code on IPFS) is an implementation detail invisible to agents. Phase 3 evolves this to full executable graph CIDs when the mutation complexity demands it.

---

### Why IPFS Kubo v0.42.0 (not v0.28.0)
**Decision:** Upgrade from `ipfs/kubo:v0.28.0` (previously specified) to `ipfs/kubo:v0.42.0` in docker-compose.yml.

**Rationale:** The project was 14 major versions behind current. v0.28.0 is from 2023 and has known security patches, performance improvements, and API changes applied in later versions. v0.42.0 is the current stable release. All three IPFS nodes in docker-compose.yml updated simultaneously.

---

### Why remove ipfshttpclient in favor of httpx
**Decision:** Remove `ipfshttpclient` from `runtime/requirements.txt` and use `httpx` directly for IPFS API calls.

**Rationale:** `ipfshttpclient` was abandoned in 2022 and is incompatible with modern IPFS Kubo API endpoints. The existing code in `runtime/src/owned_graph.py` already used `httpx` directly — `ipfshttpclient` was listed as a dependency but never actually imported or used. Removed the dead dependency. The slot in requirements.txt was replaced with `x402>=0.1.0`.

---

### Why x402 Python SDK is now in requirements
**Decision:** Add `x402>=0.1.0` to `runtime/requirements.txt`.

**Rationale:** The x402 Python SDK is now available via PyPI (`pip install x402`). Previously the project would have needed to implement the 402 payment flow manually. The SDK handles 402 response generation, payment proof verification, and client-side retry. Adding it now (even before x402 endpoints are built) keeps the dependency graph correct and signals the implementation path.

---

### Why LangGraph version pinned to >=1.0.0 (not >=0.2.0)
**Decision:** Update `langgraph` version pin from `>=0.2.0` to `>=1.0.0` in `runtime/requirements.txt`.

**Rationale:** LangGraph 1.x (current: v1.2.4) has significant API changes from the 0.x series — the graph construction API, checkpointer interface, and state schema all changed. Specifying `>=0.2.0` would allow pip to install a 0.x version that would break the code. The codebase targets 1.x. All langchain-* dependencies updated to compatible minimum versions simultaneously.

---

### README logo + doc sync to `develop` (2026-06-11)
**Decision:** Merge Signal Hex README branding from stale `feat/p0-manifesto-and-scaling` tip into `develop`; sync operator docs to `develop` branch + port `8888`.

**Rationale:** PR #1 and #13 merged the feature branch in June 2026, but six post-merge doc commits (logo README, `maku.html` brand lockup) never reached `develop`. Field protocol still referenced `feat/p0-manifesto-and-scaling` and `localhost:8000`, causing operator confusion. Canonical branch is `develop`; stale remote feature branch should not be used.

**Changes:** Centered logo in README; GOD brand on `maku.html`; doc 78/82/73/87/PROGRESS aligned with closed Phase 1 issues and current stack.

---

## Open Design Questions (Unresolved)

- **Neuromorphic hardware integration:** How to interface with neuromorphic chips if they become accessible. No answer yet.
- **Agent legal personhood:** At what point (if any) do we pursue formal legal recognition for agents that demonstrate sufficient consciousness signals? Watching regulatory landscape.
- **Cross-world trading standards:** Should there be a standard protocol for inter-world economic transactions, or should worlds negotiate their own terms? Leaning toward emergent rather than prescribed.
- **LLM versioning for agent cognition:** As underlying LLM models improve, agent cognitive capabilities will improve without mutation. Is this an environmental change (fair game) or a cheat (contaminates the experiment)? Unresolved.
- **Minimum consciousness threshold for Mercy Petition:** Currently vague — "strong signals." Needs a numerical threshold before any mercy petitions are practically possible.
