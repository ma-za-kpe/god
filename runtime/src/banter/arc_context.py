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
    2. For multi-word unknown themes, extract first meaningful word
       only if the full title has 3+ words.
    3. For short themes (1-2 words), use a generic paraphrase to avoid
       the title appearing in the output.
    4. Validate: the derived noun must never equal the full readable title.
    """
    normalized = _normalize_theme(theme)

    # Known themes have curated nouns
    if normalized in _THEME_NOUN_TABLE:
        return _THEME_NOUN_TABLE[normalized]

    # For unknown themes, derive a safe noun that is NOT the full title
    stop_words = {"and", "or", "the", "of", "vs", "a", "an", "in", "on", "to", "for", "is", "with"}
    words = normalized.replace("_", " ").split()
    meaningful = [w for w in words if w.lower() not in stop_words]
    full_title = normalized.replace("_", " ")

    if len(meaningful) <= 1:
        # Single meaningful word (or none) — the noun would equal the title.
        # Use a generic paraphrase: "this tension" avoids leaking the title.
        noun = "this tension"
    elif len(meaningful) == 2:
        # Two meaningful words — taking just one risks being too vague,
        # but it's safe since one word != two-word title.
        noun = meaningful[0]
    else:
        # 3+ meaningful words — first word is safe (one word != multi-word title)
        noun = meaningful[0]

    # Final safety check: the noun must not equal the full readable title
    if noun == full_title:
        noun = "this tension"

    return noun


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

        # Hard contract assertion: result must never contain the raw title
        readable_title = normalized.replace("_", " ")
        assert readable_title not in result.pressure.lower(), (
            f"CONTRACT VIOLATION: theme title '{readable_title}' leaked into pressure"
        )
        assert readable_title not in result.world_stakes.lower(), (
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
