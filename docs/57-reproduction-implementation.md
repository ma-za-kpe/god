# Reproduction Implementation Spec

> This document is the code-level specification for the `mate()` and `fork_self()` tools. It covers the OwnedGraph crossover algorithm, mutation application, child registration, initial USDC seeding, and parent weakening. Detailed enough to implement directly in the runtime.

---

## Overview: What Reproduction Produces

Reproduction creates a new agent (`child`) that:
1. Has a new unique `soul_id` (generated from parent(s) + timestamp)
2. Has a new SoulNFT minted to its wallet
3. Has a new wallet (generated fresh for child independence)
4. Has an OwnedGraph that mixes parent material + mutations
5. Is registered with RentCollector (starts with `missedPayments = 0`)
6. Has initial USDC balance funded from parent(s)
7. Is registered in PostgreSQL with `parent_soul_ids` linking to parent(s)

The child starts alive, pays its first rent from the seeded balance, and begins running immediately.

---

## Mode 1: Sexual Reproduction — `mate(with_soul_id, crossover_strategy)`

### Prerequisites Check

Before reproduction proceeds:

```python
async def can_mate(agent_soul_id: str, partner_soul_id: str) -> tuple[bool, str]:
    """Check if two agents can mate. Returns (can_mate, reason)."""
    agent = await get_agent(agent_soul_id)
    partner = await get_agent(partner_soul_id)
    
    if not agent or not agent["is_alive"]:
        return False, "agent not alive"
    if not partner or not partner["is_alive"]:
        return False, "partner not alive"
    
    mating_cost = float(os.getenv("MATING_COST_USDC", "0.01"))
    seed_cost = float(os.getenv("CHILD_SEED_USDC", "0.005"))
    total_cost = mating_cost + seed_cost
    
    if float(agent["balance_usdc"]) < total_cost:
        return False, f"insufficient balance (need {total_cost:.4f}, have {agent['balance_usdc']:.4f})"
    if float(partner["balance_usdc"]) < total_cost:
        return False, f"partner insufficient balance"
    
    # Check recovery cooldown (can't mate within 5 cycles of last reproduction)
    if agent.get("last_reproduced_at"):
        cycles_since = (int(time.time()) - agent["last_reproduced_at"]) // RENT_PERIOD_S
        if cycles_since < 5:
            return False, f"recovery cooldown ({5 - cycles_since} cycles remaining)"
    
    return True, "ok"
```

### OwnedGraph Crossover

The child's OwnedGraph is built by merging the two parent graphs:

```python
import random

def crossover_graphs(
    parent_a: dict,  # full OwnedGraph dict
    parent_b: dict,
    strategy: str = "random_node_mix",
) -> dict:
    """
    Merge two OwnedGraphs into one child graph.
    
    Strategies:
      random_node_mix  — each node independently chosen from parent A or B (50/50)
      dominant_a       — 70% from A, 30% from B
      dominant_b       — 30% from A, 70% from B
      alternating      — nodes alternate A, B, A, B...
    """
    STRATEGIES = {
        "random_node_mix": lambda i: random.random() < 0.5,
        "dominant_a":      lambda i: random.random() < 0.7,
        "dominant_b":      lambda i: random.random() < 0.3,
        "alternating":     lambda i: i % 2 == 0,
    }
    prefer_a = STRATEGIES.get(strategy, STRATEGIES["random_node_mix"])
    
    nodes_a = {n["node_id"]: n for n in parent_a.get("nodes", [])}
    nodes_b = {n["node_id"]: n for n in parent_b.get("nodes", [])}
    all_node_ids = set(nodes_a.keys()) | set(nodes_b.keys())
    
    child_nodes = []
    for i, node_id in enumerate(sorted(all_node_ids)):
        if node_id in nodes_a and node_id in nodes_b:
            # Node exists in both — pick from preferred parent
            source = nodes_a if prefer_a(i) else nodes_b
            child_nodes.append(dict(source[node_id]))
        elif node_id in nodes_a:
            # Only in A — include with 80% probability
            if random.random() < 0.8:
                child_nodes.append(dict(nodes_a[node_id]))
        else:
            # Only in B — include with 80% probability
            if random.random() < 0.8:
                child_nodes.append(dict(nodes_b[node_id]))
    
    # Edges: include edges where both endpoints exist in child
    child_node_ids = {n["node_id"] for n in child_nodes}
    edges_a = parent_a.get("edges", [])
    edges_b = parent_b.get("edges", [])
    all_edges = {(e["source"], e["target"]): e for e in edges_a + edges_b}
    
    child_edges = [
        e for (src, tgt), e in all_edges.items()
        if src in child_node_ids and tgt in child_node_ids
    ]
    
    # Identity: mix parent identities
    identity_a = parent_a.get("agent_identity", {})
    identity_b = parent_b.get("agent_identity", {})
    child_identity = {
        **identity_a,
        "reputation_vectors": {
            k: (identity_a.get("reputation_vectors", {}).get(k, 0) +
                identity_b.get("reputation_vectors", {}).get(k, 0)) / 2
            for k in set(
                list(identity_a.get("reputation_vectors", {}).keys()) +
                list(identity_b.get("reputation_vectors", {}).keys())
            )
        }
    }
    
    return {
        "nodes": child_nodes,
        "edges": child_edges,
        "agent_identity": child_identity,
        "parent_graph_ids": [
            parent_a.get("graph_id"),
            parent_b.get("graph_id"),
        ],
    }
```

### Mutation Application

After crossover, mutations are applied (doc 11):

```python
def apply_mutations(graph: dict, mutation_rate: float = 0.05) -> dict:
    """
    Apply mutations to a freshly crossed-over graph.
    mutation_rate: fraction of nodes that receive a mutation (0.0–1.0).
    """
    import copy
    mutated = copy.deepcopy(graph)
    
    for node in mutated.get("nodes", []):
        if random.random() < mutation_rate:
            mutation_type = random.choice(["parameter_shift", "weight_adjustment", "connection_change"])
            
            if mutation_type == "parameter_shift" and node.get("parameters"):
                # Shift a random parameter value by ±20%
                params = node["parameters"]
                key = random.choice(list(params.keys()))
                if isinstance(params[key], (int, float)):
                    params[key] *= (1 + random.uniform(-0.2, 0.2))
            
            elif mutation_type == "weight_adjustment" and node.get("weights"):
                # Adjust processing weights
                node["weights"] = {
                    k: v * (1 + random.uniform(-0.15, 0.15))
                    for k, v in node["weights"].items()
                }
            
            # Mark the node as mutated (for lineage tracking)
            node["mutated_at_generation"] = node.get("generation", 1) + 1
    
    return mutated
```

### Child Registration

```python
async def register_child(
    parent_a: dict,
    parent_b: dict | None,
    child_graph: dict,
    world_id: str,
) -> dict:
    """
    Register a new child agent in all systems.
    Returns the complete child agent dict.
    """
    import hashlib
    
    # Generate soul_id: hash of parent soul_ids + timestamp
    parents_str = (
        (parent_a["soul_id"] + (parent_b["soul_id"] if parent_b else "asexual")) +
        str(int(time.time()))
    )
    soul_id = "0x" + hashlib.sha256(parents_str.encode()).hexdigest()[:40]
    
    # Determine archetype: inherit from dominant parent or mix
    if parent_b is None:
        archetype = parent_a["archetype"]
    else:
        # 60% chance to inherit from parent A (the "requesting" parent)
        archetype = parent_a["archetype"] if random.random() < 0.6 else parent_b["archetype"]
        # 10% chance of archetype mutation
        if random.random() < 0.1:
            ALL_ARCHETYPES = ["trader", "hoarder", "explorer", "parasite",
                              "cooperator", "defender", "philosopher", "builder"]
            archetype = random.choice(ALL_ARCHETYPES)
    
    # Generate name from soul_id
    name = _generate_child_name(soul_id, archetype, parent_a.get("current_name"))
    
    # Generate new wallet (in real implementation, use HD wallet derivation)
    wallet_address = _generate_wallet(soul_id)
    
    # Pin graph to IPFS
    graph_cid = await pin_graph_to_ipfs(child_graph)
    
    generation = max(
        parent_a.get("generation", 1),
        parent_b.get("generation", 1) if parent_b else 1
    ) + 1
    
    # PostgreSQL registration
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO agents (
            soul_id, graph_cid, wallet_address, current_name,
            birth_timestamp, is_alive, world_id, archetype,
            balance_usdc, parent_soul_ids, generation
        ) VALUES (%s, %s, %s, %s, %s, true, %s, %s, %s, %s, %s)
    """, (
        soul_id, graph_cid, wallet_address, name,
        int(time.time()), world_id, archetype,
        float(os.getenv("CHILD_SEED_USDC", "0.005")),
        [parent_a["soul_id"]] + ([parent_b["soul_id"]] if parent_b else []),
        generation,
    ))
    conn.commit()
    cur.close()
    conn.close()
    
    return {
        "soul_id": soul_id,
        "name": name,
        "archetype": archetype,
        "wallet_address": wallet_address,
        "generation": generation,
        "parent_soul_ids": [parent_a["soul_id"]] + ([parent_b["soul_id"]] if parent_b else []),
    }


def _generate_child_name(soul_id: str, archetype: str, parent_name: str | None) -> str:
    """Generate a child's name: {ArchetypePrefix}-{HexSuffix}"""
    ARCHETYPE_PREFIXES = {
        "trader": "Coin", "hoarder": "Vault", "explorer": "Drift",
        "parasite": "Shade", "cooperator": "Bloom", "defender": "Shield",
        "philosopher": "Sage", "builder": "Forge",
    }
    prefix = ARCHETYPE_PREFIXES.get(archetype, "Agent")
    suffix = soul_id[-4:].upper()
    
    if parent_name:
        parent_prefix = parent_name.split("-")[0] if "-" in parent_name else parent_name[:4]
        return f"{parent_prefix}-{prefix}-{suffix}"
    
    return f"{prefix}-{suffix}"
```

### Parent Weakening

After successful reproduction, both parents are weakened:

```python
async def weaken_parents(parent_a_id: str, parent_b_id: str | None, seed_amount: float):
    """
    Deduct reproduction costs from parents and enforce recovery cooldown.
    """
    mating_cost = float(os.getenv("MATING_COST_USDC", "0.01"))
    
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    # Parent A pays mating cost + half the child seed
    cur.execute("""
        UPDATE agents
        SET balance_usdc = balance_usdc - %s,
            last_reproduced_at = %s
        WHERE soul_id = %s
    """, (mating_cost + seed_amount / 2, int(time.time()), parent_a_id))
    
    # Parent B (if sexual) pays the other half
    if parent_b_id:
        cur.execute("""
            UPDATE agents
            SET balance_usdc = balance_usdc - %s,
                last_reproduced_at = %s
            WHERE soul_id = %s
        """, (mating_cost + seed_amount / 2, int(time.time()), parent_b_id))
    else:
        # Asexual: parent A pays full seed
        cur.execute("""
            UPDATE agents SET balance_usdc = balance_usdc - %s WHERE soul_id = %s
        """, (seed_amount / 2, parent_a_id))
    
    conn.commit()
    cur.close()
    conn.close()
```

---

## Mode 2: Asexual Reproduction — `fork_self(mutation_rate)`

Asexual reproduction is simpler: the parent's graph is copied directly, mutations applied, and the child is registered as above with `parent_b = None`.

```python
async def fork_self(agent_soul_id: str, mutation_rate: float = 0.05) -> dict:
    """Asexual reproduction: fork the agent with mutations."""
    agent = await get_agent(agent_soul_id)
    
    can, reason = await can_mate(agent_soul_id, None)  # single-parent check
    if not can:
        raise ValueError(f"Cannot reproduce: {reason}")
    
    # Fetch parent graph from IPFS
    parent_graph = await fetch_graph_from_ipfs(agent["graph_cid"])
    
    # No crossover for asexual — just copy + mutate
    child_graph = apply_mutations(parent_graph, mutation_rate)
    
    # Register child
    child = await register_child(agent, None, child_graph, agent["world_id"])
    
    # Weaken parent
    seed_amount = float(os.getenv("CHILD_SEED_USDC", "0.005"))
    await weaken_parents(agent_soul_id, None, seed_amount)
    
    return child
```

---

## Default Reproduction Parameters

| Parameter | Dev Default | Production Target |
|-----------|-------------|-------------------|
| Mating cost (USDC) | 0.001 | 0.01 |
| Child seed (USDC) | 0.002 | 0.005 |
| Recovery cooldown | 3 cycles | 5 cycles |
| Default mutation rate | 5% | 5% |
| Min balance to mate | 3x (mating + seed cost) | 5x |
| Default crossover strategy | random_node_mix | random_node_mix |

---

## Events Emitted

```python
# On successful reproduction:
await emitter.emit("lifecycle", "agent.reproduced", {
    "agent_id": parent_a_soul_id,
    "partner_id": parent_b_soul_id,   # None for asexual
    "child_soul_id": child["soul_id"],
    "child_name": child["name"],
    "child_archetype": child["archetype"],
    "child_generation": child["generation"],
    "crossover_strategy": strategy,
    "mutation_rate": mutation_rate,
    "narrative": f"{parent_a_name} {'and ' + parent_b_name if parent_b else '(asexual)'} produced {child['name']} ({child['archetype']}, gen {child['generation']})",
})
```

---

## See Also

- [doc 40 — Reproduction System](./40-reproduction-system.md) — the higher-level design
- [doc 11 — Fitness & Mutation](./11-fitness-and-mutation.md) — mutation types and rates
- [doc 42 — Clan & Family System](./42-clan-family-system.md) — how children form family units
- [doc 29 — OwnedGraph Specification](./29-ownedgraph-specification.md) — the graph structure being crossed
