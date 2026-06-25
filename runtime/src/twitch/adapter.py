"""Deterministic Twitch adapter seam.

This layer normalizes Twitch-like payloads into internal world events and keeps
outbound chat behind a dry-run friendly contract until the real Helix/EventSub
implementation is ready.
"""

from __future__ import annotations

import hashlib
import os
import time
from typing import Any

import psycopg2

try:  # pragma: no cover - runtime package import path
    from ..json_safe import json_safe
except ImportError:  # pragma: no cover - tests import via flat path
    from json_safe import json_safe

try:  # pragma: no cover - runtime package import path
    from ..health_checks import probe_url
except ImportError:  # pragma: no cover - tests import via flat path
    from health_checks import probe_url

from .models import TwitchChatMessage, TwitchEvent, TwitchOutgoingChat

SUPPORTED_EVENT_TYPES = {
    "channel.chat.message",
    "channel.follow",
    "channel.raid",
    "channel.subscribe",
    "channel.subscription.gift",
    "channel.subscription.message",
    "channel.cheer",
    "channel.points.custom_reward_redemption.add",
}

EVENT_TO_WORLD = {
    "channel.chat.message": ("social", "twitch.chat.message"),
    "channel.follow": ("social", "twitch.follow"),
    "channel.raid": ("social", "twitch.raid"),
    "channel.subscribe": ("economy", "twitch.subscribe"),
    "channel.subscription.gift": ("economy", "twitch.subscription_gift"),
    "channel.subscription.message": ("economy", "twitch.subscription_message"),
    "channel.cheer": ("economy", "twitch.cheer"),
    "channel.points.custom_reward_redemption.add": ("social", "twitch.channel_point"),
}


def _env_bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() in ("1", "true", "yes", "on")


def _stable_event_id(event_type: str, payload: dict[str, Any]) -> str:
    raw = repr(
        {
            "event_type": event_type,
            "channel_name": payload.get("channel_name", ""),
            "user_name": payload.get("user_name", ""),
            "user_id": payload.get("user_id", ""),
            "message": payload.get("message", ""),
            "metadata": payload.get("metadata", {}),
        }
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:24]


def _replay_key(event_type: str, payload: dict[str, Any]) -> str:
    raw = repr(
        {
            "event_type": event_type,
            "channel_name": payload.get("channel_name", ""),
            "user_name": payload.get("user_name", ""),
            "user_id": payload.get("user_id", ""),
            "message": payload.get("message", ""),
            "metadata": payload.get("metadata", {}),
            "event_id": payload.get("event_id", ""),
        }
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _register_replay_key(replay_key: str, event_id: str, event_type: str) -> bool:
    world_id = os.getenv("WORLD_ID", "local-dev-world-1")
    db = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
    try:
        conn = psycopg2.connect(db)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO twitch_event_replays (replay_key, event_id, event_type, created_at, world_id)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (replay_key) DO NOTHING
            """,
            (replay_key, event_id, event_type, int(time.time()), world_id),
        )
        inserted = cur.rowcount > 0
        conn.commit()
        cur.close()
        conn.close()
        return inserted
    except Exception:
        return True


def normalize_twitch_event(event_type: str, payload: dict[str, Any]) -> TwitchEvent | None:
    """Normalize raw Twitch payloads into a typed event."""
    event_type = str(event_type or "").strip()
    if event_type not in SUPPORTED_EVENT_TYPES:
        return None
    payload = payload or {}
    channel_name = str(
        payload.get("channel_name")
        or payload.get("broadcaster_name")
        or payload.get("broadcaster_login")
        or os.getenv("TWITCH_CHANNEL_NAME", "")
    ).strip()
    if not channel_name:
        return None
    user_name = str(payload.get("user_name") or payload.get("chatter_name") or "").strip()
    message = str(
        payload.get("message") or payload.get("text") or payload.get("content") or ""
    ).strip()
    metadata = dict(payload.get("metadata") or {})
    metadata.setdefault("source", "twitch")
    metadata.setdefault("transport", os.getenv("TWITCH_EVENTSUB_TRANSPORT", "dry-run"))
    return TwitchEvent(
        event_id=str(payload.get("event_id") or _stable_event_id(event_type, payload)),
        event_type=event_type,
        channel_name=channel_name,
        user_name=user_name,
        user_id=str(payload.get("user_id") or "").strip(),
        message=message,
        metadata=metadata,
    )


class TwitchAdapter:
    """Local-first Twitch adapter with dry-run outbound chat."""

    def __init__(self, channel_name: str | None = None, dry_run: bool | None = None):
        self.channel_name = (channel_name or os.getenv("TWITCH_CHANNEL_NAME", "")).strip()
        self.dry_run = _env_bool("TWITCH_DRY_RUN", "true") if dry_run is None else dry_run
        self.enabled = _env_bool("TWITCH_ENABLED", "false")
        self.transport = os.getenv("TWITCH_EVENTSUB_TRANSPORT", "dry-run")

    def ingest(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        """Normalize a Twitch event into a world event payload."""
        twitch_event = normalize_twitch_event(event_type, payload)
        if twitch_event is None:
            return None

        replay_key = _replay_key(event_type, payload)
        if not _register_replay_key(replay_key, twitch_event.event_id, event_type):
            return None

        world_category, world_event_type = EVENT_TO_WORLD[event_type]
        world_event = {
            "event_id": twitch_event.event_id,
            "category": world_category,
            "event_type": f"{world_category}.{world_event_type}",
            "timestamp": int(payload.get("timestamp") or payload.get("ts") or time.time()),
            "agent_id": twitch_event.user_id or None,
            "narrative": self._narrative_for(twitch_event),
            "payload": twitch_event.to_dict(),
            "replay_key": replay_key,
        }
        return json_safe(world_event)

    async def send_chat(self, message: TwitchChatMessage) -> TwitchOutgoingChat:
        """Send or dry-run a chat message via Helix POST /chat/messages."""
        if not message.message.strip():
            return TwitchOutgoingChat(
                ok=False,
                dry_run=self.dry_run,
                channel_name=message.channel_name,
                message=message.message,
                reason="empty_message",
            )

        if self.dry_run or not self.enabled:
            return TwitchOutgoingChat(
                ok=True,
                dry_run=True,
                channel_name=message.channel_name,
                message=message.message,
                reason="dry_run",
                metadata={
                    **message.metadata,
                    "transport": self.transport,
                },
            )

        from .helix import send_chat_message  # avoid circular at module level

        result = await send_chat_message(
            message=message.message,
            reply_to_message_id=message.reply_to_message_id,
        )
        return TwitchOutgoingChat(
            ok=result.get("ok", False),
            dry_run=False,
            channel_name=message.channel_name,
            message=message.message,
            reason=result.get("reason", "") or ("sent" if result.get("ok") else "helix_error"),
            metadata={**message.metadata, **{k: v for k, v in result.items() if k not in ("ok",)}},
        )

    def status(self) -> dict[str, Any]:
        health = {
            "helix": probe_url(os.getenv("TWITCH_HELIX_HEALTH_URL"), timeout=1.5),
            "eventsub": probe_url(os.getenv("TWITCH_EVENTSUB_HEALTH_URL"), timeout=1.5),
        }
        return {
            "enabled": self.enabled,
            "dry_run": self.dry_run,
            "channel_name": self.channel_name,
            "transport": self.transport,
            "health": health,
            "supported_event_types": sorted(SUPPORTED_EVENT_TYPES),
        }

    def _narrative_for(self, twitch_event: TwitchEvent) -> str:
        if twitch_event.event_type == "channel.chat.message":
            return f"Chat from {twitch_event.user_name or twitch_event.user_id}: {twitch_event.message[:120]}"
        if twitch_event.event_type == "channel.follow":
            return f"{twitch_event.user_name or twitch_event.user_id} followed the channel."
        if twitch_event.event_type == "channel.raid":
            viewers = (
                twitch_event.metadata.get("viewer_count")
                or twitch_event.metadata.get("viewers")
                or 0
            )
            return f"Raid arrives from {twitch_event.user_name or twitch_event.user_id} with {viewers} viewers."
        if twitch_event.event_type == "channel.subscribe":
            return f"{twitch_event.user_name or twitch_event.user_id} subscribed to the channel."
        if twitch_event.event_type == "channel.subscription.gift":
            return f"{twitch_event.user_name or twitch_event.user_id} gifted subscriptions."
        if twitch_event.event_type == "channel.cheer":
            bits = twitch_event.metadata.get("bits") or 0
            return f"{twitch_event.user_name or twitch_event.user_id} cheered {bits} bits."
        if twitch_event.event_type == "channel.points.custom_reward_redemption.add":
            return f"{twitch_event.user_name or twitch_event.user_id} redeemed channel points."
        return f"Twitch event {twitch_event.event_type} observed."


def build_twitch_status() -> dict[str, Any]:
    return TwitchAdapter().status()
