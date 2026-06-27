"""Unit tests for ContractQualityScore, HardBan, and HardBanVerdict.

Validates the contract-aligned data models from Section 7 and Section 10.
"""

from __future__ import annotations

import pytest

from banter.contract_types import (
    ContractQualityScore,
    HardBan,
    HardBanVerdict,
)


# ---------------------------------------------------------------------------
# ContractQualityScore tests
# ---------------------------------------------------------------------------


class TestContractQualityScore:
    """Tests for the 6-dimension quality score dataclass."""

    def test_total_is_sum_of_all_dimensions(self):
        score = ContractQualityScore(
            sharpness=3,
            emotional_texture=2,
            rhythm=1,
            pressure_relevance=3,
            voice_authenticity=2,
            subtext_depth=1,
        )
        assert score.total == 12

    def test_total_maximum_is_18(self):
        score = ContractQualityScore(
            sharpness=3,
            emotional_texture=3,
            rhythm=3,
            pressure_relevance=3,
            voice_authenticity=3,
            subtext_depth=3,
        )
        assert score.total == 18

    def test_total_minimum_is_0(self):
        score = ContractQualityScore(
            sharpness=0,
            emotional_texture=0,
            rhythm=0,
            pressure_relevance=0,
            voice_authenticity=0,
            subtext_depth=0,
        )
        assert score.total == 0

    def test_clip_candidate_true_when_criteria_met(self):
        """Requirement 7.5: total >= 14, sharpness >= 3, emotional >= 2, voice >= 2."""
        score = ContractQualityScore(
            sharpness=3,
            emotional_texture=2,
            rhythm=3,
            pressure_relevance=2,
            voice_authenticity=2,
            subtext_depth=2,
        )
        assert score.total == 14
        assert score.clip_candidate is True

    def test_clip_candidate_false_total_below_14(self):
        score = ContractQualityScore(
            sharpness=3,
            emotional_texture=2,
            rhythm=2,
            pressure_relevance=2,
            voice_authenticity=2,
            subtext_depth=2,
        )
        assert score.total == 13
        assert score.clip_candidate is False

    def test_clip_candidate_false_sharpness_below_3(self):
        score = ContractQualityScore(
            sharpness=2,
            emotional_texture=3,
            rhythm=3,
            pressure_relevance=3,
            voice_authenticity=3,
            subtext_depth=3,
        )
        assert score.total == 17
        assert score.clip_candidate is False

    def test_clip_candidate_false_emotional_texture_below_2(self):
        score = ContractQualityScore(
            sharpness=3,
            emotional_texture=1,
            rhythm=3,
            pressure_relevance=3,
            voice_authenticity=3,
            subtext_depth=3,
        )
        assert score.total == 16
        assert score.clip_candidate is False

    def test_clip_candidate_false_voice_authenticity_below_2(self):
        score = ContractQualityScore(
            sharpness=3,
            emotional_texture=3,
            rhythm=3,
            pressure_relevance=3,
            voice_authenticity=1,
            subtext_depth=3,
        )
        assert score.total == 16
        assert score.clip_candidate is False

    def test_as_dict_has_six_dimensions(self):
        score = ContractQualityScore(
            sharpness=1,
            emotional_texture=2,
            rhythm=3,
            pressure_relevance=0,
            voice_authenticity=1,
            subtext_depth=2,
        )
        d = score.as_dict()
        assert len(d) == 6
        assert d == {
            "sharpness": 1,
            "emotional_texture": 2,
            "rhythm": 3,
            "pressure_relevance": 0,
            "voice_authenticity": 1,
            "subtext_depth": 2,
        }

    def test_as_dict_does_not_contain_shareability(self):
        """Requirement 7.6: shareability is absent from as_dict()."""
        score = ContractQualityScore(
            sharpness=1,
            emotional_texture=2,
            rhythm=3,
            pressure_relevance=0,
            voice_authenticity=1,
            subtext_depth=2,
        )
        assert "shareability" not in score.as_dict()

    def test_as_dict_does_not_contain_thematic_relevance(self):
        """Dimension renamed: thematic_relevance → pressure_relevance."""
        score = ContractQualityScore(
            sharpness=1,
            emotional_texture=2,
            rhythm=3,
            pressure_relevance=0,
            voice_authenticity=1,
            subtext_depth=2,
        )
        assert "thematic_relevance" not in score.as_dict()

    def test_frozen_dataclass_is_immutable(self):
        score = ContractQualityScore(
            sharpness=3,
            emotional_texture=2,
            rhythm=1,
            pressure_relevance=3,
            voice_authenticity=2,
            subtext_depth=1,
        )
        with pytest.raises(Exception):
            score.sharpness = 0  # type: ignore[misc]

    def test_weak_dimensions_returns_dimensions_at_or_below_1(self):
        score = ContractQualityScore(
            sharpness=0,
            emotional_texture=1,
            rhythm=2,
            pressure_relevance=3,
            voice_authenticity=1,
            subtext_depth=0,
        )
        weak = score.weak_dimensions
        assert ("sharpness", 0) in weak
        assert ("emotional_texture", 1) in weak
        assert ("voice_authenticity", 1) in weak
        assert ("subtext_depth", 0) in weak
        assert ("rhythm", 2) not in weak
        assert ("pressure_relevance", 3) not in weak


# ---------------------------------------------------------------------------
# HardBan tests
# ---------------------------------------------------------------------------


class TestHardBan:
    """Tests for the HardBan frozen dataclass."""

    def test_basic_construction(self):
        ban = HardBan(
            name="no_sentence_boundaries",
            description="Two or more clauses without punctuation between them",
        )
        assert ban.name == "no_sentence_boundaries"
        assert ban.description == "Two or more clauses without punctuation between them"
        assert ban.banned_phrases == ()
        assert ban.exceptions == ()

    def test_with_banned_phrases(self):
        ban = HardBan(
            name="discord_register",
            description="Internet slang",
            banned_phrases=("buckle up", "big yikes"),
        )
        assert ban.banned_phrases == ("buckle up", "big yikes")

    def test_with_exceptions(self):
        ban = HardBan(
            name="subjectless_opening",
            description="Line starts with verb without subject",
            exceptions=("shadow", "trickster"),
        )
        assert ban.exceptions == ("shadow", "trickster")

    def test_frozen_is_immutable(self):
        ban = HardBan(name="test", description="test ban")
        with pytest.raises(Exception):
            ban.name = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# HardBanVerdict tests
# ---------------------------------------------------------------------------


class TestHardBanVerdict:
    """Tests for the HardBanVerdict frozen dataclass."""

    def test_passing_verdict(self):
        verdict = HardBanVerdict(passed=True)
        assert verdict.passed is True
        assert verdict.violated_ban is None
        assert verdict.violation_detail is None

    def test_failing_verdict(self):
        verdict = HardBanVerdict(
            passed=False,
            violated_ban="discord_register",
            violation_detail="Contains 'buckle up'",
        )
        assert verdict.passed is False
        assert verdict.violated_ban == "discord_register"
        assert verdict.violation_detail == "Contains 'buckle up'"

    def test_frozen_is_immutable(self):
        verdict = HardBanVerdict(passed=True)
        with pytest.raises(Exception):
            verdict.passed = False  # type: ignore[misc]
