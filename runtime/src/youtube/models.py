"""Typed YouTube Live Chat adapter models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class YouTubeEvent:
    """Normalized YouTube Live Chat event that can be turned into a world event."""

    event_id: str
    event_type: str
    channel_id: str
    user_name: str = ""
    user_id: str = ""
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class YouTubeChatMessage:
    """Outbound YouTube Live Chat message."""

    message: str
    live_chat_id: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class YouTubeOutgoingChat:
    """Result of an outbound YouTube chat attempt."""

    ok: bool
    dry_run: bool
    live_chat_id: str
    message: str
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
