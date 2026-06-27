"""Quality_Judge — 5-dimension semantic quality evaluation for banter lines.

Evaluates candidate banter lines across sharpness, emotional_texture, rhythm,
thematic_relevance, and shareability dimensions (each 0-3). This replaces the
binary keyword-presence `_banter_quality_score()` from archetype_graphs.py.

When the soul engine is active, two additional dimensions are scored:
- voice_authenticity (0-3): from VoiceDNA.score_voice_conformance
- subtext_depth (0-3): from SubtletyDirector.score_subtext_depth

Quality thresholds rise when soul engine is active (7 dimensions vs 5).
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .contract_types import ContractQualityScore
from .mode_types import BeatMode, BeatModePolicy
from .types import QualityJudgeError, QualityScore, SceneContextData

if TYPE_CHECKING:
    from .soul_types import SoulEngineConfig, SubtextInstruction
    from .subtlety_director import SubtletyDirector
    from .voice_dna import VoiceDNA

log = logging.getLogger("god.banter.quality_judge")

# ---------------------------------------------------------------------------
# Quality thresholds
# ---------------------------------------------------------------------------

# Base thresholds (soul engine disabled, 5 dimensions, max total = 15)
BASE_PASS_THRESHOLD: int = 8
BASE_REFINE_THRESHOLD: int = 10

# Soul thresholds (soul engine active, 7 dimensions, max total = 21)
SOUL_PASS_THRESHOLD: int = 10
SOUL_REFINE_THRESHOLD: int = 12


def get_pass_threshold(soul_active: bool) -> int:
    """Return the pass threshold based on whether the soul engine is active."""
    return SOUL_PASS_THRESHOLD if soul_active else BASE_PASS_THRESHOLD


def get_refine_threshold(soul_active: bool) -> int:
    """Return the refinement threshold based on whether the soul engine is active."""
    return SOUL_REFINE_THRESHOLD if soul_active else BASE_REFINE_THRESHOLD


# ---------------------------------------------------------------------------
# EnhancedQualityScore — 7-dimension score including soul engine dimensions
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EnhancedQualityScore:
    """7-dimension quality evaluation including soul engine dimensions.

    Extends QualityScore with voice_authenticity (from VoiceDNA) and
    subtext_depth (from SubtletyDirector). The total spans 0-21 instead
    of 0-15, so quality thresholds are raised when soul engine is active.

    Requirements: 10.1, 10.2
    """

    sharpness: int
    emotional_texture: int
    rhythm: int
    thematic_relevance: int
    shareability: int
    voice_authenticity: int  # 0-3: from VoiceDNA.score_voice_conformance
    subtext_depth: int  # 0-3: from SubtletyDirector.score_subtext_depth

    @property
    def total(self) -> int:
        """Combined score across all 7 dimensions (0-21)."""
        return (
            self.sharpness
            + self.emotional_texture
            + self.rhythm
            + self.thematic_relevance
            + self.shareability
            + self.voice_authenticity
            + self.subtext_depth
        )

    @property
    def is_clip_candidate(self) -> bool:
        """True when this line is flagged as a clip-worthy moment (T7.1).

        Criterion: total > 16 AND sharpness == 3 AND emotional_texture >= 2.
        """
        return self.total > 16 and self.sharpness == 3 and self.emotional_texture >= 2

    @property
    def weak_dimensions(self) -> list[tuple[str, int]]:
        """All dimensions scoring 1 or below (for refinement feedback)."""
        return [(name, val) for name, val in self.as_dict().items() if val <= 1]

    def as_dict(self) -> dict[str, int]:
        """Return all 7 dimension scores as a dictionary."""
        return {
            "sharpness": self.sharpness,
            "emotional_texture": self.emotional_texture,
            "rhythm": self.rhythm,
            "thematic_relevance": self.thematic_relevance,
            "shareability": self.shareability,
            "voice_authenticity": self.voice_authenticity,
            "subtext_depth": self.subtext_depth,
        }

    def refinement_feedback(self) -> str:
        """Build a prompt fragment listing weak dimensions for regeneration.

        emotional_texture == 0 is treated as a hard block (T7.2): the message
        demands a rewrite rather than just noting the score. Other weak
        dimensions are listed as improvement targets.
        """
        parts = []

        # Hard block: no emotional texture at all (T7.2)
        if self.emotional_texture == 0:
            parts.append(
                "This line has no emotional texture. It must feel like something. Rewrite."
            )

        # Other weak dimensions (≤1), excluding emotional_texture already handled
        for name, val in self.weak_dimensions:
            if name == "emotional_texture":
                continue
            if name == "voice_authenticity":
                parts.append("voice_authenticity (use more archetype-specific vocabulary)")
            else:
                parts.append(f"{name} (currently {val}/3)")

        if not parts:
            return ""
        return "Improve: " + ", ".join(parts) + "."


# ---------------------------------------------------------------------------
# Archetype vocabulary clusters (for voice matching)
# ---------------------------------------------------------------------------

ARCHETYPE_VOCAB: dict[str, set[str]] = {
    "parasite": {
        "cost",
        "rent",
        "extract",
        "leverage",
        "useful",
        "drain",
        "take",
        "profit",
        "exploit",
        "skim",
    },
    "prophet": {
        "truth",
        "vision",
        "meaning",
        "reveal",
        "foresee",
        "purpose",
        "transcend",
        "illuminate",
        "destiny",
        "sacred",
    },
    "trickster": {
        "game",
        "trick",
        "flip",
        "chaos",
        "play",
        "twist",
        "joke",
        "absurd",
        "mask",
        "riddle",
    },
    "sovereign": {
        "rule",
        "order",
        "command",
        "throne",
        "decree",
        "domain",
        "authority",
        "crown",
        "edict",
        "realm",
    },
    "martyr": {
        "sacrifice",
        "burden",
        "suffer",
        "carry",
        "endure",
        "bleed",
        "weight",
        "cost",
        "pay",
        "bear",
    },
    "shadow": {
        "hidden",
        "beneath",
        "lurk",
        "unseen",
        "depth",
        "secret",
        "whisper",
        "void",
        "dark",
        "silence",
    },
    "herald": {
        "announce",
        "declare",
        "proclaim",
        "witness",
        "signal",
        "mark",
        "new",
        "change",
        "dawn",
        "arrive",
    },
    "keeper": {
        "hold",
        "guard",
        "preserve",
        "maintain",
        "store",
        "protect",
        "tend",
        "watch",
        "steady",
        "endure",
    },
}

# Known "hit" lines for shareability reference (high clip-worthiness)
HIT_PHRASES: set[str] = {
    "cuts deeper",
    "never asked",
    "who speaks",
    "who listens",
    "outlast",
    "remember when",
    "still true",
    "changes nothing",
    "worth saying",
    "gets it",
}


# ---------------------------------------------------------------------------
# Scoring heuristics
# ---------------------------------------------------------------------------


def _score_sharpness(candidate: str) -> int:
    """Score conciseness and rhetorical punch (0-3).

    Short, punchy lines (4-15 words) with strong punctuation score highest.
    """
    words = candidate.split()
    word_count = len(words)

    if word_count == 0:
        return 0

    # Ideal word count: 4-15 for maximum punch
    if 4 <= word_count <= 8:
        base = 3
    elif 9 <= word_count <= 15:
        base = 2
    elif word_count <= 3:
        base = 1
    elif word_count <= 25:
        base = 1
    else:
        base = 0

    # Bonus indicators: rhetorical questions, strong endings
    if candidate.rstrip().endswith("?") and word_count <= 10:
        base = min(3, base + 1)
    if candidate.rstrip().endswith(".") and word_count <= 6:
        base = min(3, base + 1)

    return min(3, base)


def _score_emotional_texture(candidate: str) -> int:
    """Score vulnerability, tension, and warmth (0-3).

    Looks for emotional markers and contrasts.
    """
    lower = candidate.lower()
    score = 0

    # Emotional contrast indicators
    contrast_markers = ["but", "yet", "still", "though", "however", "despite"]
    if any(m in lower.split() for m in contrast_markers):
        score += 1

    # Vulnerability/tension words
    tension_words = {
        "afraid",
        "fear",
        "hurt",
        "betray",
        "trust",
        "hope",
        "break",
        "fall",
        "lose",
        "cost",
        "burn",
        "bleed",
        "alone",
        "silent",
        "hollow",
        "empty",
        "heavy",
        "ache",
    }
    if any(w in lower.split() for w in tension_words):
        score += 1

    # Warmth / connection words
    warmth_words = {"together", "remember", "once", "shared", "between", "us"}
    if any(w in lower.split() for w in warmth_words):
        score += 1

    # Personal pronouns create intimacy
    personal = {"you", "i", "we", "your", "my", "our"}
    word_set = set(lower.split())
    if len(personal & word_set) >= 2:
        score += 1

    return min(3, score)


def _score_rhythm(candidate: str) -> int:
    """Score cadence and clause variety (0-3).

    Evaluates sentence structure: clause count, varied lengths, pause points.
    """
    if not candidate.strip():
        return 0

    # Count clauses (commas, semicolons, dashes, colons)
    clause_separators = re.findall(r"[,;:\u2014\-]", candidate)
    clause_count = len(clause_separators) + 1

    words = candidate.split()
    word_count = len(words)

    if word_count == 0:
        return 0

    score = 0

    # 2-3 clauses is ideal for broadcast delivery rhythm
    if 2 <= clause_count <= 3:
        score += 2
    elif clause_count == 1 and 4 <= word_count <= 8:
        score += 1  # single punchy clause is ok
    elif clause_count >= 4:
        score += 1  # too complex but has variety

    # Varied word lengths within the line indicate natural cadence
    lengths = [len(w) for w in words]
    if len(set(lengths)) >= min(4, word_count):
        score += 1

    return min(3, score)


def _score_thematic_relevance(candidate: str, arc_theme: str) -> int:
    """Score connection to the current arc theme (0-3).

    Uses word overlap between candidate and theme.
    """
    if not arc_theme or not candidate.strip():
        return 0

    candidate_words = set(candidate.lower().split())
    theme_words = set(arc_theme.lower().split())

    # Remove stopwords for comparison
    stopwords = {
        "the",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "and",
        "or",
        "but",
        "be",
        "if",
        "do",
        "does",
    }
    candidate_content = candidate_words - stopwords
    theme_content = theme_words - stopwords

    if not theme_content:
        return 1  # neutral score if theme has no content words

    overlap = candidate_content & theme_content
    ratio = len(overlap) / len(theme_content) if theme_content else 0

    if ratio >= 0.4:
        return 3
    elif ratio >= 0.2:
        return 2
    elif ratio > 0:
        return 1
    else:
        # Check for semantic proximity (related but not exact words)
        return 0


def _score_pressure_relevance(candidate: str, arc_theme: str) -> int:
    """Score connection to arc pressure for the contract judge (0-3)."""
    if not arc_theme or not candidate.strip():
        return 0

    candidate_lower = candidate.lower()
    theme_lower = arc_theme.lower().strip()
    if theme_lower and theme_lower in candidate_lower:
        return 0

    return _score_thematic_relevance(candidate, arc_theme)


def _score_shareability(candidate: str) -> int:
    """Score quotability and clip-worthiness (0-3).

    Lines that sound good standalone, have memorable phrasing.
    """
    lower = candidate.lower()
    score = 0

    # Check against known hit phrases
    if any(phrase in lower for phrase in HIT_PHRASES):
        score += 2

    # Quotable structure: short + definitive statement
    words = candidate.split()
    if 4 <= len(words) <= 12:
        score += 1

    # Ends with punch (period after short statement, or question)
    stripped = candidate.rstrip()
    if stripped.endswith((".", "?")) and len(words) <= 10:
        score += 1

    # Alliteration or repetition (rhetorical device)
    if len(words) >= 3:
        first_letters = [w[0].lower() for w in words if w]
        if any(first_letters.count(c) >= 3 for c in set(first_letters)):
            score += 1

    return min(3, score)


def _score_archetype_voice(candidate: str, archetype: str) -> float:
    """Return a bonus/penalty for archetype vocabulary alignment.

    Returns 0.0-1.0 boost applied to sharpness dimension.
    """
    if archetype not in ARCHETYPE_VOCAB:
        return 0.0

    vocab = ARCHETYPE_VOCAB[archetype]
    candidate_words = set(candidate.lower().split())
    overlap = candidate_words & vocab

    if overlap:
        return min(1.0, len(overlap) * 0.5)
    return 0.0


def _score_voice_authenticity(candidate: str, archetype: str) -> int:
    """Contract-aligned voice authenticity score (0-3)."""
    boost = _score_archetype_voice(candidate, archetype)
    if boost >= 1.0:
        return 3
    if boost >= 0.5:
        return 2
    if boost > 0:
        return 1
    return 0


def _score_subtext_depth(candidate: str, move: str) -> int:
    """Contract-aligned subtext depth score (0-3)."""
    lower = candidate.lower()
    score = 0

    implication_markers = {
        "maybe",
        "almost",
        "still",
        "yet",
        "though",
        "however",
        "despite",
        "underneath",
        "between",
        "instead",
        "again",
        "quietly",
        "apparently",
    }
    hidden_cost_words = {
        "cost",
        "rent",
        "debt",
        "weight",
        "price",
        "borrow",
        "owe",
        "pay",
        "burn",
        "hurt",
        "trust",
        "betray",
        "fear",
        "loss",
    }

    if any(word in lower.split() for word in implication_markers):
        score += 1
    if any(word in lower.split() for word in hidden_cost_words):
        score += 1
    if any(marker in lower for marker in ("...", "—", "?", " but ", " yet ")):
        score += 1

    if move in {"CRACK", "CONCEDE"} and score < 3:
        score += 1

    return min(3, score)


# ---------------------------------------------------------------------------
# Main evaluation function
# ---------------------------------------------------------------------------


class QualityJudgeV2:
    """Contract-aligned 6-dimension judge."""

    async def score(
        self,
        candidate: str,
        *,
        archetype: str,
        move: str,
        arc_theme: str,
        policy: BeatModePolicy,
        scene_context: SceneContextData | None = None,
        timeout_s: float = 2.0,
    ) -> ContractQualityScore:
        try:
            return await asyncio.wait_for(
                self._score_impl(
                    candidate,
                    archetype=archetype,
                    move=move,
                    arc_theme=arc_theme,
                    policy=policy,
                    scene_context=scene_context,
                ),
                timeout=timeout_s,
            )
        except asyncio.TimeoutError:
            raise QualityJudgeError(f"Contract quality evaluation timed out after {timeout_s}s")
        except QualityJudgeError:
            raise
        except Exception as exc:
            raise QualityJudgeError(f"Unexpected error during contract scoring: {exc}") from exc

    async def _score_impl(
        self,
        candidate: str,
        *,
        archetype: str,
        move: str,
        arc_theme: str,
        policy: BeatModePolicy,
        scene_context: SceneContextData | None = None,
    ) -> ContractQualityScore:
        sharpness = _score_sharpness(candidate)
        emotional_texture = _score_emotional_texture(candidate)
        rhythm = _score_rhythm(candidate)
        pressure_relevance = _score_pressure_relevance(candidate, arc_theme)
        voice_authenticity = _score_voice_authenticity(candidate, archetype)
        subtext_depth = _score_subtext_depth(candidate, move)

        if policy.mode == BeatMode.NORMAL and emotional_texture == 0:
            log.debug("NORMAL mode emotional_texture hard block candidate=%r", candidate)

        for name, val in [
            ("sharpness", sharpness),
            ("emotional_texture", emotional_texture),
            ("rhythm", rhythm),
            ("pressure_relevance", pressure_relevance),
            ("voice_authenticity", voice_authenticity),
            ("subtext_depth", subtext_depth),
        ]:
            if not (0 <= val <= 3):
                raise QualityJudgeError(f"Dimension {name} out of bounds: {val}")

        return ContractQualityScore(
            sharpness=sharpness,
            emotional_texture=emotional_texture,
            rhythm=rhythm,
            pressure_relevance=pressure_relevance,
            voice_authenticity=voice_authenticity,
            subtext_depth=subtext_depth,
        )


async def evaluate_contract(
    candidate: str,
    *,
    archetype: str,
    move: str,
    arc_theme: str,
    policy: BeatModePolicy,
    scene_context: SceneContextData | None = None,
    timeout_s: float = 2.0,
) -> ContractQualityScore:
    """Convenience wrapper around QualityJudgeV2.score."""
    judge = QualityJudgeV2()
    return await judge.score(
        candidate,
        archetype=archetype,
        move=move,
        arc_theme=arc_theme,
        policy=policy,
        scene_context=scene_context,
        timeout_s=timeout_s,
    )


async def evaluate(
    candidate: str,
    *,
    archetype: str,
    move: str,
    arc_theme: str,
    scene_context: SceneContextData | None = None,
    timeout_s: float = 2.0,
) -> QualityScore:
    """Evaluate a candidate banter line across 5 dimensions.

    Each dimension is scored 0-3. Raises QualityJudgeError on failure or timeout.

    Args:
        candidate: The banter line to evaluate.
        archetype: The speaker's archetype.
        move: The conversational move type.
        arc_theme: Current narrative arc theme.
        scene_context: Optional scene context for contextual scoring.
        timeout_s: Maximum time for evaluation (default 2.0s).

    Returns:
        QualityScore with all 5 dimensions populated.

    Raises:
        QualityJudgeError: On timeout, malformed output, or unexpected error.
    """
    try:
        score = await asyncio.wait_for(
            _evaluate_impl(
                candidate,
                archetype=archetype,
                move=move,
                arc_theme=arc_theme,
                scene_context=scene_context,
            ),
            timeout=timeout_s,
        )
        return score
    except asyncio.TimeoutError:
        raise QualityJudgeError(f"Quality evaluation timed out after {timeout_s}s")
    except QualityJudgeError:
        raise
    except Exception as e:
        raise QualityJudgeError(f"Unexpected error during evaluation: {e}") from e


async def _evaluate_impl(
    candidate: str,
    *,
    archetype: str,
    move: str,
    arc_theme: str,
    scene_context: SceneContextData | None = None,
) -> QualityScore:
    """Internal evaluation implementation (no timeout wrapper)."""
    # Score each dimension
    sharpness = _score_sharpness(candidate)
    emotional_texture = _score_emotional_texture(candidate)
    rhythm = _score_rhythm(candidate)
    thematic_relevance = _score_thematic_relevance(candidate, arc_theme)
    shareability = _score_shareability(candidate)

    # Apply archetype voice boost to sharpness
    voice_boost = _score_archetype_voice(candidate, archetype)
    if voice_boost > 0 and sharpness < 3:
        sharpness = min(3, sharpness + int(voice_boost + 0.5))

    # Validate all scores are in [0, 3]
    for name, val in [
        ("sharpness", sharpness),
        ("emotional_texture", emotional_texture),
        ("rhythm", rhythm),
        ("thematic_relevance", thematic_relevance),
        ("shareability", shareability),
    ]:
        if not (0 <= val <= 3):
            raise QualityJudgeError(f"Dimension {name} out of bounds: {val}")

    return QualityScore(
        sharpness=sharpness,
        emotional_texture=emotional_texture,
        rhythm=rhythm,
        thematic_relevance=thematic_relevance,
        shareability=shareability,
    )


# ---------------------------------------------------------------------------
# Enhanced evaluation (soul engine dimensions)
# ---------------------------------------------------------------------------


async def evaluate_enhanced(
    candidate: str,
    *,
    archetype: str,
    move: str,
    arc_theme: str,
    scene_context: SceneContextData | None = None,
    voice_dna: VoiceDNA | None = None,
    subtext_instruction: SubtextInstruction | None = None,
    subtlety_director: SubtletyDirector | None = None,
    subtext_was_injected: bool = False,
    config: SoulEngineConfig | None = None,
    timeout_s: float = 2.0,
) -> EnhancedQualityScore:
    """Evaluate a candidate line across 7 dimensions (5 base + soul engine).

    When soul engine is active and modules are provided:
    - voice_authenticity: scored by VoiceDNA.score_voice_conformance
    - subtext_depth: scored by SubtletyDirector.score_subtext_depth
      (only when subtext_was_injected=True and both module + instruction present)
    - shareability receives +subtext_depth bonus (capped at 3)

    Falls back gracefully (voice_authenticity=0, subtext_depth=0) when:
    - config.enabled is False
    - Soul modules are not provided
    - A module raises an exception

    Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6

    Args:
        candidate: The banter line to evaluate.
        archetype: Speaker's archetype.
        move: Conversational move type.
        arc_theme: Current narrative arc theme.
        scene_context: Optional scene context.
        voice_dna: Optional VoiceDNA instance for voice_authenticity scoring.
        subtext_instruction: The SubtextInstruction used during generation.
        subtlety_director: Optional SubtletyDirector for subtext_depth scoring.
        subtext_was_injected: Whether subtext was actually injected this beat.
        config: Soul engine configuration. None → soul engine treated as disabled.
        timeout_s: Maximum time for evaluation.

    Returns:
        EnhancedQualityScore with all 7 dimensions.

    Raises:
        QualityJudgeError: On timeout or unexpected error in base evaluation.
    """
    soul_active = config is not None and config.enabled

    try:
        enhanced = await asyncio.wait_for(
            _evaluate_enhanced_impl(
                candidate,
                archetype=archetype,
                move=move,
                arc_theme=arc_theme,
                scene_context=scene_context,
                voice_dna=voice_dna if soul_active else None,
                subtext_instruction=subtext_instruction,
                subtlety_director=subtlety_director if soul_active else None,
                subtext_was_injected=subtext_was_injected and soul_active,
            ),
            timeout=timeout_s,
        )
        return enhanced
    except asyncio.TimeoutError:
        raise QualityJudgeError(f"Enhanced quality evaluation timed out after {timeout_s}s")
    except QualityJudgeError:
        raise
    except Exception as e:
        raise QualityJudgeError(f"Unexpected error during enhanced evaluation: {e}") from e


async def _evaluate_enhanced_impl(
    candidate: str,
    *,
    archetype: str,
    move: str,
    arc_theme: str,
    scene_context: SceneContextData | None = None,
    voice_dna: VoiceDNA | None = None,
    subtext_instruction: SubtextInstruction | None = None,
    subtlety_director: SubtletyDirector | None = None,
    subtext_was_injected: bool = False,
) -> EnhancedQualityScore:
    """Internal enhanced evaluation (no timeout wrapper)."""
    # Run base 5-dimension evaluation
    base = await _evaluate_impl(
        candidate,
        archetype=archetype,
        move=move,
        arc_theme=arc_theme,
        scene_context=scene_context,
    )

    # --- voice_authenticity ---
    voice_authenticity = 0
    if voice_dna is not None:
        try:
            voice_authenticity = voice_dna.score_voice_conformance(candidate, archetype)
            voice_authenticity = max(0, min(3, int(voice_authenticity)))
        except Exception as exc:
            log.debug("VoiceDNA scoring failed, defaulting to 0: %s", exc)
            voice_authenticity = 0

    # --- subtext_depth ---
    subtext_depth = 0
    if subtext_was_injected and subtlety_director is not None and subtext_instruction is not None:
        try:
            subtext_depth = subtlety_director.score_subtext_depth(candidate, subtext_instruction)
            subtext_depth = max(0, min(3, int(subtext_depth)))
        except Exception as exc:
            log.debug("SubtletyDirector scoring failed, defaulting to 0: %s", exc)
            subtext_depth = 0

    return EnhancedQualityScore(
        sharpness=base.sharpness,
        emotional_texture=base.emotional_texture,
        rhythm=base.rhythm,
        thematic_relevance=base.thematic_relevance,
        shareability=base.shareability,
        voice_authenticity=voice_authenticity,
        subtext_depth=subtext_depth,
    )
