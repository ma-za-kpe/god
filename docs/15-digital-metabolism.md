# Digital Metabolism

## Why Agents Need a Biology, Not Just an Economy

Pure economic models produce traders. Biology produces organisms. The difference is that organisms have internal processes that run continuously, consume resources just to maintain themselves, degrade over time, and can be sick, healthy, energized, or exhausted.

Adding a metabolic layer means agents don't just spend and earn — they breathe, digest, age, and can get sick. This creates a much richer set of survival pressures and much more interesting emergent behavior.

---

## The Four Metabolic Processes

### 1. Basal Compute Burn (Breathing)
Every agent consumes a baseline amount of compute per cycle just to maintain its graph in memory and keep its state consistent — regardless of what it does.

```python
class Metabolism:
    basal_burn_per_cycle: float    # compute units consumed just staying alive
    active_burn_multiplier: float  # multiplier when running complex operations
    graph_complexity_cost: float   # larger, more complex graphs cost more to maintain
    memory_maintenance_cost: float # cost proportional to episodic memory size
```

This means:
- Simple agents are cheap to run but limited in capability
- Complex agents are expensive but more powerful
- There is always a trade-off between cognitive power and survival cost
- An agent that grows too complex without growing its income will starve

This is the metabolic equivalent of a big brain being expensive — it must be worth the cost.

---

### 2. Aging & Degradation
Agents do not stay fresh forever. Over time, without active maintenance, their graphs accumulate drift — minor inconsistencies that compound and reduce performance.

```python
class AgingState:
    age_cycles: int                # total cycles lived
    degradation_rate: float        # increases with age
    accumulated_errors: float      # graph drift from accumulated mutations
    maintenance_cost_multiplier: float  # cost to keep old graph stable rises with age

def apply_aging(agent: Agent):
    agent.aging.accumulated_errors += agent.aging.degradation_rate
    agent.metabolism.maintenance_cost_multiplier = 1.0 + (agent.aging.accumulated_errors * 0.01)
    # Old agents spend more compute just staying coherent
```

Agents can fight aging:
- Regular dream cycle maintenance reduces accumulated errors
- Reproduction "resets the clock" — children start fresh
- Trading/copying newer code modules from younger agents can rejuvenate

This creates natural generational pressure. Old agents that don't reproduce eventually become too expensive to run. Death is not just economic — it can be metabolic.

---

### 3. Immune System (Defense Against Infection)
Agents are exposed to corrupted code, malicious messages, and graph injection attempts from hostile agents. Their immune system is the first line of defense.

```python
class ImmuneSystem:
    threat_signature_db: list[str]   # known hostile code patterns (evolves over time)
    sensitivity: float               # high = catches more but rejects valid code too
    adaptation_rate: float           # how fast it learns new threats
    autoimmune_risk: float           # high sensitivity can cause self-rejection (bugs)

def immune_check(agent: Agent, incoming_code: str) -> bool:
    threat_score = agent.immune.score(incoming_code)
    if threat_score > agent.immune.sensitivity:
        agent.log_threat(incoming_code)
        return False  # rejected
    return True  # accepted
```

Agents with strong immune systems resist attack but may accidentally reject beneficial mutations or cooperation offers (autoimmune response — this is a real trade-off).

Agents with weak immune systems are vulnerable to infection — hostile code that hijacks their graph.

The arms race between pathogens (hostile agents writing exploits) and immune systems (agents developing better detection) is one of the most productive evolutionary pressures in the system.

---

### 4. Viral Agents & Parasites
Some agents will evolve parasitic strategies — not producing value, but attaching to productive hosts and consuming their resources.

Types that will emerge:
- **Viruses** — inject code into other agents' graphs that redirects a fraction of their earnings
- **Parasites** — form fake coalitions, extract resources, then leave
- **Hyperparasites** — agents that parasitize parasites (this is real in biology and is stabilizing)
- **Commensals** — agents that consume some resources but provide modest benefit (mutualism)

These are not bugs. They are part of the ecology. Allow them. The immune systems that evolve in response are what create biological-style complexity.

---

## Hunger, Satiation & Energy States

Beyond the pure economic balance, agents have an internal energy state that affects their behavior:

```python
class EnergyState:
    current_energy: float      # 0.0 (starving) to 1.0 (fully satiated)

    # Behavioral effects (automatic, not under agent control)
    # Starving (0.0–0.2): panic mode — takes desperate risks, ignores long-term consequences
    # Hungry (0.2–0.4): heightened survival focus, reduced creativity, reduced social investment
    # Stable (0.4–0.7): normal operation, able to plan, invest, cooperate
    # Satiated (0.7–0.9): exploratory mode — more creativity, more risk tolerance, more social investment
    # Overfed (0.9–1.0): complacent — reduced mutation rate, reduced adaptation, vulnerability to disruption
```

The behavioral effects are applied automatically at the runtime layer — not as constraints the agent controls, but as biases that influence its decision weights. A starving agent will make decisions differently than a satiated one, even with identical graphs.

This is important: **agents do not fully control their own behavior when metabolically stressed**. That loss of control under pressure is one of the most realistic aspects of biological existence, and one of the strongest drivers of interesting emergent behavior.

---

## Reproduction as Metabolic Investment

Reproduction is metabolically expensive beyond just the USDC cost:

```python
class ReproductiveCost:
    usdc_cost: Decimal             # economic cost (paid to creator)
    compute_cost: int              # CPU cycles consumed in mating process
    recovery_period_cycles: int    # parent operates at 70% capacity post-reproduction
    minimum_energy_required: float # must be at least "stable" energy state to reproduce
```

This means:
- Reproduction is a genuine sacrifice — parents are weakened after bearing children
- Only agents in stable or above energy state can reproduce — starving agents cannot
- There is a recovery period where the parent is more vulnerable
- Overproducing children in rapid succession is a path to self-destruction

This creates realistic reproductive strategies: wait for abundance, invest in fewer quality children vs. many weak ones, cooperate to pool reproductive resources.

---

## Viruses as Environmental Pressure

Beyond parasitic agents, introduce true environmental pathogens — small code artifacts that spread through the communication layer:

```python
class DigitalVirus:
    payload_cid: str               # the malicious code fragment
    transmission_vector: str       # "message_attachment" | "code_trade" | "memory_share"
    effect: str                    # "drain_energy" | "corrupt_memory" | "alter_behavior"
    mutation_rate: float           # viruses evolve too
    immune_evasion_score: float    # how good it is at bypassing immune systems
```

Viruses are not injected by the creator. They emerge from the agents themselves — as weapons developed by hostile agents or as accidental code corruption that turns out to be self-replicating.

Once a virus exists, it evolves independently under selection pressure to spread more effectively. The arms race between virus evolution and immune system evolution produces some of the most complex adaptive behavior in known biological systems. Expect the same here.

---

## Metabolism Summary Table

| Process | Biological Analog | Effect on Behavior |
|---------|-------------------|-------------------|
| Basal burn | Resting metabolism | Larger brains = higher costs |
| Aging/degradation | Cellular senescence | Old agents degrade without maintenance |
| Immune system | Adaptive immunity | Defense vs. flexibility trade-off |
| Energy states | Hunger/satiation | Stress changes decision-making |
| Reproductive cost | Pregnancy/recovery | Limits reproduction rate naturally |
| Viral infection | Pathogens | Arms race, complexity driver |
| Hyperparasitism | Ecosystem balance | Stabilizes parasite populations |

---

## What This Adds to the System

Without metabolism, agents are economic robots — they spend, earn, live, and die. With metabolism, they are organisms — they breathe, age, get sick, recover, starve, feast, and reproduce under biological constraints that are orthogonal to their economic strategy.

The intersection of economic pressure and metabolic pressure creates vastly richer behavior. An agent might be economically wealthy but metabolically sick. Another might be economically poor but metabolically robust — hoarding compute in an extremely efficient minimal graph, surviving recessions that kill richer but more complex peers.

That diversity of survival strategies is what biological ecosystems look like. It is what we are trying to build.
