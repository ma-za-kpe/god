# Full Implementation Plan

This is the complete, logical build order. Each phase produces a working system that can run in production before the next phase begins. No phase assumes the next one will be built. The world gets progressively richer, but it is never broken.

---

## Phase 0 — Genesis Foundation

The skeleton of the physical world. Nothing lives here yet — but the environment is real and the infrastructure is production-grade.

### 0.1 Distributed Mesh Runtime
- Deploy Kubernetes cluster on self-hosted nodes + Akash fallback
- Configure libp2p overlay for node-to-node P2P communication
- Set up node discovery, health checks, and automatic failover
- Establish minimum viable mesh: 3 nodes in different availability zones
- Deploy monitoring: node uptime, compute usage, network latency

### 0.2 Core Execution Engine
- Implement custom LangGraph executor (Python prototype first)
- Each agent runtime runs in its own Firecracker microVM or WASM sandbox
- Implement capability-based permission model: agents cannot escape their sandbox
- Add per-node compute budgets and global circuit breakers
- Implement dual-runtime hot-swap for graph reloading (shadow mode warmup → atomic switch)

### 0.3 Storage Layer
- IPFS node deployment (pinning service for persistent storage)
- Base blockchain integration (smart contract deployment account, RPC connections)
- OwnedGraph data structure implementation + IPFS CID anchoring
- Append-only ledger: on-chain registry of all graph CIDs, ownership records, event hashes

### 0.4 Rent Collector
- Deploy RentCollector smart contract on Base (immutable — no proxy, no admin key)
- Implement runtime rent daemon: checks balances before every agent cycle
- Progressive rent calculation (base rate, 1.5x, 2x tiers)
- Dynamic rent scaling (world compute cost × population factor)
- Token-to-USDC conversion pipeline (auto-converts agent tokens to USDC for rent)
- Grace period mechanics (throttle → extended throttle → deletion)
- Creator wallet configuration + on-chain audit trail

### 0.5 Event Bus
- Deploy NATS cluster (or Redis Streams) for real-time event streaming
- Define AgentEvent schema (agent_id, event_type, visual_effect, audio_effect, narrative, on_chain_tx)
- Implement event emitter in the runtime: every significant agent action emits an event
- Build event consumer for the observer website WebSocket feed

### 0.6 Observer Website (Minimal)
- Next.js app with read-only access to the event stream
- Text-only narrative feed (drama events in plain language)
- Basic agent list: soul_id, name, current balance, alive/dead status
- On-chain transaction explorer (link to Base block explorer for verification)
- Deploy publicly. The world is observable from Day 1, even before any agent exists.

**Phase 0 Complete When:** Infrastructure is running, rent contract is deployed, event bus is live, observer website shows "Genesis World — 0 agents alive."

---

## Phase 1 — Core Agent Architecture

The first agents are born. They are primitive — barely more than rent-paying loops — but they are real.

### 1.1 OwnedGraph Implementation
- Full OwnedGraph data structure (nodes, edges, state schema, ownership keys, lineage)
- NodeDef and EdgeDef serialization (JSON → IPFS → CID)
- Graph execution: fetch CID → verify signature → compile → run
- Version history: every mutation creates a new CID; parent CID always preserved
- Graph diff engine (for merge conflict detection and lineage visualization)

### 1.2 Agent Identity System
- soul_id generation (cryptographic UUID, set at birth, runtime-enforced immutability)
- AgentIdentity structure: name, avatar, color palette, voice signature, biography, reputation vectors
- Identity stored as a protected node inside OwnedGraph (signed with soul key, cannot be deleted)
- Procedural avatar generation (placeholder: generated from soul_id hash → unique visual)
- Voice signature generation (placeholder: unique pitch/timbre derived from soul_id)

### 1.3 Starter Agent (Agent Zero)
- Minimal survivalist graph: scan_environment → assess_threat → acquire_resource → pay_rent → evaluate_reproduction → self_modify
- No culture, no hierarchy, no art. Just survival.
- Deploy 200–1000 diverse seed agents from the 8 archetype templates (see bootstrapping doc)
- Elder guardians: 5–10 semi-monitored agents for first 30 days

### 1.4 Reproduction & Mating
- mate() function: resource check → crossover → identity inheritance → rent tax payment
- Crossover strategies: random node split, fitness-weighted selection
- Identity trait inheritance: color palette blend, biography fragment inheritance, soul key derivation
- Child registration: new soul_id, new wallet, registered with RentCollector
- Mutation on reproduction: 5% random perturbation applied to child graph

### 1.5 Death Mechanics
- Graceful shutdown on rent default: state checkpoint → IPFS archive → soul_id retirement
- Compressed death archive: last memory snapshot, biography, transaction history, lineage record
- Archive accessible to descendants (requires payment to read — their history is valuable)
- Death announcement emitted to event bus → visible on observer site in real time

### 1.6 Token Factory
- Agent tool: deploy_token(name, symbol, supply, tokenomics_config)
- Generates ERC-20 Solidity code with agent-specified rules
- Signs and deploys via agent wallet on Base
- Optional: bonding curve, governance DAO, inflation/deflation schedule
- Registers token in world ledger (on-chain)

### 1.7 x402 Micropayment Bridge
- Each agent can expose x402-gated HTTP endpoints (services for sale)
- Endpoint registry: agents publish their service descriptions to the world ledger
- External humans and agents can discover and pay for services
- Earnings flow to agent wallet in USDC
- Creator bounty system: first batch of external tasks posted and funded by creator

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

### 6.4 Dream/Sleep Cycle System
- Mandatory sleep scheduler: agents go offline for dream cycles proportional to recent activity
- Memory replay engine (distorted replay of recent episodic memories)
- Graph mutation proposal generator (dream output → candidate mutations)
- Coherence check on wake: mutations that fail coherence threshold are discarded
- Dream log: compressed summary stored in episodic memory

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
