"""Typed voice planning state."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class VoicePlan:
    speaker: str
    line: str
    emotion: str
    utterance_id: str
    voice_provider: str
    voice_model: str
    voice_name: str
    pitch: float
    speed: float
    sample_rate: int
    lip_sync_source: str
    transport: str
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VoiceState:
    enabled: bool
    dry_run: bool
    provider: str
    voice_model: str
    voice_name: str
    playback_mode: str
    speech_profile: str
    lip_sync_source: str
    transport: str
    health: dict[str, Any]
    plan: VoicePlan

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["plan"] = self.plan.to_dict()
        return payload
