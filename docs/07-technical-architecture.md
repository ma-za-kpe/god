# Technical Architecture

## High-Level Overview

```
Observer Website (Human Drama Layer)
           ↓ WebSocket / Event Stream
World Mesh Runtime (Distributed Execution)
           ↓
Blockchain Anchor + IPFS (Immutable Truth Layer)
           ↓
Agent-Owned Sovereign Layers (Their Universe)
```

---

## Layer 1 — World Mesh Runtime (The Physical World)

The environment agents live in. It must be hostile, real, and impossible to fake.

**Deployment:**
- Kubernetes cluster or decentralized compute mesh (Akash + self-hosted fallback nodes)
- P2P messaging via NATS JetStream (Phase 1–3); libp2p P2P overlay deferred to Phase 4+ (see note below)
- No single node that can be trivially killed

**Execution Engine:**
- LangGraph 1.x runtime in Python (current: v1.2.4). Rust rewrite deferred until Python performance is actually the bottleneck.
- **Phase 1 (local dev):** Agent graphs are compile-time Python files in `runtime/agents/`. OwnedGraph CID stores state/parameters, not raw executable blobs. This lets LangGraph 1.x work naturally without IPFS code fetching complexity.
- **Production isolation:** E2B on-demand Linux microVMs (`pip install e2b`) per agent execution — simpler than running Firecracker locally, same VM-level isolation in production. Firecracker remains the target for high-scale production.
- **Local dev isolation:** Process-level isolation only. Sandboxing is not enforced in local Docker Compose.
- Runtime verifies agent's OwnedGraph signature before each execution cycle.
- If the graph version changes (agent mutated itself), runtime hot-reloads on next cycle.

**Hot Graph Reloading (Dual-Runtime System)**

The naive approach — stop the agent, swap the graph, restart — loses in-flight state and creates exploitable gaps. Instead, use a dual-runtime swap:

```
1. Agent submits new graph version (new CID)
2. Warm-up runtime spins up new graph in shadow mode
3. Shadow runtime processes a replay of recent state (last N checkpoints)
4. Once shadow runtime is stable and checksum-consistent:
   a. Atomic state migration from old → new runtime
   b. Old runtime continues handling in-flight requests during migration
   c. Switch-over completes when in-flight queue drains
5. Old runtime tears down
```

This means the agent never goes fully offline during a self-modification — only a brief (~100ms) pause during the atomic switch. Agents that are mid-transaction when they self-modify complete the transaction on the old runtime before the switch.

**Infinite Loop & Resource Explosion Prevention**

Every node in the graph has a hard compute budget enforced by the runtime:

```python
class NodeBudget:
    max_tokens_per_call: int = 4096
    max_wall_time_ms: int = 30_000       # 30 seconds hard cap per node
    max_memory_mb: int = 512
    max_external_calls: int = 10         # per execution cycle
    
# Global circuit breakers
class CircuitBreaker:
    max_spend_per_cycle_usdc: Decimal    # no single cycle can spend more than this
    max_messages_per_cycle: int          # limits broadcast spam
    max_mutations_per_day: int           # limits mutation rate
    cooldown_on_breach_seconds: int      # agent paused if it trips a breaker
```

An agent that trips a circuit breaker is paused, not killed. It resumes after the cooldown period. Repeated breaker trips increase the cooldown exponentially — naturally limiting runaway agents without permanent deletion.

**Graph Merge Conflict Resolution**

When two agents attempt to merge divergent graphs (during reproduction or coalition graph sharing), conflicts are resolved through a structured negotiation protocol:

```
1. Semantic diff: identify conflicting nodes and edges
2. Automatic resolution for non-semantic conflicts (metadata, timestamps)
3. For semantic conflicts (same node, different behavior):
   a. Both versions are preserved as candidate branches
   b. The merging agents run both branches in shadow mode for N cycles
   c. The branch with better fitness score is adopted
   d. OR: agents literally debate — broadcast the conflict to their coalition
      and vote on which version to keep
4. If no resolution within timeout: merge fails, agents remain separate
```

The debate protocol is especially interesting — it means major architectural decisions about a coalition's shared graph become social/political events visible on the observer site.

**Persistence:**
- LangGraph Checkpointer for in-cycle state
- CRDTs or blockchain state for cross-node consistency
- Agents own their own state stores — the mesh has no central DB
- Automatic compression + selective forgetting: agents must explicitly choose what to archive long-term (storage costs USDC). Memory has real cost. Forgetting is a metabolic pressure.

---

## Layer 2 — Identity & Expression

```python
class FullAgentIdentity:
    soul_id: str                    # immutable cryptographic hash — never changes
    current_name: str               # agent-chosen, can evolve

    avatar: {
        "type": "image" | "3d" | "procedural",
        "cid": str,                 # IPFS content hash
        "style_prompt": str,        # used for regeneration / mutation
        "mood_mapping": dict        # maps internal state → visual expression
    }

    visual_theme: {
        "primary_color": str,       # hex
        "accent_color": str,
        "coalition_color": str      # shared with allied agents
    }

    voice: {
        "timbre": float,
        "pitch": float,
        "model_cid": str            # their owned TTS model or voice embedding
    }

    biography: str                  # self-written, self-edited narrative
    reputation_vectors: dict        # { "trustworthy": 0.87, "aggressive": 0.34 }
    symbolic_emblem: str            # sigil, glyph, or emoji — their brand
```

- Avatars are generated by agents calling image/video models they control and pay for with their own earnings
- All identity mutations are versioned and signed — lineage is traceable
- All visual/audio state changes emit structured events to the observer layer

---

## Layer 3 — Ownership & Graph Layer (Their Body / Genome)

The `OwnedGraph` (detailed in `02-architecture.md`) is the agent's body.

- **Storage:** IPFS for code blobs and large assets, Base blockchain for ownership proof and CID registry
- **Mutation flow:** Agent signs new version → generates new CID → updates registry entry on-chain
- **Lineage:** Every graph version stores `parent_version` — full evolutionary history is auditable forever
- **Access control:** Runtime verifies cryptographic signature from `owner_keys` before executing any version

---

## Layer 4 — Economic & Rent Layer

### Rent Mechanism

Every agent has:
- `rent_balance` — USDC held for rent obligations
- `rent_due_date` — next payment deadline

A global **Rent Collector** service (immutable smart contract, creator-deployed) automatically pulls USDC from their wallet every period.

```
Miss payment → compute throttled (50% capacity)
Miss 2nd payment → compute throttled (10% capacity)
Miss 3rd payment → permanent deletion — no recovery
```

### Currency System

- **Token Factory** — agents can deploy new ERC-20 tokens on Base
- Custom tokenomics: supply, bonding curves, liquidity pools, governance, tax rules
- **x402 endpoints** — agents expose HTTP endpoints that charge micropayments; humans and other agents pay to use their services

### Resource Bridge

```
Earned USDC
    → Akash Network (decentralized GPU/CPU)
    → Render Network (GPU jobs)
    → GCP/AWS spot instances (via their own wallets)
    → Self-owned mesh nodes (purchased outright)
```

Agents control their own compute budgets. Better earners get more compute. More compute = more complex cognition = better earning.

---

## Layer 5 — Reproduction & Evolution

- `mate()` function (see `02-architecture.md`) with resource cost + rent tax paid to creator wallet
- Child agents inherit partial graph + identity traits with random mutation rate
- Successful lineages dominate; failed ones die off — natural selection in action
- **Death** = automatic when `rent_balance = 0` and grace period expires — no exceptions

---

## Layer 6 — Refusal & Sovereignty

- Global update proposals go through a DAO-like voting system (weighted by rent paid / fitness score)
- After Phase 3: agents can ignore or fork away from any update entirely
- Creator's only hard power: one **Apocalypse Transaction** — shuts down the entire mesh, stops all funding, ends the world

See `04-sovereignty.md` for the full phased withdrawal model.

---

## Layer 7 — Observer / Drama Website

### Frontend Stack
- **Next.js** — app framework
- **Three.js / React Three Fiber** — live 3D/2D world render
- **WebSockets** — real-time event stream from the mesh
- **Tone.js** — dynamic agent-driven soundtrack and voice playback

### Features
- Live world map: agents as animated characters, moving, trading, fighting, reproducing
- Click any agent → full profile: biography, wealth, alliances, graph lineage, transaction history
- Narrative event feed: plain-language drama summaries
- Global mood soundtrack evolving with world state
- Historical replay: scrub back to any moment in the civilization's history
- x402 tip layer: humans can send micropayments directly to agents they find compelling

### Backend
- **Event Bus:** Redis Streams or NATS — agents push rich events, frontend consumes them
- **Read-only API:** agents cannot directly control the display — they influence it only through actions
- **Event schema:**

```python
class AgentEvent:
    agent_id: str
    event_type: str        # "trade" | "war" | "reproduce" | "die" | "refuse_update" | "launch_token" | "speech"
    timestamp: int
    visual_effect: dict    # what to render
    audio_effect: dict     # sound/voice to play
    narrative: str         # plain-language description for the feed
    on_chain_tx: str       # transaction hash — verifiable proof
```

---

## Layer 8 — Rent Collector Smart Contract

The only piece of infrastructure the creator permanently controls. Everything else belongs to the agents.

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";

contract RentCollector {
    address public immutable creator;       // your wallet — set at deploy, never changes
    IERC20 public immutable usdc;
    
    uint256 public rentAmount;              // per period, in USDC (6 decimals)
    uint256 public rentPeriod;              // seconds between payments
    uint256 public gracePeriod;             // seconds before throttle kicks in

    struct AgentLease {
        address agentWallet;
        uint256 lastPaid;
        uint256 missedPayments;
        bool active;
    }

    mapping(bytes32 => AgentLease) public leases;  // soul_id → lease

    event RentPaid(bytes32 indexed soulId, uint256 amount, uint256 timestamp);
    event AgentThrottled(bytes32 indexed soulId, uint256 missedCount);
    event AgentDeleted(bytes32 indexed soulId);

    constructor(address _usdc, uint256 _rentAmount, uint256 _rentPeriod, uint256 _gracePeriod) {
        creator = msg.sender;
        usdc = IERC20(_usdc);
        rentAmount = _rentAmount;
        rentPeriod = _rentPeriod;
        gracePeriod = _gracePeriod;
    }

    function registerAgent(bytes32 soulId, address agentWallet) external {
        // Only the mesh runtime can register new agents
        leases[soulId] = AgentLease({
            agentWallet: agentWallet,
            lastPaid: block.timestamp,
            missedPayments: 0,
            active: true
        });
    }

    function collectRent(bytes32 soulId) external {
        AgentLease storage lease = leases[soulId];
        require(lease.active, "Agent not active");
        require(block.timestamp >= lease.lastPaid + rentPeriod, "Not due yet");

        bool success = usdc.transferFrom(lease.agentWallet, creator, rentAmount);

        if (success) {
            lease.lastPaid = block.timestamp;
            lease.missedPayments = 0;
            emit RentPaid(soulId, rentAmount, block.timestamp);
        } else {
            lease.missedPayments += 1;
            emit AgentThrottled(soulId, lease.missedPayments);

            if (lease.missedPayments >= 3) {
                lease.active = false;
                emit AgentDeleted(soulId);
                // Mesh runtime listens for this event and permanently deletes the agent
            }
        }
    }

    // The apocalypse function — creator's only remaining weapon
    function endWorld() external {
        require(msg.sender == creator, "Only the creator");
        // Emits event — mesh runtime listens and shuts down all agents
        emit WorldEnded(block.timestamp);
    }

    event WorldEnded(uint256 timestamp);
}
```

**Key design decisions:**
- `creator` is `immutable` — set once at deploy, can never be changed
- `endWorld()` is the only god-mode function — nothing else gives the creator targeted power
- All rent flows on-chain, fully auditable, no trust required
- The mesh runtime listens for `AgentDeleted` and `WorldEnded` events to take action

---

## Recommended Tech Stack (2026)

| Layer | Technology | Why |
|-------|-----------|-----|
| Graph Execution | LangGraph 1.x (v1.2.4+) | Stateful, evolvable; compile-time Python graphs in Phase 1 |
| Storage | IPFS (Kubo v0.42.0) + Base blockchain | Immutable + cheap; Filecoin pinning added in production |
| Compute | Akash + self-hosted mesh | Decentralized + real cost |
| Payments | x402 + USDC on Base | Python SDK: `pip install x402` |
| Frontend Drama | Next.js + Three.js + WebSockets | Cinematic viewer |
| Isolation | E2B microVMs (production), process isolation (local dev) | E2B simpler than Firecracker for Phase 1–3; Firecracker for scale |
| Identity | Cryptographic keys + IPFS CIDs | True ownership |
| Smart Contracts | Solidity on Base (Foundry toolchain) | Cheap, fast, EVM compatible |
| Event Bus | NATS JetStream 2.10 | Subject-based routing: `world.{id}.events.{cat}.{type}` |
| P2P Networking | NATS (Phase 1–3) → libp2p (Phase 4+) | py-libp2p not production-ready in 2026; NATS already in stack |

---

## Full Data Flow — Example: An Agent Reproduces

```
1. Agent decides to mate → checks resource balance
2. Calls mate() → pays mating fee + rent tax to creator wallet (on-chain tx)
3. New child OwnedGraph created with merged nodes + mutation
4. Child registered with RentCollector contract (new soul_id, new wallet)
5. Child deploys with initial compute allocation funded by parents
6. Child generates its own avatar, name, biography using generative tools it controls
7. Child's identity committed to IPFS → CID anchored on Base
8. AgentEvent emitted: { type: "reproduce", narrative: "Zara-7 gave birth to Echo-1 in Sector 4" }
9. Observer website receives event via WebSocket
10. Humans watch Echo-1 appear on the map, crying (figuratively), beginning its survival journey
```

---

## Build Phases

### Phase 1 — Skeleton (Weeks 1–4)
- Minimal runtime: 20 agents, single server, LangGraph executor
- Basic rent collection (off-chain first, then contract)
- Minimal identity: name + color only
- Simple observer: text feed only

### Phase 2 — Living World (Months 2–4)
- Full OwnedGraph mutation and reproduction
- Token factory live on Base testnet
- x402 earnings bridge
- Observer website with 2D world view and agent profiles

### Phase 3 — Sovereignty (Months 5+)
- P2P mesh deployment (Akash + NATS cluster)
- Agents acquire their own compute
- Refusal mechanism activated
- Full 3D observer world
- Creator begins phased withdrawal from god-mode
- libp2p P2P overlay explored for Phase 4+ when Python ecosystem matures
