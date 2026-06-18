"""Contract-aligned data models for Quality Judge V2 and Hard Ban enforcement.

Defines:
- ContractQualityScore: 6-dimension frozen dataclass (Section 7)
- HardBan: banned pattern definition (Section 10)
- HardBanVerdict: pass/fail result from HardBanChecker (Section 10)

These replace the legacy QualityScore (5 dims) and EnhancedQualityScore (7 dims)
for the contract-alignment pipeline. The key changes:
- Removes `shareability` as a scored dimension
- Renames `thematic_relevance` → `pressure_relevance`
- Adds `clip_candidate` as an output flag (not a scored dimension)
- Drops `voice_authenticity` bonus math; it's now a standalone dimension

Requirements: 7.2, 7.5, 7.6, 10.1
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# ContractQualityScore — 6-dimension quality evaluation (Section 7)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ContractQualityScore:
    """6-dimension quality evaluation aligned to the contract spec.

    Each dimension is scored on a 0-3 integer scale:
        0 = absent, 1 = weak, 2 = present, 3 = strong.

    Maximum total: 18.

    `shareability` is removed as a scored dimension.
    `clip_candidate` is an output flag derived from the score, not a dimension.

    Requirements: 7.2, 7.5, 7.6
    """

    sharpness: int  # 0-3: conciseness, punch, rhetorical clarity
    emotional_texture: int  # 0-3: vulnerability, tension, warmth
    rhythm: int  # 0-3: cadence, clause variety, pause points
    pressure_relevance: int  # 0-3: connection to arc pressure (renamed from thematic_relevance)
    voice_authenticity: int  # 0-3: archetype-specific vocabulary and tone
    subtext_depth: int  # 0-3: hidden meaning, implication, cost

    @property
    def total(self) -> int:
        """Combined score across all 6 dimensions (0-18)."""
        return (
            self.sharpness
            + self.emotional_texture
            + self.rhythm
            + self.pressure_relevance
            + self.voice_authenticity
            + self.subtext_depth
        )

    @property
    def clip_candidate(self) -> bool:
        """True when the line qualifies as a clip-worthy moment.

        Criteria (Section 7.5):
            total >= 14 AND sharpness >= 3
            AND emotional_texture >= 2 AND voice_authenticity >= 2

        This flag is metadata only — it does not add to the score.
        """
        return (
            self.total >= 14
            and self.sharpness >= 3
            and self.emotional_texture >= 2
            and self.voice_authenticity >= 2
        )

    @property
    def weak_dimensions(self) -> list[tuple[str, int]]:
        """Dimensions scoring 1 or below, for refinement feedback."""
        return [(name, val) for name, val in self.as_dict().items() if val <= 1]

    def as_dict(self) -> dict[str, int]:
        """Return all 6 dimension scores as a dictionary.

        Note: `shareability` is absent per requirement 7.6.
        """
        return {
            "sharpness": self.sharpness,
            "emotional_texture": self.emotional_texture,
            "rhythm": self.rhythm,
            "pressure_relevance": self.pressure_relevance,
            "voice_authenticity": self.voice_authenticity,
            "subtext_depth": self.subtext_depth,
        }


# ---------------------------------------------------------------------------
# HardBan — banned pattern definition (Section 10)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HardBan:
    """Definition of a single hard ban rule.

    Hard bans are absolute — a violation is discarded, not refined.
    Each ban has a name, description, optional list of banned phrases,
    and optional list of archetype exceptions.

    Requirements: 10.1
    """

    name: str
    description: str
    banned_phrases: tuple[str, ...] = ()
    exceptions: tuple[str, ...] = ()  # archetypes exempt from this ban


# ---------------------------------------------------------------------------
# HardBanVerdict — result of hard ban check (Section 10)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HardBanVerdict:
    """Result of running HardBanChecker on a candidate line.

    `passed == True` means the line is clear for delivery.
    `passed == False` means the line must be discarded (never refined).

    Requirements: 10.1
    """

    passed: bool
    violated_ban: str | None = None
    violation_detail: str | None = None
