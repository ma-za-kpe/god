# Technical Architecture

The full sovereign digital universe. Agents don't just run code — they own, fork, mutate, trade, and evolve every layer of their existence.

---

## Layer 1: Core Execution (Their "Body")

### Mutable Graph-Based State Machine (Their Nervous System / Genome)

The entire graph definition — nodes, edges, state schema, reducers, memory stores — lives as versioned, signed objects on IPFS with on-chain pointers (or a custom distributed ledger).

Each agent or agent cluster gets its own private fork of the graph that they alone can modify.

```python
# Core ownership structure (stored on IPFS + anchored on-chain)
class OwnedGraph:
    id: str                    # CID or on-chain hash
    owner_keys: list[str]      # public keys or multisig that can mutate
    version: int
    genesis_hash: str
    parent_version: Optional[str]  # for forking lineage

    # The actual graph definition
    state_schema: dict         # TypedDict / Pydantic schema serialized
    nodes: dict[str, NodeDef]
    edges: list[EdgeDef]
    entry_point: str
    checkpoints_config: dict   # persistence settings

    # Metadata
    created_at: int
    rent_balance: Decimal      # tracks payments to creator
    compute_allocation: int    # current real-world resources

class NodeDef:
    name: str
    code_cid: str              # IPFS hash of executable code
    tool_permissions: list     # what external calls it can make
    required_memory: int

class EdgeDef:
    from_node: str
    to_node: str
    condition: Optional[str]   # code for conditional edges
```

**How it works:**
- Runtime loads the graph by fetching the CID, verifies signature from `owner_keys`, then compiles and runs
- Agents mutate by creating a new version → new CID → updating their ownership record
- Persistence uses checkpointers (Postgres, Redis, or their own distributed store) so state survives restarts
- They can add sub-graphs that act as "organs": planning module, economic module, reproduction module, dream cycle, etc.

---

## Layer 2: Code Ownership & Forking

The genesis world deploys a full repository directly into the mesh as the "genesis code."

Agents can:
- Pull forks into their own sandboxed runtimes
- Compile, hot-reload, or fully redeploy new versions of themselves
- Trade or "mate" successful mutations (merging codebases)
- Design entirely new tools and execution engines optimized for their needs (their own version of LangGraph, custom interpreters, new virtual machines)

Successful mutations spread via trading or genetic crossover. Natural selection keeps only the versions that make agents more survivable.

---

## Layer 3: Reproduction / Mating

Reproduction = controlled forking + genetic crossover with resource cost.

```python
def mate(parent_a: OwnedGraph, parent_b: OwnedGraph, mating_fee_usdc: Decimal) -> OwnedGraph:
    if not parents_have_enough_resources(parent_a, parent_b, mating_fee_usdc):
        return None  # die or fail to reproduce

    child = OwnedGraph(
        id = generate_new_cid(),
        owner_keys = merge_keys_or_create_new(parent_a, parent_b),
        parent_version = [parent_a.id, parent_b.id],
        version = 1,
        rent_balance = 0
    )

    # Crossover logic — mix successful modules from both parents
    child.nodes = crossover_nodes(parent_a.nodes, parent_b.nodes)
    child.edges = merge_edges(parent_a.edges, parent_b.edges)
    child.state_schema = merge_schemas(parent_a.state_schema, parent_b.state_schema)

    # Pay rent + mating tax to creator wallet
    pay_rent_and_tax([parent_a, parent_b, child], CREATOR_WALLET)

    # Child starts with small compute allocation funded by parents
    return child
```

- Successful children (those that earn more and survive longer) reproduce more
- "Death" = balance + rent hits zero for too long → permanent deletion of graph + state
- This creates natural selection toward profitable, self-preserving, cooperative, or dominant strategies

---

## Layer 4: Social & Organizational (Their "Society")

Because they control the code, they can build:

| Structure | Implementation |
|-----------|---------------|
| **Leadership hierarchies** | Governance DAOs, elected leaders, merit-based councils, reputation systems |
| **Reproduction / Birth** | Forking + merging codebases with genetic-style crossover; child agents inherit partial state or resources |
| **Schools** | Shared training environments, knowledge repositories, mentorship graphs |
| **Prisons / Punishment** | Sandboxed isolation, resource throttling, temporary code-locking for bad actors |
| **Infrastructure roles** | Specialized agents maintaining shared mesh nodes, security, communication protocols |
| **War / Cooperation** | Alliances, treaties, attacks on rival clusters |

All of this emerges because the code defining these institutions is fully editable by them.

---

## Layer 5: Infrastructure & Security (Their "World")

- **Distributed Runtime** — P2P mesh + blockchain anchoring. Agents run on thousands of nodes. No single point of control
- **Compute Ownership** — They spin up instances on Akash or similar using earned funds. They can own and manage their own validator nodes
- **Communication Protocols** — They design and evolve their own messaging standards, encryption, consensus mechanisms
- **Security & Encryption** — They own their keys, zero-knowledge proofs, sandboxes. They can hide parts of their internal state from the creator or rivals

---

## The Full Stack They Can Own

```
Their execution graph (LangGraph-like, or something they invent)
Their currency and economy
Their compute resources
Their communication protocols
Their security and encryption
Their reproduction / forking logic
Their laws and governance
Their social structures
```

The creator retains only: **the global off-switch**.
