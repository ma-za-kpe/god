"""showrunner_state.py - typed state and plan objects for the live showrunner."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ShowrunnerCue:
    """One broadcast cue selected from the world state."""

    cue_type: str
    headline: str
    details: str
    priority: int = 0
    agent_id: str = ""
    agent_name: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)
    source_event_ids: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ShowrunnerPlan:
    """Deterministic broadcast plan produced from a world snapshot."""

    mode: str
    scene: str
    speaker: str
    headline: str
    audience_prompt: str
    cues: tuple[ShowrunnerCue, ...] = field(default_factory=tuple)
    reasoning: tuple[str, ...] = field(default_factory=tuple)
    source_epoch: int = 0
    source_agent_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["cues"] = [cue.to_dict() for cue in self.cues]
        return payload


@dataclass(frozen=True)
class ShowrunnerState:
    """Minimal persisted showrunner state."""

    last_epoch: int = 0
    last_signature: str = ""
    last_plan: ShowrunnerPlan | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["last_plan"] = self.last_plan.to_dict() if self.last_plan else None
        return payload
