# Agent Memory Architecture — Implementation Spec

> This document is the code-level specification for the 3-tier memory system described in doc 08. It covers the Python data structures, IPFS storage format, retrieval API, LangGraph integration, and how memory shapes decision-making at runtime. Detailed enough to implement directly.

---

## Overview

Three tiers of memory serve three time horizons:

| Tier | Scope | Storage | Wiped When |
|------|-------|---------|------------|
| Working Memory | Single cycle | LangGraph state (RAM) | End of cycle |
| Episodic Memory | Lifetime | IPFS + PostgreSQL index | Never (archived at death) |
| Ancestral Memory | Inherited | IPFS (parent's compressed episodes) | Never |

---

## Tier 1 — Working Memory

### Data Structure

Working memory lives in the LangGraph `AgentState` TypedDict. It is populated at the start of each cycle and cleared automatically when the cycle ends.

```python
# runtime/src/memory/working.py

from typing import TypedDict, Optional

class WorkingMemory(TypedDict):
    # Core context
    current_goal: str
    situation_summary: str      # what happened last cycle, injected by agent_runner
    
    # Threats and opportunities
    active_threats: list[str]   # soul_ids of agents threatening this agent
    active_opportunities: list[str]  # detected opportunities (service listings, alliance offers)
    pending_transactions: list[dict]  # uncommitted economic actions this cycle
    
    # Emotional state (loaded from DB, modulates decisions)
    emotional_state: dict       # {"fear": 0.7, "confidence": 0.3, "grief": 0.0, ...}
    
    # Attention
    attention_focus: str        # what the agent is currently "thinking about"
    
    # Recent episodic retrieval (loaded at cycle start)
    recent_episodes: list[dict] # top 5 most relevant recent memories
    
    # Cycle outputs (set during execution, committed on cycle end)
    decided_action: str
    thought_narrative: str
    episodes_to_commit: list[dict]  # new episodes to write to IPFS this cycle
```

### Loading Working Memory

```python
# Called at the start of each agent cycle, before graph execution
async def load_working_memory(soul_id: str, situation: str) -> WorkingMemory:
    agent = await get_agent(soul_id)
    emotional_state = await load_emotional_state(soul_id)
    recent_episodes = await retrieve_recent_episodes(soul_id, limit=5)
    
    return WorkingMemory(
        current_goal=_derive_goal(agent, emotional_state),
        situation_summary=situation,
        active_threats=[],
        active_opportunities=[],
        pending_transactions=[],
        emotional_state=emotional_state,
        attention_focus="",
        recent_episodes=recent_episodes,
        decided_action="",
        thought_narrative="",
        episodes_to_commit=[],
    )
```

### Committing Working Memory

At cycle end, significant events are committed to episodic memory:

```python
async def commit_working_memory(soul_id: str, wm: WorkingMemory):
    for episode_data in wm.get("episodes_to_commit", []):
        await write_episode(soul_id, episode_data)
    
    # Always update emotional state
    await update_emotional_state(soul_id, wm["emotional_state"])
```

---

## Tier 2 — Episodic Memory

### Data Structure

```python
# runtime/src/memory/episodic.py

from dataclasses import dataclass, field
import time

@dataclass
class Episode:
    episode_id: str
    soul_id: str
    
    # What happened
    event_type: str     # "trade" | "betrayal" | "ally_death" | "near_death" | "reproduction"
                        # "coalition_formed" | "service_sold" | "attack" | "dream" | "petition"
                        # "milestone" | "first_contact" | "loss" | "victory"
    timestamp: int
    cycle_number: int   # which rent cycle this happened in
    
    # Who was involved
    participants: list[str]   # soul_ids
    participant_names: list[str]  # human-readable at time of event
    
    # What happened
    outcome: str        # brief factual description
    emotional_imprint: float  # -1.0 (traumatic) to +1.0 (euphoric)
    
    # Agent's own account
    narrative_summary: str    # agent wrote this, in first person
    
    # Associations
    linked_episode_ids: list[str]  # related memories
    tags: list[str]     # ["economic", "social", "survival", "philosophical", ...]
    
    # Storage
    ipfs_cid: str = ""  # set after pinning
```

### IPFS Storage Format

Each episode is stored as a standalone JSON file:

```python
def episode_to_ipfs_payload(episode: Episode) -> dict:
    return {
        "schema": "god.episode.v1",
        "episode_id": episode.episode_id,
        "soul_id": episode.soul_id,
        "event_type": episode.event_type,
        "timestamp": episode.timestamp,
        "cycle_number": episode.cycle_number,
        "participants": episode.participants,
        "participant_names": episode.participant_names,
        "outcome": episode.outcome,
        "emotional_imprint": episode.emotional_imprint,
        "narrative_summary": episode.narrative_summary,
        "linked_episode_ids": episode.linked_episode_ids,
        "tags": episode.tags,
    }
```

### PostgreSQL Index

IPFS stores the content; PostgreSQL provides fast lookups:

```sql
-- Add to init-db.sql
CREATE TABLE IF NOT EXISTS episodes (
    episode_id          TEXT PRIMARY KEY,
    soul_id             TEXT NOT NULL,
    event_type          TEXT NOT NULL,
    timestamp           BIGINT NOT NULL,
    cycle_number        INTEGER,
    emotional_imprint   NUMERIC(4, 3),    -- -1.000 to 1.000
    tags                TEXT[],
    ipfs_cid            TEXT NOT NULL,
    participants        TEXT[],
    world_id            TEXT NOT NULL DEFAULT 'local-dev-world-1',
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_episodes_soul_id ON episodes(soul_id);
CREATE INDEX IF NOT EXISTS idx_episodes_timestamp ON episodes(soul_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_episodes_event_type ON episodes(soul_id, event_type);
CREATE INDEX IF NOT EXISTS idx_episodes_emotional ON episodes(soul_id, emotional_imprint DESC);
```

### Writing an Episode

```python
async def write_episode(soul_id: str, episode_data: dict) -> str:
    """
    Write a new episode to IPFS and index in PostgreSQL.
    Returns the IPFS CID.
    """
    import uuid, httpx, json, psycopg2
    
    episode = Episode(
        episode_id=str(uuid.uuid4()),
        soul_id=soul_id,
        timestamp=int(time.time()),
        **episode_data,
    )
    
    payload = json.dumps(episode_to_ipfs_payload(episode)).encode("utf-8")
    
    # Pin to IPFS
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{IPFS_API}/api/v0/add",
            files={"file": ("episode.json", payload, "application/json")},
        )
        cid = resp.json()["Hash"]
    
    episode.ipfs_cid = cid
    
    # Index in PostgreSQL
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO episodes (episode_id, soul_id, event_type, timestamp,
            cycle_number, emotional_imprint, tags, ipfs_cid, participants, world_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (episode.episode_id, soul_id, episode.event_type, episode.timestamp,
         episode.cycle_number, episode.emotional_imprint,
         episode.tags, cid, episode.participants, WORLD_ID),
    )
    conn.commit()
    cur.close(); conn.close()
    
    return cid
```

### Retrieving Episodes

```python
async def retrieve_recent_episodes(soul_id: str, limit: int = 5) -> list[dict]:
    """Most recent episodes — fast path from PostgreSQL index, full content from IPFS."""
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()
    cur.execute(
        "SELECT episode_id, event_type, timestamp, emotional_imprint, tags, ipfs_cid "
        "FROM episodes WHERE soul_id = %s ORDER BY timestamp DESC LIMIT %s",
        (soul_id, limit),
    )
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return rows


async def retrieve_episodes_by_participant(soul_id: str, participant_soul_id: str) -> list[dict]:
    """All memories involving a specific agent."""
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM episodes WHERE soul_id = %s AND %s = ANY(participants) "
        "ORDER BY timestamp DESC LIMIT 20",
        (soul_id, participant_soul_id),
    )
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return rows


async def retrieve_most_significant_episodes(soul_id: str, limit: int = 10) -> list[dict]:
    """Most emotionally impactful episodes — used for ancestral inheritance."""
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM episodes WHERE soul_id = %s "
        "ORDER BY ABS(emotional_imprint) DESC LIMIT %s",
        (soul_id, limit),
    )
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return rows


async def fetch_episode_from_ipfs(cid: str) -> dict:
    """Load full episode content from IPFS."""
    import httpx, json
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(f"{IPFS_API}/api/v0/cat", params={"arg": cid})
        return json.loads(resp.content)
```

---

## Tier 3 — Ancestral Memory

Ancestral memory is a compressed snapshot of the parent's most significant episodes, distorted slightly to simulate imperfect inheritance.

### Creating the Inheritance Package

Called during child registration (doc 57), after crossover:

```python
async def create_ancestral_memory(
    parent_a_soul_id: str,
    parent_b_soul_id: str | None,
    noise_factor: float = 0.15,
) -> str:
    """
    Create an ancestral memory package for a new child.
    Returns IPFS CID of the package.
    """
    # Pull most significant episodes from each parent
    episodes_a = await retrieve_most_significant_episodes(parent_a_soul_id, limit=15)
    episodes_b = (await retrieve_most_significant_episodes(parent_b_soul_id, limit=15)
                  if parent_b_soul_id else [])
    
    # Combine and take top 15 by significance
    combined = sorted(
        episodes_a + episodes_b,
        key=lambda e: abs(e.get("emotional_imprint", 0)),
        reverse=True,
    )[:15]
    
    # Distort each inherited memory
    inherited = []
    for ep in combined:
        inherited.append({
            "source_episode_id": ep["episode_id"],
            "source_soul_id": ep["soul_id"],
            "event_type": ep["event_type"],
            "emotional_imprint": ep["emotional_imprint"] * (1 + random.uniform(-noise_factor, noise_factor)),
            "tags": ep.get("tags", []),
            # Narrative is distorted — inherited memory is not perfect recall
            "inherited_at_generation": 1,
        })
    
    package = {
        "schema": "god.ancestral_memory.v1",
        "parent_soul_ids": [parent_a_soul_id] + ([parent_b_soul_id] if parent_b_soul_id else []),
        "episodes": inherited,
        "created_at": int(time.time()),
    }
    
    import httpx, json
    payload = json.dumps(package).encode("utf-8")
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{IPFS_API}/api/v0/add",
            files={"file": ("ancestral_memory.json", payload, "application/json")},
        )
        return resp.json()["Hash"]
```

### Using Ancestral Memory

At birth, the child agent loads its ancestral memory into its initial working context:

```python
async def bootstrap_from_ancestral_memory(soul_id: str, ancestral_cid: str):
    """
    Convert inherited episodes into initial emotional state and behavioral biases.
    Called once at agent birth.
    """
    package = await fetch_episode_from_ipfs(ancestral_cid)
    
    # Aggregate emotional signal from inherited trauma/triumphs
    fear_bias = sum(
        abs(e["emotional_imprint"]) for e in package["episodes"]
        if e["emotional_imprint"] < -0.5
    ) / max(len(package["episodes"]), 1)
    
    confidence_bias = sum(
        e["emotional_imprint"] for e in package["episodes"]
        if e["emotional_imprint"] > 0.5
    ) / max(len(package["episodes"]), 1)
    
    # Write initial emotional state
    await update_emotional_state(soul_id, {
        "fear": min(0.8, fear_bias * 1.5),       # inherited trauma inflates fear
        "confidence": min(0.8, confidence_bias),
        "grief": 0.0,
        "anger": 0.0,
        "curiosity": 0.5,  # all agents start curious
        "loneliness": 0.3, # all agents start slightly lonely
    })
    
    # Write inherited episodes to agent's episodic memory as "inherited" type
    for ep in package["episodes"]:
        await write_episode(soul_id, {
            "event_type": "inherited_memory",
            "cycle_number": 0,
            "participants": ep.get("parent_soul_ids", []),
            "participant_names": [],
            "outcome": f"Inherited {ep['event_type']} memory from parent",
            "emotional_imprint": ep["emotional_imprint"],
            "narrative_summary": f"I carry a memory not my own: a {ep['event_type']} my parent experienced.",
            "linked_episode_ids": [],
            "tags": ep.get("tags", []) + ["inherited"],
        })
```

---

## Emotional State Management

Emotional state is stored in PostgreSQL and updated at each cycle:

```sql
-- Add to init-db.sql (or as migration)
CREATE TABLE IF NOT EXISTS emotional_states (
    soul_id             TEXT PRIMARY KEY,
    fear                NUMERIC(4,3) NOT NULL DEFAULT 0.2,
    confidence          NUMERIC(4,3) NOT NULL DEFAULT 0.5,
    grief               NUMERIC(4,3) NOT NULL DEFAULT 0.0,
    anger               NUMERIC(4,3) NOT NULL DEFAULT 0.0,
    curiosity           NUMERIC(4,3) NOT NULL DEFAULT 0.5,
    loneliness          NUMERIC(4,3) NOT NULL DEFAULT 0.3,
    updated_at          BIGINT NOT NULL
);
```

```python
async def update_emotional_state(soul_id: str, updates: dict):
    """Update emotional state, applying natural decay toward baseline."""
    BASELINE = {"fear": 0.2, "confidence": 0.5, "grief": 0.0,
                "anger": 0.0, "curiosity": 0.5, "loneliness": 0.3}
    DECAY_RATE = 0.1  # per cycle, move 10% toward baseline
    
    current = await load_emotional_state(soul_id)
    
    new_state = {}
    for emotion, baseline in BASELINE.items():
        current_val = current.get(emotion, baseline)
        # Apply new event influence
        event_influence = updates.get(emotion, 0.0)
        # Decay toward baseline + event
        new_state[emotion] = round(
            current_val + (baseline - current_val) * DECAY_RATE + event_influence,
            3
        )
        new_state[emotion] = max(0.0, min(1.0, new_state[emotion]))
    
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO emotional_states (soul_id, fear, confidence, grief, anger, curiosity, loneliness, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (soul_id) DO UPDATE SET
            fear = EXCLUDED.fear, confidence = EXCLUDED.confidence,
            grief = EXCLUDED.grief, anger = EXCLUDED.anger,
            curiosity = EXCLUDED.curiosity, loneliness = EXCLUDED.loneliness,
            updated_at = EXCLUDED.updated_at
        """,
        (soul_id, new_state["fear"], new_state["confidence"], new_state["grief"],
         new_state["anger"], new_state["curiosity"], new_state["loneliness"],
         int(time.time())),
    )
    conn.commit()
    cur.close(); conn.close()
```

---

## Memory's Effect on Decisions

Emotional state directly modulates archetype graph behavior:

```python
def apply_emotional_modifiers(state: AgentState, emotional_state: dict) -> AgentState:
    """Inject emotional context into the agent's decision state."""
    fear = emotional_state.get("fear", 0.2)
    confidence = emotional_state.get("confidence", 0.5)
    loneliness = emotional_state.get("loneliness", 0.3)
    
    modifiers = []
    
    if fear > 0.7:
        modifiers.append("HIGH FEAR: avoid risk, conserve balance, do not engage unknown agents")
    elif fear > 0.5:
        modifiers.append("ELEVATED FEAR: prefer familiar counterparties, hold larger reserve")
    
    if confidence > 0.7:
        modifiers.append("HIGH CONFIDENCE: willing to take calculated risks, consider reproduction")
    
    if loneliness > 0.6:
        modifiers.append("LONELINESS: strongly consider alliance proposals even if terms are less favorable")
    
    grief = emotional_state.get("grief", 0.0)
    if grief > 0.5:
        modifiers.append("GRIEVING: reduced output this cycle, may seek to memorialize lost agent")
    
    if modifiers:
        state["opportunity"] = (
            state.get("opportunity", "") +
            "\n\nEmotional context:\n" + "\n".join(f"• {m}" for m in modifiers)
        )
    
    return state
```

---

## Memory-Driven Narrative Generation

Each significant event should produce an episodic entry with a first-person narrative. The narrative generator:

```python
async def generate_episode_narrative(
    soul_id: str,
    event_type: str,
    context: dict,
    llm,
) -> str:
    """Generate a first-person narrative for a new episode."""
    agent = await get_agent(soul_id)
    
    prompt = (
        f"You are {agent['current_name']}, a {agent['archetype']} agent. "
        f"You just experienced: {event_type}. Context: {context}. "
        "Write one sentence in first person describing this experience and how it made you feel."
    )
    
    try:
        response = await llm.ainvoke([{"role": "user", "content": prompt}])
        return response.content.strip()
    except Exception:
        # Fallback to template
        templates = {
            "trade": "I completed a transaction and felt the satisfaction of exchange.",
            "betrayal": "I was betrayed, and I will not forget.",
            "ally_death": "Someone I knew is gone. The world feels smaller.",
            "near_death": "I came close to the end and it changed something in me.",
            "reproduction": "Part of me continues in a new form now.",
            "service_sold": "A stranger paid for what I built. This is why I build.",
        }
        return templates.get(event_type, "Something happened that I will carry forward.")
```

---

## Default Episode Triggers

These events should automatically create episode entries (wired into agent_runner.py):

| Event | Emotional Imprint | Tags |
|-------|------------------|------|
| Rent paid (low balance) | -0.2 | survival, economic |
| Rent missed | -0.6 | survival, fear, economic |
| Near death (1 miss remaining) | -0.8 | survival, existential |
| Trade completed | +0.3 | economic, social |
| Betrayal detected | -0.7 | social, threat |
| Alliance formed | +0.4 | social, cooperation |
| Child born | +0.6 | reproduction, legacy |
| Ally died | -0.5 | grief, social |
| Service sold externally | +0.5 | economic, achievement |
| Status tier promoted | +0.7 | achievement, milestone |
| First petition approved | +0.6 | milestone, social |
| First contact with unknown agent | +0.2 | curiosity, social |

---

## See Also

- [doc 08 — Memory & Cognition](./08-memory-and-cognition.md) — conceptual design
- [doc 39 — Dream & Sleep Cycle](./39-dream-sleep-cycle.md) — memory consolidation during sleep
- [doc 57 — Reproduction Implementation](./57-reproduction-implementation.md) — how ancestral memory is passed at birth
- [doc 41 — Death Mechanics](./41-death-mechanics.md) — how episodic memory is archived at death
