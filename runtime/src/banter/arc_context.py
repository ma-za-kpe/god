"""Arc theme pressure builder — converts raw theme names into generative prompts.

The arc theme title string MUST NEVER appear in any generated prompt.
This module is the single conversion point from theme name → pressure text.
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


def _theme_noun(theme: str) -> str:
    return theme.replace("_", " ").replace("-", " ")


class ArcContextBuilder:
    """Converts arc theme names into generative pressure prompts."""

    def get_pressure(self, theme: str) -> ArcPressure:
        """Return ArcPressure for the given theme name. Never returns the theme name itself."""
        normalized = theme.lower().strip().replace(" ", "_").replace("-", "_")
        if normalized in _PRESSURE_TABLE:
            return _PRESSURE_TABLE[normalized]
        noun = _theme_noun(theme)
        return ArcPressure(
            pressure=f"what does {noun} cost the beings who have nothing left to give?",
            world_stakes="the Swarm watches who answers this honestly and who performs an answer",
        )

    def format_injection(self, theme: str) -> str:
        """Return the [ARC] prompt block for the given theme. Title never included."""
        p = self.get_pressure(theme)
        return (
            f"[ARC]\n"
            f"The question burning through the Veil right now: {p.pressure}\n"
            f"The cosmic stakes: {p.world_stakes}\n"
            f"Take a position on this tension — directly or indirectly — in every line.\n"
            f"Do not quote or name this question. Embody it."
        )


# Module-level singleton — engine imports this directly
arc_context_builder = ArcContextBuilder()
