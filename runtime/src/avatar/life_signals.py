"""Procedural life signals for live avatar rendering."""

from __future__ import annotations

import math
import random
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


class LifeSignals:
    """Small deterministic motion layer for avatars before model-driven embodiment."""

    def __init__(
        self,
        *,
        breath_speed_seconds: float = 2.8,
        blink_interval_range: tuple[float, float] = (3.0, 8.0),
        blink_duration_range: tuple[float, float] = (0.1, 0.25),
    ) -> None:
        self.state = LifeState()
        self.breath_speed_seconds = max(0.1, breath_speed_seconds)
        self.blink_interval_range = blink_interval_range
        self.blink_duration_range = blink_duration_range
        self._blink_until = 0.0
        self._next_blink_at = time.time() + random.uniform(*self.blink_interval_range)

    def update(self, *, is_speaking: bool, audio_rms: float = 0.0, now: float | None = None) -> LifeState:
        now = now if now is not None else time.time()

        self.state.breathing_phase = (math.sin((now / self.breath_speed_seconds) * math.tau) + 1.0) / 2.0

        if now >= self._next_blink_at:
            self._blink_until = now + random.uniform(*self.blink_duration_range)
            self._next_blink_at = self._blink_until + random.uniform(*self.blink_interval_range)
        self.state.blink_state = now < self._blink_until

        self.state.head_sway_x = math.sin(now * 0.7) * 0.08
        self.state.head_sway_y = math.cos(now * 0.4) * 0.05

        clamped_rms = min(1.0, max(0.0, float(audio_rms or 0.0)))
        self.state.mouth_amplitude = min(1.0, clamped_rms * 1.8) if is_speaking else 0.0

        self.state.eye_focus_x = math.sin(now * 0.3) * 0.15
        self.state.eye_focus_y = math.cos(now * 0.5) * 0.1

        return self.state
