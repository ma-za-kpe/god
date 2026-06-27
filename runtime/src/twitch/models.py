"""Typed Twitch adapter models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class TwitchEvent:
    """Normalized Twitch event that can be turned into a world event."""

    event_id: str
    event_type: str
    channel_name: str
    user_name: str = ""
    user_id: str = ""
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TwitchChatMessage:
    """Outbound Twitch chat message."""

    message: str
    channel_name: str
    reply_to_message_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TwitchOutgoingChat:
    """Result of an outbound chat attempt."""

    ok: bool
    dry_run: bool
    channel_name: str
    message: str
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
