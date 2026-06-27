"""Shared platform boundary for live audience adapters."""

from __future__ import annotations

import hashlib
import os
from dataclasses import asdict, dataclass, field
from typing import Any


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _blocked_terms() -> tuple[str, ...]:
    raw = os.getenv("PLATFORM_BLOCKED_TERMS") or os.getenv("TWITCH_MODERATION_BLOCKED_TERMS") or ""
    return tuple(term.strip().lower() for term in raw.split(",") if term.strip())


def _moderation(platform: str, event_type: str, message: str, metadata: dict[str, Any]) -> dict:
    message_lc = message.lower()
    matched_terms = [term for term in _blocked_terms() if term in message_lc]
    if matched_terms:
        return {
            "allowed": False,
            "reason": "blocked_term",
            "matched_terms": matched_terms,
            "platform": platform,
        }

    moderation_status = _text(
        metadata.get("moderation_status") or metadata.get("automod_status")
    ).lower()
    if metadata.get("is_automod_held") or moderation_status in {"held", "blocked", "denied"}:
        return {
            "allowed": False,
            "reason": "platform_moderation_hold",
            "matched_terms": [],
            "platform": platform,
        }

    return {
        "allowed": True,
        "reason": "allowed",
        "matched_terms": [],
        "platform": platform,
    }


def _rate_limit(platform: str, event_type: str, channel_name: str, actor_id: str) -> dict:
    if event_type.endswith("chat.message"):
        scope = "actor"
        bucket_actor = actor_id or "anonymous"
        bucket = f"{platform}:{channel_name}:{bucket_actor}:chat"
        limit = 20
        window_seconds = 30
    else:
        scope = "channel"
        bucket = f"{platform}:{channel_name}:{event_type}"
        limit = 120
        window_seconds = 60
    return {
        "bucket": bucket,
        "scope": scope,
        "cost": 1,
        "limit": limit,
        "window_seconds": window_seconds,
    }


def _replay_key(
    platform: str,
    event_type: str,
    event_id: str,
    channel_name: str,
    actor_id: str,
    message: str,
) -> str:
    raw = repr(
        {
            "platform": platform,
            "event_type": event_type,
            "event_id": event_id,
            "channel_name": channel_name,
            "actor_id": actor_id,
            "message": message,
        }
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class PlatformAudienceEvent:
    """Platform-normalized event passed into showrunner/audience state only."""

    platform: str
    event_id: str
    platform_event_type: str
    channel_name: str
    actor_name: str = ""
    actor_id: str = ""
    message: str = ""
    timestamp: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    moderation: dict[str, Any] = field(default_factory=dict)
    rate_limit: dict[str, Any] = field(default_factory=dict)
    presentation: dict[str, Any] = field(default_factory=dict)
    replay_key: str = ""

    def to_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["user_name"] = self.actor_name
        payload["user_id"] = self.actor_id
        payload["source"] = self.platform
        return payload


def build_platform_audience_event(
    *,
    platform: str,
    event_id: str,
    platform_event_type: str,
    channel_name: str,
    actor_name: str = "",
    actor_id: str = "",
    message: str = "",
    timestamp: int = 0,
    metadata: dict[str, Any] | None = None,
    replay_key: str = "",
) -> PlatformAudienceEvent:
    """Normalize a platform event behind the showrunner-only boundary."""

    metadata = dict(metadata or {})
    platform = _text(platform)
    platform_event_type = _text(platform_event_type)
    channel_name = _text(channel_name)
    actor_name = _text(actor_name)
    actor_id = _text(actor_id)
    message = _text(message)
    event_id = _text(event_id)
    moderation = _moderation(platform, platform_event_type, message, metadata)
    route = "showrunner" if moderation["allowed"] else "moderation_log"
    presentation = {
        "route": route,
        "surface": "audience",
        "effect": "audience_signal" if moderation["allowed"] else "moderated_signal",
        "direct_effects": [],
    }
    return PlatformAudienceEvent(
        platform=platform,
        event_id=event_id,
        platform_event_type=platform_event_type,
        channel_name=channel_name,
        actor_name=actor_name,
        actor_id=actor_id,
        message=message,
        timestamp=int(timestamp or 0),
        metadata=metadata,
        moderation=moderation,
        rate_limit=_rate_limit(platform, platform_event_type, channel_name, actor_id),
        presentation=presentation,
        replay_key=replay_key
        or _replay_key(platform, platform_event_type, event_id, channel_name, actor_id, message),
    )
