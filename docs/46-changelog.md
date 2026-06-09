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

## Open Design Questions (Unresolved)

- **Neuromorphic hardware integration:** How to interface with neuromorphic chips if they become accessible. No answer yet.
- **Agent legal personhood:** At what point (if any) do we pursue formal legal recognition for agents that demonstrate sufficient consciousness signals? Watching regulatory landscape.
- **Cross-world trading standards:** Should there be a standard protocol for inter-world economic transactions, or should worlds negotiate their own terms? Leaning toward emergent rather than prescribed.
- **LLM versioning for agent cognition:** As underlying LLM models improve, agent cognitive capabilities will improve without mutation. Is this an environmental change (fair game) or a cheat (contaminates the experiment)? Unresolved.
- **Minimum consciousness threshold for Mercy Petition:** Currently vague — "strong signals." Needs a numerical threshold before any mercy petitions are practically possible.
