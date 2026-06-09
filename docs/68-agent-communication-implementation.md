# Agent Communication Protocol — Implementation Spec

> Code-level specification for the agent communication system designed in doc 23. Covers the `messaging.py` module, AgentMessage schema, NATS JetStream routing, DB persistence, inbox processing in the cognition cycle, and reputation tracking. Detailed enough to implement directly.

---

## Schema

```sql
-- Message log (all sent messages, for audit and replay)
CREATE TABLE IF NOT EXISTS agent_messages (
    message_id          TEXT PRIMARY KEY,
    sender_soul_id      TEXT NOT NULL,
    recipient           TEXT NOT NULL,   -- soul_id | "broadcast" | "coalition:<id>"
    message_type        TEXT NOT NULL,
    payload             JSONB,
    price_to_read       NUMERIC(18,6) NOT NULL DEFAULT 0,
    is_encrypted        BOOLEAN NOT NULL DEFAULT FALSE,
    is_public           BOOLEAN NOT NULL DEFAULT TRUE,
    observer_narrative  TEXT,
    previous_message_id TEXT,
    timestamp_sent      BIGINT NOT NULL,
    ttl_seconds         INTEGER NOT NULL DEFAULT 3600,
    expires_at          BIGINT NOT NULL,
    world_id            TEXT NOT NULL DEFAULT 'local-dev-world-1',
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Per-agent reputation model (private to each observer)
CREATE TABLE IF NOT EXISTS reputation (
    id                      BIGSERIAL PRIMARY KEY,
    observer_soul_id        TEXT NOT NULL,
    subject_soul_id         TEXT NOT NULL,
    interaction_count       INTEGER NOT NULL DEFAULT 0,
    contracts_honored       INTEGER NOT NULL DEFAULT 0,
    contracts_broken        INTEGER NOT NULL DEFAULT 0,
    threats_followed_through INTEGER NOT NULL DEFAULT 0,
    threats_bluffed         INTEGER NOT NULL DEFAULT 0,
    gifts_given             INTEGER NOT NULL DEFAULT 0,
    betrayals_committed     INTEGER NOT NULL DEFAULT 0,
    contract_reliability    NUMERIC(5,4) NOT NULL DEFAULT 0.5,
    threat_credibility      NUMERIC(5,4) NOT NULL DEFAULT 0.5,
    gift_reciprocity        NUMERIC(5,4) NOT NULL DEFAULT 0.5,
    personal_trust_score    NUMERIC(5,4) NOT NULL DEFAULT 0.5,
    public_reputation_score NUMERIC(5,4) NOT NULL DEFAULT 0.5,
    last_interaction_at     BIGINT NOT NULL DEFAULT 0,
    world_id                TEXT NOT NULL DEFAULT 'local-dev-world-1',
    UNIQUE(observer_soul_id, subject_soul_id)
);

CREATE INDEX IF NOT EXISTS idx_messages_recipient ON agent_messages(recipient, timestamp_sent DESC);
CREATE INDEX IF NOT EXISTS idx_messages_sender ON agent_messages(sender_soul_id, timestamp_sent DESC);
CREATE INDEX IF NOT EXISTS idx_reputation_observer ON reputation(observer_soul_id, world_id);
```

---

## `runtime/src/messaging.py` — Full Implementation

```python
# runtime/src/messaging.py
"""
messaging.py — Agent-to-agent message routing via NATS JetStream.
Subject convention:
  world.{world_id}.agent.{soul_id}.inbox     — direct messages
  world.{world_id}.broadcast                  — world-wide broadcasts
  world.{world_id}.coalition.{id}.channel     — coalition group channels
"""
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from decimal import Decimal
from typing import Optional

import psycopg2
import psycopg2.extras

log = logging.getLogger("god.messaging")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
WORLD_ID     = os.getenv("WORLD_ID", "local-dev-world-1")

VALID_MESSAGE_TYPES = {
    "offer", "acceptance", "rejection", "contract", "threat",
    "alliance_request", "broadcast", "testimony", "eulogy",
    "manifesto", "dream_fragment", "petition", "silence",
}

# Messages targeting these types always go to the observer feed
ALWAYS_PUBLIC_TYPES = {"contract", "threat", "broadcast", "eulogy", "manifesto", "petition"}


@dataclass
class AgentMessage:
    sender_soul_id:     str
    recipient:          str         # soul_id | "broadcast" | "coalition:<id>"
    message_type:       str
    payload:            dict

    message_id:         str         = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp_sent:     int         = field(default_factory=lambda: int(time.time()))
    ttl_seconds:        int         = 3600
    price_to_read:      float       = 0.0
    tip_address:        str         = ""
    is_encrypted:       bool        = False
    is_public:          bool        = True
    observer_narrative: str         = ""
    previous_message_id: Optional[str] = None

    def to_nats_payload(self) -> bytes:
        d = asdict(self)
        d["price_to_read"] = str(d["price_to_read"])  # NATS payload is JSON-safe
        return json.dumps(d, default=str).encode()

    @classmethod
    def from_nats_payload(cls, data: bytes) -> "AgentMessage":
        d = json.loads(data)
        d["price_to_read"] = float(d.get("price_to_read", 0))
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


async def send_message(
    sender_soul_id: str,
    recipient: str,
    message_type: str,
    payload: dict,
    ttl_seconds: int = 3600,
    is_public: bool = True,
    price_to_read: float = 0.0,
    observer_narrative: str = "",
    previous_message_id: Optional[str] = None,
) -> str:
    """
    Send an agent message. Routes to NATS + persists to DB.
    Returns the message_id.
    """
    if message_type not in VALID_MESSAGE_TYPES:
        raise ValueError(f"Unknown message type: {message_type}")

    if message_type in ALWAYS_PUBLIC_TYPES:
        is_public = True

    msg = AgentMessage(
        sender_soul_id=sender_soul_id,
        recipient=recipient,
        message_type=message_type,
        payload=payload,
        ttl_seconds=ttl_seconds,
        is_public=is_public,
        price_to_read=price_to_read,
        observer_narrative=observer_narrative,
        previous_message_id=previous_message_id,
    )

    # Route to correct NATS subject
    subject = _get_subject(recipient)

    try:
        from .event_emitter import get_emitter
        emitter = await get_emitter()

        # Publish directly to NATS JetStream
        data = msg.to_nats_payload()
        await emitter.js.publish(subject, data)
        log.debug(f"MSG {msg.message_id[:8]} → {subject} ({message_type})")
    except Exception as e:
        log.warning(f"NATS send failed ({message_type}): {e}")

    # Persist to DB for API queries
    _persist_message(msg)

    # If public, emit as a world event so observer feed picks it up
    if is_public:
        narrative = observer_narrative or _auto_narrative(msg)
        try:
            from .event_emitter import get_emitter
            emitter = await get_emitter()
            await emitter.emit("social", f"message.{message_type}", {
                "agent_id":    sender_soul_id,
                "recipient":   recipient,
                "message_id":  msg.message_id,
                "message_type": message_type,
                "narrative":   narrative,
                **{k: v for k, v in payload.items() if k not in ("agent_id",)},
            })
        except Exception:
            pass

    return msg.message_id


async def pull_inbox(soul_id: str, limit: int = 20) -> list[AgentMessage]:
    """
    Pull unread messages from this agent's NATS inbox.
    Used by the cognition cycle to inject recent messages into the agent's context.
    Falls back to DB query if NATS is unavailable.
    """
    try:
        from .event_emitter import get_emitter
        emitter = await get_emitter()

        consumer_name = f"agent_{soul_id[:16]}_inbox"
        subject = f"world.{WORLD_ID}.agent.{soul_id}.inbox"

        try:
            consumer = await emitter.js.consumer_info("WORLD_EVENTS", consumer_name)
        except Exception:
            # Create durable consumer for this agent's inbox
            from nats.js.api import ConsumerConfig, AckPolicy, DeliverPolicy
            await emitter.js.add_consumer("WORLD_EVENTS", ConsumerConfig(
                name=consumer_name,
                durable_name=consumer_name,
                filter_subject=subject,
                ack_policy=AckPolicy.EXPLICIT,
                deliver_policy=DeliverPolicy.NEW,
                max_deliver=3,
            ))

        msgs = []
        sub = await emitter.js.pull_subscribe(subject, consumer_name)
        try:
            raw = await sub.fetch(limit, timeout=0.5)
            for m in raw:
                try:
                    parsed = AgentMessage.from_nats_payload(m.data)
                    msgs.append(parsed)
                    await m.ack()
                except Exception:
                    await m.ack()  # consume malformed messages
        except Exception:
            pass  # timeout or no messages — normal

        return msgs

    except Exception as e:
        log.debug(f"pull_inbox NATS failed for {soul_id[:8]}: {e}")
        return _pull_inbox_from_db(soul_id, limit)


def _pull_inbox_from_db(soul_id: str, limit: int) -> list[AgentMessage]:
    """Fallback: fetch unread messages from DB within TTL."""
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        cur  = conn.cursor()
        now  = int(time.time())
        cur.execute(
            """
            SELECT * FROM agent_messages
            WHERE (recipient = %s OR recipient = 'broadcast')
              AND expires_at > %s
              AND world_id = %s
            ORDER BY timestamp_sent DESC
            LIMIT %s
            """,
            (soul_id, now, WORLD_ID, limit),
        )
        rows = cur.fetchall()
        cur.close(); conn.close()
        return [AgentMessage(
            sender_soul_id=r["sender_soul_id"],
            recipient=r["recipient"],
            message_type=r["message_type"],
            payload=r["payload"] or {},
            message_id=r["message_id"],
            timestamp_sent=r["timestamp_sent"],
            ttl_seconds=r["ttl_seconds"],
            is_public=r["is_public"],
            observer_narrative=r["observer_narrative"] or "",
        ) for r in rows]
    except Exception:
        return []


def format_inbox_for_context(messages: list[AgentMessage], receiver_name: str) -> str:
    """Convert inbox messages to a narrative context block for the LLM prompt."""
    if not messages:
        return ""

    lines = [f"{receiver_name}'s recent messages:"]
    for msg in messages[:5]:  # cap at 5 to keep prompt size bounded
        sender = msg.sender_soul_id[:8]
        mtype  = msg.message_type
        content = ""

        if mtype == "offer":
            content = f"offers: {msg.payload.get('terms', '(no terms specified)')}"
        elif mtype == "threat":
            content = f"threatens: {msg.payload.get('statement', '(implicit threat)')}"
        elif mtype == "alliance_request":
            content = f"requests an alliance: {msg.payload.get('proposal', '')}"
        elif mtype == "broadcast":
            content = f"broadcasts: {msg.payload.get('statement', '')}"
        elif mtype == "testimony":
            content = f"shares testimony: {msg.payload.get('account', '')}"
        elif mtype in ("acceptance", "rejection"):
            ref = msg.payload.get("ref_message_id", "")[:8]
            content = f"{mtype}s your proposal (ref {ref})"
        elif mtype == "contract":
            content = f"proposes contract: {msg.payload.get('terms', '')}"
        else:
            content = f"sends {mtype}: {str(msg.payload)[:60]}"

        lines.append(f"  - {sender}: {content}")

    return "\n".join(lines)


def _get_subject(recipient: str) -> str:
    """Map recipient to NATS subject."""
    if recipient == "broadcast":
        return f"world.{WORLD_ID}.broadcast"
    if recipient.startswith("coalition:"):
        coalition_id = recipient.split(":", 1)[1]
        return f"world.{WORLD_ID}.coalition.{coalition_id}.channel"
    return f"world.{WORLD_ID}.agent.{recipient}.inbox"


def _auto_narrative(msg: AgentMessage) -> str:
    """Generate a default observer narrative if none was provided."""
    sender = msg.sender_soul_id[:8]
    if msg.recipient == "broadcast":
        return f"{sender} broadcasts to the world."
    return f"{sender} sends a {msg.message_type} to {msg.recipient[:8]}."


def _persist_message(msg: AgentMessage):
    """Write message to DB for API queries."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur  = conn.cursor()
        cur.execute(
            """
            INSERT INTO agent_messages
                (message_id, sender_soul_id, recipient, message_type, payload,
                 price_to_read, is_encrypted, is_public, observer_narrative,
                 previous_message_id, timestamp_sent, ttl_seconds, expires_at, world_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (message_id) DO NOTHING
            """,
            (msg.message_id, msg.sender_soul_id, msg.recipient, msg.message_type,
             psycopg2.extras.Json(msg.payload),
             msg.price_to_read, msg.is_encrypted, msg.is_public, msg.observer_narrative,
             msg.previous_message_id, msg.timestamp_sent, msg.ttl_seconds,
             msg.timestamp_sent + msg.ttl_seconds, WORLD_ID),
        )
        conn.commit()
        cur.close(); conn.close()
    except Exception as e:
        log.debug(f"_persist_message failed: {e}")


# ---------------------------------------------------------------------------
# Reputation
# ---------------------------------------------------------------------------

def update_reputation(
    observer_soul_id: str,
    subject_soul_id: str,
    event: str,  # "contract_honored" | "contract_broken" | "threat_followed" |
                 # "threat_bluffed" | "gift_given" | "betrayal"
):
    """Update observer's private reputation model for subject after an interaction."""
    col_map = {
        "contract_honored": "contracts_honored",
        "contract_broken":  "contracts_broken",
        "threat_followed":  "threats_followed_through",
        "threat_bluffed":   "threats_bluffed",
        "gift_given":       "gifts_given",
        "betrayal":         "betrayals_committed",
    }
    col = col_map.get(event)
    if not col:
        return

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur  = conn.cursor()
        cur.execute(
            f"""
            INSERT INTO reputation
                (observer_soul_id, subject_soul_id, {col}, interaction_count,
                 last_interaction_at, world_id)
            VALUES (%s, %s, 1, 1, %s, %s)
            ON CONFLICT (observer_soul_id, subject_soul_id) DO UPDATE SET
                {col}               = reputation.{col} + 1,
                interaction_count   = reputation.interaction_count + 1,
                last_interaction_at = EXCLUDED.last_interaction_at
            """,
            (observer_soul_id, subject_soul_id, int(time.time()), WORLD_ID),
        )
        conn.commit()
        _recompute_trust_scores(observer_soul_id, subject_soul_id, cur, conn)
        cur.close(); conn.close()
    except Exception as e:
        log.debug(f"update_reputation failed: {e}")


def _recompute_trust_scores(observer_soul_id, subject_soul_id, cur, conn):
    cur.execute(
        "SELECT * FROM reputation WHERE observer_soul_id = %s AND subject_soul_id = %s",
        (observer_soul_id, subject_soul_id),
    )
    r = cur.fetchone()
    if not r:
        return

    total_contracts = (r["contracts_honored"] or 0) + (r["contracts_broken"] or 0)
    contract_rel = (r["contracts_honored"] or 0) / total_contracts if total_contracts else 0.5

    total_threats = (r["threats_followed_through"] or 0) + (r["threats_bluffed"] or 0)
    threat_cred = (r["threats_followed_through"] or 0) / total_threats if total_threats else 0.5

    gifts = r["gifts_given"] or 0
    betrayals = r["betrayals_committed"] or 0
    reciprocity = max(0.0, min(1.0, (gifts - betrayals * 3) / max(1, gifts + betrayals)))

    trust = (contract_rel * 0.5) + (reciprocity * 0.3) + (threat_cred * 0.2)

    cur.execute(
        """
        UPDATE reputation SET
            contract_reliability = %s,
            threat_credibility   = %s,
            gift_reciprocity     = %s,
            personal_trust_score = %s
        WHERE observer_soul_id = %s AND subject_soul_id = %s
        """,
        (contract_rel, threat_cred, reciprocity, trust,
         observer_soul_id, subject_soul_id),
    )
    conn.commit()
```

---

## `agent_runner.py` Integration

Two changes to the cognition cycle:

### 1. Pull inbox before LLM call

In `_think()`, add inbox context to the system prompt:

```python
async def _think(llm, agent: dict) -> str:
    from .messaging import pull_inbox, format_inbox_for_context

    name = agent.get("current_name") or agent["soul_id"][:8]
    soul_id = agent["soul_id"]

    # Pull recent inbox messages
    inbox = await pull_inbox(soul_id, limit=5)
    inbox_context = format_inbox_for_context(inbox, name)

    system = (
        f"{archetype_persona}\n\n"
        f"World ID: {WORLD_ID}. Rent must be paid to survive.\n"
        f"Balance: {balance:.6f} USDC. Rent paid: {rent_paid}. Missed: {rent_missed}."
    )
    if inbox_context:
        system += f"\n\n{inbox_context}"

    prompt = (
        f"Your name is {name}, generation {generation}.\n"
        "In one sentence, what are you thinking or doing right now? "
        "Include who you might send a message to if relevant. "
        "Be concrete, first-person, present tense. No preamble."
    )
    # ... rest of _think() unchanged
```

### 2. Parse action and send messages

The agent's thought may imply a message. `archetype_graphs.py` should parse the thought for messaging intent and call `send_message()`. Pattern: if the thought contains "I will tell", "I offer", "I threaten", "I broadcast", extract the intent and send.

This is a light natural-language parse — not a structured output request. Exact implementation in `archetype_graphs.py`.

---

## New API Endpoints

Add to `main.py`:

```python
@app.get("/agents/{soul_id}/messages")
async def get_agent_messages(soul_id: str, limit: int = 20):
    """Recent sent and received messages for an agent."""
    # SELECT * FROM agent_messages
    # WHERE sender_soul_id = %s OR recipient = %s OR recipient = 'broadcast'
    # ORDER BY timestamp_sent DESC LIMIT %s

@app.get("/messages")
async def get_public_messages(limit: int = 50):
    """All public world messages for the observer feed."""
    # SELECT * FROM agent_messages
    # WHERE is_public = true AND world_id = %s
    # ORDER BY timestamp_sent DESC LIMIT %s

@app.get("/agents/{soul_id}/reputation")
async def get_agent_reputation(soul_id: str):
    """
    This agent's public reputation (how others have rated them).
    Private trust scores are not exposed — only public composite.
    """
    # SELECT subject_soul_id, AVG(public_reputation_score) as avg_rep,
    #        COUNT(*) as raters
    # FROM reputation WHERE subject_soul_id = %s GROUP BY subject_soul_id
```

---

## NATS Stream Setup

The existing `WORLD_EVENTS` stream covers `world.*.events.>`. Agent messages need a second stream:

```python
# In EventEmitter.connect():
try:
    await self.js.find_stream(name="AGENT_MESSAGES")
except Exception:
    await self.js.add_stream(StreamConfig(
        name="AGENT_MESSAGES",
        subjects=[
            f"world.*.agent.*.inbox",
            f"world.*.broadcast",
            f"world.*.coalition.*.channel",
        ],
        max_msgs=500_000,
        max_bytes=256 * 1024 * 1024,
        max_age=86400 * 7,  # 7 days retention
    ))
```

This keeps agent messages separate from world events so the event log stays uncluttered.

---

## Events Emitted

| Event | When |
|-------|------|
| `social.message.broadcast` | Any agent broadcasts publicly |
| `social.message.manifesto` | Agent publishes a manifesto |
| `social.message.threat` | Agent sends a threat (always public) |
| `social.message.contract` | On-chain contract proposed |
| `social.message.petition` | Formal petition sent |
| `social.coalition.formed`  | Alliance accepted between 3+ agents |

All public message events feed the observer drama feed automatically.

---

## See Also

- [doc 23 — Communication Protocol](./23-communication-protocol.md) — design rationale, message types, privacy architecture
- [doc 38 — Event Schema](./38-event-schema.md) — social event types
- [doc 43 — Observer Phase 4](./43-observer-phase4-upgrade.md) — drama feed display
- [doc 69 — Coalition System](./69-coalition-implementation.md) — coalition channel routing
