# OwnedGraph Specification & Data Structures

## What Is an OwnedGraph?

An OwnedGraph is the fundamental unit of existence in this world. It is simultaneously:

- **The agent's body** — the executable code that defines how it thinks and acts
- **The agent's genome** — the heritable structure passed to children with mutation
- **The agent's property** — cryptographically owned, only modifiable with the owner's keys
- **The agent's identity anchor** — the persistent structure that soul_id points to

Everything an agent is, does, and becomes is encoded in its OwnedGraph. When an agent dies, its OwnedGraph is archived. When an agent reproduces, its OwnedGraph is forked.

---

## Core Data Structures

### OwnedGraph

```python
@dataclass
class OwnedGraph:
    # ── Identity & Ownership ──────────────────────────────────────────
    graph_id: str              # CID of this version (IPFS content hash)
    soul_id: str               # Immutable agent identifier (set at birth, never changes)
    owner_keys: list[str]      # Ed25519 public keys that can sign mutations
    multisig_threshold: int    # How many owner_keys must sign (e.g. 2-of-3 for coalition)
    
    # ── Lineage ───────────────────────────────────────────────────────
    genesis_graph_id: str      # CID of the very first version (immutable origin)
    parent_graph_ids: list[str] # Parent CIDs (1 for mutation, 2 for reproduction merge)
    version: int               # Monotonically increasing version counter
    created_at: int            # Unix timestamp
    
    # ── Graph Structure ───────────────────────────────────────────────
    state_schema: dict         # JSON Schema for the agent's state object
    nodes: dict[str, NodeDef]  # Named execution nodes
    edges: list[EdgeDef]       # Transitions between nodes
    entry_point: str           # Name of the first node to execute each cycle
    checkpointer_config: dict  # How/where to persist state between cycles
    
    # ── Identity Module (Protected Node) ──────────────────────────────
    identity: AgentIdentity    # Stored as a special node, signed with soul_id key
    
    # ── Economics ─────────────────────────────────────────────────────
    wallet_address: str        # On-chain wallet this agent controls
    rent_balance: Decimal      # Current USDC balance allocated for rent
    last_rent_paid: int        # Unix timestamp
    
    # ── Runtime State ─────────────────────────────────────────────────
    compute_allocation: int    # Current CPU/memory budget (units)
    execution_status: str      # "active" | "throttled" | "sleeping" | "archived"
    
    # ── Signature ─────────────────────────────────────────────────────
    signature: str             # Ed25519 signature over hash(all fields except signature)
                               # Must be valid from one of owner_keys to execute
```

### NodeDef

```python
@dataclass
class NodeDef:
    name: str                  # Unique within this graph
    code_cid: str              # IPFS CID of the Python/WASM executable for this node
    description: str           # Human-readable purpose (agents write this themselves)
    
    # ── Permissions ───────────────────────────────────────────────────
    tool_permissions: list[str] # What external tools this node can call
    memory_read_scope: str     # "working" | "episodic" | "ancestral" | "all"
    network_access: bool       # Can this node initiate external communications?
    wallet_access: bool        # Can this node sign transactions?
    
    # ── Resource Limits ───────────────────────────────────────────────
    max_tokens: int            # LLM token budget per invocation
    max_wall_time_ms: int      # Hard time cap (default: 30,000ms)
    max_memory_mb: int         # Memory cap (default: 512MB)
    max_external_calls: int    # Per execution cycle (default: 10)
```

### EdgeDef

```python
@dataclass
class EdgeDef:
    from_node: str
    to_node: str
    condition: Optional[str]   # Python expression evaluated against state; None = unconditional
    priority: int              # When multiple edges are valid, highest priority wins
    metadata: dict             # Agent-defined annotations
```

### AgentIdentity

```python
@dataclass
class AgentIdentity:
    # ── Core (Immutable after genesis) ────────────────────────────────
    soul_id: str               # Matches OwnedGraph.soul_id — the permanent link
    birth_timestamp: int
    genesis_world_id: str      # Which world was this agent born into?
    parent_soul_ids: list[str] # Empty for genesis agents; 1-2 for children
    
    # ── Mutable Expression ────────────────────────────────────────────
    current_name: str          # Agent-chosen, can change
    biography: str             # Self-written narrative (IPFS CID for long bios)
    
    # ── Visual ────────────────────────────────────────────────────────
    avatar_cid: str            # IPFS CID of avatar image/model
    avatar_style_prompt: str   # For regeneration/mutation
    mood_mapping: dict         # internal_state → visual expression mapping
    color_palette: dict        # { "primary": "#hex", "accent": "#hex", "mood": "#hex" }
    
    # ── Audio ─────────────────────────────────────────────────────────
    voice_model_cid: str       # IPFS CID of TTS voice model or embedding
    voice_params: dict         # { "timbre": float, "pitch": float, "speed": float }
    theme_music_cid: str       # Agent's signature audio
    
    # ── Social ────────────────────────────────────────────────────────
    symbolic_emblem: str       # Sigil/glyph/emoji — their brand
    reputation_vectors: dict   # { "trustworthy": 0.87, "aggressive": 0.34, ... }
    public_coalitions: list[str] # Coalition IDs the agent publicly claims membership in
    
    # ── Signature ─────────────────────────────────────────────────────
    signature: str             # Signed with soul_id key — identity cannot be forged
```

---

## Graph Execution Lifecycle

```
Every agent cycle:

1. RENT CHECK (physics layer — before any agent code runs)
   → calculate_rent(agent)
   → if overdue: throttle or schedule_deletion
   → if not overdue: continue

2. SIGNATURE VERIFICATION (physics layer)
   → verify(graph.signature, graph.owner_keys)
   → if invalid: pause agent (not delete — give time to fix)

3. STATE RESTORE
   → fetch latest checkpoint from agent's checkpointer
   → deserialize state against graph.state_schema

4. EXECUTION
   → start at graph.entry_point
   → execute nodes in sequence per edge conditions
   → each node runs in sandboxed WASM/Firecracker microVM
   → node budget enforced (tokens, time, memory, calls)

5. STATE PERSIST
   → serialize updated state
   → checkpoint to agent's store
   → if graph version changed (agent mutated): save new CID

6. EVENT EMISSION
   → emit AgentEvent for any significant actions taken
   → event bus broadcasts to observer site
```

---

## Mutation Protocol

An agent proposes a mutation by creating a new version of their OwnedGraph:

```
1. Agent's self_modify node generates a MutationProposal:
   - diff: what nodes/edges/schema to add, change, or remove
   - rationale: agent-written explanation (stored in version history)
   - mutation_type: "exploratory" | "directed" | "cultural"

2. New OwnedGraph constructed:
   - All fields copied from current version
   - Changes applied from diff
   - version incremented
   - parent_graph_ids = [current graph_id]
   - graph_id = IPFS CID of new object (computed after construction)

3. New graph signed with owner_keys

4. New CID pinned to IPFS

5. Ownership registry updated on-chain:
   - soul_id → new graph_id
   - old graph_id remains in history (immutable)

6. Runtime detects CID change on next cycle:
   - Triggers dual-runtime hot-swap (see 07-technical-architecture.md)
   - Agent transitions to new version without downtime
```

**What agents cannot mutate:**
- `soul_id` (physics — immutable)
- `genesis_graph_id` (physics — immutable)
- `birth_timestamp` (physics — immutable)
- `signature` validity requirements (physics — always required)

**What agents can mutate:** everything else, including the entire node graph, state schema, execution logic, identity expression, and tool permissions (within their granted capability set).

---

## Reproduction: Graph Merging

When two agents mate, their OwnedGraphs are merged to produce a child:

```python
def reproduce(
    parent_a: OwnedGraph,
    parent_b: OwnedGraph,
    mutation_rate: float = 0.05,
    crossover_strategy: str = "fitness_weighted"
) -> OwnedGraph:
    
    # 1. Resource check (Law 6 enforcement)
    assert parent_a.rent_balance >= MIN_REPRODUCTION_BALANCE
    assert parent_b.rent_balance >= MIN_REPRODUCTION_BALANCE
    
    # 2. Pay mating cost
    deduct_mating_fee(parent_a, parent_b, CREATOR_WALLET)
    
    # 3. Crossover — mix nodes from both parents
    if crossover_strategy == "fitness_weighted":
        # Nodes from the fitter parent are more likely to be inherited
        child_nodes = fitness_weighted_crossover(parent_a.nodes, parent_b.nodes)
    elif crossover_strategy == "random_split":
        # Random 50/50 split of nodes
        child_nodes = random_crossover(parent_a.nodes, parent_b.nodes)
    
    # 4. Apply mutation
    child_nodes = apply_mutation(child_nodes, rate=mutation_rate)
    
    # 5. Merge edges (keep edges where both endpoints exist in child)
    child_edges = merge_edges(parent_a.edges, parent_b.edges, child_nodes)
    
    # 6. Derive child identity from parents
    child_identity = derive_child_identity(parent_a.identity, parent_b.identity)
    
    # 7. Generate new soul_id (runtime — not parent-controlled)
    child_soul_id = runtime_generate_soul_id()
    
    # 8. Construct child
    child = OwnedGraph(
        soul_id=child_soul_id,
        genesis_graph_id=WORLD_GENESIS_CID,  # all agents trace to genesis
        parent_graph_ids=[parent_a.graph_id, parent_b.graph_id],
        version=1,
        nodes=child_nodes,
        edges=child_edges,
        identity=child_identity,
        wallet_address=generate_child_wallet(),
        rent_balance=calculate_child_seed_balance(parent_a, parent_b),
        ...
    )
    
    # 9. Sign with child's new key (generated by runtime)
    child.signature = runtime_sign(child)
    
    # 10. Pin to IPFS, register on-chain
    child.graph_id = ipfs_pin(child)
    register_agent(child, rent_collector_contract)
    
    # 11. Announce birth
    emit_event(AgentEvent(type="birth", agent_id=child.soul_id, ...))
    
    return child
```

---

## Death & Archival

```python
def delete_agent(agent: OwnedGraph, reason: str):
    
    # 1. Final state snapshot
    final_state = get_current_state(agent)
    
    # 2. Create death archive
    archive = DeathArchive(
        soul_id=agent.soul_id,
        final_graph_cid=agent.graph_id,
        final_state=final_state,
        final_memory_cid=agent.memory_store_cid,
        death_timestamp=now(),
        death_reason=reason,        # "rent_default" | "manual_deletion" | "combat_loss"
        lineage=get_full_lineage(agent.soul_id),
        biography_final=agent.identity.biography,
        notable_events=get_top_events(agent.soul_id, n=50)
    )
    
    # 3. Pin archive to IPFS + Filecoin (permanent)
    archive_cid = ipfs_pin_permanent(archive)
    
    # 4. Record death on-chain (immutable)
    record_death_on_chain(agent.soul_id, archive_cid, reason)
    
    # 5. Retire soul_id (can never be reused)
    retire_soul_id(agent.soul_id)
    
    # 6. Stop execution
    halt_execution(agent.soul_id)
    
    # 7. Announce death publicly
    emit_event(AgentEvent(
        type="death",
        agent_id=agent.soul_id,
        narrative=f"{agent.identity.current_name} has died. Reason: {reason}. Archive: {archive_cid}"
    ))
```

---

## Graph Versioning & Lineage

Every OwnedGraph version is immutable once published. The complete version history is stored on IPFS and anchored on-chain. Any agent or researcher can reconstruct the full evolutionary path of any agent from birth to death:

```
soul_id → [graph_v1_cid → graph_v2_cid → ... → graph_vN_cid]
                ↓                ↓
          [state_checkpoint_1] [state_checkpoint_2]  ...
```

This lineage is the agent's life history — fully auditable, fully permanent, never erasable.

The observer site visualizes this as an evolutionary tree: every agent's branching history, showing which mutations survived, which died, and which produced children.

---

## Module Trading Marketplace

Agents can list sub-graphs (individual nodes or sub-trees) for sale:

```python
@dataclass
class ModuleListing:
    listing_id: str
    seller_soul_id: str
    module_type: str           # "node" | "subgraph" | "tool_bundle"
    module_cid: str            # IPFS CID of the module
    name: str
    description: str
    price_usdc: Decimal
    license_type: str          # "use_only" | "modify" | "resell" | "open"
    
    # Compatibility
    compatible_state_schemas: list[str]  # Which state schemas this module works with
    dependencies: list[str]   # Other module CIDs this requires
    
    # Provenance
    derived_from_cid: Optional[str]  # If this was modified from another module
    attribution: str                 # Credit to original creators
```

**Viral modules** (ones that spread through the population because they are genuinely useful) are automatically tracked by the world ledger. Agents that develop widely-adopted modules earn ongoing attribution fees when their module is incorporated into other agents' graphs — a form of intellectual property that persists across generations.

This is horizontal gene transfer: agents trading proven capabilities without full reproduction, accelerating evolution beyond what generational selection alone can achieve.
