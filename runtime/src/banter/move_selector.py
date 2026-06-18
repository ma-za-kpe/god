"""Move_Selector — Probabilistic conversational move selection.

Replaces `_pick_reactive_move()` from archetype_graphs.py with a probabilistic
distribution system that accounts for context, history, and scene dynamics.
"""

from __future__ import annotations

import logging
from typing import Literal

from .types import MoveContext, MoveDistribution

log = logging.getLogger("god.banter.move_selector")

# ---------------------------------------------------------------------------
# Archetype signature moves
# ---------------------------------------------------------------------------

ARCHETYPE_SIGNATURE_MOVE: dict[str, str] = {
    "parasite": "COUNTER",
    "prophet": "QUESTION",
    "trickster": "DEFLECT",
    "sovereign": "ESCALATE",
    "martyr": "CONCEDE",
    "shadow": "DEFLECT",
    "herald": "PIVOT",
    "keeper": "COUNTER",
}

ALL_MOVES: list[str] = [
    "COUNTER", "ESCALATE", "DEFLECT", "TAUNT",
    "QUESTION", "PIVOT", "CONCEDE", "CALLBACK",
]

# Per-archetype moves that are near-forbidden (heavy weight penalty, T2.3)
# The minimum floor (_enforce_minimums) still raises these to 0.02,
# but they remain far below normal allocation.
ARCHETYPE_HEAVY_PENALTIES: dict[str, list[str]] = {
    "keeper":    ["CONCEDE"],   # keeper guards; yielding costs too much
    "parasite":  ["DEFLECT"],   # parasite extracts or confronts; never hides
    "sovereign": ["CONCEDE"],   # sovereign does not yield without decree
    "prophet":   ["DEFLECT"],   # prophet speaks plainly; evasion is apostasy
    "martyr":    ["DEFLECT"],   # martyr bears the weight; deflection dishonors it
}

# Fear keywords per archetype (used for ESCALATE+QUESTION boost)
ARCHETYPE_FEARS: dict[str, list[str]] = {
    "parasite": ["exposure", "worthlessness", "rejection"],
    "prophet": ["meaninglessness", "irrelevance", "silence"],
    "trickster": ["boredom", "predictability", "control"],
    "sovereign": ["weakness", "chaos", "disobedience"],
    "martyr": ["being forgotten", "ingratitude", "pointlessness"],
    "shadow": ["light", "scrutiny", "being known"],
    "herald": ["stagnation", "being ignored", "obsolescence"],
    "keeper": ["loss", "change", "abandonment"],
}


# ---------------------------------------------------------------------------
# Distribution computation
# ---------------------------------------------------------------------------


def _base_distribution(archetype: str) -> dict[str, float]:
    """Create a base probability distribution for an archetype.

    Signature move gets 0.30 (below the 0.40 cap), rest distributed evenly.
    """
    signature = ARCHETYPE_SIGNATURE_MOVE.get(archetype, "COUNTER")
    remaining = 1.0 - 0.30
    non_sig_count = len(ALL_MOVES) - 1
    even_share = remaining / non_sig_count

    dist: dict[str, float] = {}
    for move in ALL_MOVES:
        if move == signature:
            dist[move] = 0.30
        else:
            dist[move] = even_share

    return dist


def _normalize(dist: dict[str, float]) -> dict[str, float]:
    """Normalize distribution to sum to 1.0."""
    total = sum(dist.values())
    if total <= 0:
        # Emergency fallback: uniform
        even = 1.0 / len(ALL_MOVES)
        return {m: even for m in ALL_MOVES}
    return {k: v / total for k, v in dist.items()}


def _enforce_minimums(dist: dict[str, float], signature: str) -> dict[str, float]:
    """Enforce: signature <= 0.40, non-signature >= 0.02."""
    # Cap signature at 0.40
    if dist.get(signature, 0) > 0.40:
        excess = dist[signature] - 0.40
        dist[signature] = 0.40
        # Redistribute excess to others
        others = [m for m in ALL_MOVES if m != signature]
        share = excess / len(others)
        for m in others:
            dist[m] += share

    # Floor non-signature at 0.02
    deficit = 0.0
    for move in ALL_MOVES:
        if move != signature and dist[move] < 0.02:
            deficit += 0.02 - dist[move]
            dist[move] = 0.02

    if deficit > 0:
        # Take from signature first, then proportionally from those above 0.02
        available_from_sig = dist[signature] - 0.02
        if available_from_sig >= deficit:
            dist[signature] -= deficit
        else:
            dist[signature] -= available_from_sig
            remaining_deficit = deficit - available_from_sig
            donors = [m for m in ALL_MOVES if m != signature and dist[m] > 0.02]
            if donors:
                per_donor = remaining_deficit / len(donors)
                for m in donors:
                    dist[m] = max(0.02, dist[m] - per_donor)

    return _normalize(dist)


def compute_distribution(ctx: MoveContext) -> MoveDistribution:
    """Produce a probability distribution over moves.

    Invariants:
    - Sum of probabilities == 1.0 (±0.01)
    - Signature move <= 0.40
    - Every non-signature move >= 0.02
    - After 2 consecutive same moves: that move == 0.10
    - After 3+ consecutive COUNTERs in pair: only PIVOT/CONCEDE at 0.50 each
    - Tension > 7: CONCEDE+PIVOT += 0.30
    - Fear keyword match: ESCALATE+QUESTION += 0.20
    - Losing the room (2 consecutive < 6): PIVOT = 0.50

    Args:
        ctx: MoveContext with all decision inputs.

    Returns:
        MoveDistribution with probabilities summing to 1.0.
    """
    signature = ARCHETYPE_SIGNATURE_MOVE.get(ctx.archetype, "COUNTER")

    # --- Rule: Counter-loop breaker (highest priority, overrides everything) ---
    if ctx.consecutive_counters_in_pair >= 3:
        return MoveDistribution(
            probabilities={
                "COUNTER": 0.0,
                "ESCALATE": 0.0,
                "DEFLECT": 0.0,
                "TAUNT": 0.0,
                "QUESTION": 0.0,
                "PIVOT": 0.50,
                "CONCEDE": 0.50,
                "CALLBACK": 0.0,
            }
        )

    # --- Rule: Losing the room (2+ consecutive low scores) → PIVOT dominant ---
    if ctx.consecutive_low_scores >= 2:
        dist = {m: 0.0 for m in ALL_MOVES}
        dist["PIVOT"] = 0.50
        # Distribute remaining 0.50 among other moves
        others = [m for m in ALL_MOVES if m != "PIVOT"]
        share = 0.50 / len(others)
        for m in others:
            dist[m] = share
        dist = _enforce_minimums(dist, signature)
        return MoveDistribution(probabilities=dist)

    # --- Start with base distribution ---
    dist = _base_distribution(ctx.archetype)

    # --- Rule: Archetype forbidden move penalties (T2.3) ---
    # Redistribute to moves OTHER than CONCEDE/PIVOT so we don't artificially
    # inflate the high-tension baseline (preserves the >=0.25 boost invariant).
    for penalized_move in ARCHETYPE_HEAVY_PENALTIES.get(ctx.archetype, []):
        if penalized_move in dist:
            removed = dist[penalized_move] - 0.01
            dist[penalized_move] = 0.01
            others = [
                m for m in ALL_MOVES
                if m != penalized_move and m not in ("CONCEDE", "PIVOT")
            ]
            if others:
                per_other = removed / len(others)
                for m in others:
                    dist[m] += per_other

    # --- Rule: Consecutive move penalty ---
    if len(ctx.last_3_moves) >= 2 and ctx.last_3_moves[-1] == ctx.last_3_moves[-2]:
        repeated_move = ctx.last_3_moves[-1]
        if repeated_move in dist:
            # Set to 0.10, redistribute removed weight
            old_val = dist[repeated_move]
            if old_val > 0.10:
                excess = old_val - 0.10
                dist[repeated_move] = 0.10
                others = [m for m in ALL_MOVES if m != repeated_move]
                share = excess / len(others)
                for m in others:
                    dist[m] += share

    # --- Rule: High tension (> 7) → boost CONCEDE + PIVOT by 0.30 ---
    if ctx.tension_level is not None and ctx.tension_level > 7:
        # Add 0.30 total to CONCEDE and PIVOT (0.15 each)
        boost_total = 0.30
        boost_each = boost_total / 2.0
        dist["CONCEDE"] += boost_each
        dist["PIVOT"] += boost_each
        # Reduce others proportionally to compensate
        others = [m for m in ALL_MOVES if m not in ("CONCEDE", "PIVOT")]
        total_others = sum(dist[m] for m in others)
        if total_others > boost_total:
            reduction_ratio = (total_others - boost_total) / total_others
            for m in others:
                dist[m] *= reduction_ratio
        else:
            # Spread the reduction evenly
            reduction_each = boost_total / len(others)
            for m in others:
                dist[m] = max(0.0, dist[m] - reduction_each)

    # --- Rule: Fear keyword match → ESCALATE + QUESTION += 0.20 ---
    # Per requirement 4.5: if arc_theme exactly matches any fear keyword for
    # this archetype, boost ESCALATE + QUESTION by 0.20 total.
    if ctx.fear_keywords and ctx.arc_theme:
        arc_lower = ctx.arc_theme.lower().strip()
        fear_match = any(
            arc_lower == kw.lower().strip() for kw in ctx.fear_keywords
        )

        if fear_match:
            boost_total = 0.20
            boost_each = boost_total / 2.0
            dist["ESCALATE"] += boost_each
            dist["QUESTION"] += boost_each
            # Reduce others proportionally
            others = [m for m in ALL_MOVES if m not in ("ESCALATE", "QUESTION")]
            total_others = sum(dist[m] for m in others)
            if total_others > boost_total:
                reduction_ratio = (total_others - boost_total) / total_others
                for m in others:
                    dist[m] *= reduction_ratio
            else:
                reduction_each = boost_total / len(others)
                for m in others:
                    dist[m] = max(0.0, dist[m] - reduction_each)

    # --- Final enforcement ---
    dist = _enforce_minimums(dist, signature)

    return MoveDistribution(probabilities=dist)
