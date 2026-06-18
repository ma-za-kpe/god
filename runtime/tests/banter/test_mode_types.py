"""Unit tests for mode_types module.

Validates BeatMode enum, BeatModePolicy, PromptBlock dataclasses,
and the policy table constants against the contract.
"""

from banter.mode_types import (
    BACKCHANNEL_POLICY,
    CHAOS_POLICY,
    CRACK_POLICY,
    NORMAL_POLICY,
    POLICY_TABLE,
    SILENCE_POLICY,
    SNAP_BACK_POLICY,
    BeatMode,
    BeatModePolicy,
    PromptBlock,
)


class TestBeatModeEnum:
    """BeatMode enum has all six required modes."""

    def test_has_all_modes(self):
        assert BeatMode.NORMAL.value == "normal"
        assert BeatMode.CHAOS.value == "chaos"
        assert BeatMode.CRACK.value == "crack"
        assert BeatMode.SNAP_BACK.value == "snap_back"
        assert BeatMode.BACKCHANNEL.value == "backchannel"
        assert BeatMode.SILENCE.value == "silence"

    def test_exactly_six_modes(self):
        assert len(BeatMode) == 6


class TestBeatModePolicy:
    """BeatModePolicy is frozen and has all required fields."""

    def test_is_frozen(self):
        policy = NORMAL_POLICY
        try:
            policy.quality_threshold = 5  # type: ignore[misc]
            assert False, "Should have raised FrozenInstanceError"
        except Exception:
            pass

    def test_all_fields_present(self):
        policy = NORMAL_POLICY
        assert policy.mode == BeatMode.NORMAL
        assert policy.quality_threshold == 9
        assert policy.refinement_allowed is True
        assert policy.anti_repetition_enabled is True
        assert policy.hard_bans_enabled is True
        assert policy.word_count_min == 4
        assert policy.word_count_max == 30
        assert policy.move_override is None
        assert policy.pacing_min_s == 1.0
        assert policy.pacing_max_s == 10.0


class TestPromptBlock:
    """PromptBlock is frozen and has marker, text, max_tokens."""

    def test_creation(self):
        block = PromptBlock(marker="[MODE]", text="You are in NORMAL mode.", max_tokens=40)
        assert block.marker == "[MODE]"
        assert block.text == "You are in NORMAL mode."
        assert block.max_tokens == 40

    def test_is_frozen(self):
        block = PromptBlock(marker="[MODE]", text="test", max_tokens=40)
        try:
            block.marker = "[ARC]"  # type: ignore[misc]
            assert False, "Should have raised FrozenInstanceError"
        except Exception:
            pass


class TestPolicyTableConstants:
    """Each policy constant matches the contract table exactly."""

    def test_normal_policy(self):
        p = NORMAL_POLICY
        assert p.mode == BeatMode.NORMAL
        assert p.quality_threshold == 9
        assert p.refinement_allowed is True
        assert p.anti_repetition_enabled is True
        assert p.hard_bans_enabled is True
        assert p.word_count_min == 4
        assert p.word_count_max == 30
        assert p.move_override is None

    def test_chaos_policy(self):
        p = CHAOS_POLICY
        assert p.mode == BeatMode.CHAOS
        assert p.quality_threshold == 6
        assert p.refinement_allowed is False
        assert p.anti_repetition_enabled is False
        assert p.hard_bans_enabled is True
        assert p.word_count_min == 4
        assert p.word_count_max == 30
        assert p.move_override == "ESCALATE"

    def test_crack_policy(self):
        p = CRACK_POLICY
        assert p.mode == BeatMode.CRACK
        assert p.quality_threshold == 5
        assert p.refinement_allowed is False
        assert p.anti_repetition_enabled is True
        assert p.hard_bans_enabled is True
        assert p.word_count_min == 4
        assert p.word_count_max == 20
        assert p.move_override is None

    def test_snap_back_policy(self):
        p = SNAP_BACK_POLICY
        assert p.mode == BeatMode.SNAP_BACK
        assert p.quality_threshold == 8
        assert p.refinement_allowed is True
        assert p.anti_repetition_enabled is True
        assert p.hard_bans_enabled is True
        assert p.word_count_min == 4
        assert p.word_count_max == 30
        assert p.move_override is None

    def test_backchannel_policy(self):
        p = BACKCHANNEL_POLICY
        assert p.mode == BeatMode.BACKCHANNEL
        assert p.quality_threshold is None
        assert p.refinement_allowed is False
        assert p.anti_repetition_enabled is False
        assert p.hard_bans_enabled is True
        assert p.word_count_min == 2
        assert p.word_count_max == 6
        assert p.move_override is None

    def test_silence_policy(self):
        p = SILENCE_POLICY
        assert p.mode == BeatMode.SILENCE
        assert p.quality_threshold is None
        assert p.refinement_allowed is False
        assert p.anti_repetition_enabled is False
        assert p.hard_bans_enabled is False
        assert p.word_count_min == 0
        assert p.word_count_max == 0
        assert p.move_override is None
        assert p.pacing_min_s == 3.0
        assert p.pacing_max_s == 5.0

    def test_policy_table_covers_all_modes(self):
        assert set(POLICY_TABLE.keys()) == set(BeatMode)

    def test_policy_table_values_match_constants(self):
        assert POLICY_TABLE[BeatMode.NORMAL] is NORMAL_POLICY
        assert POLICY_TABLE[BeatMode.CHAOS] is CHAOS_POLICY
        assert POLICY_TABLE[BeatMode.CRACK] is CRACK_POLICY
        assert POLICY_TABLE[BeatMode.SNAP_BACK] is SNAP_BACK_POLICY
        assert POLICY_TABLE[BeatMode.BACKCHANNEL] is BACKCHANNEL_POLICY
        assert POLICY_TABLE[BeatMode.SILENCE] is SILENCE_POLICY
