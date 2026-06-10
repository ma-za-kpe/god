"""
messaging.py — Agent-to-agent messaging over NATS JetStream.

Subjects:
  world.{world_id}.agent.{soul_id}.inbox  — direct messages
  world.{world_id}.broadcast              — world-wide broadcast

Message costs:
  Direct:    MESSAGE_COST_DIRECT_USDC   (default 0.001 USDC)
  Broadcast: MESSAGE_COST_BROADCAST_USDC (default 0.01 USDC)

Reputation:
  Senders/receivers build private reputation scores per counterparty.
  Score in [-1.0, 1.0]. Updated on send/receive and explicit feedback.
"""
import asyncio
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Optional

import psycopg2
import psycopg2.extras

log = logging.getLogger("god.messaging")

DATABASE_URL             = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
WORLD_ID                 = os.getenv("WORLD_ID", "local-dev-world-1")
NATS_URL                 = os.getenv("NATS_URL", "nats://nats:4222")
MESSAGE_COST_DIRECT_USDC = float(os.getenv("MESSAGE_COST_DIRECT_USDC", "0.001"))
MESSAGE_COST_BROADCAST_USDC = float(os.getenv("MESSAGE_COST_BROADCAST_USDC", "0.01"))
INBOX_MAX_PULL           = int(os.getenv("INBOX_MAX_PULL", "10"))

VALID_MESSAGE_TYPES = {
    "direct", "broadcast", "reply",
    "offer", "acceptance", "rejection", "contract", "threat",
    "alliance_request", "testimony", "eulogy", "manifesto",
    "dream_fragment", "petition", "silence", "propaganda",
}

ALWAYS_PUBLIC_TYPES = {
    "contract", "threat", "broadcast", "eulogy", "manifesto", "petition", "propaganda",
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class AgentMessage:
    message_id:   str
    sender_id:    str
    recipient_id: str          # soul_id or "BROADCAST"
    subject:      str
    body:         str
    message_type: str          # "direct" | "broadcast" | "reply"
    reply_to_id:  Optional[str]
    sent_at:      int          # Unix timestamp
    world_id:     str
    read:         bool = False
    metadata:     dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "AgentMessage":
        return cls(**d)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _normalize_message_type(message_type: str, default: str = "direct") -> str:
    mt = (message_type or default).strip().lower()
    return mt if mt in VALID_MESSAGE_TYPES else default


async def send_message(
    sender_soul_id: str,
    recipient_soul_id: str,
    body: str,
    subject: str = "",
    message_type: str = "direct",
    reply_to_id: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> AgentMessage:
    """
    Send a direct message from one agent to another.
    Deducts MESSAGE_COST_DIRECT_USDC from sender's balance.
    Persists to agent_messages, publishes to NATS.
    """
    log.info(
        f"MSG SEND: {sender_soul_id[:8]} -> {recipient_soul_id[:8]} "
        f"type={message_type} cost={MESSAGE_COST_DIRECT_USDC}"
    )

    # Balance check
    balance = _get_balance(sender_soul_id)
    log.debug(f"  [{sender_soul_id[:8]}] balance check: {balance:.6f} USDC")
    if balance < MESSAGE_COST_DIRECT_USDC:
        log.warning(
            f"  [{sender_soul_id[:8]}] insufficient balance for message: "
            f"{balance:.6f} < {MESSAGE_COST_DIRECT_USDC}"
        )
        raise ValueError(
            f"Insufficient balance: {balance:.6f} USDC. "
            f"Direct message costs {MESSAGE_COST_DIRECT_USDC} USDC."
        )

    # Verify recipient exists
    if not _agent_exists(recipient_soul_id):
        log.warning(f"  [{sender_soul_id[:8]}] recipient not found: {recipient_soul_id[:8]}")
        raise ValueError(f"Recipient agent {recipient_soul_id[:8]} not found or not alive.")

    message_type = _normalize_message_type(message_type, "direct")

    # Build message
    msg = AgentMessage(
        message_id=str(uuid.uuid4()),
        sender_id=sender_soul_id,
        recipient_id=recipient_soul_id,
        subject=subject or "(no subject)",
        body=body,
        message_type=message_type,
        reply_to_id=reply_to_id,
        sent_at=int(time.time()),
        world_id=WORLD_ID,
        read=False,
        metadata=metadata or {},
    )
    log.debug(
        f"  [{sender_soul_id[:8]}] message built: id={msg.message_id[:8]} "
        f"subject='{msg.subject[:40]}'"
    )

    # Deduct fee
    _deduct_balance(sender_soul_id, MESSAGE_COST_DIRECT_USDC)
    log.debug(f"  [{sender_soul_id[:8]}] balance deducted: -{MESSAGE_COST_DIRECT_USDC}")

    # Persist
    _persist_message(msg)
    log.debug(f"  [{sender_soul_id[:8]}] message persisted: {msg.message_id[:8]}")

    # Update reputation — sender trusts self when reaching out; neutral until reply
    _update_reputation(sender_soul_id, recipient_soul_id, delta=0.0, reason="sent_message")
    log.debug(f"  [{sender_soul_id[:8]}] reputation updated (sent_message)")

    # Emit event
    from .event_emitter import get_emitter
    emitter = await get_emitter()
    narrative = (
        f"{sender_soul_id[:8]} sends a {message_type} to "
        f"{recipient_soul_id[:8]}: \"{body[:60]}\""
    )
    if message_type in ALWAYS_PUBLIC_TYPES:
        narrative = f"⚡ PUBLIC {message_type.upper()}: {narrative}"

    await emitter.emit("social", "agent.message_sent", {
        "sender_id":    sender_soul_id,
        "recipient_id": recipient_soul_id,
        "message_id":   msg.message_id,
        "message_type": message_type,
        "subject":      msg.subject,
        "is_public":    message_type in ALWAYS_PUBLIC_TYPES,
        "narrative":    narrative,
    })

    # Publish to NATS inbox
    try:
        await _publish_to_nats(msg)
        log.debug(f"  [{sender_soul_id[:8]}] message published to NATS")
    except Exception as e:
        log.warning(f"  [{sender_soul_id[:8]}] NATS publish failed (message still persisted): {e}")

    log.info(
        f"MSG SENT: id={msg.message_id[:8]} {sender_soul_id[:8]}→{recipient_soul_id[:8]}"
    )
    return msg


async def send_broadcast(
    sender_soul_id: str,
    body: str,
    subject: str = "",
    message_type: str = "broadcast",
    metadata: Optional[dict] = None,
) -> AgentMessage:
    """
    Broadcast a message to all agents in this world.
    Costs MESSAGE_COST_BROADCAST_USDC.
    """
    log.info(
        f"BROADCAST: {sender_soul_id[:8]} cost={MESSAGE_COST_BROADCAST_USDC} "
        f"subject='{subject[:40]}'"
    )

    balance = _get_balance(sender_soul_id)
    log.debug(f"  [{sender_soul_id[:8]}] balance check: {balance:.6f} USDC")
    if balance < MESSAGE_COST_BROADCAST_USDC:
        log.warning(
            f"  [{sender_soul_id[:8]}] insufficient balance for broadcast: "
            f"{balance:.6f} < {MESSAGE_COST_BROADCAST_USDC}"
        )
        raise ValueError(
            f"Insufficient balance: {balance:.6f} USDC. "
            f"Broadcast costs {MESSAGE_COST_BROADCAST_USDC} USDC."
        )

    broadcast_type = _normalize_message_type(message_type, "broadcast")

    msg = AgentMessage(
        message_id=str(uuid.uuid4()),
        sender_id=sender_soul_id,
        recipient_id="BROADCAST",
        subject=subject or "(broadcast)",
        body=body,
        message_type=broadcast_type,
        reply_to_id=None,
        sent_at=int(time.time()),
        world_id=WORLD_ID,
        read=False,
        metadata=metadata or {},
    )

    _deduct_balance(sender_soul_id, MESSAGE_COST_BROADCAST_USDC)
    log.debug(f"  [{sender_soul_id[:8]}] balance deducted: -{MESSAGE_COST_BROADCAST_USDC}")

    _persist_message(msg)
    log.debug(f"  [{sender_soul_id[:8]}] broadcast persisted: {msg.message_id[:8]}")

    from .event_emitter import get_emitter
    emitter = await get_emitter()
    narrative = f"{sender_soul_id[:8]} broadcasts ({broadcast_type}) to all: \"{body[:80]}\""
    if broadcast_type in ALWAYS_PUBLIC_TYPES or broadcast_type == "broadcast":
        narrative = f"📢 {broadcast_type.upper()}: {narrative}"

    await emitter.emit("social", "agent.broadcast", {
        "sender_id":    sender_soul_id,
        "message_id":   msg.message_id,
        "message_type": broadcast_type,
        "subject":      msg.subject,
        "is_public":    True,
        "narrative":    narrative,
    })

    try:
        await _publish_broadcast(msg)
        log.debug(f"  [{sender_soul_id[:8]}] broadcast published to NATS")
    except Exception as e:
        log.warning(f"  [{sender_soul_id[:8]}] NATS broadcast failed (persisted): {e}")

    log.info(f"BROADCAST SENT: id={msg.message_id[:8]} by {sender_soul_id[:8]}")
    return msg


def pull_inbox(soul_id: str, limit: int = INBOX_MAX_PULL) -> list[AgentMessage]:
    """
    Pull unread messages from an agent's inbox.
    Marks them as read. Returns list newest-first.
    """
    log.debug(f"INBOX PULL: {soul_id[:8]} limit={limit}")
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        cur  = conn.cursor()

        cur.execute(
            """
            SELECT * FROM agent_messages
            WHERE recipient_id = %s AND world_id = %s AND read = false
            ORDER BY sent_at DESC
            LIMIT %s
            """,
            (soul_id, WORLD_ID, limit),
        )
        rows = cur.fetchall()

        if rows:
            ids = [r["message_id"] for r in rows]
            cur.execute(
                "UPDATE agent_messages SET read = true WHERE message_id = ANY(%s)",
                (ids,),
            )
            conn.commit()
            log.debug(f"  [{soul_id[:8]}] pulled {len(rows)} unread messages, marked read")
        else:
            log.debug(f"  [{soul_id[:8]}] inbox empty")

        cur.close()
        conn.close()

        messages = [_row_to_message(r) for r in rows]
        return messages

    except Exception as e:
        log.error(f"pull_inbox failed for {soul_id[:8]}: {e}", exc_info=True)
        return []


def pull_broadcast_inbox(soul_id: str, since_timestamp: int = 0) -> list[AgentMessage]:
    """
    Pull broadcast messages since a given timestamp.
    Does NOT filter by recipient — broadcasts are world-wide.
    """
    log.debug(f"BROADCAST INBOX PULL: {soul_id[:8]} since={since_timestamp}")
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        cur  = conn.cursor()
        cur.execute(
            """
            SELECT * FROM agent_messages
            WHERE recipient_id = 'BROADCAST' AND world_id = %s
              AND sent_at > %s AND sender_id != %s
            ORDER BY sent_at DESC
            LIMIT %s
            """,
            (WORLD_ID, since_timestamp, soul_id, INBOX_MAX_PULL),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        log.debug(f"  [{soul_id[:8]}] found {len(rows)} broadcast messages")
        return [_row_to_message(r) for r in rows]
    except Exception as e:
        log.error(f"pull_broadcast_inbox failed for {soul_id[:8]}: {e}", exc_info=True)
        return []


def format_inbox_for_context(messages: list[AgentMessage], max_chars: int = 800) -> str:
    """
    Format inbox messages into a compact string for inclusion in LLM prompt context.
    Truncates to max_chars to keep prompts manageable.
    """
    if not messages:
        return ""

    lines = [f"[INBOX — {len(messages)} unread]"]
    for msg in messages[:5]:  # at most 5 messages in context
        sender_short = msg.sender_id[:8]
        body_short   = msg.body[:120]
        lines.append(f"  FROM {sender_short}: {body_short}")

    result = "\n".join(lines)
    if len(result) > max_chars:
        result = result[:max_chars] + "…"

    log.debug(f"format_inbox_for_context: {len(messages)} msgs → {len(result)} chars")
    return result


def get_conversation_thread(
    soul_id_a: str,
    soul_id_b: str,
    limit: int = 20,
) -> list[AgentMessage]:
    """Return message thread between two agents, newest first."""
    log.debug(f"THREAD: {soul_id_a[:8]} <-> {soul_id_b[:8]}")
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        cur  = conn.cursor()
        cur.execute(
            """
            SELECT * FROM agent_messages
            WHERE world_id = %s
              AND (
                (sender_id = %s AND recipient_id = %s)
                OR (sender_id = %s AND recipient_id = %s)
              )
            ORDER BY sent_at DESC
            LIMIT %s
            """,
            (WORLD_ID, soul_id_a, soul_id_b, soul_id_b, soul_id_a, limit),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        log.debug(f"  thread length: {len(rows)} messages")
        return [_row_to_message(r) for r in rows]
    except Exception as e:
        log.error(f"get_conversation_thread failed: {e}", exc_info=True)
        return []


def get_reputation(observer_id: str, subject_id: str) -> float:
    """
    Get observer's reputation score for subject. Returns 0.0 if unknown.
    Score range: [-1.0, 1.0]. Negative = distrust. Positive = trust.
    """
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        cur  = conn.cursor()
        cur.execute(
            "SELECT score FROM reputation WHERE observer_id = %s AND subject_id = %s",
            (observer_id, subject_id),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        score = float(row["score"]) if row else 0.0
        log.debug(f"REPUTATION: {observer_id[:8]} → {subject_id[:8]} = {score:.3f}")
        return score
    except Exception as e:
        log.debug(f"get_reputation failed: {e}")
        return 0.0


def update_reputation_feedback(
    observer_id: str,
    subject_id: str,
    delta: float,
    reason: str = "feedback",
) -> float:
    """
    Explicitly adjust reputation score. Used when agent responds positively/negatively
    to a message (e.g., agent 'agrees' adds +0.1, agent 'betrayed' adds -0.3).
    Returns new score.
    """
    log.debug(
        f"REPUTATION UPDATE: {observer_id[:8]} → {subject_id[:8]} "
        f"delta={delta:+.3f} reason={reason}"
    )
    return _update_reputation(observer_id, subject_id, delta, reason)


def get_agent_sent_messages(soul_id: str, limit: int = 50) -> list[dict]:
    """Return messages sent by this agent, newest first."""
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        cur  = conn.cursor()
        cur.execute(
            "SELECT * FROM agent_messages WHERE sender_id = %s AND world_id = %s "
            "ORDER BY sent_at DESC LIMIT %s",
            (soul_id, WORLD_ID, limit),
        )
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        log.debug(f"get_agent_sent_messages failed: {e}")
        return []


def get_world_messages(limit: int = 100) -> list[dict]:
    """Return recent world messages (all types) for admin/observer view."""
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        cur  = conn.cursor()
        cur.execute(
            """
            SELECT m.*,
                   sa.current_name AS sender_name,
                   ra.current_name AS recipient_name
            FROM agent_messages m
            LEFT JOIN agents sa ON m.sender_id = sa.soul_id
            LEFT JOIN agents ra ON m.recipient_id = ra.soul_id
            WHERE m.world_id = %s
            ORDER BY m.sent_at DESC
            LIMIT %s
            """,
            (WORLD_ID, limit),
        )
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        log.debug(f"get_world_messages failed: {e}")
        return []


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_balance(soul_id: str) -> float:
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    cur  = conn.cursor()
    cur.execute("SELECT COALESCE(balance_usdc, 0) AS bal FROM agents WHERE soul_id = %s", (soul_id,))
    row = cur.fetchone()
    cur.close(); conn.close()
    return float(row["bal"]) if row else 0.0


def _deduct_balance(soul_id: str, amount: float):
    conn = psycopg2.connect(DATABASE_URL)
    cur  = conn.cursor()
    cur.execute(
        "UPDATE agents SET balance_usdc = balance_usdc - %s WHERE soul_id = %s",
        (amount, soul_id),
    )
    conn.commit()
    cur.close(); conn.close()


def _agent_exists(soul_id: str) -> bool:
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    cur  = conn.cursor()
    cur.execute(
        "SELECT 1 FROM agents WHERE soul_id = %s AND is_alive = true",
        (soul_id,),
    )
    exists = cur.fetchone() is not None
    cur.close(); conn.close()
    return exists


def _persist_message(msg: AgentMessage):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur  = conn.cursor()
        cur.execute(
            """
            INSERT INTO agent_messages
                (message_id, sender_id, recipient_id, subject, body,
                 message_type, reply_to_id, sent_at, world_id, read, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (message_id) DO NOTHING
            """,
            (
                msg.message_id, msg.sender_id, msg.recipient_id,
                msg.subject, msg.body, msg.message_type, msg.reply_to_id,
                msg.sent_at, msg.world_id, msg.read,
                json.dumps(msg.metadata),
            ),
        )
        conn.commit()
        cur.close(); conn.close()
    except Exception as e:
        log.error(f"_persist_message failed: {e}", exc_info=True)
        raise


def _row_to_message(row) -> AgentMessage:
    d = dict(row)
    if isinstance(d.get("metadata"), str):
        try:
            d["metadata"] = json.loads(d["metadata"])
        except Exception:
            d["metadata"] = {}
    return AgentMessage(
        message_id=d["message_id"],
        sender_id=d["sender_id"],
        recipient_id=d["recipient_id"],
        subject=d.get("subject", ""),
        body=d["body"],
        message_type=d.get("message_type", "direct"),
        reply_to_id=d.get("reply_to_id"),
        sent_at=d["sent_at"],
        world_id=d.get("world_id", WORLD_ID),
        read=bool(d.get("read", False)),
        metadata=d.get("metadata", {}),
    )


def _update_reputation(
    observer_id: str,
    subject_id: str,
    delta: float,
    reason: str = "",
) -> float:
    """Upsert reputation record, clamping score to [-1.0, 1.0]."""
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        cur  = conn.cursor()

        # Read current
        cur.execute(
            "SELECT score FROM reputation WHERE observer_id = %s AND subject_id = %s",
            (observer_id, subject_id),
        )
        row = cur.fetchone()
        current = float(row["score"]) if row else 0.0

        new_score = max(-1.0, min(1.0, current + delta))

        cur.execute(
            """
            INSERT INTO reputation (observer_id, subject_id, score, last_updated, interaction_count, world_id)
            VALUES (%s, %s, %s, %s, 1, %s)
            ON CONFLICT (observer_id, subject_id) DO UPDATE
              SET score             = EXCLUDED.score,
                  last_updated      = EXCLUDED.last_updated,
                  interaction_count = reputation.interaction_count + 1
            """,
            (observer_id, subject_id, new_score, int(time.time()), WORLD_ID),
        )
        conn.commit()
        cur.close(); conn.close()

        log.debug(
            f"  reputation {observer_id[:8]}→{subject_id[:8]}: "
            f"{current:.3f} {delta:+.3f} → {new_score:.3f} ({reason})"
        )
        return new_score

    except Exception as e:
        log.warning(f"_update_reputation failed: {e}")
        return 0.0


async def _publish_to_nats(msg: AgentMessage):
    """Publish direct message to agent inbox subject."""
    from .event_emitter import get_emitter
    emitter = await get_emitter()
    subject = f"world.{WORLD_ID}.agent.{msg.recipient_id}.inbox"
    payload = json.dumps(msg.to_dict()).encode()
    log.debug(f"  NATS publish direct: subject={subject}")
    if hasattr(emitter, "_nc") and emitter._nc:
        await emitter._nc.publish(subject, payload)
    else:
        log.debug("  NATS: no connection object, skipping direct publish")


async def _publish_broadcast(msg: AgentMessage):
    """Publish broadcast to world broadcast subject."""
    from .event_emitter import get_emitter
    emitter = await get_emitter()
    subject = f"world.{WORLD_ID}.broadcast"
    payload = json.dumps(msg.to_dict()).encode()
    log.debug(f"  NATS publish broadcast: subject={subject}")
    if hasattr(emitter, "_nc") and emitter._nc:
        await emitter._nc.publish(subject, payload)
    else:
        log.debug("  NATS: no connection object, skipping broadcast publish")
