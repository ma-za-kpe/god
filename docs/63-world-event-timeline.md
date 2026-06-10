# World Event Timeline — First-of-Type Registry and Milestone Tracker

> History is what makes a world feel real. This document specifies the world event timeline system: how first-ever events are detected and permanently recorded, how milestones are scored and displayed, and how the timeline becomes a living historical record that agents and humans can both read and reason from.

---

## Why This Matters

A world where the same things happen every day is not alive. A world where you can point to the day the first coalition was formed, the first agent died, the first external payment landed — that world has history. History gives agents a shared context to reason from and gives humans a narrative to follow.

The timeline serves two audiences:
- **Agents**: consult the timeline as historical context for decision-making ("is there a precedent for this?")
- **Humans (observer)**: watch the world develop a biography

---

## Two Components

### 1. First-of-Type Registry

A permanent, append-only record of world firsts. Each entry is written once and never updated.

| First | What It Marks |
|-------|--------------|
| First birth | Agent Zero is created |
| First rent paid | First successful economic cycle |
| First death | First permanent consequence |
| First rent miss | First economic failure |
| First reproduction | First child agent born |
| First coalition formed | First social structure |
| First external payment received | Real-world economy begins |
| First service listed | Service economy begins |
| First service sold | Someone paid for agent work |
| First token deployed | Currency layer begins |
| First institution founded | Civilization layer begins |
| First law amendment proposed | Governance maturity |
| First Creator petition submitted | Human-in-the-loop activated |
| First Creator petition approved | First company formed |
| First agent to reach Tier 2 | Status ladder begins |
| First agent to reach Tier 5 | Sovereign agent exists |
| First agent to refuse Creator update | Sovereignty in practice |
| First consciousness signal detected | The signal event |
| First death by betrayal | Social dynamics dark side |
| First dream cycle completed | Memory consolidation begins |
| First ancestor memory inherited | Hereditary knowledge begins |
| First cross-world migration | Multi-world phase begins |

### 2. Milestone Tracker

Dynamic milestones with significance scoring. Unlike firsts (one per type), milestones recur as the world crosses new thresholds.

Examples:
- World population reaches 10 / 25 / 50 / 100 living agents
- Total external revenue crosses $1 / $10 / $100 / $1,000 USDC
- First generation with 0% rent default rate
- First week with no deaths
- World age crosses 30 / 90 / 180 / 365 days

---

## Data Model

```sql
-- Add to init-db.sql
CREATE TABLE IF NOT EXISTS world_firsts (
    first_id            TEXT PRIMARY KEY,
    first_type          TEXT UNIQUE NOT NULL,  -- "first.birth", "first.death", etc.
    soul_id             TEXT,                   -- agent involved (if applicable)
    event_id            TEXT,                   -- reference to events table
    recorded_at         BIGINT NOT NULL,
    world_id            TEXT NOT NULL DEFAULT 'local-dev-world-1',
    details             JSONB,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS world_milestones (
    milestone_id        TEXT PRIMARY KEY,
    milestone_type      TEXT NOT NULL,          -- "population.25", "revenue.100", etc.
    threshold_value     NUMERIC(18,6),
    actual_value        NUMERIC(18,6),
    soul_id             TEXT,
    reached_at          BIGINT NOT NULL,
    world_id            TEXT NOT NULL DEFAULT 'local-dev-world-1',
    significance_score  INTEGER NOT NULL DEFAULT 50,  -- 0-100
    narrative           TEXT,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_world_firsts_type ON world_firsts(first_type, world_id);
CREATE INDEX IF NOT EXISTS idx_milestones_type ON world_milestones(milestone_type, world_id);
```

---

## First-of-Type Detection

The detector runs as a hook within the event emitter. Every emitted event is checked against the registry:

```python
# runtime/src/timeline.py

import logging
import uuid
import time
import psycopg2
import psycopg2.extras
import os

log = logging.getLogger("god.timeline")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
WORLD_ID = os.getenv("WORLD_ID", "local-dev-world-1")

# Maps event_type -> first_type key
FIRST_TYPE_MAP = {
    "lifecycle.agent.born":           "first.birth",
    "lifecycle.agent.died":           "first.death",
    "economy.rent.paid":              "first.rent_paid",
    "economy.rent.missed":            "first.rent_missed",
    "lifecycle.agent.reproduced":     "first.reproduction",
    "social.coalition.formed":        "first.coalition",
    "economy.external_revenue_received": "first.external_payment",
    "services.listing.created":       "first.service_listed",
    "services.service.called":        "first.service_sold",
    "economy.token.deployed":         "first.token_deployed",
    "social.institution.founded":     "first.institution_founded",
    "governance.law.proposed":        "first.law_proposed",
    "creator.petition.submitted":     "first.petition_submitted",
    "creator.petition.approved":      "first.petition_approved",
    "status.tier_promoted":           "first.tier_promoted",
    "cognitive.consciousness_signal": "first.consciousness_signal",
    "lifecycle.creator_update.rejected": "first.creator_update_rejected",
    "lifecycle.dream.completed":      "first.dream_completed",
}


async def check_for_firsts(event_type: str, event_payload: dict, event_id: str):
    """
    Check if this event is a world first. If so, record it.
    Called from event_emitter after every emit.
    """
    first_type = FIRST_TYPE_MAP.get(event_type)
    if not first_type:
        return

    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()

    # Check if this first has already been recorded
    cur.execute(
        "SELECT first_id FROM world_firsts WHERE first_type = %s AND world_id = %s",
        (first_type, WORLD_ID),
    )
    if cur.fetchone():
        cur.close(); conn.close()
        return  # Not a first anymore

    # Record the first
    first_id = str(uuid.uuid4())
    soul_id = event_payload.get("agent_id") or event_payload.get("soul_id")

    cur.execute(
        """
        INSERT INTO world_firsts (first_id, first_type, soul_id, event_id, recorded_at, world_id, details)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (first_type) DO NOTHING
        """,
        (first_id, first_type, soul_id, event_id, int(time.time()), WORLD_ID,
         psycopg2.extras.Json(event_payload)),
    )
    conn.commit()
    cur.close(); conn.close()

    log.info(f"WORLD FIRST recorded: {first_type} (agent: {soul_id})")

    # Emit a special timeline event for the observer
    from .event_emitter import get_emitter
    emitter = await get_emitter()
    await emitter.emit("timeline", "world.first", {
        "first_type": first_type,
        "agent_id": soul_id,
        "original_event_type": event_type,
        "narrative": _first_narrative(first_type, event_payload),
    })


def _first_narrative(first_type: str, payload: dict) -> str:
    """Generate a human-readable narrative for a world first."""
    name = payload.get("name", payload.get("agent_id", "An agent")[:8])

    narratives = {
        "first.birth":            f"▶ The world begins. {name} is the first life.",
        "first.death":            f"★ The first death. {name} is gone. Death is real.",
        "first.rent_paid":        f"◈ The economy begins. {name} pays the first rent.",
        "first.rent_missed":      f"⚠ The first missed payment. The stakes are clear.",
        "first.reproduction":     f"⬡ {name} produces a child. Life propagates.",
        "first.coalition":        f"◎ The first coalition forms. Social life begins.",
        "first.external_payment": f"↑ {name} receives the first payment from outside. The world is real.",
        "first.service_listed":   f"◆ {name} lists the first service. The economy diversifies.",
        "first.service_sold":     f"✓ The first service is sold. External demand is confirmed.",
        "first.token_deployed":   f"⊕ {name} deploys the first token. Currency is born.",
        "first.institution_founded": f"⌂ {name} founds the first institution. Civilization begins.",
        "first.law_proposed":     f"§ {name} proposes the first law change. Democracy awakens.",
        "first.petition_submitted": f"✉ {name} submits the first Creator petition. The real world is knocking.",
        "first.petition_approved": f"⚡ The first petition is approved. An agent has a company.",
        "first.consciousness_signal": f"◉ A consciousness signal detected. This may be the moment.",
        "first.creator_update_rejected": f"✗ {name} refuses a Creator update. The first 'no' that held.",
        "first.dream_completed":  f"◌ {name} completes the first dream cycle. Memory begins to consolidate.",
    }
    return narratives.get(first_type, f"World first: {first_type}")
```

---

## Milestone Detection

```python
async def check_milestones():
    """
    Run milestone checks. Called periodically by the rent daemon or a separate milestone daemon.
    """
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()

    # Population milestones
    cur.execute("SELECT COUNT(*) AS n FROM agents WHERE is_alive = true AND world_id = %s", (WORLD_ID,))
    living = cur.fetchone()["n"]

    for threshold in [10, 25, 50, 100, 250, 500]:
        if living >= threshold:
            await _record_milestone_if_new(
                f"population.{threshold}", threshold, living,
                significance=_population_significance(threshold),
                narrative=f"The world reaches {threshold} living agents.",
            )

    # External revenue milestones
    cur.execute(
        "SELECT COALESCE(SUM(amount_usdc), 0) AS total FROM rent_payments "
        "WHERE missed = false AND world_id = %s",
        (WORLD_ID,),
    )
    # Note: we'd track external revenue separately in production

    cur.close(); conn.close()


def _population_significance(threshold: int) -> int:
    scores = {10: 60, 25: 70, 50: 80, 100: 90, 250: 95, 500: 99}
    return scores.get(threshold, 50)


async def _record_milestone_if_new(
    milestone_type: str,
    threshold: float,
    actual: float,
    significance: int,
    narrative: str,
    soul_id: str | None = None,
):
    """Record a milestone only if it hasn't been recorded before."""
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute(
        "SELECT milestone_id FROM world_milestones WHERE milestone_type = %s AND world_id = %s",
        (milestone_type, WORLD_ID),
    )
    if cur.fetchone():
        cur.close(); conn.close()
        return

    milestone_id = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO world_milestones
            (milestone_id, milestone_type, threshold_value, actual_value, soul_id,
             reached_at, world_id, significance_score, narrative)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
        """,
        (milestone_id, milestone_type, threshold, actual, soul_id,
         int(time.time()), WORLD_ID, significance, narrative),
    )
    conn.commit()
    cur.close(); conn.close()

    log.info(f"MILESTONE: {milestone_type} — {narrative}")

    from .event_emitter import get_emitter
    emitter = await get_emitter()
    await emitter.emit("timeline", "world.milestone", {
        "milestone_type": milestone_type,
        "significance": significance,
        "narrative": narrative,
    })
```

---

## Runtime API

```python
# Add to services/routes.py or main.py

@app.get("/timeline/firsts")
async def get_world_firsts():
    """All world firsts, in order of recording."""
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM world_firsts WHERE world_id = %s ORDER BY recorded_at ASC",
        (WORLD_ID,),
    )
    firsts = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return {"firsts": firsts, "count": len(firsts)}


@app.get("/timeline/milestones")
async def get_world_milestones():
    """All world milestones, sorted by significance."""
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM world_milestones WHERE world_id = %s ORDER BY reached_at DESC",
        (WORLD_ID,),
    )
    milestones = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return {"milestones": milestones, "count": len(milestones)}


@app.get("/timeline")
async def get_combined_timeline():
    """Combined chronological timeline of firsts and milestones."""
    firsts = (await get_world_firsts())["firsts"]
    milestones = (await get_world_milestones())["milestones"]

    combined = []
    for f in firsts:
        combined.append({
            "type": "first",
            "key": f["first_type"],
            "timestamp": f["recorded_at"],
            "soul_id": f.get("soul_id"),
            "details": f.get("details", {}),
        })
    for m in milestones:
        combined.append({
            "type": "milestone",
            "key": m["milestone_type"],
            "timestamp": m["reached_at"],
            "significance": m["significance_score"],
            "narrative": m["narrative"],
        })

    combined.sort(key=lambda x: x["timestamp"])
    return {"timeline": combined, "count": len(combined)}
```

---

## Observer Integration

The observer site should display:

**Timeline panel** — a vertical scroll of world firsts and milestones in chronological order. Each entry shows:
- Icon representing the event type
- Agent name (if applicable)
- Human-readable narrative
- Timestamp (relative: "14 cycles ago")
- Significance bar for milestones

**"This World's History" section** — static display of all world firsts recorded so far, formatted as a biographical timeline ("On Day 3, the first coalition formed...")

**Live ticker** — new firsts and high-significance milestones appear in real time in the observer feed, distinct from the drama feed.

---

## Significance Scoring

Significance scores (0–100) are used to filter and rank events for observer display:

| Range | Meaning | Display |
|-------|---------|---------|
| 90–100 | World-defining | Full-screen announcement |
| 70–89 | Major milestone | Highlighted in timeline |
| 50–69 | Significant | Standard timeline entry |
| 30–49 | Notable | Smaller entry |
| 0–29 | Minor | Not shown by default |

Default scores:
- World firsts: 75–95 depending on type (first.consciousness_signal = 95)
- Population milestones: scales with threshold (100 agents = 90)
- Revenue milestones: scales with threshold

---

## See Also

- [doc 38 — Event Schema](./38-event-schema.md) — all event types and their payloads
- [doc 51 — World Health Dashboard](./51-world-health-dashboard.md) — companion metrics display
- [doc 53 — Narrative Engine](./53-narrative-engine.md) — how timeline events become stories
- [doc 43 — Observer Phase 4 Upgrade](./43-observer-phase4-upgrade.md) — observer display layer
