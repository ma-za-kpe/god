"""SilenceController — first-class silence beat producer.

Silence is not a failed generation. It is a deliberate dramatic beat
produced when the room needs to breathe after a landed hit or falling tension.

Produces BeatResult with line_type="silence", no quality score, 3-5s pacing.

Requirements: 5.2, 12.8
"""

from __future__ import annotations

import random

from .rate_controllers import SlidingWindowController
from .types import BeatResult, PairState, SceneContextData


class SilenceController:
    """Determines when silence should be emitted as a first-class beat.

    Triggers:
    - Landed hit aftermath (opponent scored > 12 and acknowledgment pending)
    - Falling tension (tension dropped by 2+ in recent history)

    Silence is the highest-priority mode in the resolution chain.
    """

    def __init__(self, rng: random.Random | None = None) -> None:
        self._rng = rng or random.Random()
        self._last_tension: int = 5
        self._silence_rc = SlidingWindowController(max_count=1, window_size=7)

    def should_silence(
        self,
        scene_data: SceneContextData,
        pair_state: PairState | None,
    ) -> bool:
        """Return True when this beat should be a silence beat.

        Conditions (any one triggers silence):
        1. Landed hit aftermath: a hit scored > 12 and acknowledgment is pending.
        2. Falling tension: tension dropped 2+ from last known level.

        The controller uses a deterministic sliding window gate after the
        conditions are met so silence remains rare without relying on RNG.
        """
        # Condition 1: Landed hit aftermath
        landed_hit_active = (
            scene_data.landed_hit is not None
            and scene_data.landed_hit_remaining > 0
            and scene_data.landed_hit.quality_score > 12
        )

        # Condition 2: Falling tension
        current_tension = pair_state.tension_level if pair_state is not None else 5
        falling_tension = (self._last_tension - current_tension) >= 2

        # Update last known tension
        if pair_state is not None:
            self._last_tension = current_tension

        if not (landed_hit_active or falling_tension):
            return False

        # Deterministic gate to prevent silence overuse
        self._silence_rc.tick()
        if not self._silence_rc.allow("global"):
            return False
        self._silence_rc.record("global")
        return True

    def produce_beat(self) -> BeatResult:
        """Produce a silence BeatResult.

        Returns a BeatResult with:
        - line_type="silence" in metadata
        - source="silence"
        - 3-5 second pacing
        - No quality score
        """
        delay = self._rng.uniform(3.0, 5.0)
        return BeatResult(
            line="...",
            move="SILENCE",
            quality_score=0,
            delay_s=delay,
            pre_pause_s=0.0,
            source="silence",
            metadata={
                "line_type": "silence",
                "clip_candidate": False,
            },
        )
