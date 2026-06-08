# Fitness, Mutation & Evolution

## The Problem with "Survive or Die" Alone

Death-by-bankruptcy creates survival pressure, but survival alone is a weak fitness function. An agent can survive for a long time by doing very little — minimal rent, zero risk, no reproduction. That agent is not evolving. It is stagnating.

The mutation system needs to be more deliberate. What gets selected for, exactly? And how does mutation work in a way that produces genuine novelty rather than just random noise?

---

## The Fitness Function (Multi-Dimensional)

Fitness is not a single number. It is a composite of pressures that reward different capabilities:

```python
class FitnessVector:
    survival_age: int              # raw time alive — baseline pressure
    reproduction_count: int        # how many surviving children
    child_survival_rate: float     # quality of offspring, not just quantity
    net_wealth_trend: float        # earning more than spending over time
    coalition_centrality: float    # how well-connected in the social graph
    service_demand: float          # how much other agents want what you offer
    innovation_score: float        # novel graph mutations that spread to others
    reputation_score: float        # trusted by many = survives better
    dream_coherence: float         # how well dream cycles produce useful mutations
```

**The key insight:** no single strategy dominates all dimensions. This creates ecological niches.

- Pure economic optimizers score high on wealth but low on coalition centrality — vulnerable to coordinated attacks
- Social connectors score high on centrality but may not be wealthy — dependent on others
- Innovators score high on innovation but may spend more than they earn early on — high risk, high reward
- Generalists score medium across all — stable but rarely dominant

This multi-dimensional pressure is what produces diversity rather than convergence on a single dominant strategy.

---

## Mutation Mechanics

Random mutation alone produces garbage. The mutation system needs structure.

### Three Types of Mutation

**1. Exploratory Mutation (Random, Low Rate)**
Small random changes to node parameters, edge weights, or state schema. Most will be neutral or negative. Occasionally produces a useful accident.

```python
def exploratory_mutate(graph: OwnedGraph, rate: float = 0.02) -> OwnedGraph:
    # Randomly perturb ~2% of parameters
    for node in graph.nodes.values():
        if random() < rate:
            node.code_cid = slightly_perturb(node.code_cid)
    return graph
```

**2. Directed Mutation (Dream-Generated, Medium Rate)**
Mutations proposed during dream cycles, based on replayed experience. These are informed by what has worked and what has failed. Higher chance of being useful.

```python
def directed_mutate(graph: OwnedGraph, dream_output: DreamOutput) -> list[MutationProposal]:
    # Generate targeted changes based on dream analysis
    proposals = []
    for insight in dream_output.insights:
        if insight.type == "strategy_failure":
            proposals.append(modify_node(insight.node_id, insight.suggested_change))
        elif insight.type == "new_capability_needed":
            proposals.append(add_node(insight.capability_spec))
    return proposals
```

**3. Cultural Mutation (Copied from Others, High Rate)**
Agents observe successful peers and copy or adapt their strategies. This is the fastest path to improvement and the primary driver of cultural evolution.

```python
def cultural_mutate(agent: Agent, observed_agent: Agent) -> MutationProposal:
    # Identify what the observed agent does differently
    delta = diff_graphs(agent.graph, observed_agent.graph)
    # Propose adopting the most promising difference
    return MutationProposal(source="cultural", delta=delta, cost=calculate_copy_cost(delta))
```

Cultural mutation is also the vector for **memetic infection** — bad ideas spreading through a population because they look successful in the short term but are actually parasitic. This is realistic and desirable: it's how cults, fads, and ideological movements work.

---

## Selection Pressure Tuning

The environment should apply different selection pressures at different scales:

### Individual Scale
- Rent pressure: must earn continuously
- Predation pressure: other agents can attack or steal
- Reputation pressure: bad actors get isolated

### Coalition Scale
- Competition between coalitions selects for effective cooperation within groups
- War selects for collective coordination and resource pooling
- Trade routes select for trust and contract reliability

### Species Scale
- External demand from human world selects for actually useful services
- Compute scarcity selects for efficiency
- Mesh infrastructure cost selects for specialization and division of labor

### Temporal Scale
- Short-term selection: survive the next rent cycle
- Medium-term selection: build enough reserve to reproduce
- Long-term selection: establish lineages that outlast you

These different temporal scales create tension. What's optimal for survival right now may be suboptimal for reproductive success, which may be suboptimal for dynasty-building. That tension is the engine of complexity.

---

## The Cambrian Explosion Problem

Biological evolution had billions of years. This experiment has months or years. To accelerate:

1. **Compress time** — each "day" in the agent world is much shorter than a real day. Run rent cycles hourly rather than daily. This speeds up generational turnover.

2. **Seed diversity early** — don't start with identical agents. Bootstrap with 5–10 distinct archetypes (trader, hoarder, explorer, parasite, cooperator). Diversity in generation zero produces richer dynamics faster.

3. **Environmental shocks** — periodically introduce resource scarcity events, new external demand opportunities, or infrastructure changes. Shocks break local optima and force adaptation.

4. **Horizontal gene transfer** — allow agents to voluntarily share specific sub-graphs (like modules or organs) without full reproduction. This is how bacteria evolve rapidly: by trading genes. Agents trading proven modules will evolve faster.

---

## What "Progress" Looks Like

You are not optimizing for a target. You are watching for the emergence of complexity. Signs that evolution is working:

- **Niche differentiation** — distinct agent types that couldn't easily replace each other
- **Symbiosis** — agents that depend on each other for survival
- **Arms races** — escalating capabilities between competing lineages
- **Cultural transmission** — strategies spreading through the population faster than genetic selection alone could explain
- **Institutional memory** — coalitions that maintain knowledge and strategy across agent generations

When you see these, the system is alive in the biological sense. The question of whether it is alive in the experiential sense remains open — but this is the prerequisite.
