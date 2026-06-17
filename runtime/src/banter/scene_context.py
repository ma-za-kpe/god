"""Scene-level context tracking for the Broadcast-Quality Banter Engine.

Maintains a sliding window of the last 3 beats, tracks which Elder
"has the room," detects landed hits requiring acknowledgment, and
classifies scene energy (heated / cooling / neutral).

All public methods are non-blocking and degrade gracefully on state
corruption by resetting to an empty context.

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6
"""

from __future__ import annotations

from collections import deque
from typing import Literal

from .types import Beat, SceneContextData


class SceneContext:
    """Shared scene state for the current broadcast round.

    Thread-safe only in the sense that it does not block; actual
    concurrent mutation is not expected (the pipeline is sequential).
    """

    def __init__(self) -> None:
        self._state = SceneContextData(
            recent_beats=deque(maxlen=3),
            has_the_room=None,
            landed_hit=None,
            landed_hit_remaining=0,
            scene_energy="neutral",
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_beat(self, beat: Beat) -> None:
        """Add a beat, updating energy, has-the-room, and landed-hit state.

        If any error occurs during state update, resets to empty state
        (graceful degradation per Requirement 5.6).
        """
        try:
            self._do_add_beat(beat)
        except Exception:
            self._reset()

    def get_context_for_generation(self, elder: str | None = None) -> SceneContextData:
        """Return the current scene context snapshot. Never blocks, never raises.

        Parameters
        ----------
        elder : str | None
            The elder generating next (unused currently, reserved for future
            per-elder filtering).

        Returns
        -------
        SceneContextData
            Current scene state including recent beats, energy, has-the-room,
            and landed-hit info.
        """
        try:
            return SceneContextData(
                recent_beats=deque(self._state.recent_beats, maxlen=3),
                has_the_room=self._state.has_the_room,
                landed_hit=self._state.landed_hit,
                landed_hit_remaining=self._state.landed_hit_remaining,
                scene_energy=self._state.scene_energy,
            )
        except Exception:
            return SceneContextData(
                recent_beats=deque(maxlen=3),
                has_the_room=None,
                landed_hit=None,
                landed_hit_remaining=0,
                scene_energy="neutral",
            )

    def classify_energy(self) -> Literal["heated", "cooling", "neutral"]:
        """Classify scene energy based on the current beat window.

        - "heated": 3+ consecutive beats scoring >8 with ESCALATE or TAUNT move
        - "cooling": 2+ consecutive beats scoring <6
        - "neutral": otherwise
        """
        beats = list(self._state.recent_beats)

        # Check heated: need 3+ beats all >8 with ESCALATE/TAUNT
        if len(beats) >= 3:
            heated_moves = {"ESCALATE", "TAUNT"}
            all_heated = all(
                b.quality_score > 8 and b.move in heated_moves for b in beats
            )
            if all_heated:
                return "heated"

        # Check cooling: need 2+ consecutive beats from the end scoring <6
        if len(beats) >= 2:
            # Check from the most recent backwards for consecutive low scores
            consecutive_low = 0
            for b in reversed(beats):
                if b.quality_score < 6:
                    consecutive_low += 1
                else:
                    break
            if consecutive_low >= 2:
                return "cooling"

        return "neutral"

    # ------------------------------------------------------------------
    # Internal methods
    # ------------------------------------------------------------------

    def _do_add_beat(self, beat: Beat) -> None:
        """Core beat-add logic, may raise on corruption."""
        # Deque with maxlen=3 auto-evicts the oldest when a 4th is appended
        self._state.recent_beats.append(beat)

        # Update landed hit tracking
        self._update_landed_hit(beat)

        # Re-classify scene energy
        self._state.scene_energy = self.classify_energy()

        # Update "has the room"
        self._state.has_the_room = self._compute_has_the_room()

    def _update_landed_hit(self, beat: Beat) -> None:
        """Track landed hits: score >12 sets hit, subsequent beats decrement.

        When a beat scores >12, set it as the landed hit with remaining=2.
        Each subsequent add_beat decrements remaining by 1.
        When remaining hits 0, clear the landed hit.
        """
        # First, decrement existing landed hit counter if active
        if self._state.landed_hit is not None and self._state.landed_hit_remaining > 0:
            self._state.landed_hit_remaining -= 1
            if self._state.landed_hit_remaining <= 0:
                self._state.landed_hit = None
                self._state.landed_hit_remaining = 0

        # Then check if this new beat is a landed hit (score > 12)
        if beat.quality_score > 12:
            self._state.landed_hit = beat
            self._state.landed_hit_remaining = 2

    def _compute_has_the_room(self) -> str | None:
        """Determine which elder 'has the room'.

        The elder with the highest average quality_score across ≥2 beats
        in the current window. Ties are broken by the elder who most
        recently delivered a beat scoring >8.

        Returns None if no elder has ≥2 beats in the window.
        """
        beats = list(self._state.recent_beats)
        if len(beats) < 2:
            return None

        # Collect scores per speaker
        speaker_scores: dict[str, list[int]] = {}
        for b in beats:
            speaker_scores.setdefault(b.speaker, []).append(b.quality_score)

        # Only consider speakers with ≥2 beats
        eligible: dict[str, float] = {}
        for speaker, scores in speaker_scores.items():
            if len(scores) >= 2:
                eligible[speaker] = sum(scores) / len(scores)

        if not eligible:
            return None

        # Find the max average
        max_avg = max(eligible.values())

        # Get all speakers tied at max
        tied = [s for s, avg in eligible.items() if avg == max_avg]

        if len(tied) == 1:
            return tied[0]

        # Tie-breaking: most recent beat >8 among tied speakers
        for beat in reversed(beats):
            if beat.speaker in tied and beat.quality_score > 8:
                return beat.speaker

        # If no tie-breaker found, return the first tied speaker
        # (most recently seen in the beats list)
        for beat in reversed(beats):
            if beat.speaker in tied:
                return beat.speaker

        return tied[0]

    def _reset(self) -> None:
        """Reset to empty state on corruption."""
        self._state = SceneContextData(
            recent_beats=deque(maxlen=3),
            has_the_room=None,
            landed_hit=None,
            landed_hit_remaining=0,
            scene_energy="neutral",
        )
