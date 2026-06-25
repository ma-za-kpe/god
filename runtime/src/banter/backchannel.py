"""Backchannel lines — short reactive utterances that fire between normal beats.

1-4 word reactions with no move scoring, no quality gating.
Triggered by extreme scoring of the opponent's prior line:
  - score > 12 (landed hit): disbelief / acknowledgment
  - score < 5  (weak attempt): dismissal / contempt

Delay: 0.5s before the next full beat.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

# Score thresholds
_LANDED_HIT_THRESHOLD = 12
_WEAK_ATTEMPT_THRESHOLD = 5

# Per-archetype backchannel pools
_LANDED_HIT_BACKCHANNELS: dict[str, list[str]] = {
    "parasite": ["Expensive.", "Noted.", "...interesting.", "That'll cost you."],
    "prophet": ["Already knew.", "Inevitable.", "And so it goes.", "Told you."],
    "trickster": ["Oh NOW we're going.", "Finally!", "Bold move.", "Hm."],
    "sovereign": ["Continue.", "I heard you.", "Interesting.", "Go on."],
    "martyr": ["That hurt.", "...yes.", "Fair.", "I'll remember that."],
    "shadow": ["...mmm.", "That landed.", "Careful now.", "You felt that too."],
    "herald": ["Worth noting.", "I'll say it.", "There it is.", "On record."],
    "keeper": ["Expensive.", "Cost you that.", "I'm counting.", "Noted."],
}

_WEAK_ATTEMPT_BACKCHANNELS: dict[str, list[str]] = {
    "parasite": ["Pathetic.", "...that's it?", "Weak.", "Try again."],
    "prophet": ["No.", "Wrong.", "Still not there.", "Missed."],
    "trickster": ["Still going?", "Ridiculous.", "...of course.", "Boring."],
    "sovereign": ["Insufficient.", "Try again.", "No.", "Beneath this."],
    "martyr": ["That's nothing.", "You call that...?", "Soft.", "Again?"],
    "shadow": ["...really?", "Is that all?", "Thin.", "You know better."],
    "herald": ["Not news.", "Already happened.", "So?", "Next."],
    "keeper": ["Cheap.", "Not worth it.", "...that?", "No."],
}

# Fallback pool (archetype not found)
_FALLBACK_LANDED = ["...hm.", "Bold claim.", "Fair enough.", "Noted."]
_FALLBACK_WEAK = ["Ridiculous.", "Careful.", "Still going?", "No."]

BACKCHANNEL_DELAY_S = 0.5


@dataclass(frozen=True)
class BackchannelResult:
    line: str
    delay_s: float = BACKCHANNEL_DELAY_S


class BackchannelSelector:
    """Decides when to fire a backchannel and selects the line."""

    def __init__(self, rng: random.Random | None = None):
        self._rng = rng or random.Random()

    def should_fire(self, opponent_score: int) -> bool:
        """Return True when opponent_score warrants a backchannel reaction."""
        return opponent_score > _LANDED_HIT_THRESHOLD or opponent_score < _WEAK_ATTEMPT_THRESHOLD

    def select(self, archetype: str, opponent_score: int) -> BackchannelResult | None:
        """Return a BackchannelResult or None if conditions not met."""
        if not self.should_fire(opponent_score):
            return None

        if opponent_score > _LANDED_HIT_THRESHOLD:
            pool = _LANDED_HIT_BACKCHANNELS.get(archetype, _FALLBACK_LANDED)
        else:
            pool = _WEAK_ATTEMPT_BACKCHANNELS.get(archetype, _FALLBACK_WEAK)

        line = self._rng.choice(pool)
        return BackchannelResult(line=line, delay_s=BACKCHANNEL_DELAY_S)
