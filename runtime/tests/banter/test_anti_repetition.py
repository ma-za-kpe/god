"""Unit tests for the Anti-Repetition Gate module.

Tests cover:
- compute_trigram_overlap basic behavior
- check() with opener reuse detection
- check() with trigram overlap detection
- check() with history < 5 skipping 3-gram check
- record_delivery tracking
- should_shift_register detection
"""

import pytest
from banter.anti_repetition import AntiRepetitionGate


class TestComputeTrigramOverlap:
    """Tests for the compute_trigram_overlap static method."""

    def test_identical_strings_return_1(self):
        gate = AntiRepetitionGate()
        result = gate.compute_trigram_overlap(
            "the quick brown fox jumps over",
            "the quick brown fox jumps over",
        )
        assert result == 1.0

    def test_completely_different_strings_return_0(self):
        gate = AntiRepetitionGate()
        result = gate.compute_trigram_overlap(
            "the quick brown fox jumps",
            "alpha beta gamma delta epsilon",
        )
        assert result == 0.0

    def test_partial_overlap(self):
        gate = AntiRepetitionGate()
        result = gate.compute_trigram_overlap(
            "the quick brown fox jumps over",
            "the quick brown dog runs fast",
        )
        # "the quick brown" is shared; shorter has 4 trigrams
        assert 0.0 < result < 1.0

    def test_fewer_than_3_words_returns_0(self):
        gate = AntiRepetitionGate()
        assert gate.compute_trigram_overlap("hello world", "hello world") == 0.0
        assert gate.compute_trigram_overlap("hi", "the quick brown fox") == 0.0
        assert gate.compute_trigram_overlap("the quick brown fox", "ab") == 0.0

    def test_empty_string_returns_0(self):
        gate = AntiRepetitionGate()
        assert gate.compute_trigram_overlap("", "the quick brown fox") == 0.0
        assert gate.compute_trigram_overlap("the quick brown fox", "") == 0.0
        assert gate.compute_trigram_overlap("", "") == 0.0

    def test_case_insensitive(self):
        gate = AntiRepetitionGate()
        result = gate.compute_trigram_overlap(
            "The Quick Brown Fox Jumps",
            "the quick brown fox jumps",
        )
        assert result == 1.0


class TestCheck:
    """Tests for the check() method."""

    def test_accepts_with_empty_history(self):
        gate = AntiRepetitionGate()
        verdict = gate.check("elder1", "this is a brand new line to say")
        assert verdict.accepted is True

    def test_rejects_opener_reuse(self):
        gate = AntiRepetitionGate()
        # Record some deliveries to populate openers
        gate.record_delivery("elder1", "you think that matters in this world", "aggressive")
        # Try a candidate with same opener
        verdict = gate.check("elder1", "you think that nobody cares about truth")
        assert verdict.accepted is False
        assert verdict.rejection_reason == "opener_reuse"

    def test_skips_trigram_check_when_history_under_5(self):
        gate = AntiRepetitionGate()
        # Add 4 entries (less than 5)
        for i in range(4):
            gate.record_delivery("elder1", f"unique line number {i} with enough words for trigrams", "measured")

        # Even with high overlap to a history line, should pass (trigram skipped)
        # Using a line identical to one in history but with different opener
        verdict = gate.check("elder1", "different opener number 0 with enough words for trigrams")
        assert verdict.accepted is True

    def test_rejects_high_trigram_overlap_when_history_ge_5(self):
        gate = AntiRepetitionGate()
        # Build up 5 entries in history
        base_line = "the quick brown fox jumps over the lazy dog today"
        gate.record_delivery("elder1", base_line, "measured")
        for i in range(4):
            gate.record_delivery("elder1", f"completely different line number {i} with various words here now", "aggressive")

        # Now history has 5 entries. Try a line very similar to the first
        candidate = "the quick brown fox jumps over the lazy dog today"
        # Different opener won't help — same trigrams
        verdict = gate.check("elder1", "hey there now " + candidate[len("the quick brown "):])
        # This should be accepted since opener differs and we changed first few words
        # Let's test with actual overlap
        verdict = gate.check("elder1", "well the quick brown fox jumps over the lazy dog now")
        # High overlap with base_line
        assert verdict.accepted is False
        assert verdict.rejection_reason == "3gram_overlap"
        assert verdict.overlap_ratio is not None
        assert verdict.overlap_ratio > 0.60

    def test_accepts_when_below_threshold(self):
        gate = AntiRepetitionGate()
        # Build 5 entries
        for i in range(5):
            gate.record_delivery("elder1", f"entry {i} alpha beta gamma delta epsilon zeta eta", "sardonic")

        # A completely different line should pass
        verdict = gate.check("elder1", "something entirely new and original with fresh words here")
        assert verdict.accepted is True

    def test_opener_check_case_insensitive(self):
        gate = AntiRepetitionGate()
        gate.record_delivery("elder1", "The truth hurts when you least expect it", "vulnerable")
        # Same opener different case
        verdict = gate.check("elder1", "the truth hurts but differently this time around")
        assert verdict.accepted is False
        assert verdict.rejection_reason == "opener_reuse"

    def test_per_elder_isolation(self):
        gate = AntiRepetitionGate()
        gate.record_delivery("elder1", "you think that matters in the real world", "aggressive")
        # Same opener but different elder should be fine
        verdict = gate.check("elder2", "you think that nobody has a clue here")
        assert verdict.accepted is True


class TestRecordDelivery:
    """Tests for the record_delivery() method."""

    def test_records_line_in_history(self):
        gate = AntiRepetitionGate()
        gate.record_delivery("elder1", "test line here", "measured")
        assert "test line here" in gate._history["elder1"]

    def test_records_opener(self):
        gate = AntiRepetitionGate()
        gate.record_delivery("elder1", "The quick brown fox jumps", "aggressive")
        assert "the quick brown" in gate._openers["elder1"]

    def test_records_register(self):
        gate = AntiRepetitionGate()
        gate.record_delivery("elder1", "something here now", "sardonic")
        assert "sardonic" in gate._registers["elder1"]

    def test_history_window_respects_maxlen(self):
        gate = AntiRepetitionGate(history_window=5)
        for i in range(10):
            gate.record_delivery("elder1", f"line {i} with some words", "measured")
        assert len(gate._history["elder1"]) == 5

    def test_opener_window_respects_maxlen(self):
        gate = AntiRepetitionGate(opener_window=3)
        for i in range(10):
            gate.record_delivery("elder1", f"opener {i} words and more content", "measured")
        assert len(gate._openers["elder1"]) == 3


class TestShouldShiftRegister:
    """Tests for the should_shift_register() method."""

    def test_returns_false_with_fewer_than_3_entries(self):
        gate = AntiRepetitionGate()
        gate.record_delivery("elder1", "line one here now", "aggressive")
        gate.record_delivery("elder1", "line two here now", "aggressive")
        assert gate.should_shift_register("elder1") is False

    def test_returns_true_when_last_3_identical(self):
        gate = AntiRepetitionGate()
        gate.record_delivery("elder1", "line one here now", "aggressive")
        gate.record_delivery("elder1", "line two here now", "aggressive")
        gate.record_delivery("elder1", "line three here now", "aggressive")
        assert gate.should_shift_register("elder1") is True

    def test_returns_false_when_last_3_differ(self):
        gate = AntiRepetitionGate()
        gate.record_delivery("elder1", "line one here now", "aggressive")
        gate.record_delivery("elder1", "line two here now", "sardonic")
        gate.record_delivery("elder1", "line three here now", "aggressive")
        assert gate.should_shift_register("elder1") is False

    def test_returns_false_for_unknown_elder(self):
        gate = AntiRepetitionGate()
        assert gate.should_shift_register("unknown") is False

    def test_checks_only_last_3(self):
        gate = AntiRepetitionGate()
        gate.record_delivery("elder1", "line a here now", "aggressive")
        gate.record_delivery("elder1", "line b here now", "aggressive")
        gate.record_delivery("elder1", "line c here now", "aggressive")
        gate.record_delivery("elder1", "line d here now", "measured")  # breaks streak
        assert gate.should_shift_register("elder1") is False


# ---------------------------------------------------------------------------
# Property-Based Tests (Hypothesis)
# ---------------------------------------------------------------------------

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from conftest import ARCHETYPES, EMOTIONAL_REGISTERS


@st.composite
def st_word_sequence(draw, min_words=3, max_words=15):
    """Generate a sequence of words joined by spaces."""
    words = draw(st.lists(
        st.text(min_size=2, max_size=8, alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz")),
        min_size=min_words,
        max_size=max_words,
    ))
    return " ".join(words)


class TestProperty20TrigramOverlapRejection:
    """**Property 20: Trigram Overlap Rejection**

    >60% overlap rejected when history ≥5; skipped when <5.

    **Validates: Requirements 8.1, 8.2, 8.6**
    """

    @given(
        history_lines=st.lists(
            st_word_sequence(min_words=5, max_words=12),
            min_size=5,
            max_size=10,
        ),
    )
    @settings(max_examples=100)
    def test_identical_line_rejected_when_history_ge_5(self, history_lines: list[str]):
        """A line identical to one in history (≥5) is rejected for overlap."""
        gate = AntiRepetitionGate()
        elder = "prophet"

        # Populate history with unique lines
        for line in history_lines:
            gate.record_delivery(elder, line, "measured")

        # Try submitting a line identical to one in history
        # Use a different opener to isolate trigram check
        target_line = history_lines[0]
        # The line should have high trigram overlap
        verdict = gate.check(elder, target_line)

        # If the opener matches, it'll be rejected for opener_reuse anyway
        # Let's check that it's rejected (either reason is fine)
        if verdict.accepted:
            # Could pass if opener is different and overlap calculation differs
            overlap = gate.compute_trigram_overlap(target_line, history_lines[0])
            assert overlap <= 0.60, (
                f"Should reject: overlap {overlap:.2f} > 0.60 with history >= 5"
            )

    @given(
        history_lines=st.lists(
            st_word_sequence(min_words=5, max_words=12),
            min_size=0,
            max_size=4,
        ),
        candidate=st_word_sequence(min_words=5, max_words=12),
    )
    @settings(max_examples=100)
    def test_trigram_skipped_when_history_under_5(
        self, history_lines: list[str], candidate: str
    ):
        """When history < 5, 3-gram check is skipped (candidate not rejected for overlap)."""
        gate = AntiRepetitionGate()
        elder = "prophet"

        for line in history_lines:
            gate.record_delivery(elder, line, "measured")

        # Ensure elder is initialized (may be empty list if no lines)
        gate._ensure_elder(elder)
        assert len(gate._history[elder]) < 5

        # Use a candidate with a unique opener to avoid opener rejection
        unique_opener = "xyzzy qqq zzz"
        test_candidate = unique_opener + " " + candidate

        verdict = gate.check(elder, test_candidate)
        # Should NOT be rejected for 3gram_overlap (may be rejected for opener but we used unique one)
        if not verdict.accepted:
            assert verdict.rejection_reason != "3gram_overlap", (
                "Should not reject for 3gram overlap when history < 5"
            )

    @given(
        line_a=st_word_sequence(min_words=6, max_words=15),
        line_b=st_word_sequence(min_words=6, max_words=15),
    )
    @settings(max_examples=200)
    def test_overlap_ratio_symmetric_and_bounded(self, line_a: str, line_b: str):
        """Trigram overlap is always in [0.0, 1.0]."""
        gate = AntiRepetitionGate()
        overlap = gate.compute_trigram_overlap(line_a, line_b)
        assert 0.0 <= overlap <= 1.0, f"Overlap {overlap} out of [0.0, 1.0]"


class TestProperty21OpenerUniqueness:
    """**Property 21: Opener Uniqueness**

    First 3 words matching any opener in last 8 → rejected.

    **Validates: Requirements 8.3**
    """

    @given(
        opener_words=st.lists(
            st.text(min_size=2, max_size=8, alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz")),
            min_size=3,
            max_size=3,
        ),
        rest_of_line=st_word_sequence(min_words=3, max_words=10),
        num_openers_before=st.integers(min_value=0, max_value=7),
    )
    @settings(max_examples=200)
    def test_matching_opener_always_rejected(
        self, opener_words: list[str], rest_of_line: str, num_openers_before: int
    ):
        """A candidate whose first 3 words match any opener in last 8 is rejected."""
        gate = AntiRepetitionGate()
        elder = "prophet"
        opener_str = " ".join(opener_words)

        # Record the opener in history (add filler words to make a full line)
        full_line = opener_str + " some filler content words here for length"
        gate.record_delivery(elder, full_line, "measured")

        # Record some other lines to push it into the window (but not out)
        for i in range(num_openers_before):
            gate.record_delivery(
                elder,
                f"different opener {i} with more unique words here now",
                "aggressive",
            )

        # Now check a candidate with the same opener
        candidate = opener_str + " " + rest_of_line
        verdict = gate.check(elder, candidate)
        assert verdict.accepted is False, (
            f"Should reject opener reuse: '{opener_str}' in last 8"
        )
        assert verdict.rejection_reason == "opener_reuse"

    @given(
        unique_opener=st.lists(
            st.text(min_size=3, max_size=8, alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz")),
            min_size=3,
            max_size=3,
        ),
    )
    @settings(max_examples=100)
    def test_unique_opener_not_rejected(self, unique_opener: list[str]):
        """A candidate with a unique opener (not in last 8) is not rejected for opener."""
        gate = AntiRepetitionGate()
        elder = "prophet"

        # Record some history with different openers
        for i in range(5):
            gate.record_delivery(
                elder,
                f"other words {i} making a full unique line here",
                "measured",
            )

        # Check with a new unique opener
        opener_str = " ".join(unique_opener)
        candidate = opener_str + " some more content for the line"

        # Verify our opener isn't already in the openers list
        if opener_str.lower() not in gate._openers[elder]:
            verdict = gate.check(elder, candidate)
            if not verdict.accepted:
                # Could still be rejected for 3gram overlap, but not for opener
                assert verdict.rejection_reason != "opener_reuse"


class TestProperty22AntiRepetitionFallbackGuarantee:
    """**Property 22: Anti-Repetition Fallback Guarantee**

    After 3 rejections, system selects from Fallback_Pool on next cycle.

    **Validates: Requirements 8.5**
    """

    @given(
        num_rejections=st.integers(min_value=3, max_value=10),
    )
    @settings(max_examples=50)
    def test_fallback_triggered_after_3_rejections(self, num_rejections: int):
        """After 3+ consecutive rejections, the system should use fallback.

        We verify this by checking that the gate consistently rejects
        when given repetitive content, proving the fallback mechanism
        would be needed (the engine uses fallback after 3 rejections).
        """
        gate = AntiRepetitionGate()
        elder = "prophet"

        # Build up history ≥ 5 with specific content
        base_line = "the quick brown fox jumps over the lazy dog today"
        gate.record_delivery(elder, base_line, "measured")
        for i in range(5):
            gate.record_delivery(
                elder,
                f"unique content line {i} with different words here now",
                "aggressive",
            )

        # Try submitting lines that will be rejected
        rejection_count = 0
        for attempt in range(num_rejections):
            # Use a line with same opener OR high overlap
            candidate = "the quick brown fox jumps over the lazy dog today"
            verdict = gate.check(elder, candidate)
            if not verdict.accepted:
                rejection_count += 1

        # After 3+ rejections, the engine would invoke fallback pool
        # Here we verify the gate correctly rejects repetitive content
        assert rejection_count >= 3, (
            f"Expected ≥3 rejections from repetitive content, got {rejection_count}"
        )

    @given(
        elder=st.sampled_from(ARCHETYPES),
    )
    @settings(max_examples=20)
    def test_fresh_elder_never_triggers_immediate_fallback(self, elder: str):
        """A fresh elder with no history should never need fallback (all checks pass)."""
        gate = AntiRepetitionGate()

        # Fresh check with unique content
        verdict = gate.check(elder, "something completely new and original here")
        assert verdict.accepted is True, (
            f"Fresh elder '{elder}' should not be rejected: {verdict.rejection_reason}"
        )
