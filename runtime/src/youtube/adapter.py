"""YouTube Live Chat adapter seam.

Normalizes YouTube Live Chat payloads into internal world events and keeps
outbound chat behind a dry-run friendly contract.
"""

from __future__ import annotations

import hashlib
import os
import time
from typing import Any

try:  # pragma: no cover - runtime package import path
    from ..health_checks import probe_url
except ImportError:  # pragma: no cover - flat test path
    from health_checks import probe_url

from .models import YouTubeChatMessage, YouTubeEvent, YouTubeOutgoingChat

SUPPORTED_EVENT_TYPES = {
    "textMessageEvent",
    "superChatEvent",
    "superStickerEvent",
    "newSponsorEvent",
    "memberMilestoneChatEvent",
}

EVENT_TO_WORLD = {
    "textMessageEvent": ("social", "youtube.chat.message"),
    "superChatEvent": ("economy", "youtube.super_chat"),
    "superStickerEvent": ("economy", "youtube.super_sticker"),
    "newSponsorEvent": ("economy", "youtube.membership"),
    "memberMilestoneChatEvent": ("economy", "youtube.membership_milestone"),
}


def _env_bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() in ("1", "true", "yes", "on")


def _stable_event_id(event_type: str, payload: dict[str, Any]) -> str:
    raw = repr(
        {
            "event_type": event_type,
            "channel_id": payload.get("channel_id", ""),
            "user_id": payload.get("user_id", ""),
            "message": payload.get("message", ""),
            "published_at": payload.get("published_at", ""),
        }
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:24]


def normalize_youtube_event(event_type: str, payload: dict[str, Any]) -> YouTubeEvent | None:
    """Normalize a raw YouTube Live Chat item into a typed event."""
    event_type = str(event_type or "").strip()
    if event_type not in SUPPORTED_EVENT_TYPES:
        return None
    payload = payload or {}

    channel_id = str(
        payload.get("channel_id")
        or os.getenv("YOUTUBE_CHANNEL_ID", "")
    ).strip()
    if not channel_id:
        return None

    user_name = str(payload.get("user_name") or payload.get("display_name") or "").strip()
    user_id = str(payload.get("user_id") or "").strip()
    message = str(payload.get("message") or payload.get("text") or "").strip()

    metadata: dict[str, Any] = dict(payload.get("metadata") or {})
    metadata.setdefault("source", "youtube")
    metadata.setdefault("transport", os.getenv("YOUTUBE_TRANSPORT", "dry-run"))

    if event_type == "superChatEvent":
        metadata.setdefault("amount_micros", payload.get("amount_micros", 0))
        metadata.setdefault("currency", payload.get("currency", ""))
    if event_type == "memberMilestoneChatEvent":
        metadata.setdefault("member_month", payload.get("member_month", 0))

    return YouTubeEvent(
        event_id=str(payload.get("event_id") or _stable_event_id(event_type, payload)),
        event_type=event_type,
        channel_id=channel_id,
        user_name=user_name,
        user_id=user_id,
        message=message,
        metadata=metadata,
    )


class YouTubeAdapter:
    """Local-first YouTube adapter with dry-run outbound chat."""

    def __init__(self, channel_id: str | None = None, dry_run: bool | None = None):
        self.channel_id = (channel_id or os.getenv("YOUTUBE_CHANNEL_ID", "")).strip()
        self.dry_run = _env_bool("YOUTUBE_DRY_RUN", "true") if dry_run is None else dry_run
        self.enabled = _env_bool("YOUTUBE_ENABLED", "false")
        self.transport = os.getenv("YOUTUBE_TRANSPORT", "dry-run")

    def ingest(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        """Normalize a YouTube Live Chat event into a world event payload."""
        yt_event = normalize_youtube_event(event_type, payload)
        if yt_event is None:
            return None

        world_category, world_event_type = EVENT_TO_WORLD[event_type]
        world_event = {
            "event_id": yt_event.event_id,
            "category": world_category,
            "event_type": f"{world_category}.{world_event_type}",
            "timestamp": int(payload.get("timestamp") or payload.get("ts") or time.time()),
            "agent_id": yt_event.user_id or None,
            "narrative": self._narrative_for(yt_event),
            "payload": yt_event.to_dict(),
        }
        return world_event

    async def send_chat(self, message: YouTubeChatMessage) -> YouTubeOutgoingChat:
        """Send or dry-run a chat message to YouTube Live Chat."""
        if not message.message.strip():
            return YouTubeOutgoingChat(
                ok=False,
                dry_run=self.dry_run,
                live_chat_id=message.live_chat_id,
                message=message.message,
                reason="empty_message",
            )

        if self.dry_run or not self.enabled:
            return YouTubeOutgoingChat(
                ok=True,
                dry_run=True,
                live_chat_id=message.live_chat_id,
                message=message.message,
                reason="dry_run",
                metadata={**message.metadata, "transport": self.transport},
            )

        from .api import send_chat_message  # avoid circular at module level

        result = await send_chat_message(
            live_chat_id=message.live_chat_id,
            message=message.message,
        )
        return YouTubeOutgoingChat(
            ok=result.get("ok", False),
            dry_run=False,
            live_chat_id=message.live_chat_id,
            message=message.message,
            reason=result.get("reason", "") or ("sent" if result.get("ok") else "api_error"),
            metadata={**message.metadata, **{k: v for k, v in result.items() if k != "ok"}},
        )

    def status(self) -> dict[str, Any]:
        health = probe_url(os.getenv("YOUTUBE_HEALTH_URL"), timeout=1.5)
        return {
            "enabled": self.enabled,
            "dry_run": self.dry_run,
            "channel_id": self.channel_id,
            "transport": self.transport,
            "health": health,
            "supported_event_types": sorted(SUPPORTED_EVENT_TYPES),
        }

    def _narrative_for(self, yt_event: YouTubeEvent) -> str:
        name = yt_event.user_name or yt_event.user_id or "someone"
        if yt_event.event_type == "textMessageEvent":
            return f"Chat from {name}: {yt_event.message[:120]}"
        if yt_event.event_type == "superChatEvent":
            amount = yt_event.metadata.get("amount_micros", 0)
            currency = yt_event.metadata.get("currency", "")
            display = f"{currency} {int(amount) // 1_000_000}" if amount else ""
            return f"{name} sent a Super Chat{f' ({display})' if display else ''}. {yt_event.message[:80]}"
        if yt_event.event_type == "superStickerEvent":
            return f"{name} sent a Super Sticker."
        if yt_event.event_type == "newSponsorEvent":
            return f"{name} became a channel member."
        if yt_event.event_type == "memberMilestoneChatEvent":
            months = yt_event.metadata.get("member_month", 0)
            return f"{name} has been a member for {months} month(s). {yt_event.message[:80]}"
        return f"YouTube event {yt_event.event_type} observed."


def build_youtube_status() -> dict[str, Any]:
    return YouTubeAdapter().status()
