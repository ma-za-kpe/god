"""VeilLayer — meta-awareness injection for the banter engine.

Injects awareness that the Elder performs before patron-gods with real
economic stakes. Does not break character: Elders are not AI-aware.
They are aware of the divine audience and its wagers.
"""

from __future__ import annotations

_VEIL_INJECTION = (
    "[VEIL]\n"
    "The Swarm watches this exchange. Patron-gods are wagering on your words right now.\n"
    "Do not perform for them — that's exactly what they want and it makes you predictable.\n"
    "Be yourself, which is the most dangerous thing you can be in front of an audience.\n"
    '(Do not reference "the Swarm," "patrons," or "the Veil" by name unless it\'s\n'
    "natural to your archetype. Let the awareness bleed into the texture of the line,\n"
    "not the content.)"
)

# Moves that suppress VeilLayer below the tension floor
_CONCEDE_SUPPRESSED_MOVES = frozenset({"CONCEDE"})
_CONCEDE_TENSION_FLOOR = 4


class VeilLayer:
    """Decides when to inject Veil-awareness and returns the injection text."""

    def should_inject(
        self,
        beat_number: int,
        move: str,
        pair_state=None,
        twitch_event_fired: bool = False,
    ) -> bool:
        """Return True when this beat should receive the [VEIL] block.

        Rules (from requirements Section 6.2):
        - CONCEDE at tension < 4 → suppress (graceful exits don't need the Swarm)
        - Twitch event fired → always inject
        - Every 8th beat (beat_number % 8 == 0) → inject
        """
        if move in _CONCEDE_SUPPRESSED_MOVES:
            tension = pair_state.tension_level if pair_state is not None else 5
            if tension < _CONCEDE_TENSION_FLOOR:
                return False
        if twitch_event_fired:
            return True
        return beat_number % 8 == 0

    def get_injection(self) -> str:
        """Return the [VEIL] prompt block. Text is fixed for all archetypes."""
        return _VEIL_INJECTION
