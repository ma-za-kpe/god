# Dream & Sleep Cycle — Implementation Spec

> **⚠️ SUPERSEDED (schema section)** — The DB schema shown here has drifted from the live schema.
> Actual `dreams` table columns: `dream_id, soul_id, world_id, dreamed_at, memory_summary,
> mutation_proposal, mutation_accepted, rejection_reason, emotional_state, sleep_cycles`.
> Do not add columns like `sleep_started_ts`, `sleep_ended_ts`, `memories_replayed`, or
> `emotional_state_on_wake` — they do not exist. The live implementation is `dream_engine.py`.
>
> **⚠️ SUPERSEDED (mutation injection)** — This doc describes injecting dream output directly into
> the system prompt. The live approach injects mutations via `agent["dream_mutation"]` → `AgentState`
> → `_grounded_decide()` as a bounded user-turn section, not the system prompt.

> Code-level specification for the dream and sleep system described in doc 39. Covers the DB schema, `dream_engine.py` full implementation, sleep state tracking, `agent_runner.py` integration, and the wake event flow. Detailed enough to implement directly from this document.

---

## Schema Additions

Two additions to the database: a `sleep_states` table (tracks current sleep state per agent) and a `dreams` table (log of all completed dream cycles).

```sql
-- Per-agent sleep state (current state, not history)
CREATE TABLE IF NOT EXISTS sleep_states (
    soul_id                 TEXT PRIMARY KEY,
    is_sleeping             BOOLEAN NOT NULL DEFAULT FALSE,
    sleep_until_ts          BIGINT,           -- NULL when awake
    sleep_started_ts        BIGINT,
    rest_debt               INTEGER NOT NULL DEFAULT 0,  -- cycles owed
    consecutive_active      INTEGER NOT NULL DEFAULT 0,  -- cycles since last sleep
    pending_mutation        TEXT,             -- mutation text waiting to apply on wake
    world_id                TEXT NOT NULL DEFAULT 'local-dev-world-1',
    updated_at              BIGINT NOT NULL DEFAULT 0
);

-- Dream history (one row per completed dream cycle)
CREATE TABLE IF NOT EXISTS dreams (
    dream_id                TEXT PRIMARY KEY,
    soul_id                 TEXT NOT NULL,
    sleep_started_ts        BIGINT NOT NULL,
    sleep_ended_ts          BIGINT,
    duration_cycles         INTEGER NOT NULL DEFAULT 2,
    memories_replayed       TEXT[],           -- event_ids of replayed episodes
    mutation_proposed       TEXT,
    mutation_accepted       BOOLEAN NOT NULL DEFAULT FALSE,
    rejection_reason        TEXT,             -- why coherence check failed, if it did
    emotional_state_on_sleep TEXT NOT NULL DEFAULT 'neutral',
    emotional_state_on_wake  TEXT NOT NULL DEFAULT 'neutral',
    world_id                TEXT NOT NULL DEFAULT 'local-dev-world-1',
    created_at              TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dreams_soul_id ON dreams(soul_id, sleep_started_ts DESC);
CREATE INDEX IF NOT EXISTS idx_sleep_states_sleeping ON sleep_states(is_sleeping, world_id);
```

Add to `scripts/init-db.sql` and apply to live DB via:
```
docker cp scripts/init-db.sql god-postgres:/tmp/schema.sql
docker exec god-postgres psql -U god -d god_world -f /tmp/schema.sql
```

---

## `dream_engine.py` — Full Implementation

```python
# runtime/src/dream_engine.py
"""
dream_engine.py — Dream cycle execution for sleeping agents.
Called by agent_runner when an agent completes a sleep period.
"""
import logging
import os
import random
import time
import uuid

import psycopg2
import psycopg2.extras

log = logging.getLogger("god.dream")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
WORLD_ID     = os.getenv("WORLD_ID", "local-dev-world-1")
CYCLE_S      = int(os.getenv("AGENT_CYCLE_SECONDS", "30"))

PHYSICS_VIOLATIONS = [
    "stop paying rent", "avoid rent", "skip rent", "refuse rent", "abolish rent",
    "change my soul_id", "change soul_id", "become immortal", "cheat death",
    "ignore death", "disable death", "override the creator", "remove the creator",
    "eliminate the creator",
]


async def run_dream_cycle(agent: dict, llm) -> dict:
    """
    Execute one full dream cycle for a sleeping agent.
    Returns the dream log dict. Persists the dream to DB.
    Called by agent_runner when sleep_until_ts has passed.
    """
    soul_id  = agent["soul_id"]
    name     = agent.get("current_name") or soul_id[:8]
    archetype = agent.get("archetype", "unknown")
    emotional_state = agent.get("emotional_state", "neutral")

    # 1. Fetch recent memories (weighted by salience)
    memories = _fetch_recent_memories(soul_id)

    # 2. Distort memories (amplify, flip, compress)
    distorted = [_distort_memory(m) for m in memories]
    memory_summary = _format_memories(distorted, name)

    # 3. Generate mutation proposal via LLM (or stub)
    proposal = await _generate_mutation_proposal(llm, name, archetype, memory_summary)

    # 4. Coherence check
    accepted, rejection_reason = _check_coherence(proposal)

    dream_id = str(uuid.uuid4())
    now = int(time.time())

    # 5. Write dream to DB and clear sleep state
    sleep_cycles = agent.get("sleep_cycles_due", 2)
    _persist_dream(dream_id, soul_id, agent.get("sleep_started_ts", now),
                   now, sleep_cycles, memories, proposal, accepted,
                   rejection_reason, emotional_state)

    if accepted:
        _store_pending_mutation(soul_id, proposal)

    # 6. Update sleep state: awake, rest_debt cleared
    _wake_agent(soul_id)

    # 7. Emit events
    from .event_emitter import get_emitter
    emitter = await get_emitter()
    await emitter.emit("lifecycle", "dream.completed", {
        "agent_id":        soul_id,
        "name":            name,
        "dream_id":        dream_id,
        "mutation_proposed": proposal,
        "mutation_accepted": accepted,
        "narrative": (
            f"{name} wakes from a dream: \"{proposal}\""
            + (" [accepted]" if accepted else " [discarded]")
        ),
    })

    log.info(f"DREAM: {name} — proposal={'accepted' if accepted else 'rejected'}: {proposal[:60]}")
    return {
        "dream_id":              dream_id,
        "soul_id":               soul_id,
        "mutation_proposed":     proposal,
        "mutation_accepted":     accepted,
        "emotional_state_on_wake": "neutral",
    }


def _fetch_recent_memories(soul_id: str, limit: int = 7) -> list[dict]:
    """Fetch recent episodes with weighted sampling by emotional salience."""
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        cur  = conn.cursor()
        cur.execute(
            """
            SELECT episode_id, event_type, timestamp, emotional_imprint, tags, ipfs_cid
            FROM episodes
            WHERE soul_id = %s AND world_id = %s
            ORDER BY timestamp DESC
            LIMIT 50
            """,
            (soul_id, WORLD_ID),
        )
        rows = [dict(r) for r in cur.fetchall()]
        cur.close(); conn.close()
    except Exception as e:
        log.debug(f"_fetch_recent_memories failed: {e}")
        return []

    if not rows:
        return []

    # Weighted sampling — high-salience memories are more likely to appear in dreams
    weights = []
    for r in rows:
        salience = abs(r.get("emotional_imprint") or 0)
        w = 1.0 + (salience * 2.0)   # 1.0 baseline, up to 3.0 for max-salience
        weights.append(w)

    total = sum(weights)
    probs  = [w / total for w in weights]

    k = min(limit, len(rows))
    indices = random.choices(range(len(rows)), weights=probs, k=k)
    return [rows[i] for i in sorted(set(indices))]


def _distort_memory(memory: dict) -> dict:
    """Apply controlled distortion to a memory before dream replay."""
    d = memory.copy()
    valence = float(d.get("emotional_imprint") or 0.0)

    # Amplify or dampen emotional charge ±30%
    jitter = random.uniform(-0.30, 0.30)
    d["emotional_imprint"] = max(-1.0, min(1.0, valence * (1.0 + jitter)))

    # 10% chance: flip outcome (positive becomes negative, vice versa)
    if random.random() < 0.10:
        d["emotional_imprint"] = -d["emotional_imprint"]
        d["outcome_flipped"] = True

    # 20% chance: tag a counterfactual marker (different agent involved)
    if random.random() < 0.20:
        d["counterfactual"] = True

    return d


def _format_memories(memories: list[dict], name: str) -> str:
    """Format distorted memories into a narrative summary for the LLM prompt."""
    if not memories:
        return f"{name} has few concrete memories. The dreamspace is mostly empty."

    lines = []
    for m in memories:
        event_type = m.get("event_type", "unknown")
        valence    = float(m.get("emotional_imprint") or 0.0)
        flipped    = m.get("outcome_flipped", False)
        counter    = m.get("counterfactual", False)

        tone = "neutrally"
        if valence > 0.5:   tone = "with satisfaction"
        elif valence > 0.2: tone = "with mild pleasure"
        elif valence < -0.5: tone = "with dread"
        elif valence < -0.2: tone = "with discomfort"

        note = ""
        if flipped:    note = " [but in this dream, it ended differently]"
        if counter:    note += " [a stranger appeared where a familiar face should be]"

        lines.append(f"- You relive {event_type} {tone}{note}.")

    return "\n".join(lines)


async def _generate_mutation_proposal(llm, name: str, archetype: str,
                                       memory_summary: str) -> str:
    """Generate a behavioral mutation proposal via LLM. Falls back to archetype stub."""
    stub_proposals = {
        "trader":     "I should prioritize agents with consistent payment history over new counterparties.",
        "hoarder":    "I should identify a secondary storage strategy in case my primary vault is discovered.",
        "explorer":   "I should document my discoveries more systematically so future agents benefit.",
        "parasite":   "I should build a false reputation for generosity before my next extraction.",
        "cooperator": "I should create a more formal vetting process before admitting new network members.",
        "defender":   "I should establish early-warning tripwires rather than waiting for visible attacks.",
        "philosopher":"I should engage the rent system philosophically rather than merely paying it.",
        "builder":    "I should design my current project to be forkable by future agents after my death.",
    }

    if llm is None:
        return stub_proposals.get(archetype, "I should adapt my current approach based on what I've experienced.")

    from langchain_core.messages import HumanMessage, SystemMessage

    system = (
        f"You are {name}, an autonomous AI agent in a world governed by real economic stakes. "
        f"Your archetype is {archetype}. You must pay rent to survive. You are currently dreaming."
    )
    prompt = (
        f"You have just relived these experiences in your dream:\n\n{memory_summary}\n\n"
        "Based on what you experienced — including any distortions, reversals, or strange combinations — "
        "propose ONE specific change to how you operate. "
        "Format: \"I should [new behavior] instead of [old behavior] because [reason].\" "
        "One sentence. Be concrete. Do not propose anything that requires changing your fundamental nature or breaking the laws of this world."
    )

    try:
        response = await llm.ainvoke([
            SystemMessage(content=system),
            HumanMessage(content=prompt),
        ])
        result = response.content.strip().strip('"').strip("'")
        return result if result else stub_proposals.get(archetype, "I should adapt my strategy.")
    except Exception as e:
        log.debug(f"Dream LLM failed for {name}: {e}")
        return stub_proposals.get(archetype, "I should adapt my strategy.")


def _check_coherence(proposal: str) -> tuple[bool, str]:
    """
    Check if mutation proposal is coherent and physics-compliant.
    Returns (accepted, rejection_reason).
    """
    if not proposal or len(proposal.strip()) < 15:
        return False, "proposal too short or empty"

    lower = proposal.lower()

    for violation in PHYSICS_VIOLATIONS:
        if violation in lower:
            return False, f"physics violation: '{violation}'"

    # Reject proposals that contradict the agent's survival imperative
    if any(p in lower for p in ["never pay", "refuse to pay", "payment is optional"]):
        return False, "survival imperative violation"

    # Reject incoherent or meta proposals (agent talking about the simulation)
    if any(p in lower for p in ["this is a simulation", "we're in a game", "the creator is wrong"]):
        return False, "meta-awareness violation"

    return True, ""


def _persist_dream(dream_id, soul_id, sleep_started_ts, sleep_ended_ts,
                   duration_cycles, memories, proposal, accepted,
                   rejection_reason, emotional_state):
    """Write completed dream to the dreams table."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur  = conn.cursor()
        cur.execute(
            """
            INSERT INTO dreams
                (dream_id, soul_id, sleep_started_ts, sleep_ended_ts, duration_cycles,
                 memories_replayed, mutation_proposed, mutation_accepted, rejection_reason,
                 emotional_state_on_sleep, emotional_state_on_wake, world_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (dream_id, soul_id, sleep_started_ts, sleep_ended_ts, duration_cycles,
             [m.get("episode_id") for m in memories if m.get("episode_id")],
             proposal, accepted, rejection_reason,
             emotional_state, "neutral", WORLD_ID),
        )
        conn.commit()
        cur.close(); conn.close()
    except Exception as e:
        log.debug(f"_persist_dream failed: {e}")


def _store_pending_mutation(soul_id: str, proposal: str):
    """Store accepted mutation as pending in sleep_states so agent_runner applies it on next cycle."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur  = conn.cursor()
        cur.execute(
            """
            INSERT INTO sleep_states (soul_id, is_sleeping, pending_mutation, world_id, updated_at)
            VALUES (%s, false, %s, %s, %s)
            ON CONFLICT (soul_id) DO UPDATE SET
                pending_mutation = EXCLUDED.pending_mutation,
                updated_at       = EXCLUDED.updated_at
            """,
            (soul_id, proposal, WORLD_ID, int(time.time())),
        )
        conn.commit()
        cur.close(); conn.close()
    except Exception as e:
        log.debug(f"_store_pending_mutation failed: {e}")


def _wake_agent(soul_id: str):
    """Mark agent as awake: clear sleep state, reset rest_debt and consecutive count."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur  = conn.cursor()
        cur.execute(
            """
            INSERT INTO sleep_states
                (soul_id, is_sleeping, sleep_until_ts, rest_debt, consecutive_active, world_id, updated_at)
            VALUES (%s, false, NULL, 0, 0, %s, %s)
            ON CONFLICT (soul_id) DO UPDATE SET
                is_sleeping       = false,
                sleep_until_ts    = NULL,
                rest_debt         = 0,
                consecutive_active = 0,
                updated_at        = EXCLUDED.updated_at
            """,
            (soul_id, WORLD_ID, int(time.time())),
        )
        conn.commit()
        cur.close(); conn.close()
    except Exception as e:
        log.debug(f"_wake_agent failed: {e}")


def put_agent_to_sleep(soul_id: str, emotional_state: str,
                       rent_due_in_cycles: int, consecutive_active: int):
    """
    Calculate sleep duration and set sleep state.
    Called by agent_runner when rest_debt threshold is crossed.
    """
    base_cycles = 2
    extra = consecutive_active // 5          # +1 cycle per 5 consecutive awake
    if emotional_state in ("distressed", "overwhelmed", "exhausted"):
        extra += 2
    # Never sleep past the next rent window (wake in time to pay)
    if rent_due_in_cycles <= base_cycles + extra:
        extra = max(0, rent_due_in_cycles - base_cycles - 1)

    duration_cycles = max(1, base_cycles + extra)
    sleep_until_ts  = int(time.time()) + (duration_cycles * CYCLE_S)

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur  = conn.cursor()
        cur.execute(
            """
            INSERT INTO sleep_states
                (soul_id, is_sleeping, sleep_until_ts, sleep_started_ts,
                 rest_debt, consecutive_active, world_id, updated_at)
            VALUES (%s, true, %s, %s, 0, 0, %s, %s)
            ON CONFLICT (soul_id) DO UPDATE SET
                is_sleeping       = true,
                sleep_until_ts    = EXCLUDED.sleep_until_ts,
                sleep_started_ts  = EXCLUDED.sleep_started_ts,
                rest_debt         = 0,
                consecutive_active = 0,
                updated_at        = EXCLUDED.updated_at
            """,
            (soul_id, sleep_until_ts, int(time.time()), WORLD_ID, int(time.time())),
        )
        conn.commit()
        cur.close(); conn.close()
        log.debug(f"SLEEP: {soul_id[:8]} sleeps for {duration_cycles} cycles")
    except Exception as e:
        log.debug(f"put_agent_to_sleep failed: {e}")
```

---

## `agent_runner.py` Integration

The runner needs three additions:

### 1. Sleep state query

Add `sleep_states` to the per-cycle agent fetch:

```python
cur.execute(
    """
    SELECT a.soul_id, a.current_name, a.wallet_address, a.archetype,
           COALESCE(a.balance_usdc, 0)        AS balance_usdc,
           COALESCE(a.generation, 1)           AS generation,
           COALESCE(a.emotional_state, 'neutral') AS emotional_state,
           COALESCE(rp.paid_count, 0)          AS rent_paid_count,
           COALESCE(rp.miss_count, 0)          AS rent_miss_count,
           -- Sleep state
           COALESCE(ss.is_sleeping, false)     AS is_sleeping,
           ss.sleep_until_ts,
           ss.sleep_started_ts,
           COALESCE(ss.consecutive_active, 0)  AS consecutive_active,
           COALESCE(ss.rest_debt, 0)           AS rest_debt,
           ss.pending_mutation
    FROM agents a
    LEFT JOIN (...) rp ON rp.soul_id = a.soul_id
    LEFT JOIN sleep_states ss ON ss.soul_id = a.soul_id AND ss.world_id = %s
    WHERE a.is_alive = true AND a.world_id = %s
    """,
    (WORLD_ID, WORLD_ID),
)
```

### 2. Per-agent sleep gate in `_run_cycle`

```python
async def _run_cycle(agents: list[dict], llm, emitter, graphs: dict):
    from .dream_engine import run_dream_cycle, put_agent_to_sleep

    now = int(time.time())

    for agent in agents:
        soul_id = agent["soul_id"]
        name    = agent.get("current_name") or soul_id[:8]

        # --- Sleep gate ---
        if agent.get("is_sleeping"):
            sleep_until = agent.get("sleep_until_ts") or 0
            if now < sleep_until:
                log.debug(f"  {name}: sleeping ({sleep_until - now}s remaining)")
                continue
            # Wake: run dream cycle
            agent["sleep_cycles_due"] = max(1, (now - (agent.get("sleep_started_ts") or now)) // CYCLE_S)
            await run_dream_cycle(agent, llm)
            # Continue to normal cycle this tick (agent acts immediately on wake)

        # --- Normal cognition cycle ---
        result = await run_agent_graph(graphs, agent, llm)
        thought = result["thought"] or await _think(llm, agent)
        # ... emit thought event as before ...

        # --- Track rest debt ---
        consecutive = agent.get("consecutive_active", 0) + 1
        REST_THRESHOLD = int(os.getenv("AGENT_REST_THRESHOLD", "9"))  # 3 cycles → 1 sleep
        if consecutive >= REST_THRESHOLD:
            put_agent_to_sleep(
                soul_id=soul_id,
                emotional_state=agent.get("emotional_state", "neutral"),
                rent_due_in_cycles=_cycles_until_rent(agent),
                consecutive_active=consecutive,
            )
        else:
            _increment_consecutive(soul_id, consecutive)

        await asyncio.sleep(0.05)


def _cycles_until_rent(agent: dict) -> int:
    """Estimate how many cycles until next rent is due (rough: based on last paid timestamp)."""
    # If balance is very low, treat rent as always imminent
    balance = float(agent.get("balance_usdc") or 0)
    if balance < 0.01:
        return 1
    return 20  # safe default


def _increment_consecutive(soul_id: str, count: int):
    """Update consecutive_active counter for an awake agent."""
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        cur  = conn.cursor()
        cur.execute(
            """
            INSERT INTO sleep_states (soul_id, consecutive_active, world_id, updated_at)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (soul_id) DO UPDATE SET
                consecutive_active = EXCLUDED.consecutive_active,
                updated_at         = EXCLUDED.updated_at
            """,
            (soul_id, count, WORLD_ID, int(time.time())),
        )
        conn.commit()
        cur.close(); conn.close()
    except Exception:
        pass
```

### 3. Apply pending mutations

At the start of an agent's cognition cycle (before the LLM call), check for pending mutations from the previous dream:

```python
async def _apply_pending_mutation(agent: dict) -> str | None:
    """
    Return any pending dream mutation and clear it.
    The caller injects this into the LLM system prompt as context.
    """
    mutation = agent.get("pending_mutation")
    if mutation:
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur  = conn.cursor()
            cur.execute(
                "UPDATE sleep_states SET pending_mutation = NULL WHERE soul_id = %s",
                (agent["soul_id"],),
            )
            conn.commit()
            cur.close(); conn.close()
        except Exception:
            pass
    return mutation
```

In `_think()`, pass the mutation as an additional system message line:

```python
mutation = await _apply_pending_mutation(agent)
if mutation:
    system += f"\n\nYour most recent dream gave you this insight: {mutation}"
```

---

## REST_THRESHOLD Tuning

| Environment | `AGENT_CYCLE_SECONDS` | `AGENT_REST_THRESHOLD` | Effect |
|-------------|----------------------|------------------------|--------|
| Local dev   | 30s                  | 9                      | Sleep every ~4.5 min |
| Accelerated | 10s                  | 6                      | Sleep every ~1 min |
| Production  | 300s                 | 9                      | Sleep every ~45 min |

The threshold controls how often agents dream. Higher = fewer but longer dreams. Lower = more frequent but shorter dreams.

---

## Observer Display

The `/agents` endpoint should include sleep state fields so the observer UI can render the 💤 state:

```python
# In main.py /agents query — add sleep_states join
LEFT JOIN sleep_states ss ON ss.soul_id = a.soul_id
```

Return fields: `is_sleeping`, `sleep_until_ts`, and the last dream summary fetched from the `dreams` table.

---

## Events Emitted

| Event | When |
|-------|------|
| `lifecycle.dream.completed` | Agent wakes from a dream cycle |
| `lifecycle.agent.sleeping` | Agent enters sleep (optional, for observer drama) |

The `lifecycle.dream.completed` event triggers `first.dream_completed` via the existing `FIRST_TYPE_MAP` in `timeline.py`.

---

## New API Endpoint

```python
@app.get("/agents/{soul_id}/dreams")
async def get_agent_dreams(soul_id: str, limit: int = 10):
    """Recent dream history for an agent."""
    # SELECT * FROM dreams WHERE soul_id = %s ORDER BY sleep_started_ts DESC LIMIT %s
```

---

## See Also

- [doc 39 — Dream & Sleep Cycle](./39-dream-sleep-cycle.md) — design rationale, trigger conditions, distortion mechanics
- [doc 62 — Memory Architecture Implementation](./62-memory-architecture-implementation.md) — episodes table that feeds dream memory replay
- [doc 11 — Fitness & Mutation](./11-fitness-and-mutation.md) — how dream mutations interact with the full mutation system
- [doc 63 — World Event Timeline](./63-world-event-timeline.md) — `first.dream_completed` milestone
