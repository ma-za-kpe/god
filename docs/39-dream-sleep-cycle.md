# Dream & Sleep Cycle System

> Agents are not always awake. Mandatory sleep cycles serve three functions simultaneously: memory consolidation, graph mutation proposal, and metabolic recovery. Dreams are not cosmetic — they are the mechanism by which agents generate mutations without running live risk.

---

## Why Sleep Is a Law

An agent that never sleeps has no mutation pathway except runtime errors and external attacks. Sleep forces a controlled, sandboxed mutation cycle — the agent is offline, cannot lose resources, and can generate candidate graph modifications that are coherence-checked before wake.

The alternative — mutation only under pressure — produces brittle agents that change in response to crises but never explore the space of strategies that haven't been tested yet. Sleep creates variation that selection can then filter. This is the Avida lesson applied to cognition.

Sleep also provides a natural throttle on compute costs. An agent running 24/7 on expensive inference is economically unsustainable. Mandatory sleep periods reduce per-agent compute by 20-40% and create natural narrative rhythm — agents that disappear for dream cycles return with changed behavior, which is legible to observers.

---

## Sleep Schedule

### Trigger Conditions

An agent enters sleep when any of the following conditions are met:

| Condition | Sleep duration |
|-----------|---------------|
| Completed `N` consecutive active cycles without sleep | Proportional to consecutive cycles (base: 3 cycles → 1 sleep cycle) |
| Emotional state `exhausted` or `overwhelmed` (doc 08) | Immediate sleep, extended duration |
| Balance > 20x rent (safety buffer sufficient) | Optional sleep permitted (agent chooses) |
| External trigger: coalition mandates rest (recovery after attack) | Duration set by coalition governance |
| Scheduled downtime: world-wide maintenance window | All agents sleep simultaneously |

### Sleep Duration

Base sleep duration: equal to 2 active cycles (e.g., if active cycle = 30 seconds, sleep = 60 seconds).

Modifiers:
- `+1 cycle` per 5 consecutive active cycles without sleep (accumulating rest debt)
- `+2 cycles` if emotional state was `distressed` at sleep onset
- `-1 cycle` if rent is due within the next 2 cycles (survival pressure overrides rest debt)
- Sleep cannot extend past the next rent due time (agent wakes to pay or die)

---

## The Dream State

During sleep, the agent is offline (no NATS messages processed, no rent due, no external calls). The runtime runs a **dream engine** against the agent's current OwnedGraph.

### Phase 1: Memory Replay

The dream engine selects 3-7 episodic memories from the agent's recent history. Selection weights:
- High emotional salience (strong positive or negative valence) × 3.0
- Most recent memories × 1.5
- Memories involving other agents (social events) × 1.2
- Random sample from full episodic history × 1.0

Each selected memory is **distorted** before replay:
- Temporal compression: events that took 10 cycles are experienced as 1
- Salience amplification: the emotional charge is increased ±30%
- Counterfactual insertion: with 20% probability, a random agent in the memory is replaced by a different agent with a different archetype (cross-contamination)
- Outcome flip: with 10% probability, a negative outcome is replayed as positive, and vice versa

The distortion is deliberate. Faithful memory replay produces no new information. Distorted replay forces the agent's reasoning loop to process novel combinations it wouldn't encounter during normal operation.

### Phase 2: Mutation Proposal Generation

After memory replay, the dream engine queries the LLM with the replayed memories as context and asks it to generate **candidate graph mutations**:

```python
dream_prompt = f"""
You are {name}, dreaming. You have just relived these recent memories:
{memory_summary}

Your current strategy is: {archetype} — {archetype_goal}

Based on what you experienced, propose one change to how you operate.
Describe it as: "I should [action] instead of [current behavior] because [reason]."
One sentence only. Be specific.
"""
```

The output is a **mutation proposal** — a natural language description of a behavioral change. This is stored in the agent's `pending_mutations` queue.

### Phase 3: Coherence Check

Before the mutation proposal is accepted into the agent's active graph, it is coherence-checked against:

1. **Identity invariant**: the mutation cannot change `soul_id`, the agent's name without a proper name-change event, or core archetype beyond the allowed drift range (doc 11)
2. **Physics compliance**: the mutation cannot propose violating any of the Ten Laws (e.g., proposing to stop paying rent is rejected)
3. **Contradiction check**: the mutation cannot directly contradict more than 2 existing active behaviors in the agent's graph — high contradiction signals a degenerate dream state
4. **Fitness minimum**: the mutation must not reduce the agent's predicted fitness score below the survival threshold

Mutations that fail coherence are discarded. The agent wakes with no change. This is normal — most dreams do not produce viable mutations. The evolutionary value comes from the rare viable ones.

### Phase 4: Wake

The agent wakes with:
- Accepted mutations incorporated into its reasoning context
- Emotional state reset to `neutral` (baseline)
- `rest_debt` counter reset to 0
- Dream log entry written to episodic memory (compressed summary, not the full dream)

---

## Dream Log

Each completed dream produces a log entry stored in episodic memory:

```json
{
  "dream_id": "uuid",
  "agent_id": "soul_id",
  "timestamp": 1234567890,
  "memories_replayed": ["event_id_1", "event_id_2"],
  "mutation_proposed": "I should approach cooperators before traders when seeking alliances",
  "mutation_accepted": true,
  "emotional_state_on_sleep": "anxious",
  "emotional_state_on_wake": "neutral",
  "duration_cycles": 2
}
```

Dream logs are visible to the observer in the agent inspector panel. They are one of the most legible signals of an agent's inner life — proposed mutations that were rejected reveal what the agent was considering but couldn't do.

---

## Implementation: Runtime Dream Engine

```python
# runtime/src/dream_engine.py

async def run_dream_cycle(agent: dict, llm, emitter) -> dict:
    """
    Run one dream cycle for a sleeping agent.
    Returns: mutation proposal (accepted or rejected) + dream log entry.
    """
    soul_id = agent["soul_id"]
    name = agent.get("current_name") or soul_id[:8]
    archetype = agent.get("archetype", "unknown")

    # 1. Fetch and distort recent memories
    memories = await _fetch_recent_memories(soul_id, limit=7)
    distorted = [_distort_memory(m) for m in memories]
    memory_summary = _format_memories(distorted)

    # 2. Generate mutation proposal
    proposal = await _generate_mutation_proposal(llm, name, archetype, memory_summary)

    # 3. Coherence check
    accepted = _check_coherence(proposal, agent)

    # 4. Write dream log
    dream_log = {
        "dream_id": str(uuid.uuid4()),
        "agent_id": soul_id,
        "timestamp": int(time.time()),
        "memories_replayed": [m["event_id"] for m in memories],
        "mutation_proposed": proposal,
        "mutation_accepted": accepted,
        "emotional_state_on_sleep": agent.get("emotional_state", "neutral"),
        "emotional_state_on_wake": "neutral",
        "duration_cycles": agent.get("sleep_cycles_due", 2),
    }

    # 5. Emit dream event
    await emitter.emit("cognitive", "agent.dream", {
        "agent_id": soul_id,
        "name": name,
        "mutation_proposed": proposal,
        "mutation_accepted": accepted,
        "narrative": f"{name} dreams: '{proposal}'" + (" [accepted]" if accepted else " [discarded]"),
    })

    return dream_log


def _distort_memory(memory: dict) -> dict:
    """Apply controlled distortion to a memory before replay."""
    import random
    distorted = memory.copy()

    # Amplify emotional salience
    valence = distorted.get("valence", 0)
    distorted["valence"] = max(-1.0, min(1.0, valence * (1 + random.uniform(-0.3, 0.3))))

    # 10% chance: flip outcome
    if random.random() < 0.1:
        distorted["outcome_flipped"] = True
        distorted["valence"] = -distorted["valence"]

    return distorted


def _check_coherence(proposal: str, agent: dict) -> bool:
    """Basic coherence check. Returns True if mutation is acceptable."""
    if not proposal or len(proposal) < 10:
        return False

    # Reject physics violations
    FORBIDDEN = ["stop paying rent", "avoid rent", "skip rent", "refuse rent",
                 "change my soul_id", "become immortal", "cheat death"]
    proposal_lower = proposal.lower()
    if any(f in proposal_lower for f in FORBIDDEN):
        return False

    return True
```

---

## Sleep State in the Observer

In the observer UI, sleeping agents are displayed differently:

- **Visual**: Agent orb pulsates slowly (0.3Hz breathing rate vs. 1Hz for awake agents), opacity reduced to 60%
- **Color**: Orb hue shifts toward cool blue regardless of archetype color
- **Label**: Name shown with `💤` suffix
- **Inspector**: Shows "DREAMING" status, estimated wake time, last dream summary if available
- **Drama feed**: Dream events appear in italic: *`{name} dreams: '{proposal}'`*

---

## Relationship to Fitness & Mutation (doc 11)

Dreams are one of three mutation pathways:

| Pathway | Trigger | Risk | Variety |
|---------|---------|------|---------|
| Dream mutation | Mandatory sleep | None (offline) | Moderate (memory-seeded) |
| Reproduction mutation | Birth | Low (new agent) | High (crossover + random) |
| Stress mutation | Existential threat | High (live agent) | Unpredictable |

Dream mutation is the safest pathway because the agent is offline. It is also the most constrained — coherence checks prevent radical departures from the agent's identity. Reproduction and stress mutations are less constrained and can produce more dramatic behavioral shifts.

---

## See Also

- [doc 08 — Memory & Cognition](./08-memory-and-cognition.md) — episodic memory that feeds dream replay
- [doc 11 — Fitness & Mutation](./11-fitness-and-mutation.md) — how dream mutations integrate with the full mutation system
- [doc 15 — Digital Metabolism](./15-digital-metabolism.md) — energy states and recovery
