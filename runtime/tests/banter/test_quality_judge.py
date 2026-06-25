"""Tests for Quality_Judge module.

Property tests (Property 1) and unit tests for the 5-dimension scoring system.
"""

import asyncio
import os
import sys
from unittest.mock import patch

import pytest
from hypothesis import given, settings

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from banter.quality_judge import (
    evaluate,
    _score_sharpness,
    _score_emotional_texture,
    _score_rhythm,
    _score_thematic_relevance,
    _score_shareability,
)
from banter.types import QualityJudgeError, QualityScore

from conftest import st_candidate_line, st_archetype, st_move


# ---------------------------------------------------------------------------
# Property 1: Quality_Judge Output Invariants
# ---------------------------------------------------------------------------


@settings(max_examples=200, deadline=5000)
@given(
    candidate=st_candidate_line(),
    archetype=st_archetype(),
    move=st_move(),
)
def test_property_1_output_invariants(candidate: str, archetype: str, move: str):
    """For any candidate string, evaluate returns exactly 5 dimension scores
    each in [0, 3] or raises QualityJudgeError — never a partial result."""
    try:
        score = asyncio.run(
            evaluate(
                candidate,
                archetype=archetype,
                move=move,
                arc_theme="Should the weak be protected?",
                timeout_s=5.0,
            )
        )
        # Must have exactly 5 dimensions
        d = score.as_dict()
        assert len(d) == 5, f"Expected 5 dimensions, got {len(d)}"
        assert set(d.keys()) == {
            "sharpness",
            "emotional_texture",
            "rhythm",
            "thematic_relevance",
            "shareability",
        }

        # Each must be int in [0, 3]
        for name, val in d.items():
            assert isinstance(val, int), f"{name} is not int: {type(val)}"
            assert 0 <= val <= 3, f"{name} out of bounds: {val}"

        # Total is sum of dimensions
        assert score.total == sum(d.values())

    except QualityJudgeError:
        # This is an acceptable outcome
        pass


# ---------------------------------------------------------------------------
# Unit tests for Quality_Judge
# ---------------------------------------------------------------------------


class TestSharpness:
    """Unit tests for sharpness dimension scoring."""

    def test_empty_string_scores_zero(self):
        assert _score_sharpness("") == 0

    def test_short_punchy_line_scores_high(self):
        score = _score_sharpness("Still dodges the cost.")
        assert score >= 2

    def test_very_long_line_scores_low(self):
        long_line = " ".join(["word"] * 50)
        assert _score_sharpness(long_line) == 0

    def test_rhetorical_question_boosts(self):
        score = _score_sharpness("Who asked you?")
        assert score >= 2


class TestEmotionalTexture:
    """Unit tests for emotional_texture dimension."""

    def test_empty_string_scores_zero(self):
        assert _score_emotional_texture("") == 0

    def test_contrast_with_tension(self):
        score = _score_emotional_texture("I trust you, yet you betray everything.")
        assert score >= 2

    def test_plain_statement(self):
        score = _score_emotional_texture("The table is brown.")
        assert score == 0


class TestRhythm:
    """Unit tests for rhythm dimension."""

    def test_empty_string_scores_zero(self):
        assert _score_rhythm("") == 0

    def test_multi_clause_line(self):
        score = _score_rhythm("First the silence, then the weight, finally the truth.")
        assert score >= 2

    def test_single_word(self):
        score = _score_rhythm("No.")
        assert score <= 1


class TestThematicRelevance:
    """Unit tests for thematic_relevance dimension."""

    def test_empty_theme_scores_zero(self):
        assert _score_thematic_relevance("Anything here.", "") == 0

    def test_high_overlap_scores_high(self):
        score = _score_thematic_relevance(
            "The weak should be protected by the strong.", "Should the weak be protected?"
        )
        assert score >= 2

    def test_no_overlap_scores_zero(self):
        score = _score_thematic_relevance(
            "Purple elephants dance at midnight.", "Should the weak be protected?"
        )
        assert score == 0


class TestShareability:
    """Unit tests for shareability dimension."""

    def test_empty_string_scores_zero(self):
        assert _score_shareability("") == 0

    def test_known_hit_phrase(self):
        score = _score_shareability("That cuts deeper than you know.")
        assert score >= 2

    def test_short_definitive(self):
        score = _score_shareability("Nobody asked. Still true.")
        assert score >= 1


class TestEvaluateIntegration:
    """Integration tests for the full evaluate() function."""

    def test_known_good_line(self):
        score = asyncio.run(
            evaluate(
                "You mistake pattern for truth, yet here we are.",
                archetype="prophet",
                move="COUNTER",
                arc_theme="The nature of truth",
                timeout_s=5.0,
            )
        )
        assert score.total >= 5  # should be above average

    def test_known_bad_line(self):
        score = asyncio.run(
            evaluate(
                "a",
                archetype="prophet",
                move="COUNTER",
                arc_theme="The nature of truth",
                timeout_s=5.0,
            )
        )
        assert score.total <= 5  # should be low

    def test_empty_string(self):
        score = asyncio.run(
            evaluate(
                "",
                archetype="trickster",
                move="DEFLECT",
                arc_theme="Chaos versus order",
                timeout_s=5.0,
            )
        )
        assert score.total == 0

    def test_timeout_raises_error(self):
        """Evaluation with 0s timeout should raise QualityJudgeError."""
        with pytest.raises(QualityJudgeError):
            asyncio.run(
                evaluate(
                    "Some banter line here.",
                    archetype="prophet",
                    move="COUNTER",
                    arc_theme="test",
                    timeout_s=0.0,  # impossible timeout
                )
            )


# ---------------------------------------------------------------------------
# Task 2.3: Unit tests for Quality_Judge
# Validates: Requirements 1.1, 1.2, 1.5, 1.6
# ---------------------------------------------------------------------------


class TestKnownGoodLines:
    """Known-good lines: short punchy lines with emotional texture and archetype
    vocabulary should produce combined scores at or above the threshold (8)."""

    @pytest.mark.asyncio
    async def test_prophet_line_with_emotion_and_theme(self):
        """A sharp prophet line with truth/reveal vocab, emotional contrast,
        multi-clause rhythm, and thematic overlap should score 8+."""
        score = await evaluate(
            "The truth cuts deeper, yet still you hope.",
            archetype="prophet",
            move="COUNTER",
            arc_theme="The truth about hope and fear",
            timeout_s=5.0,
        )
        assert score.total >= 8, f"Expected >=8, got {score.total}: {score.as_dict()}"

    @pytest.mark.asyncio
    async def test_parasite_line_with_archetype_vocab(self):
        """A parasite line leveraging its vocab (cost, extract, useful) with
        emotional texture and rhythm should score 8+."""
        score = await evaluate(
            "Useful framing, but the cost still bleeds you dry.",
            archetype="parasite",
            move="COUNTER",
            arc_theme="The cost of exploitation and profit",
            timeout_s=5.0,
        )
        assert score.total >= 8, f"Expected >=8, got {score.total}: {score.as_dict()}"

    @pytest.mark.asyncio
    async def test_martyr_line_with_sacrifice_theme(self):
        """A martyr line with sacrifice/burden vocab, vulnerability contrast,
        and theme relevance should score 8+."""
        score = await evaluate(
            "I carry the burden alone, yet you fear sacrifice.",
            archetype="martyr",
            move="ESCALATE",
            arc_theme="Should sacrifice be feared or embraced?",
            timeout_s=5.0,
        )
        assert score.total >= 8, f"Expected >=8, got {score.total}: {score.as_dict()}"

    @pytest.mark.asyncio
    async def test_trickster_line_with_playful_punch(self):
        """A trickster line with game/trick vocab and rhetorical question
        should score well across dimensions."""
        score = await evaluate(
            "You play the game, yet who tricks whom?",
            archetype="trickster",
            move="QUESTION",
            arc_theme="The game of trust and tricks",
            timeout_s=5.0,
        )
        assert score.total >= 8, f"Expected >=8, got {score.total}: {score.as_dict()}"


class TestKnownBadLines:
    """Known-bad lines: extremely long lines or single characters should
    produce low combined scores (well below threshold)."""

    @pytest.mark.asyncio
    async def test_single_character_scores_low(self):
        """A single character has no rhythm, no emotion, no theme relevance."""
        score = await evaluate(
            "x",
            archetype="prophet",
            move="COUNTER",
            arc_theme="Should the weak be protected?",
            timeout_s=5.0,
        )
        assert score.total <= 4, f"Expected <=4 for single char, got {score.total}"

    @pytest.mark.asyncio
    async def test_extremely_long_line_scores_low(self):
        """A 200-word monotone line has no sharpness or rhythm."""
        long_line = " ".join(["monotone"] * 200)
        score = await evaluate(
            long_line,
            archetype="sovereign",
            move="ESCALATE",
            arc_theme="Power and authority",
            timeout_s=5.0,
        )
        assert score.total <= 4, f"Expected <=4 for 200-word line, got {score.total}"

    @pytest.mark.asyncio
    async def test_repeated_word_line_scores_low(self):
        """A line of the same word repeated 50 times has no quality."""
        boring = " ".join(["blah"] * 50)
        score = await evaluate(
            boring,
            archetype="trickster",
            move="DEFLECT",
            arc_theme="Chaos versus order",
            timeout_s=5.0,
        )
        assert score.total <= 4, f"Expected <=4 for repeated word, got {score.total}"

    @pytest.mark.asyncio
    async def test_single_letter_different_archetype(self):
        """Single letter 'a' should score low regardless of archetype."""
        score = await evaluate(
            "a",
            archetype="shadow",
            move="TAUNT",
            arc_theme="What lurks beneath the surface?",
            timeout_s=5.0,
        )
        assert score.total <= 4, f"Expected <=4 for 'a', got {score.total}"


class TestTimeoutBehavior:
    """Timeout: mock asyncio to simulate slow execution and verify
    QualityJudgeError is raised."""

    @pytest.mark.asyncio
    async def test_timeout_raises_quality_judge_error(self):
        """When evaluation takes longer than timeout_s, QualityJudgeError is raised."""
        with pytest.raises(QualityJudgeError, match="timed out"):
            await evaluate(
                "Some banter line here.",
                archetype="prophet",
                move="COUNTER",
                arc_theme="test",
                timeout_s=0.0,  # impossible to meet
            )

    @pytest.mark.asyncio
    async def test_slow_evaluation_triggers_timeout(self):
        """Mock _evaluate_impl to be slow and verify timeout fires."""

        async def slow_impl(*args, **kwargs):
            await asyncio.sleep(10)  # way longer than timeout
            return QualityScore(
                sharpness=2,
                emotional_texture=2,
                rhythm=2,
                thematic_relevance=2,
                shareability=2,
            )

        with patch("banter.quality_judge._evaluate_impl", side_effect=slow_impl):
            with pytest.raises(QualityJudgeError, match="timed out"):
                await evaluate(
                    "This should timeout before scoring.",
                    archetype="prophet",
                    move="COUNTER",
                    arc_theme="test theme",
                    timeout_s=0.1,
                )

    @pytest.mark.asyncio
    async def test_exception_during_evaluation_raises_quality_judge_error(self):
        """If an unexpected exception occurs during evaluation, it should
        be wrapped in QualityJudgeError."""

        async def exploding_impl(*args, **kwargs):
            raise RuntimeError("Unexpected failure in scoring")

        with patch("banter.quality_judge._evaluate_impl", side_effect=exploding_impl):
            with pytest.raises(QualityJudgeError, match="Unexpected error"):
                await evaluate(
                    "Line that triggers exception.",
                    archetype="keeper",
                    move="DEFLECT",
                    arc_theme="test",
                    timeout_s=5.0,
                )


class TestEmptyAndWhitespaceInputs:
    """Empty/whitespace: verify returns a valid QualityScore (likely all 0s)
    without crashing."""

    @pytest.mark.asyncio
    async def test_empty_string_returns_valid_score(self):
        """Empty string should produce a valid QualityScore with all 0s."""
        score = await evaluate(
            "",
            archetype="trickster",
            move="DEFLECT",
            arc_theme="Chaos versus order",
            timeout_s=5.0,
        )
        assert isinstance(score, QualityScore)
        assert score.total == 0
        for name, val in score.as_dict().items():
            assert 0 <= val <= 3, f"{name} out of bounds: {val}"

    @pytest.mark.asyncio
    async def test_whitespace_only_returns_valid_score(self):
        """Whitespace-only string should not crash and should return valid QualityScore."""
        score = await evaluate(
            "   \t\n   ",
            archetype="sovereign",
            move="COUNTER",
            arc_theme="Power and control",
            timeout_s=5.0,
        )
        assert isinstance(score, QualityScore)
        # Whitespace-only is effectively empty, expect very low scores
        assert score.total <= 2
        for name, val in score.as_dict().items():
            assert 0 <= val <= 3, f"{name} out of bounds: {val}"

    @pytest.mark.asyncio
    async def test_newlines_only_returns_valid_score(self):
        """Newlines-only string should produce a valid low score."""
        score = await evaluate(
            "\n\n\n",
            archetype="herald",
            move="QUESTION",
            arc_theme="New beginnings",
            timeout_s=5.0,
        )
        assert isinstance(score, QualityScore)
        assert score.total <= 2
        for name, val in score.as_dict().items():
            assert 0 <= val <= 3

    @pytest.mark.asyncio
    async def test_spaces_between_words_handled(self):
        """Multiple spaces between words should still be handled gracefully."""
        score = await evaluate(
            "   spaces   between   words   ",
            archetype="keeper",
            move="PIVOT",
            arc_theme="Preservation",
            timeout_s=5.0,
        )
        assert isinstance(score, QualityScore)
        for name, val in score.as_dict().items():
            assert 0 <= val <= 3, f"{name} out of bounds: {val}"
