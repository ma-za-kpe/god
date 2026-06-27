"""Procedural life signals for live avatar rendering."""

from __future__ import annotations

import hashlib
import math
import time
from dataclasses import asdict, dataclass


@dataclass
class LifeState:
    breathing_phase: float = 0.0
    blink_state: bool = False
    head_sway_x: float = 0.0
    head_sway_y: float = 0.0
    mouth_amplitude: float = 0.0
    eye_focus_x: float = 0.0
    eye_focus_y: float = 0.0

    def to_dict(self) -> dict[str, float | bool]:
        return asdict(self)


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _stable_unit(identity_key: str, salt: str) -> float:
    if not identity_key:
        return 0.0
    digest = hashlib.sha256(f"{salt}:{identity_key}".encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") / 0xFFFFFFFF


def _positive_range(values: tuple[float, float], minimum: float) -> tuple[float, float]:
    low = max(minimum, float(values[0]))
    high = max(low, float(values[1]))
    return low, high


def generate_life_state(
    *,
    now: float,
    is_speaking: bool,
    audio_rms: float = 0.0,
    identity_key: str = "",
    breath_speed_seconds: float = 2.8,
    blink_interval_range: tuple[float, float] = (3.0, 8.0),
    blink_duration_range: tuple[float, float] = (0.1, 0.25),
) -> LifeState:
    """Pure procedural signal generator with timestamp injection for tests."""

    breath_speed = max(0.1, float(breath_speed_seconds))
    identity_phase = _stable_unit(identity_key, "life-phase") * math.tau
    breathing_phase = (
        math.sin((float(now) / breath_speed) * math.tau + identity_phase) + 1.0
    ) / 2.0

    blink_low, blink_high = _positive_range(blink_interval_range, 0.2)
    duration_low, duration_high = _positive_range(blink_duration_range, 0.02)
    blink_interval = blink_low + _stable_unit(identity_key, "blink-interval") * (
        blink_high - blink_low
    )
    blink_duration = duration_low + _stable_unit(identity_key, "blink-duration") * (
        duration_high - duration_low
    )
    blink_offset = _stable_unit(identity_key, "blink-offset") * blink_interval
    blink_progress = (float(now) + blink_offset) % blink_interval
    blink_state = blink_progress < min(blink_duration, blink_interval * 0.4)

    audio = _clamp(float(audio_rms or 0.0), 0.0, 1.0)
    fallback_mouth = 0.30 + 0.22 * (0.5 + 0.5 * math.sin(float(now) * 10.5 + identity_phase))
    mouth_amplitude = 0.0
    if is_speaking:
        mouth_amplitude = min(1.0, audio * 1.8) if audio > 0.0 else fallback_mouth

    return LifeState(
        breathing_phase=_clamp(breathing_phase, 0.0, 1.0),
        blink_state=blink_state,
        head_sway_x=math.sin(float(now) * 0.7 + identity_phase) * 0.08,
        head_sway_y=math.cos(float(now) * 0.4 + identity_phase) * 0.05,
        mouth_amplitude=_clamp(mouth_amplitude, 0.0, 1.0),
        eye_focus_x=math.sin(float(now) * 0.3 + identity_phase) * 0.15,
        eye_focus_y=math.cos(float(now) * 0.5 + identity_phase) * 0.1,
    )


class LifeSignals:
    """Small deterministic motion layer for avatars before model-driven embodiment."""

    def __init__(
        self,
        *,
        breath_speed_seconds: float = 2.8,
        blink_interval_range: tuple[float, float] = (3.0, 8.0),
        blink_duration_range: tuple[float, float] = (0.1, 0.25),
        identity_key: str = "",
    ) -> None:
        self.state = LifeState()
        self.breath_speed_seconds = max(0.1, breath_speed_seconds)
        self.blink_interval_range = blink_interval_range
        self.blink_duration_range = blink_duration_range
        self.identity_key = identity_key

    def update(
        self,
        *,
        is_speaking: bool,
        audio_rms: float = 0.0,
        now: float | None = None,
        identity_key: str = "",
    ) -> LifeState:
        now = now if now is not None else time.time()
        self.state = generate_life_state(
            now=now,
            is_speaking=is_speaking,
            audio_rms=audio_rms,
            identity_key=identity_key or self.identity_key,
            breath_speed_seconds=self.breath_speed_seconds,
            blink_interval_range=self.blink_interval_range,
            blink_duration_range=self.blink_duration_range,
        )
        return self.state
