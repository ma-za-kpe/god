"""Typed avatar planning state."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class AvatarPlan:
    speaker: str
    agent_id: str
    renderer: str
    avatar_format: str
    expression: str
    pose: str
    motion: str
    lip_sync_source: str
    render_target: str
    speaker_soul_id: str = ""
    speaking: bool = False
    mouth_open: float = 0.0
    presentation_mode: str = "standard"
    notes: tuple[str, ...] = field(default_factory=tuple)
    rigged_avatar_cid: str = ""
    vrm_avatar_url: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AvatarState:
    enabled: bool
    dry_run: bool
    renderer: str
    avatar_format: str
    avatar_asset: str
    expression: str
    motion: str
    lip_sync_source: str
    render_target: str
    health: dict[str, Any]
    plan: AvatarPlan
    speaker_soul_id: str = ""
    speaking: bool = False
    mouth_open: float = 0.0
    presentation_mode: str = "standard"
    rigged_avatar_cid: str = ""
    vrm_avatar_url: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["plan"] = self.plan.to_dict()
        return payload
