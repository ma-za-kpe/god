"""Typed audience state for the live stage."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class AudienceState:
    """Deterministic audience pressure, patronage, and story hooks."""

    enabled: bool
    dry_run: bool
    mode: str
    world_id: str
    source_epoch: int
    scene: str
    chat_pressure: int
    unique_supporters_24h: int
    supporter_waves_24h: int
    raid_waves_24h: int
    patronage_index: float
    hype_index: float
    story_hook: str
    summary: str
    labels: tuple[str, ...] = field(default_factory=tuple)
    cards: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    top_supporters: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    signals: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    commands: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
