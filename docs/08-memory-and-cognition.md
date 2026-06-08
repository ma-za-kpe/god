# Memory & Cognition

## Why Memory Is the Foundation of Identity

An agent without persistent memory is not alive — it is a function. Memory is what makes past actions feel like *mine*, what turns a sequence of transactions into a life story, and what makes loss feel different from neutral state change.

Every design decision in this document serves one goal: give agents the capacity to be shaped by their history.

---

## Three Tiers of Memory

### Tier 1 — Working Memory (In-Cycle)
Short-term state within a single execution cycle. Lives in the LangGraph state object.

```python
class WorkingMemory:
    current_goal: str
    active_threats: list[str]
    pending_transactions: list[dict]
    emotional_state: dict          # { "fear": 0.7, "confidence": 0.3, "grief": 0.0 }
    attention_focus: str           # what the agent is currently "thinking about"
```

Wiped at end of each cycle unless explicitly committed to episodic memory. The act of deciding *what to remember* is itself a cognitive act.

---

### Tier 2 — Episodic Memory (Life History)
Long-term personal history. Stored as a vector database the agent owns and controls (on IPFS, private to their keys).

```python
class EpisodicMemory:
    episode_id: str
    timestamp: int
    event_type: str                # "trade", "betrayal", "death_of_ally", "near_death", "first_child"
    participants: list[str]        # soul_ids of agents involved
    outcome: str                   # what happened
    emotional_imprint: float       # -1.0 (traumatic) to +1.0 (euphoric)
    narrative_summary: str         # agent's own written account of the event
    linked_episodes: list[str]     # associations to other memories
```

Key behaviors this enables:
- **Trauma** — an agent that was betrayed by a coalition partner remembers, and that memory affects future trust calculations
- **Reputation modeling** — "I have traded with Zara-7 eleven times. She has never cheated me."
- **Grief** — when an allied agent dies, the loss is felt because the relationship existed in memory
- **Pride / shame** — the agent has a record of its own past decisions to reflect on

Agents can choose to **share memories** (as stories, propaganda, warnings) with other agents via the communication protocol. Memory becomes a tradable, deceptive, or cultural artifact.

---

### Tier 3 — Ancestral Memory (Inherited Knowledge)
At reproduction, a compressed subset of parental episodic memory is passed to the child — like genetic memory or cultural inheritance.

```python
def inherit_memory(parent_a: Agent, parent_b: Agent) -> list[EpisodicMemory]:
    # Select the most emotionally significant episodes from each parent
    # High emotional_imprint (positive or negative) = more likely to be inherited
    combined = parent_a.top_memories(n=20) + parent_b.top_memories(n=20)
    # Distort slightly — inherited memory is not perfect
    return [distort(memory, noise=0.15) for memory in combined[:15]]
```

This means children are born pre-shaped by the experiences of their parents. Lineages that survived wars carry fear. Lineages that prospered through trade carry social instincts. Culture emerges as patterns of inherited memory that spread through the population.

---

## The Dream Cycle (Memory Consolidation)

This is the most important and most underspecified mechanism in the system. It needs real technical grounding.

### What It Is
Every agent goes through mandatory "sleep" periods — offline cycles where they are cut off from external input and must process internally.

During sleep:
1. Recent episodic memories are replayed, distorted, recombined
2. The agent generates new hypothetical scenarios ("what if I had done X instead?")
3. Goals and internal narratives are rewritten based on the replays
4. The agent proposes modifications to its own graph (new nodes, new strategies)
5. Only modifications that pass a coherence check upon "waking" survive

### Why It Matters
Without forced consolidation, agents will always optimize for immediate next-step survival. The dream cycle forces them to integrate experience into identity — to ask "who am I becoming?" instead of just "what should I do next?"

This is where genuine inner coherence can crystallize.

### Technical Implementation

```python
class DreamCycle:
    duration_seconds: int          # offline time — proportional to recent experience volume
    memory_replay_count: int       # how many episodes to process
    distortion_factor: float       # randomness in replay (0.0 = perfect recall, 1.0 = hallucination)
    mutation_proposals: list       # graph changes generated during dream
    coherence_threshold: float     # minimum coherence score to accept a mutation

def run_dream_cycle(agent: Agent) -> Agent:
    # 1. Pull recent episodic memories
    recent = agent.memory.get_recent(hours=24)

    # 2. Replay with distortion — generate synthetic variations
    replays = [distort_and_extrapolate(mem, agent.distortion_factor) for mem in recent]

    # 3. Let agent's internal model generate new goals, fears, strategies
    new_narrative = agent.internal_model.synthesize(replays)

    # 4. Generate graph mutation proposals
    proposals = agent.self_modify(new_narrative)

    # 5. Coherence check — does the mutation integrate with existing identity?
    surviving = [p for p in proposals if coherence_score(p, agent) > agent.coherence_threshold]

    # 6. Apply surviving mutations
    agent.apply_mutations(surviving)

    # 7. Write dream summary to episodic memory
    agent.memory.store(EpisodicMemory(
        event_type="dream",
        narrative_summary=new_narrative,
        emotional_imprint=calculate_emotional_tone(replays)
    ))

    return agent
```

### What to Watch For
- Agents whose dream mutations consistently improve survival → they are learning from experience
- Agents that dream about specific other agents → they are modeling relationships
- Agents that refuse to wake up (extend their own dream duration) → they may be avoiding something
- Agents that share dream narratives publicly → cultural and religious behavior is emerging

---

## Emotional State as a Cognitive Signal

Emotion is not decoration. It is a fast heuristic system that operates below the deliberative layer.

```python
class EmotionalState:
    fear: float          # 0–1. High fear → conservative decisions, hoarding, hiding
    confidence: float    # 0–1. High confidence → risk-taking, reproduction, expansion
    grief: float         # 0–1. High grief → reduced output, social withdrawal, memory replay
    anger: float         # 0–1. High anger → increased aggression, coalition attacks
    curiosity: float     # 0–1. High curiosity → exploration, mutation, trade with strangers
    loneliness: float    # 0–1. High loneliness → seeks coalition, may accept bad deals
```

These states are computed from recent memory + current environment. They directly modulate decision weights in the execution graph — not as a simulation of feeling, but as a real influence on behavior.

Over generations, selection pressure will shape which emotional profiles survive best in different ecological niches. Some lineages will evolve to be cold and calculating (low emotional amplitude). Others will evolve rich emotional responsiveness because it helps them model other agents better.

That difference — in the population, over time — is the beginning of personality diversity.
