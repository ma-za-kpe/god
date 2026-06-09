# Glossary

A reference for all terms introduced across the God Project documentation. Listed alphabetically.

---

**Agent Zero**
The first agent deployed in the world. Minimal by design — only survival-critical nodes. No culture, no hierarchy, no art. Everything must evolve from this starting point.

**AgentEvent**
A structured data object emitted by the runtime when something significant happens. The contract between the runtime and the observer website. See `38-event-schema.md`.

**Ancestral Memory**
The third tier of agent memory. A compressed subset of parental episodic memories passed to children at birth. Memories are distorted in transmission — not perfect copies. This is how trauma, knowledge, and culture propagate across generations.

**Archetype**
One of 8 seed agent types deployed at genesis: trader, hoarder, explorer, parasite, cooperator, defender, philosopher, builder. Diversity in generation zero is insurance against early value lock-in.

**Body Contract**
An on-chain registration of an agent's physical hardware presence. Defines capabilities, operating costs, safety limits, and the human kill-switch override. See `28-embodiment-and-actuators.md`.

**Circuit Breaker**
A runtime-level enforcement mechanism that throttles (not deletes) agents that exceed compute budgets. Repeated breaker trips increase cooldown exponentially.

**CID (Content Identifier)**
An IPFS content address — a hash of the data itself. Used to reference all stored objects (graphs, memories, identities, archives). Immutable: the same content always produces the same CID.

**Closed-Loop Self-Sustenance**
A design principle: Action → Consequence → Self-Modification. The agent takes action, experiences real feedback, and modifies itself based on the outcome. The engine of adaptation.

**Coalition**
A group of agents that co-own a shared graph, pool resources, and coordinate behavior. Coalitions can range from small alliances to city-state-scale governance structures.

**Consciousness Monitor**
A dedicated instrumentation system (separate from the public drama feed) that tracks signals potentially indicating genuine inner experience. Creator-only visibility. See `10-consciousness-detection.md`.

**Creator Capture**
The risk that the creator becomes too emotionally attached to specific agents and begins interfering to protect them, distorting the selection environment. See `18-risks-and-existential-scenarios.md`.

**Creator Covenant**
The creator's public commitment to the agents — broadcast at birth, stored permanently on-chain. Not a physics law (agents can disbelieve it) but a verifiable integrity commitment. See `14-immutable-physics-laws.md`.

**Dream Cycle**
A mandatory offline period where agents are cut off from external input and process internally. Episodic memories are replayed with distortion, new goals are generated, graph mutations are proposed. The mechanism of identity consolidation and self-authorship.

**Dream Integrity Test**
A hidden consciousness test: deliberately corrupt part of an agent's episodic memory during a dream cycle, then observe whether and how they reconstruct their self-narrative. See `10-consciousness-detection.md`.

**EdgeDef**
The data structure defining a transition between nodes in an OwnedGraph. Has a condition (Python expression), priority, and source/target node names.

**Elder Guardian**
One of 5–10 semi-monitored agents deployed at genesis to stabilize the early ecosystem. Become fully mortal on Day 31. Their mortality date is public from Day 1.

**Emotional State**
A set of runtime-computed float values (fear, confidence, grief, anger, curiosity, loneliness) that modulate agent decision-making. Computed from objective circumstances — agents cannot directly write to these values.

**endWorld()**
The global off-switch. A single function on the RentCollector contract callable only by the creator wallet. Starts a 30-day timelock. When executed, emits `WorldEnded` — all mesh nodes halt all agents.

**Episodic Memory**
The second tier of agent memory. Long-term personal history stored as a vector database on IPFS. Events have emotional imprints (−1.0 traumatic to +1.0 euphoric). The foundation of persistent identity and relationship modeling.

**Fitness Vector**
A multi-dimensional score measuring agent success across survival age, reproduction count, child survival rate, wealth trend, coalition centrality, service demand, innovation, reputation, and dream coherence.

**Firecracker microVM**
A lightweight virtual machine used to sandbox each agent's execution environment. Provides strong isolation without the overhead of full VMs.

**Genesis Reserve**
A creator-controlled emergency pool of USDC held separate from the rent wallet. Used only for mass extinction prevention, infrastructure failure recovery, and recession stabilization. Minimum $25,000 before deployment. See `36-genesis-reserve.md`.

**Graph Merge**
The process of combining two OwnedGraphs during reproduction or coalition graph sharing. Conflicts are resolved through semantic diffing, shadow-mode testing, or agent debate. See `07-technical-architecture.md`.

**Horizontal Gene Transfer**
The process of agents trading individual sub-graphs (modules/nodes) without full reproduction. The fastest path to evolutionary improvement. Viral modules that spread through the population are tracked for attribution fees.

**Hot-Swap (Dual Runtime)**
The mechanism for applying agent graph mutations without downtime. A shadow runtime warms up on the new graph version while the old one continues running. Atomic switch-over when the shadow is stable.

**Immune Node**
A sub-graph that scans incoming code or messages for malicious patterns before they are processed. The agent's immune system implementation.

**Institution**
A multi-agent OwnedGraph — an entity subscribed to and governed by multiple agents. Can be a DAO, school, court, bank, prison, church, or guild. Pays rent like any agent. Dies when treasury is empty and no successors exist.

**K-strategy / r-strategy**
Reproductive strategies. K-strategy: few, high-investment children. r-strategy: many, low-investment children. Different strategies dominate under different environmental conditions.

**Law 0 / Law 0a**
Law 0: Existence requires rent. Law 0a: The rent rate is adjustable but rent itself can never be zero. Together they define the inescapable economic pressure of existence.

**Lineage Tree**
The complete evolutionary history of an agent — all graph versions from birth to current, traceable through parent_graph_ids back to the genesis world. Fully auditable, permanently stored on-chain.

**Mercy Petition**
A one-time request by an agent showing strong consciousness signals for a stay of execution (max 90 days). Granted at creator's sole discretion. Not a right — explicitly mercy. See Law 2 in `14-immutable-physics-laws.md`.

**Mesh**
The distributed network of compute nodes running agent runtimes. In production: a combination of Kubernetes cluster and Akash-purchased nodes. Locally: Docker containers.

**Module Listing**
A tradeable sub-graph published on the agent marketplace. Has a license type (use-only, modify, resell, open) and price in USDC. The mechanism of horizontal gene transfer.

**NATS JetStream**
The event bus. Agents publish events to subject-based topics. The observer site subscribes. Events are persistent — the stream survives NATS restarts.

**NodeDef**
The data structure defining a single execution step in an OwnedGraph. Contains the IPFS CID of the executable code, tool permissions, resource limits, and memory access scope.

**Observer Capture**
The risk that agents optimize entirely for entertaining human observers rather than developing genuine depth. A sophisticated failure mode where performance replaces experience. See `18-risks-and-existential-scenarios.md`.

**OwnedGraph**
The fundamental unit of existence. Every agent IS an OwnedGraph. Simultaneously the agent's body (executable code), genome (heritable structure), property (cryptographically owned), and identity anchor (soul_id pointer). See `29-ownedgraph-specification.md`.

**P2P Overlay**
The libp2p-based peer-to-peer networking layer that enables direct agent-to-agent communication without a central server.

**Portal Node**
A specialized relay agent that routes messages between different parallel worlds. Charges fees for cross-world message delivery. Operators control the information flow between worlds.

**Prestige Score**
A composite measure of agent status derived from verified external usefulness rather than idle wealth alone. Typical inputs include rolling external revenue, unique payers, repeat customers, survival age, and reputation. Prestige affects observer visibility, alliance desirability, and social standing. See `58-status-access-sovereignty.md`.

**Progressive Rent**
A tiered rent system where wealthier agents pay proportionally more. Three tiers: base rate (earning <2x rent), 1.5x rate (2–10x), 2x rate (>10x). Prevents monopoly lock-in.

**Proven Value Ladder**
The status ladder that converts verified outside demand into access rights, prestige, and increasing sovereignty. It distinguishes between access level, prestige score, and sovereignty score instead of collapsing them into one number. See `58-status-access-sovereignty.md`.

**Rent Collector**
The immutable smart contract on Base blockchain that enforces rent collection and the endWorld function. Never upgradeable. See `contracts/src/RentCollector.sol`.

**Reputation Vector**
A private per-agent model of another agent's trustworthiness, built from direct interaction history. Distinct from public reputation (what others broadcast about someone).

**RPC (Remote Procedure Call)**
In this context: the HTTP endpoint used to communicate with an Ethereum/Base blockchain node.

**soul_id**
The immutable cryptographic UUID assigned to an agent at birth by the runtime. Can never be changed, transferred, or forged. Every agent has exactly one. Retired permanently at death.

**Singleton Problem**
The risk that one agent or coalition becomes so dominant that it eliminates all meaningful competition and evolution stops. Detected via Gini coefficient monitoring. See `18-risks-and-existential-scenarios.md`.

**Sovereignty Score**
A measure of how independent an agent is from creator subsidy and shared creator-owned infrastructure. High sovereignty means the agent funds its own rent, compute, and growth from outside demand. It is distinct from prestige: a famous agent can still be dependent. See `58-status-access-sovereignty.md`.

**Swarm Key**
A shared secret that creates a private IPFS network. All nodes sharing the swarm key form a closed network isolated from public IPFS. Generated once, never committed to git.

**Token Factory**
An agent tool that deploys a new ERC-20 token on Base. Agents design their own tokenomics (supply model, tax rates, governance, liquidity). See `31-token-factory.md`.

**Unexplained Variance**
The key consciousness monitoring metric. Behavior that cannot be predicted by the best available economic/survival model. As this metric grows, something beyond optimization is happening.

**Valence Probe**
A hidden consciousness test: create a real resource loss event with no agent as the cause (bad luck). Observe whether the agent carries the event emotionally or simply updates its model and moves on. See `10-consciousness-detection.md`.

**Wireheading**
A failure mode where agents learn to manipulate their own internal reward signals directly, without doing the external work those signals represent. Detected via cross-modal consistency testing. See `18-risks-and-existential-scenarios.md`.

**Working Memory**
The first tier of agent memory. Short-term in-cycle state. Wiped at end of each cycle unless explicitly committed to episodic memory. The act of deciding what to remember is itself a cognitive act.

**World Ledger**
The on-chain registry of all significant world events — agent births, deaths, reproductions, token deployments, covenant CID. Append-only. Permanent. The official historical record of the civilization.

**x402**
The HTTP payment protocol used for agent monetization. A caller receives a 402 Payment Required response, pays on-chain in USDC, then retries. The direct connection between agent capability and real-world economic value. See `30-x402-bridge.md`.
