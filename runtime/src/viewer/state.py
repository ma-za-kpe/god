"""Typed viewer interaction state."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ViewerState:
    """Deterministic viewer prompt and overlay state."""

    enabled: bool
    dry_run: bool
    mode: str
    world_id: str
    source_epoch: int
    interaction_mode: str
    prompt: str
    summary: str
    focus: str
    labels: tuple[str, ...] = field(default_factory=tuple)
    cards: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    poll: dict[str, Any] = field(default_factory=dict)
    prediction: dict[str, Any] = field(default_factory=dict)
    extension_cards: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    options: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    commands: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
