"""Property tests for HardBanChecker — validates Section 10 enforcement.

Properties tested:
- Property 12: Hard ban checker rejects all banned content
- Property 13: Backchannel exemptions from length bans
- Property 14: Fallback lines pass full delivery gate
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from banter.hard_bans import (
    DISCORD_REGISTER_PHRASES,
    GENERIC_DEBATER_PHRASES,
    HardBanChecker,
)
from banter.mode_types import (
    BACKCHANNEL_POLICY,
    NORMAL_POLICY,
)

ARCHETYPES = [
    "parasite",
    "prophet",
    "trickster",
    "sovereign",
    "martyr",
    "shadow",
    "herald",
    "keeper",
]


@pytest.fixture
def checker() -> HardBanChecker:
    return HardBanChecker()


# ---------------------------------------------------------------------------
# Property 12: Hard ban checker rejects all banned content
# ---------------------------------------------------------------------------


class TestProperty12HardBanEnforcement:
    """Property 12: Hard ban checker rejects all banned content.

    For any candidate line containing a banned phrase from discord_register
    or generic_debater lists, or containing the arc theme title, or exceeding
    mode word limits, the HardBanChecker must return passed == False.

    Validates: Requirements 10.1, 10.2, 10.3
    """

    @given(phrase_idx=st.integers(min_value=0, max_value=len(DISCORD_REGISTER_PHRASES) - 1))
    @settings(max_examples=100)
    def test_discord_register_always_rejected(self, phrase_idx: int):
        """Any line containing a discord register phrase is rejected."""
        checker = HardBanChecker()
        phrase = DISCORD_REGISTER_PHRASES[phrase_idx]
        candidate = f"Well {phrase} and that's the truth."

        verdict = checker.check(
            candidate,
            policy=NORMAL_POLICY,
            arc_theme_title="scarcity vs flow",
            archetype="prophet",
        )
        assert not verdict.passed
        assert verdict.violated_ban == "discord_register"

    @given(phrase_idx=st.integers(min_value=0, max_value=len(GENERIC_DEBATER_PHRASES) - 1))
    @settings(max_examples=100)
    def test_generic_debater_always_rejected(self, phrase_idx: int):
        """Any line containing a generic debater phrase is rejected."""
        checker = HardBanChecker()
        phrase = GENERIC_DEBATER_PHRASES[phrase_idx]
        candidate = f"I mean, {phrase}, but also not really."

        verdict = checker.check(
            candidate,
            policy=NORMAL_POLICY,
            arc_theme_title="scarcity vs flow",
            archetype="prophet",
        )
        assert not verdict.passed
        assert verdict.violated_ban == "generic_debater"

    @given(
        theme=st.text(
            min_size=5, max_size=30, alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz ")
        ),
        archetype=st.sampled_from(ARCHETYPES),
    )
    @settings(max_examples=100)
    def test_arc_title_leak_always_rejected(self, theme: str, archetype: str):
        """Any line containing the arc theme title is rejected."""
        assume(len(theme.strip()) >= 5)
        checker = HardBanChecker()
        candidate = f"The truth about {theme} is clear to everyone."

        verdict = checker.check(
            candidate,
            policy=NORMAL_POLICY,
            arc_theme_title=theme.strip(),
            archetype=archetype,
        )
        assert not verdict.passed
        assert verdict.violated_ban == "arc_theme_title_leak"

    @given(word_count=st.integers(min_value=31, max_value=60))
    @settings(max_examples=50)
    def test_too_long_rejected_normal_mode(self, word_count: int):
        """Lines exceeding NORMAL mode word limit (30) are rejected."""
        checker = HardBanChecker()
        # Use proper sentences to avoid triggering no_sentence_boundaries first
        candidate = ". ".join(["The cost arrives"] * (word_count // 3 + 1))
        # Ensure word count is at least 31
        words = candidate.split()
        if len(words) <= 30:
            candidate = candidate + " " + " ".join(["extra"] * (31 - len(words)))

        verdict = checker.check(
            candidate,
            policy=NORMAL_POLICY,
            arc_theme_title="something",
            archetype="prophet",
        )
        assert not verdict.passed
        assert verdict.violated_ban in ("too_long", "no_sentence_boundaries")

    @given(word_count=st.integers(min_value=1, max_value=3))
    @settings(max_examples=50)
    def test_too_short_rejected_normal_mode(self, word_count: int):
        """Lines below NORMAL mode word limit (4) are rejected."""
        checker = HardBanChecker()
        candidate = " ".join(["word"] * word_count)

        verdict = checker.check(
            candidate,
            policy=NORMAL_POLICY,
            arc_theme_title="something irrelevant",
            archetype="prophet",
        )
        assert not verdict.passed
        assert verdict.violated_ban == "too_short"


# ---------------------------------------------------------------------------
# Property 13: Backchannel exemptions from length bans
# ---------------------------------------------------------------------------


class TestProperty13BackchannelExemptions:
    """Property 13: Backchannel exemptions from length bans.

    For any backchannel candidate (2-6 words), the too_short hard ban must
    not trigger. However, discord_register, generic_debater, and arc_theme_title_leak
    bans must still apply.

    Validates: Requirements 10.1, 10.3, 12.7
    """

    @given(word_count=st.integers(min_value=2, max_value=6))
    @settings(max_examples=50)
    def test_backchannel_exempt_from_too_short(self, word_count: int):
        """Backchannel mode lines (2-6 words) are NOT rejected by too_short."""
        checker = HardBanChecker()
        candidate = " ".join(["noted"] * word_count)

        verdict = checker.check(
            candidate,
            policy=BACKCHANNEL_POLICY,
            arc_theme_title="something irrelevant",
            archetype="prophet",
        )
        # Should pass (no too_short violation for backchannel)
        assert verdict.passed

    def test_backchannel_still_catches_discord_register(self):
        """Backchannel mode still rejects discord register phrases."""
        checker = HardBanChecker()
        candidate = "big yikes"

        verdict = checker.check(
            candidate,
            policy=BACKCHANNEL_POLICY,
            arc_theme_title="something",
            archetype="prophet",
        )
        assert not verdict.passed
        assert verdict.violated_ban == "discord_register"

    def test_backchannel_still_catches_generic_debater(self):
        """Backchannel mode still rejects generic debater phrases."""
        checker = HardBanChecker()
        candidate = "good point"

        verdict = checker.check(
            candidate,
            policy=BACKCHANNEL_POLICY,
            arc_theme_title="something",
            archetype="prophet",
        )
        assert not verdict.passed
        assert verdict.violated_ban == "generic_debater"

    def test_backchannel_still_catches_arc_title_leak(self):
        """Backchannel mode still rejects arc title leaks."""
        checker = HardBanChecker()
        candidate = "scarcity truth"

        verdict = checker.check(
            candidate,
            policy=BACKCHANNEL_POLICY,
            arc_theme_title="scarcity truth",
            archetype="prophet",
        )
        assert not verdict.passed
        assert verdict.violated_ban == "arc_theme_title_leak"


# ---------------------------------------------------------------------------
# Property 14: Fallback lines pass delivery gate
# ---------------------------------------------------------------------------


class TestProperty14FallbackPassGate:
    """Property 14: Fallback lines pass full delivery gate.

    For any fallback template in the pool, after variable substitution,
    the resulting line must pass hard bans, arc title leak check, and
    mode word count limits.

    Validates: Requirements 10.3, 12.9
    """

    def test_sample_fallback_lines_pass(self):
        """Known good fallback lines should all pass the hard ban checker."""
        checker = HardBanChecker()
        sample_fallbacks = [
            "The cost arrives whether you count it or not.",
            "Trust is just a word people use before the bill.",
            "You already know the answer to that question.",
            "Every choice here has weight you refuse to measure.",
            "The ledger remembers what your pride forgot.",
        ]

        for line in sample_fallbacks:
            verdict = checker.check(
                line,
                policy=NORMAL_POLICY,
                arc_theme_title="scarcity vs flow",
                archetype="prophet",
            )
            assert verdict.passed, f"Fallback line failed: '{line}' — {verdict.violation_detail}"
