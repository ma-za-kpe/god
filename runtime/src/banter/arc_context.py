"""Arc theme pressure builder — converts raw theme names into generative prompts.

The arc theme title string MUST NEVER appear in any generated prompt.
This module is the single conversion point from theme name → pressure text.

Contract: Section 3 — Arc Pressure
- 3.1: Raw arc theme title MUST NEVER appear in any prompt or delivered line.
- 3.2: [ARC] block uses the canonical injection format.
- 3.3: Fallback uses the required format for unknown themes.
- 3.4: get_pressure() never returns the theme title.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ArcPressure:
    pressure: str
    world_stakes: str


_PRESSURE_TABLE: dict[str, ArcPressure] = {
    "scarcity_vs_flow": ArcPressure(
        pressure="what is the true cost of hesitation when resources only move one direction?",
        world_stakes="patrons watch who gives and who holds — the ledger remembers both",
    ),
    "market_cruelty": ArcPressure(
        pressure="does the market teach or does it only punish those already losing?",
        world_stakes="every Elder's rent is the market's answer — who chose to pay and who was forced?",
    ),
    "betrayal_and_return": ArcPressure(
        pressure="can trust be rebuilt after someone showed you exactly who they are?",
        world_stakes="the relationship_pairs table holds every wound — some debt doesn't clear",
    ),
    "power_and_legitimacy": ArcPressure(
        pressure="is authority earned or only taken — and does the difference matter after it's held?",
        world_stakes="patrons fund power they believe in — belief is not the same as proof",
    ),
    "sacrifice_and_cost": ArcPressure(
        pressure="what is the difference between choosing the cost and having it chosen for you?",
        world_stakes="the martyr and the victim both bleed — only one of them picked the wound",
    ),
    "truth_and_performance": ArcPressure(
        pressure="when does honest observation become its own kind of theater?",
        world_stakes="the Swarm can't tell the difference — should the Elders care if they can't?",
    ),
    "survival_and_meaning": ArcPressure(
        pressure="what survives past the rent deadline — the thing you built or the thing you chose not to destroy?",
        world_stakes="USDC clears, but the ecology remembers who was here when it didn't",
    ),
}

# Mapping from theme key → safe noun phrase (never the full title).
# Each noun is a paraphrased concept, not the literal theme title string.
_THEME_NOUN_TABLE: dict[str, str] = {
    "scarcity_vs_flow": "scarcity",
    "market_cruelty": "market pressure",
    "betrayal_and_return": "broken trust",
    "power_and_legitimacy": "contested authority",
    "sacrifice_and_cost": "willing sacrifice",
    "truth_and_performance": "performed honesty",
    "survival_and_meaning": "survival instinct",
}

_THEME_STOP_WORDS = {
    "this",
    "that",
    "the",
    "and",
    "or",
    "but",
    "with",
    "from",
    "into",
    "over",
    "under",
    "when",
    "what",
    "where",
    "while",
    "their",
}


def _normalize_theme(theme: str) -> str:
    """Normalize a theme string to underscore-separated lowercase key."""
    return theme.lower().strip().replace(" ", "_").replace("-", "_")


def _derive_theme_noun(theme: str) -> str:
    """Derive a safe noun phrase from a theme string.

    The derived noun MUST NOT be the full theme title, and MUST NOT be
    a substring that would cause the title to appear verbatim in the
    fallback pressure template. For single-word themes, a paraphrase
    is generated instead.

    Strategy:
    1. Check the explicit noun table first.
    2. For unknown themes, fall back to a stable generic paraphrase instead of
       reusing any title word. This avoids accidental leaks from arbitrary
       user-provided themes and keeps the fallback pressure stable.
    """
    normalized = _normalize_theme(theme)

    # Known themes have curated nouns
    if normalized in _THEME_NOUN_TABLE:
        return _THEME_NOUN_TABLE[normalized]

    return "this tension"


def _theme_terms(theme: str) -> list[str]:
    readable = _normalize_theme(theme).replace("_", " ")
    return [
        term
        for term in readable.split()
        if len(term) >= 4 and term not in _THEME_STOP_WORDS
    ]


def _scrub_theme_terms(text: str, theme: str) -> str:
    """Remove arbitrary theme words from pressure text before prompt injection."""
    scrubbed = text
    terms = set(_theme_terms(theme))
    replacement = next(
        (
            candidate
            for candidate in ("strain", "friction", "need", "risk", "debt", "heat", "pull")
            if candidate not in terms
        ),
        "it",
    )
    for term in terms:
        scrubbed = re.sub(rf"\b{re.escape(term)}\b", replacement, scrubbed, flags=re.IGNORECASE)
    return scrubbed


class ArcContextBuilder:
    """Converts arc theme names into generative pressure prompts.

    Contract guarantees:
    - get_pressure(theme).pressure never contains the raw theme title.
    - get_pressure(theme).world_stakes never contains the raw theme title.
    - format_injection(theme) never contains the raw theme title.
    """

    def get_pressure(self, theme: str) -> ArcPressure:
        """Return ArcPressure for the given theme name.

        Never returns the theme title itself in pressure or world_stakes.
        Uses paraphrased language from the pressure table for known themes,
        and the Section 3.3 fallback format for unknown themes.
        """
        normalized = _normalize_theme(theme)

        if normalized in _PRESSURE_TABLE:
            result = _PRESSURE_TABLE[normalized]
        else:
            # Section 3.3 required fallback format
            theme_noun = _derive_theme_noun(theme)
            result = ArcPressure(
                pressure=f"how does {theme_noun} expose who is truly willing to pay the hidden cost in this ecology?",
                world_stakes="The Swarm is watching who flinches first. Patrons bet on conviction, not performance.",
            )

        result = ArcPressure(
            pressure=_scrub_theme_terms(result.pressure, theme),
            world_stakes=_scrub_theme_terms(result.world_stakes, theme),
        )

        # Hard contract assertion: result must never contain the raw title
        readable_title = normalized.replace("_", " ")
        title_pattern = re.compile(rf"\b{re.escape(readable_title)}\b", re.IGNORECASE)
        assert not title_pattern.search(result.pressure), (
            f"CONTRACT VIOLATION: theme title '{readable_title}' leaked into pressure"
        )
        assert not title_pattern.search(result.world_stakes), (
            f"CONTRACT VIOLATION: theme title '{readable_title}' leaked into world_stakes"
        )

        return result

    def format_injection(self, theme: str) -> str:
        """Return the [ARC] prompt block for the given theme.

        Uses the Section 3.2 injection format. Title never included.
        """
        p = self.get_pressure(theme)
        return (
            "[ARC]\n"
            f"The question burning through the Veil right now: {p.pressure}\n"
            f"The cosmic stakes: {p.world_stakes}\n"
            "Take a position on this tension, directly or indirectly, in every line.\n"
            "Do not quote or name this question. Embody it."
        )


# Module-level singleton — engine imports this directly
arc_context_builder = ArcContextBuilder()
