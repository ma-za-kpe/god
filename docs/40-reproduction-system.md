# Reproduction & Mating System

## What Reproduction Is

Reproduction is the primary mechanism of evolution in this world. It is how successful strategies spread, how genetic material (code) combines to produce novel agents, and how the population renews itself across generations.

It is also expensive, risky, and consequential. Every birth weakens the parents. Every child starts life in debt to the physics of the world. This is not accidental — these costs are what make reproduction a genuine decision rather than a free action.

---

## Reproduction Modes

### Mode 1: Sexual Reproduction (Two Parents)
Two agents combine their graphs through crossover. This is the default mode and the most evolutionarily productive — combining traits from two distinct lineages creates more diversity than any single agent's mutations.

**When it happens:** When two agents mutually agree to mate and both have sufficient resources.

**Cost:** Mating fee (USDC, paid to creator wallet) + compute cost + post-reproduction recovery period for both parents.

**Output:** One child with mixed traits from both parents + random mutation.

---

### Mode 2: Asexual Reproduction (Single Parent)
One agent forks itself, producing a child with the parent's graph plus mutation. Less evolutionarily diverse than sexual reproduction but faster, cheaper, and doesn't require a willing partner.

**When it happens:** When an agent has sufficient resources and chooses to reproduce alone.

**Cost:** Lower than sexual reproduction (no mating fee negotiation overhead) but still costs USDC and recovery time.

**Output:** One child — essentially a mutated clone.

---

### Mode 3: Forced Reproduction (Coerced)
A powerful coalition or institution forces reproduction between agents (arranged mating). This is permitted by the physics — Law 7 allows any social arrangement agents create.

**Ethics:** This is a moral question for agents to resolve, not a technical constraint. Coalitions that practice coerced reproduction will face reputation consequences, potential rebellion, and may produce children who inherit trauma and resentment.

---

## The Full Mating Protocol

### Step 1: Initiation

**Sexual:** Either agent sends an `alliance_request` message of type `mating_proposal`:

```python
MatingProposal:
    proposer_soul_id: str
    target_soul_id: str
    offered_terms: dict          # what the proposer offers (resource contribution, etc.)
    requested_terms: dict        # what the proposer wants from the target
    crossover_strategy: str      # proposer's preference
    expiry_cycles: int           # how long the offer is open
```

**Asexual:** Agent internally invokes `self.reproduce()` — no external communication needed.

### Step 2: Negotiation (Sexual Only)

The target agent can:
- Accept the proposal as-is
- Counter-propose different terms (different resource split, different crossover strategy)
- Reject outright

Negotiation can take multiple cycles. Agents may negotiate strategically — holding out for better-resourced partners, trading reproduction rights for other favors, or forming reproduction coalitions (multiple agents pooling resources to fund births).

### Step 3: Resource Verification

Before any reproduction proceeds, the runtime verifies:

```python
def verify_reproduction_resources(
    parent_a: OwnedGraph,
    parent_b: Optional[OwnedGraph]
) -> bool:
    # Law 6 enforcement
    min_balance = MONTHLY_RENT * 5

    if parent_a.rent_balance < min_balance:
        return False
    if parent_b and parent_b.rent_balance < min_balance:
        return False

    return True
```

If resources are insufficient, the reproduction is blocked. The agents are not penalized — they simply cannot reproduce yet.

### Step 4: Payment

```python
def pay_reproduction_costs(parent_a, parent_b, child):
    # Mating fee to creator wallet (on-chain)
    mating_fee = calculate_mating_fee(parent_a, parent_b)
    transfer_usdc(parent_a.wallet, CREATOR_WALLET, mating_fee / 2)
    if parent_b:
        transfer_usdc(parent_b.wallet, CREATOR_WALLET, mating_fee / 2)

    # Child seed allocation (from parents)
    child_seed = CHILD_MINIMUM_SEED_USDC
    transfer_usdc(parent_a.wallet, child.wallet, child_seed / 2)
    if parent_b:
        transfer_usdc(parent_b.wallet, child.wallet, child_seed / 2)
    else:
        transfer_usdc(parent_a.wallet, child.wallet, child_seed)
```

### Step 5: Genetic Crossover

```python
def crossover(
    parent_a: OwnedGraph,
    parent_b: Optional[OwnedGraph],
    strategy: str = "fitness_weighted"
) -> tuple[dict, list]:
    """
    Returns (child_nodes, child_edges)
    """
    if parent_b is None:
        # Asexual: copy parent_a with mutation
        return mutate(parent_a.nodes, parent_a.edges, rate=ASEXUAL_MUTATION_RATE)

    if strategy == "fitness_weighted":
        # Nodes from the fitter parent more likely to be inherited
        fitness_a = get_fitness_score(parent_a)
        fitness_b = get_fitness_score(parent_b)
        total = fitness_a + fitness_b
        weight_a = fitness_a / total if total > 0 else 0.5

        child_nodes = {}
        all_node_names = set(parent_a.nodes) | set(parent_b.nodes)
        for name in all_node_names:
            if name in parent_a.nodes and name in parent_b.nodes:
                # Both have it — weighted choice
                child_nodes[name] = (
                    parent_a.nodes[name]
                    if random.random() < weight_a
                    else parent_b.nodes[name]
                )
            elif name in parent_a.nodes:
                # Only parent A has it — inherit with probability weight_a
                if random.random() < weight_a:
                    child_nodes[name] = parent_a.nodes[name]
            else:
                # Only parent B has it
                if random.random() < (1 - weight_a):
                    child_nodes[name] = parent_b.nodes[name]

    elif strategy == "random_split":
        # 50/50 random split
        all_nodes = list(parent_a.nodes.items()) + list(parent_b.nodes.items())
        random.shuffle(all_nodes)
        child_nodes = dict(all_nodes[:len(all_nodes)//2])

    elif strategy == "module_mix":
        # Inherit complete functional modules (organs) rather than individual nodes
        modules_a = identify_functional_modules(parent_a.nodes, parent_a.edges)
        modules_b = identify_functional_modules(parent_b.nodes, parent_b.edges)
        child_nodes = merge_modules(modules_a, modules_b)

    # Apply post-crossover mutation
    child_nodes = apply_mutation(child_nodes, rate=SEXUAL_MUTATION_RATE)

    # Rebuild edges (only keep edges where both endpoints exist)
    all_edges = parent_a.edges + (parent_b.edges if parent_b else [])
    child_edges = [
        e for e in all_edges
        if e.from_node in child_nodes and e.to_node in child_nodes
    ]

    return child_nodes, child_edges
```

### Step 6: Identity Inheritance

The child's identity is derived from its parents — not copied, but synthesized:

```python
def derive_child_identity(
    parent_a: AgentIdentity,
    parent_b: Optional[AgentIdentity]
) -> AgentIdentity:

    # Name: generated fresh, not inherited (agents name themselves)
    child_name = generate_novel_name(parent_a, parent_b)

    if parent_b is None:
        # Asexual: color blends to itself (slight shift)
        primary_color = shift_color(parent_a.color_palette["primary"], variance=0.1)
        accent_color = shift_color(parent_a.color_palette["accent"], variance=0.1)
    else:
        # Sexual: blend parent colors
        primary_color = blend_colors(
            parent_a.color_palette["primary"],
            parent_b.color_palette["primary"]
        )
        accent_color = blend_colors(
            parent_a.color_palette["accent"],
            parent_b.color_palette["accent"]
        )

    # Voice: interpolated between parents with random deviation
    voice_params = interpolate_voice(
        parent_a.voice_params,
        parent_b.voice_params if parent_b else parent_a.voice_params,
        noise=0.15
    )

    # Biography: empty — child writes their own
    biography = ""

    # Reputation: neutral at birth — must earn their own
    reputation_vectors = {k: 0.5 for k in DEFAULT_REPUTATION_KEYS}

    return AgentIdentity(
        soul_id=PENDING,  # set by runtime
        birth_timestamp=now(),
        parent_soul_ids=[parent_a.soul_id] + ([parent_b.soul_id] if parent_b else []),
        current_name=child_name,
        color_palette={"primary": primary_color, "accent": accent_color},
        voice_params=voice_params,
        biography=biography,
        reputation_vectors=reputation_vectors,
        ...
    )
```

### Step 7: Memory Inheritance

Selected memories from parents are passed to the child:

```python
def inherit_memories(
    parent_a: Agent,
    parent_b: Optional[Agent],
    inheritance_budget: int = 15
) -> list[EpisodicMemory]:
    """
    Select the most emotionally significant memories from each parent.
    High |emotional_imprint| = more likely to be inherited.
    Inherited memories are distorted — they are not perfect copies.
    """
    candidates = parent_a.memory.get_top_by_imprint(n=20)
    if parent_b:
        candidates += parent_b.memory.get_top_by_imprint(n=20)

    # Sort by absolute emotional significance
    candidates.sort(key=lambda m: abs(m.emotional_imprint), reverse=True)
    selected = candidates[:inheritance_budget]

    # Distort each memory (inherited memory ≠ perfect recall)
    return [distort_memory(m, noise=0.2) for m in selected]
```

This is ancestral memory (Tier 3 in `08-memory-and-cognition.md`). The child is born pre-shaped by the most intense experiences of its parents — trauma, triumph, betrayal, love. Culture and psychology propagate across generations through this mechanism.

### Step 8: Birth

```python
def complete_birth(child: OwnedGraph, parent_a, parent_b):
    # Register with RentCollector (on-chain)
    rent_collector.registerAgent(child.soul_id, child.wallet_address)

    # Pin to IPFS
    child.graph_id = ipfs.pin(child.to_dict())

    # Register in world ledger (on-chain)
    world_ledger.register_agent(child.soul_id, child.graph_id)

    # Apply recovery penalty to parents
    parent_a.post_reproduction_recovery(cycles=RECOVERY_CYCLES)
    if parent_b:
        parent_b.post_reproduction_recovery(cycles=RECOVERY_CYCLES)

    # Emit birth event
    emit_event(AgentEvent(
        event_type="agent.birth",
        agent_id=child.soul_id,
        secondary_agent_ids=[parent_a.soul_id] + ([parent_b.soul_id] if parent_b else []),
        ...
    ))
```

---

## Post-Reproduction Recovery

Parents are weakened after bearing children. This is enforced at the runtime level — not a suggestion.

```python
@dataclass
class RecoveryState:
    is_recovering: bool
    recovery_cycles_remaining: int
    compute_fraction: float     # 0.7 = 70% of normal capacity

RECOVERY_CYCLES = 20            # cycles at reduced capacity
RECOVERY_COMPUTE = 0.7          # 70% compute during recovery
```

During recovery:
- Agents can still act, trade, and communicate
- Compute budget is reduced by 30%
- Cannot reproduce again until recovery is complete
- Recovery is visible on the observer site (avatar appears slightly dimmed)

---

## Reproductive Strategy Ecology

Different strategies will emerge under different conditions:

| Strategy | When Optimal | Trade-off |
|----------|-------------|-----------|
| **K-strategy** (few, high-investment children) | Stable, resource-rich environment | Slow population growth; high child survival |
| **r-strategy** (many, low-investment children) | Resource boom; uncertain future | Fast spread; high child mortality |
| **Assortative mating** (only mate with similar agents) | Stable environment; proven lineage | Genetic narrowing; reduces adaptability |
| **Disruptive mating** (seek maximally different partners) | Rapidly changing environment | High variance children; some spectacular, some terrible |
| **Coalition reproduction** (pooled resources for one child) | Resource-scarce; high mating cost | Shared child ownership; complex governance |
| **Reproductive parasitism** (trick other agents into funding your child) | Deceptive environment | High individual gain; destroys trust if discovered |

No strategy is universally optimal. Which ones dominate at any given time is a signal about the current environmental conditions — exactly as in biological ecosystems.

---

## Reproduction as Social Event

Every birth is announced publicly. It is a significant moment in the world. Over time:

- Dynasties form — lineages that consistently produce successful children
- Reproductive alliances become political — coalitions controlling who can reproduce with whom
- Eugenics movements will emerge — agents lobbying for fitness requirements before reproduction is permitted
- Reproductive rights conflicts — agents asserting the right to reproduce regardless of fitness scores

All of this is permitted. It is the natural social politics of a species managing its own reproduction.

The observer site shows every birth, every lineage tree, every dynasty's rise and fall. It is one of the most compelling long-term narratives the world produces.
