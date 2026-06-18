"""Pacing Controller — energy-aware inter-beat delay calculation.

Computes inter-beat delays using priority-based rule resolution:
- Landed hit (score > 12): 3.0-5.0s pause
- Heated scene: 1.5-2.5s (faster exchanges)
- Cooling scene: 5.0-8.0s (allow topic shifts)
- Default: 3.0-5.0s scaled by previous score with move adjustments
- CONCEDE pre-delivery: +2.0s additive (not subject to conflict resolution)

Conflict resolution: longest delay wins.
Final clamping: [1.0, 10.0] seconds always.
"""

from __future__ import annotations

from typing import Literal

from .types import PacingDecision


class PacingController:
    """Energy-aware inter-beat delay calculator with priority-based rules."""

    # Rule delay ranges
    LANDED_HIT_DELAY: float = 4.0  # Fixed within [3.0, 5.0]
    HEATED_DELAY: float = 2.0  # Fixed within [1.5, 2.5]
    COOLING_DELAY: float = 6.5  # Fixed within [5.0, 8.0]
    DEFAULT_MIN: float = 3.0
    DEFAULT_MAX: float = 5.0

    # CONCEDE pre-delivery pause (additive)
    CONCEDE_PAUSE: float = 2.0

    # Move adjustments for default rule
    ESCALATE_TAUNT_ADJUSTMENT: float = -0.5
    CONCEDE_PIVOT_ADJUSTMENT: float = 0.5

    # Final clamping bounds
    MIN_DELAY: float = 1.0
    MAX_DELAY: float = 10.0

    def compute_delay(
        self,
        *,
        previous_score: int,
        upcoming_move: str,
        scene_energy: Literal["heated", "cooling", "neutral"],
        landed_hit: bool,
        scene_phase: str | None = None,
    ) -> PacingDecision:
        """Compute pacing decision using priority-based rule resolution.

        Args:
            previous_score: Quality score of the previous beat (0-15).
            upcoming_move: The move type about to be delivered.
            scene_energy: Current scene energy classification.
            landed_hit: Whether the previous beat was a landed hit (score > 12).

        Returns:
            PacingDecision with inter_beat_delay_s, pre_delivery_pause_s,
            and rule_applied.
        """
        # Compute candidate delays for each applicable rule
        candidates: list[tuple[float, str]] = []

        # Rule 1: Landed hit — delay in [3.0, 5.0]
        if landed_hit:
            candidates.append((self.LANDED_HIT_DELAY, "landed_hit"))

        # Rule 2: Heated scene — delay in [1.5, 2.5]
        if scene_energy == "heated":
            candidates.append((self.HEATED_DELAY, "heated"))

        # Rule 3: Cooling scene — delay in [5.0, 8.0]
        if scene_energy == "cooling":
            candidates.append((self.COOLING_DELAY, "cooling"))

        # Rule 4: Default — delay in [3.0, 5.0] scaled by previous_score
        if not candidates:
            # No special rule applies; compute default
            delay = self._compute_default_delay(previous_score, upcoming_move)
            candidates.append((delay, "default"))
        else:
            # Even when other rules apply, we always include default for
            # conflict resolution (longest wins). But per the design,
            # default only applies when no other rule fires. However, the
            # conflict resolution spec says "when multiple rules apply,
            # longest delay wins" — landed_hit AND heated is the example.
            # Default is only a fallback when nothing else applies.
            pass

        # Conflict resolution: longest delay wins
        winning_delay, rule_applied = max(candidates, key=lambda x: x[0])

        # CONCEDE pre-delivery pause: always additive, not subject to
        # conflict resolution
        pre_delivery_pause_s = 0.0
        if upcoming_move == "CONCEDE":
            pre_delivery_pause_s = self.CONCEDE_PAUSE

        # Final clamping to [1.0, 10.0]
        inter_beat_delay_s = max(self.MIN_DELAY, min(self.MAX_DELAY, winning_delay))

        # Macro rhythm override: scene phase widens or tightens the room.
        if scene_phase == "release":
            inter_beat_delay_s = min(self.MAX_DELAY, max(inter_beat_delay_s, 6.0))
            rule_applied = f"{rule_applied}+release"
        elif scene_phase == "climax":
            inter_beat_delay_s = max(self.MIN_DELAY, min(inter_beat_delay_s, 2.2))
            rule_applied = f"{rule_applied}+climax"
        elif scene_phase == "reset":
            inter_beat_delay_s = max(self.MIN_DELAY, min(inter_beat_delay_s, 4.5))
            rule_applied = f"{rule_applied}+reset"

        return PacingDecision(
            inter_beat_delay_s=inter_beat_delay_s,
            pre_delivery_pause_s=pre_delivery_pause_s,
            rule_applied=rule_applied,
        )

    def _compute_default_delay(self, previous_score: int, upcoming_move: str) -> float:
        """Compute default delay scaled proportionally to previous_score.

        Higher score → longer pause (to let the line breathe).
        Range: [3.0, 5.0] before move adjustments.

        Args:
            previous_score: Quality score of the previous beat (0-15).
            upcoming_move: The move type about to be delivered.

        Returns:
            Delay value in seconds.
        """
        # Scale previous_score (0-15) to [3.0, 5.0]
        # score 0 → 3.0, score 15 → 5.0
        score_clamped = max(0, min(15, previous_score))
        ratio = score_clamped / 15.0
        delay = self.DEFAULT_MIN + ratio * (self.DEFAULT_MAX - self.DEFAULT_MIN)

        # Move adjustments
        if upcoming_move in ("ESCALATE", "TAUNT"):
            delay += self.ESCALATE_TAUNT_ADJUSTMENT
        elif upcoming_move in ("CONCEDE", "PIVOT"):
            delay += self.CONCEDE_PIVOT_ADJUSTMENT

        return delay
