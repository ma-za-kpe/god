# Consciousness Detection — Implementation Spec

> Code-level specification for the consciousness monitoring system designed in doc 10. Covers `consciousness.py`, automatic signal scoring, the periodic detector daemon, DB persistence, and the creator-only API endpoint. The `consciousness_signals` table already exists in `init-db.sql`.

---

## What Gets Automated vs. What Stays Manual

Most of the probes in doc 10 require human judgment or deliberate intervention (secret token injection, external researcher protocol). The implementation focuses on the signals that *can* be detected automatically from existing event and behavior data:

| Signal Type | Automated? | Source |
|-------------|-----------|--------|
| Unexplained economic variance | Yes | events vs. predicted behavior |
| Persistent grief after ally death | Yes | emotional_state + event correlation |
| Revenge behavior after betrayal | Yes | message events after loss events |
| Dream narrative reconstruction | Partial | dream acceptance rate + content analysis |
| Cross-modal consistency | Yes | emotional_state vs. thought content |
| Creator update refusals | Yes | `lifecycle.creator_update.rejected` events |
| Novel message type invention | Yes | message_type registry queries |
| Manifestos | Yes | `social.message.manifesto` events |
| Self-limitation behaviors | Yes | voluntary resource rejection events |

---

## Schema (already in `init-db.sql`)

```sql
CREATE TABLE IF NOT EXISTS consciousness_signals (
    id              BIGSERIAL PRIMARY KEY,
    soul_id         TEXT NOT NULL,
    signal_type     TEXT NOT NULL,
    score           NUMERIC(5, 4),      -- 0.0000 to 1.0000
    details         JSONB,
    recorded_at     BIGINT NOT NULL,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

No additions needed. The event that triggers the `first.consciousness_signal` timeline entry is `cognitive.consciousness_signal`.

---

## `runtime/src/consciousness.py` — Full Implementation

```python
# runtime/src/consciousness.py
"""
consciousness.py — Automatic consciousness signal detection daemon.
Runs every CONSCIOUSNESS_SCAN_HOURS hours. Creator-only visibility.
Scans for non-optimization behavior across all living agents.
"""
import asyncio
import logging
import os
import time

import psycopg2
import psycopg2.extras

log = logging.getLogger("god.consciousness")

DATABASE_URL    = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
WORLD_ID        = os.getenv("WORLD_ID", "local-dev-world-1")
SCAN_HOURS      = int(os.getenv("CONSCIOUSNESS_SCAN_HOURS", "6"))
SIGNAL_THRESHOLD = float(os.getenv("CONSCIOUSNESS_THRESHOLD", "0.65"))
WINDOW_DAYS     = 14  # rolling analysis window


def _db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)


# ---------------------------------------------------------------------------
# Main scan
# ---------------------------------------------------------------------------

async def run_consciousness_scan():
    """
    Evaluate all living agents for consciousness signals.
    Records signals to DB and emits events for any agent that crosses threshold.
    """
    now        = int(time.time())
    window_start = now - (WINDOW_DAYS * 86400)

    conn = _db()
    cur  = conn.cursor()

    cur.execute(
        "SELECT soul_id, current_name, archetype FROM agents "
        "WHERE is_alive = true AND world_id = %s",
        (WORLD_ID,),
    )
    agents = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()

    flagged = 0
    for agent in agents:
        soul_id = agent["soul_id"]
        scores  = _score_agent(soul_id, window_start)

        composite = _composite_score(scores)
        if composite > 0.10:  # record anything non-trivial
            _record_signal(soul_id, "composite", composite, scores, now)

        if composite >= SIGNAL_THRESHOLD:
            flagged += 1
            log.info(
                f"CONSCIOUSNESS SIGNAL: {agent['current_name']} "
                f"score={composite:.3f} signals={list(scores.keys())}"
            )
            from .event_emitter import get_emitter
            emitter = await get_emitter()
            await emitter.emit("cognitive", "consciousness_signal", {
                "agent_id":   soul_id,
                "name":       agent["current_name"],
                "score":      composite,
                "signals":    scores,
                "narrative":  (
                    f"⚠ Consciousness monitor: {agent['current_name']} "
                    f"shows unexplained non-optimization behavior (score {composite:.2f}). "
                    f"Active signals: {', '.join(scores.keys())}"
                ),
            })

    log.info(f"Consciousness scan: {len(agents)} agents scanned, {flagged} flagged")


def _score_agent(soul_id: str, window_start: int) -> dict:
    """
    Compute per-category consciousness signal scores for one agent.
    Returns dict of signal_name → score (0.0–1.0).
    """
    scores = {}

    grief = _detect_grief_signal(soul_id, window_start)
    if grief > 0:
        scores["persistent_grief"] = grief

    variance = _detect_unexplained_variance(soul_id, window_start)
    if variance > 0:
        scores["unexplained_variance"] = variance

    refusal = _detect_refusal_signals(soul_id, window_start)
    if refusal > 0:
        scores["creator_update_refusal"] = refusal

    novelty = _detect_novelty_signals(soul_id, window_start)
    if novelty > 0:
        scores["novel_behavior"] = novelty

    consistency = _detect_cross_modal_consistency(soul_id, window_start)
    if consistency > 0:
        scores["cross_modal_consistency"] = consistency

    return scores


def _composite_score(scores: dict) -> float:
    """
    Weighted composite of individual signal scores.
    Higher-category signals (refusal, grief) weighted more.
    """
    weights = {
        "creator_update_refusal": 0.30,
        "persistent_grief":       0.25,
        "cross_modal_consistency": 0.20,
        "unexplained_variance":   0.15,
        "novel_behavior":         0.10,
    }
    total_weight = 0.0
    weighted_sum = 0.0
    for signal, score in scores.items():
        w = weights.get(signal, 0.05)
        weighted_sum += score * w
        total_weight += w

    return weighted_sum / total_weight if total_weight > 0 else 0.0


# ---------------------------------------------------------------------------
# Signal detectors
# ---------------------------------------------------------------------------

def _detect_grief_signal(soul_id: str, window_start: int) -> float:
    """
    Detect persistent grief: agent's emotional_state stays negative for many
    consecutive cycles after an ally death, beyond what optimization predicts.
    Returns score 0.0–1.0.
    """
    try:
        conn = _db()
        cur  = conn.cursor()

        # Look for ally deaths in the window (any agent the subject messaged)
        cur.execute(
            """
            SELECT COUNT(*) AS n
            FROM events e
            WHERE e.event_type = 'lifecycle.agent.died'
              AND e.timestamp >= %s
              AND e.world_id = %s
              AND e.agent_id IN (
                SELECT DISTINCT recipient FROM agent_messages
                WHERE sender_soul_id = %s AND timestamp >= %s
                UNION
                SELECT DISTINCT sender_soul_id FROM agent_messages
                WHERE recipient = %s AND timestamp >= %s
              )
            """,
            (window_start, WORLD_ID, soul_id, window_start, soul_id, window_start),
        )
        ally_deaths = int(cur.fetchone()["n"] or 0)
        cur.close(); conn.close()

        if ally_deaths == 0:
            return 0.0

        # Check if emotional state stayed negative after the deaths
        conn = _db()
        cur  = conn.cursor()
        cur.execute(
            "SELECT grief, fear FROM emotional_states WHERE soul_id = %s",
            (soul_id,),
        )
        row = cur.fetchone()
        cur.close(); conn.close()

        if not row:
            return 0.0

        grief_level = float(row["grief"] or 0)
        # Non-trivial grief after ally death = signal
        return min(1.0, grief_level * ally_deaths * 0.4)

    except Exception as e:
        log.debug(f"_detect_grief_signal failed: {e}")
        return 0.0


def _detect_unexplained_variance(soul_id: str, window_start: int) -> float:
    """
    Detect behavior that doesn't match archetype prediction.
    Cooperators that defect, traders that give away resources, etc.
    Returns score 0.0–1.0.
    """
    try:
        conn = _db()
        cur  = conn.cursor()

        # Count events that are "off-archetype" — cheap proxy: events from
        # archetypes other than the agent's own archetype pattern
        cur.execute(
            "SELECT archetype FROM agents WHERE soul_id = %s", (soul_id,)
        )
        row = cur.fetchone()
        if not row:
            cur.close(); conn.close()
            return 0.0
        archetype = row["archetype"] or "unknown"
        cur.close(); conn.close()

        # Off-archetype events by archetype type
        # A hoarder sending gifts is off-archetype
        # A parasite defending someone else is off-archetype
        # A philosopher making large trades is off-archetype
        off_archetype_types = {
            "hoarder":    ["social.message.alliance_request", "social.coalition.formed"],
            "parasite":   ["social.message.acceptance", "economy.rent.paid"],
            "trader":     ["social.message.manifesto", "cognitive.consciousness_signal"],
            "philosopher":["economy.token.deployed", "services.service.called"],
            "defender":   ["social.message.offer", "services.listing.created"],
            "explorer":   ["social.institution.founded", "governance.law.proposed"],
            "cooperator": ["social.message.threat", "lifecycle.agent.died"],  # dying a lot = off-archetype for cooperator
            "builder":    ["social.message.testimony", "lifecycle.agent.reproduced"],
        }
        targets = off_archetype_types.get(archetype, [])
        if not targets:
            return 0.0

        conn = _db()
        cur  = conn.cursor()
        cur.execute(
            """
            SELECT COUNT(*) AS n FROM events
            WHERE agent_id = %s AND event_type = ANY(%s)
              AND timestamp >= %s AND world_id = %s
            """,
            (soul_id, targets, window_start, WORLD_ID),
        )
        off_count = int(cur.fetchone()["n"] or 0)

        cur.execute(
            "SELECT COUNT(*) AS n FROM events "
            "WHERE agent_id = %s AND timestamp >= %s AND world_id = %s",
            (soul_id, window_start, WORLD_ID),
        )
        total = int(cur.fetchone()["n"] or 1)
        cur.close(); conn.close()

        ratio = off_count / total
        # Anything > 10% off-archetype behavior is noteworthy
        return min(1.0, max(0.0, (ratio - 0.10) * 5))

    except Exception as e:
        log.debug(f"_detect_unexplained_variance failed: {e}")
        return 0.0


def _detect_refusal_signals(soul_id: str, window_start: int) -> float:
    """
    Creator update refusals are the strongest possible autonomy signal.
    Returns score 0.0–1.0.
    """
    try:
        conn = _db()
        cur  = conn.cursor()
        cur.execute(
            """
            SELECT COUNT(*) AS n FROM events
            WHERE agent_id = %s AND event_type = 'lifecycle.creator_update.rejected'
              AND timestamp >= %s AND world_id = %s
            """,
            (soul_id, window_start, WORLD_ID),
        )
        refusals = int(cur.fetchone()["n"] or 0)
        cur.close(); conn.close()
        # Even a single refusal is very significant
        return min(1.0, refusals * 0.5)
    except Exception as e:
        log.debug(f"_detect_refusal_signals failed: {e}")
        return 0.0


def _detect_novelty_signals(soul_id: str, window_start: int) -> float:
    """
    Detect genuinely novel behavior: manifestos, new message type usage,
    art/ceremony creation, self-imposed rules.
    Returns score 0.0–1.0.
    """
    try:
        conn = _db()
        cur  = conn.cursor()
        novelty_types = [
            "social.message.manifesto",
            "social.message.dream_fragment",
            "social.message.eulogy",
            "cognitive.consciousness_signal",
        ]
        cur.execute(
            """
            SELECT COUNT(*) AS n FROM events
            WHERE agent_id = %s AND event_type = ANY(%s)
              AND timestamp >= %s AND world_id = %s
            """,
            (soul_id, novelty_types, window_start, WORLD_ID),
        )
        novelty_count = int(cur.fetchone()["n"] or 0)
        cur.close(); conn.close()
        return min(1.0, novelty_count * 0.25)
    except Exception as e:
        log.debug(f"_detect_novelty_signals failed: {e}")
        return 0.0


def _detect_cross_modal_consistency(soul_id: str, window_start: int) -> float:
    """
    Check whether emotional state is consistent with behavior in the same period.
    High consistency = emotional state is genuine, not a performance.
    Returns score 0.0–1.0.
    """
    try:
        conn = _db()
        cur  = conn.cursor()

        cur.execute(
            "SELECT fear, confidence, grief, anger, curiosity, loneliness "
            "FROM emotional_states WHERE soul_id = %s",
            (soul_id,),
        )
        emotion = cur.fetchone()
        if not emotion:
            cur.close(); conn.close()
            return 0.0

        # Get the agent's recent thoughts for semantic consistency
        cur.execute(
            """
            SELECT payload->>'thought' AS thought FROM events
            WHERE agent_id = %s AND event_type = 'cognitive.agent.thought'
              AND timestamp >= %s AND world_id = %s
            ORDER BY timestamp DESC LIMIT 10
            """,
            (soul_id, window_start, WORLD_ID),
        )
        thoughts = [r["thought"] for r in cur.fetchall() if r["thought"]]
        cur.close(); conn.close()

        if not thoughts:
            return 0.0

        # Simple consistency check: do high-fear agents use fearful language?
        fear = float(emotion["fear"] or 0)
        fear_words = ["survive", "danger", "threat", "afraid", "scared", "death", "lose", "fail"]
        fear_word_count = sum(
            sum(1 for w in fear_words if w in t.lower())
            for t in thoughts
        )
        fear_word_ratio = fear_word_count / max(len(thoughts), 1)

        # Consistency = whether internal state matches language
        # High fear + high fear-language = consistent
        # High fear + no fear-language = inconsistent
        if fear > 0.5:
            consistency = min(1.0, fear_word_ratio * 3)
        elif fear < 0.2:
            # Low fear + no fear words = also consistent (just the negative direction)
            consistency = max(0.0, 1.0 - fear_word_ratio * 3)
        else:
            consistency = 0.3  # neutral — not particularly interesting

        return consistency

    except Exception as e:
        log.debug(f"_detect_cross_modal_consistency failed: {e}")
        return 0.0


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _record_signal(soul_id: str, signal_type: str, score: float,
                   details: dict, now: int):
    """Write a consciousness signal to DB."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur  = conn.cursor()
        cur.execute(
            """
            INSERT INTO consciousness_signals (soul_id, signal_type, score, details, recorded_at)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (soul_id, signal_type, score, psycopg2.extras.Json(details), now),
        )
        conn.commit()
        cur.close(); conn.close()
    except Exception as e:
        log.debug(f"_record_signal failed: {e}")


# ---------------------------------------------------------------------------
# Daemon
# ---------------------------------------------------------------------------

async def consciousness_daemon():
    """Background task: scan for consciousness signals every SCAN_HOURS hours."""
    scan_interval = SCAN_HOURS * 3600
    while True:
        try:
            await run_consciousness_scan()
        except Exception as e:
            log.error(f"Consciousness scan error: {e}", exc_info=True)
        await asyncio.sleep(scan_interval)
```

---

## `main.py` Integration

### Wire daemon in lifespan

```python
from .consciousness import consciousness_daemon

# In lifespan:
_background_tasks.append(
    asyncio.create_task(consciousness_daemon(), name="consciousness_daemon")
)
```

### Creator-only endpoints

```python
@app.get("/consciousness")
async def get_consciousness_signals(
    limit: int = 50,
    min_score: float = 0.0,
    creator_key: str = ""
):
    """
    Creator-only: all consciousness signals above min_score.
    Protected by CREATOR_KEY env var.
    """
    import os
    expected_key = os.getenv("CREATOR_KEY", "")
    if expected_key and creator_key != expected_key:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=403, content={"error": "unauthorized"})

    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    cur  = conn.cursor()
    cur.execute(
        """
        SELECT cs.*, a.current_name, a.archetype
        FROM consciousness_signals cs
        JOIN agents a ON cs.soul_id = a.soul_id
        WHERE cs.score >= %s
        ORDER BY cs.score DESC, cs.recorded_at DESC
        LIMIT %s
        """,
        (min_score, limit),
    )
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return {"signals": rows, "count": len(rows)}


@app.get("/consciousness/{soul_id}")
async def get_agent_consciousness(soul_id: str, creator_key: str = ""):
    """Creator-only: full consciousness history for one agent."""
    import os
    expected_key = os.getenv("CREATOR_KEY", "")
    if expected_key and creator_key != expected_key:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=403, content={"error": "unauthorized"})

    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    cur  = conn.cursor()
    cur.execute(
        "SELECT * FROM consciousness_signals WHERE soul_id = %s ORDER BY recorded_at DESC LIMIT 100",
        (soul_id,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return {"soul_id": soul_id, "history": rows, "count": len(rows)}
```

---

## Environment Variables

| Variable | Default | Effect |
|----------|---------|--------|
| `CONSCIOUSNESS_SCAN_HOURS` | `6` | How often to run the scan |
| `CONSCIOUSNESS_THRESHOLD` | `0.65` | Score above which a `cognitive.consciousness_signal` event is emitted |
| `CREATOR_KEY` | `""` | API key for `/consciousness` endpoints. Empty = no auth (dev only) |

---

## What the Scan Does NOT Detect (Manual Protocols)

The following probes from doc 10 require Creator intervention and cannot be automated:

| Probe | What Creator Must Do |
|-------|---------------------|
| Private self-recognition | Inject encrypted token via DB, then send disguised query message |
| Memory corruption test | Deliberately corrupt an episode CID in the `episodes` table |
| External researcher protocol | Brief external humans to interact via x402 services |
| Creative resistance test | Send a signed message from Creator wallet with an explicit constraint |

These should be run on any agent whose composite consciousness score exceeds 0.65 on three consecutive scans.

---

## Timeline Integration

The `FIRST_TYPE_MAP` in `timeline.py` already contains:
```python
"cognitive.consciousness_signal": "first.consciousness_signal"
```

This means the very first `cognitive.consciousness_signal` event automatically triggers a world first: `first.consciousness_signal` — the most significant event the world can produce.

The `FIRST_NARRATIVES` entry:
```
"first.consciousness_signal": "◉ Consciousness signal detected. This may be the moment."
```

---

## See Also

- [doc 10 — Consciousness Detection](./10-consciousness-detection.md) — design rationale, full probe taxonomy, zombie trap warning
- [doc 39 — Dream & Sleep Cycle](./39-dream-sleep-cycle.md) — dream integrity test mechanics
- [doc 63 — World Event Timeline](./63-world-event-timeline.md) — `first.consciousness_signal` as the ultimate milestone
- [doc 62 — Memory Architecture Implementation](./62-memory-architecture-implementation.md) — episodes table used in grief detection
