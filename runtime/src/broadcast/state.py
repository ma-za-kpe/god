"""Typed broadcast state derived from the world snapshot."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class BroadcastScene:
    scene_id: str
    scene_name: str
    layout: str
    fallback_scene: str
    reason: str
    mode: str = "dry-run"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BroadcastCaption:
    headline: str
    subhead: str
    lower_third: str
    ticker_lines: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BroadcastOverlay:
    title: str
    subtitle: str
    cards: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    labels: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BroadcastState:
    enabled: bool
    dry_run: bool
    scene: BroadcastScene
    caption: BroadcastCaption
    overlay: BroadcastOverlay
    commands: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    summary: str = ""
    world_id: str = ""
    source_epoch: int = 0

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["scene"] = self.scene.to_dict()
        payload["caption"] = self.caption.to_dict()
        payload["overlay"] = self.overlay.to_dict()
        return payload


def build_broadcast_state(snapshot: dict[str, Any]) -> dict[str, Any]:
    try:  # pragma: no cover - runtime package import path
        from .obs import BroadcastSurface
    except ImportError:  # pragma: no cover - flat test path
        from obs import BroadcastSurface

    return BroadcastSurface().compose(snapshot).to_dict()
