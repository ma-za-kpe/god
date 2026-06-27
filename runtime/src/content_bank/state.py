"""Typed content bank state for pre-generated story assets."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ContentBankState:
    """Structured pre-generated story assets for the live stage."""

    enabled: bool
    dry_run: bool
    mode: str
    world_id: str
    source_epoch: int
    horizon_days: int
    bank_id: str
    arc_count: int
    dialogue_count: int
    scene_count: int
    clip_count: int
    focus: str
    summary: str
    labels: tuple[str, ...] = field(default_factory=tuple)
    cards: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    arcs: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    dialogue: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    scene_prompts: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    clip_prompts: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    assets: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    commands: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
