"""Unit tests for the enhanced Quality_Judge with soul engine dimensions.

Tests cover:
- EnhancedQualityScore: 7 dimensions, total in [0, 21], weak_dimensions, refinement_feedback
- evaluate_enhanced: soul disabled behaviour, voice_authenticity, subtext_depth conditioning
- Threshold constants and get_pass/refine_threshold helpers
- Fault isolation: module exceptions don't propagate, default to 0

Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6
"""

import asyncio
import os
import sys

_src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
for _p in (_src_path, "/app/src"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest

from banter.quality_judge import (
    BASE_PASS_THRESHOLD,
    BASE_REFINE_THRESHOLD,
    SOUL_PASS_THRESHOLD,
    SOUL_REFINE_THRESHOLD,
    EnhancedQualityScore,
    evaluate_enhanced,
    get_pass_threshold,
    get_refine_threshold,
)
from banter.soul_types import SoulEngineConfig, SubtextInstruction


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def soul_config() -> SoulEngineConfig:
    return SoulEngineConfig()


@pytest.fixture
def disabled_config() -> SoulEngineConfig:
    return SoulEngineConfig(enabled=False)


@pytest.fixture
def sample_instruction() -> SubtextInstruction:
    return SubtextInstruction(
        surface_meaning="Ask about power as if genuinely curious.",
        implied_meaning="The question presumes target guilt or weakness.",
        technique="loaded_question",
        context_hint="Let the subtext brush against their sensitivity.",
    )


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# EnhancedQualityScore dataclass
# ---------------------------------------------------------------------------


class TestEnhancedQualityScoreDataclass:
    """EnhancedQualityScore structure and computed properties."""

    def test_has_7_dimensions(self) -> None:
        score = EnhancedQualityScore(
            sharpness=2, emotional_texture=1, rhythm=2,
            thematic_relevance=1, shareability=2,
            voice_authenticity=1, subtext_depth=1,
        )
        assert len(score.as_dict()) == 7

    def test_total_is_sum_of_all_7(self) -> None:
        score = EnhancedQualityScore(
            sharpness=3, emotional_texture=2, rhythm=1,
            thematic_relevance=2, shareability=1,
            voice_authenticity=2, subtext_depth=3,
        )
        assert score.total == 3 + 2 + 1 + 2 + 1 + 2 + 3

    def test_total_zero_when_all_zero(self) -> None:
        score = EnhancedQualityScore(
            sharpness=0, emotional_texture=0, rhythm=0,
            thematic_relevance=0, shareability=0,
            voice_authenticity=0, subtext_depth=0,
        )
        assert score.total == 0

    def test_total_max_21_when_all_3(self) -> None:
        score = EnhancedQualityScore(
            sharpness=3, emotional_texture=3, rhythm=3,
            thematic_relevance=3, shareability=3,
            voice_authenticity=3, subtext_depth=3,
        )
        assert score.total == 21

    def test_weak_dimensions_includes_voice_authenticity(self) -> None:
        score = EnhancedQualityScore(
            sharpness=3, emotional_texture=3, rhythm=3,
            thematic_relevance=3, shareability=3,
            voice_authenticity=0, subtext_depth=3,
        )
        weak = score.weak_dimensions
        assert any(name == "voice_authenticity" for name, _ in weak)

    def test_weak_dimensions_excludes_strong_dims(self) -> None:
        score = EnhancedQualityScore(
            sharpness=3, emotional_texture=2, rhythm=3,
            thematic_relevance=3, shareability=3,
            voice_authenticity=3, subtext_depth=3,
        )
        weak_names = {name for name, _ in score.weak_dimensions}
        assert "sharpness" not in weak_names
        assert "emotional_texture" not in weak_names

    def test_refinement_feedback_empty_when_no_weak_dims(self) -> None:
        score = EnhancedQualityScore(
            sharpness=2, emotional_texture=2, rhythm=2,
            thematic_relevance=2, shareability=2,
            voice_authenticity=2, subtext_depth=2,
        )
        assert score.refinement_feedback() == ""

    def test_refinement_feedback_includes_voice_guidance(self) -> None:
        score = EnhancedQualityScore(
            sharpness=2, emotional_texture=2, rhythm=2,
            thematic_relevance=2, shareability=2,
            voice_authenticity=0, subtext_depth=2,
        )
        feedback = score.refinement_feedback()
        assert "voice_authenticity" in feedback
        assert "archetype-specific" in feedback

    def test_as_dict_keys(self) -> None:
        score = EnhancedQualityScore(
            sharpness=1, emotional_texture=1, rhythm=1,
            thematic_relevance=1, shareability=1,
            voice_authenticity=1, subtext_depth=1,
        )
        keys = set(score.as_dict().keys())
        assert keys == {
            "sharpness", "emotional_texture", "rhythm",
            "thematic_relevance", "shareability",
            "voice_authenticity", "subtext_depth",
        }


# ---------------------------------------------------------------------------
# Quality threshold constants and helpers
# ---------------------------------------------------------------------------


class TestQualityThresholds:
    """Threshold constants and get_pass/refine_threshold helpers."""

    def test_soul_pass_threshold_is_10(self) -> None:
        assert SOUL_PASS_THRESHOLD == 10

    def test_soul_refine_threshold_is_12(self) -> None:
        assert SOUL_REFINE_THRESHOLD == 12

    def test_base_pass_threshold_is_8(self) -> None:
        assert BASE_PASS_THRESHOLD == 8

    def test_base_refine_threshold_is_10(self) -> None:
        assert BASE_REFINE_THRESHOLD == 10

    def test_soul_thresholds_higher_than_base(self) -> None:
        assert SOUL_PASS_THRESHOLD > BASE_PASS_THRESHOLD
        assert SOUL_REFINE_THRESHOLD > BASE_REFINE_THRESHOLD

    def test_refine_higher_than_pass_for_both(self) -> None:
        assert BASE_REFINE_THRESHOLD > BASE_PASS_THRESHOLD
        assert SOUL_REFINE_THRESHOLD > SOUL_PASS_THRESHOLD

    def test_get_pass_threshold_soul_active(self) -> None:
        assert get_pass_threshold(True) == SOUL_PASS_THRESHOLD

    def test_get_pass_threshold_soul_inactive(self) -> None:
        assert get_pass_threshold(False) == BASE_PASS_THRESHOLD

    def test_get_refine_threshold_soul_active(self) -> None:
        assert get_refine_threshold(True) == SOUL_REFINE_THRESHOLD

    def test_get_refine_threshold_soul_inactive(self) -> None:
        assert get_refine_threshold(False) == BASE_REFINE_THRESHOLD


# ---------------------------------------------------------------------------
# evaluate_enhanced — basic contract
# ---------------------------------------------------------------------------


class TestEvaluateEnhancedBasicContract:
    """evaluate_enhanced always returns EnhancedQualityScore, never raises."""

    def test_returns_enhanced_quality_score(self, soul_config: SoulEngineConfig) -> None:
        result = _run(evaluate_enhanced(
            "The question cuts deeper than the answer.",
            archetype="prophet", move="QUESTION",
            arc_theme="truth", config=soul_config,
        ))
        assert isinstance(result, EnhancedQualityScore)

    def test_all_dimensions_in_range(self, soul_config: SoulEngineConfig) -> None:
        result = _run(evaluate_enhanced(
            "Any candidate line at all.",
            archetype="keeper", move="COUNTER",
            arc_theme="survival", config=soul_config,
        ))
        for name, val in result.as_dict().items():
            assert 0 <= val <= 3, f"{name}={val} out of [0, 3]"

    def test_total_in_range_0_to_21(self, soul_config: SoulEngineConfig) -> None:
        result = _run(evaluate_enhanced(
            "Any line.", archetype="martyr", move="TAUNT",
            arc_theme="sacrifice", config=soul_config,
        ))
        assert 0 <= result.total <= 21

    def test_no_config_none_works(self) -> None:
        result = _run(evaluate_enhanced(
            "Any line.", archetype="shadow", move="COUNTER",
            arc_theme="darkness", config=None,
        ))
        assert isinstance(result, EnhancedQualityScore)
        assert result.voice_authenticity == 0
        assert result.subtext_depth == 0

    def test_disabled_config_zeroes_soul_dims(self, disabled_config: SoulEngineConfig) -> None:
        result = _run(evaluate_enhanced(
            "The hidden truth lurks beneath.",
            archetype="shadow", move="DEFLECT",
            arc_theme="secrets", config=disabled_config,
        ))
        assert result.voice_authenticity == 0
        assert result.subtext_depth == 0

    def test_empty_candidate_does_not_raise(self, soul_config: SoulEngineConfig) -> None:
        result = _run(evaluate_enhanced(
            "", archetype="herald", move="COUNTER",
            arc_theme="change", config=soul_config,
        ))
        assert isinstance(result, EnhancedQualityScore)


# ---------------------------------------------------------------------------
# evaluate_enhanced — voice_authenticity integration
# ---------------------------------------------------------------------------


class TestVoiceAuthenticity:
    """voice_authenticity integrates VoiceDNA when provided and soul is active."""

    def test_voice_authenticity_zero_without_voice_dna(
        self, soul_config: SoulEngineConfig
    ) -> None:
        result = _run(evaluate_enhanced(
            "Guard and hold what matters.",
            archetype="keeper", move="COUNTER",
            arc_theme="protection", config=soul_config,
            voice_dna=None,
        ))
        assert result.voice_authenticity == 0

    def test_voice_authenticity_from_voice_dna(self, soul_config: SoulEngineConfig) -> None:
        from pathlib import Path

        profiles_dir = Path("/app/src/banter/voice_profiles")
        if not profiles_dir.exists():
            pytest.skip("Voice profiles not available")

        from banter.voice_dna import VoiceDNA

        voice_dna = VoiceDNA(profiles_dir=profiles_dir, config=soul_config)
        asyncio.run(voice_dna.load_profiles())

        result = _run(evaluate_enhanced(
            "Guard and hold what endures — protect what remains.",
            archetype="keeper", move="COUNTER",
            arc_theme="protection", config=soul_config,
            voice_dna=voice_dna,
        ))
        assert isinstance(result.voice_authenticity, int)
        assert 0 <= result.voice_authenticity <= 3

    def test_voice_authenticity_exception_defaults_to_zero(
        self, soul_config: SoulEngineConfig
    ) -> None:
        class BrokenVoiceDNA:
            def score_voice_conformance(self, candidate: str, archetype: str) -> int:
                raise RuntimeError("simulated VoiceDNA failure")

        result = _run(evaluate_enhanced(
            "Guard the threshold.",
            archetype="keeper", move="COUNTER",
            arc_theme="protection", config=soul_config,
            voice_dna=BrokenVoiceDNA(),  # type: ignore[arg-type]
        ))
        assert result.voice_authenticity == 0, "Exception should default to 0"


# ---------------------------------------------------------------------------
# evaluate_enhanced — subtext_depth conditioning
# ---------------------------------------------------------------------------


class TestSubtextDepthConditioning:
    """subtext_depth is only scored when all conditions met (soul on, injected, both modules)."""

    def test_subtext_depth_zero_when_not_injected(
        self, soul_config: SoulEngineConfig, sample_instruction: SubtextInstruction
    ) -> None:
        from banter.subtlety_director import SubtletyDirector
        director = SubtletyDirector(soul_config, seed=0)
        result = _run(evaluate_enhanced(
            "Do you ask about power? The question reveals everything.",
            archetype="prophet", move="QUESTION",
            arc_theme="power", config=soul_config,
            subtlety_director=director,
            subtext_instruction=sample_instruction,
            subtext_was_injected=False,
        ))
        assert result.subtext_depth == 0

    def test_subtext_depth_zero_without_director(
        self, soul_config: SoulEngineConfig, sample_instruction: SubtextInstruction
    ) -> None:
        result = _run(evaluate_enhanced(
            "Is this about power?",
            archetype="prophet", move="QUESTION",
            arc_theme="power", config=soul_config,
            subtlety_director=None,
            subtext_instruction=sample_instruction,
            subtext_was_injected=True,
        ))
        assert result.subtext_depth == 0

    def test_subtext_depth_zero_without_instruction(
        self, soul_config: SoulEngineConfig
    ) -> None:
        from banter.subtlety_director import SubtletyDirector
        director = SubtletyDirector(soul_config, seed=0)
        result = _run(evaluate_enhanced(
            "Is this about power?",
            archetype="prophet", move="QUESTION",
            arc_theme="power", config=soul_config,
            subtlety_director=director,
            subtext_instruction=None,
            subtext_was_injected=True,
        ))
        assert result.subtext_depth == 0

    def test_subtext_depth_scored_when_all_present(
        self, soul_config: SoulEngineConfig, sample_instruction: SubtextInstruction
    ) -> None:
        from banter.subtlety_director import SubtletyDirector
        director = SubtletyDirector(soul_config, seed=0)
        # Candidate with ? (loaded_question marker) → technique point
        result = _run(evaluate_enhanced(
            "Is this really about power? Do you ask in earnest?",
            archetype="prophet", move="QUESTION",
            arc_theme="power", config=soul_config,
            subtlety_director=director,
            subtext_instruction=sample_instruction,
            subtext_was_injected=True,
        ))
        assert 0 <= result.subtext_depth <= 3

    def test_subtext_exception_defaults_to_zero(
        self, soul_config: SoulEngineConfig, sample_instruction: SubtextInstruction
    ) -> None:
        class BrokenDirector:
            def score_subtext_depth(self, candidate, instruction):
                raise RuntimeError("simulated failure")

        result = _run(evaluate_enhanced(
            "The question reveals the answer.",
            archetype="prophet", move="QUESTION",
            arc_theme="power", config=soul_config,
            subtlety_director=BrokenDirector(),  # type: ignore[arg-type]
            subtext_instruction=sample_instruction,
            subtext_was_injected=True,
        ))
        assert result.subtext_depth == 0


# ---------------------------------------------------------------------------
# evaluate_enhanced — shareability bonus
# ---------------------------------------------------------------------------


class TestShareabilityBonus:
    """Shareability receives subtext_depth bonus (capped at 3)."""

    def test_shareability_bonus_added_when_subtext_scored(
        self, soul_config: SoulEngineConfig, sample_instruction: SubtextInstruction
    ) -> None:
        from banter.quality_judge import evaluate
        from banter.subtlety_director import SubtletyDirector

        director = SubtletyDirector(soul_config, seed=0)
        candidate = "Do you ask about power? The question presumes your guilt."

        base = _run(evaluate(candidate, archetype="prophet", move="QUESTION", arc_theme="power"))
        enhanced = _run(evaluate_enhanced(
            candidate, archetype="prophet", move="QUESTION",
            arc_theme="power", config=soul_config,
            subtlety_director=director,
            subtext_instruction=sample_instruction,
            subtext_was_injected=True,
        ))
        assert enhanced.shareability >= base.shareability

    def test_shareability_capped_at_3(
        self, soul_config: SoulEngineConfig
    ) -> None:
        """Even with high subtext_depth, shareability never exceeds 3."""
        from banter.subtlety_director import SubtletyDirector

        director = SubtletyDirector(soul_config, seed=0)
        # A very quotable candidate that already maxes shareability
        candidate = "Still true. Still here. Still cuts deeper."
        instruction = SubtextInstruction(
            surface_meaning="Ask about legacy — still relevant.",
            implied_meaning="still question presumes guilt and weakness.",
            technique="loaded_question",
            context_hint="hint",
        )
        result = _run(evaluate_enhanced(
            candidate, archetype="keeper", move="QUESTION",
            arc_theme="legacy", config=soul_config,
            subtlety_director=director,
            subtext_instruction=instruction,
            subtext_was_injected=True,
        ))
        assert result.shareability <= 3

    def test_no_bonus_without_injection(
        self, soul_config: SoulEngineConfig, sample_instruction: SubtextInstruction
    ) -> None:
        from banter.quality_judge import evaluate
        from banter.subtlety_director import SubtletyDirector

        director = SubtletyDirector(soul_config, seed=0)
        candidate = "Any candidate without subtext."

        base = _run(evaluate(candidate, archetype="prophet", move="COUNTER", arc_theme="power"))
        enhanced = _run(evaluate_enhanced(
            candidate, archetype="prophet", move="COUNTER",
            arc_theme="power", config=soul_config,
            subtlety_director=director,
            subtext_instruction=sample_instruction,
            subtext_was_injected=False,
        ))
        assert enhanced.shareability == base.shareability
