"""Property tests for SacredPromptBuilder — validates Section 1 contract.

Properties tested:
- Property 1: Canonical marker order preserved
- Property 2: No banned content in assembled prompts
- Property 3: Token budgets respected per block
- Property 4: Arc pressure never contains theme title
- Property 5: REACT block biconditional on opponent prior line
"""

from __future__ import annotations

import re

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from banter.arc_context import ArcContextBuilder
from banter.mode_types import (
    BACKCHANNEL_POLICY,
    CHAOS_POLICY,
    CRACK_POLICY,
    NORMAL_POLICY,
    SNAP_BACK_POLICY,
    BeatMode,
    BeatModePolicy,
)
from banter.prompt_builder import SacredPromptBuilder, PromptContractError, estimate_tokens

# Strategies
st_archetype_text = st.text(min_size=10, max_size=200, alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz .,-"))
st_arc_pressure = st.text(min_size=10, max_size=100, alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz .,-?"))
st_scene_block = st.text(min_size=5, max_size=80, alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz .,-:"))
st_move_block = st.text(min_size=5, max_size=80, alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz .,-:"))
st_banned_block = st.text(min_size=5, max_size=40, alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz .,-:"))
st_optional_block = st.one_of(st.none(), st.text(min_size=5, max_size=100, alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz .,-:")))

POLICIES = [NORMAL_POLICY, CHAOS_POLICY, CRACK_POLICY, SNAP_BACK_POLICY]
CANONICAL_ORDER = SacredPromptBuilder.CANONICAL_ORDER


# ---------------------------------------------------------------------------
# Property 1: Canonical marker order preserved
# ---------------------------------------------------------------------------


class TestProperty1CanonicalOrder:
    """Property 1: Canonical marker order preserved.

    For any combination of available context, the assembled prompt must
    contain markers in exactly the canonical order — optional markers omitted
    but never reordered.

    Validates: Requirements 1.1, 1.3, 12.1
    """

    @given(
        policy=st.sampled_from(POLICIES),
        archetype_text=st_archetype_text,
        arc_pressure=st_arc_pressure,
        react_block=st_optional_block,
        emotional_block=st_optional_block,
        callback_block=st_optional_block,
        scene_block=st_scene_block,
        move_block=st_move_block,
        banned_block=st_banned_block,
        rhythm_block=st_optional_block,
    )
    @settings(max_examples=200, deadline=None)
    def test_markers_always_in_canonical_order(
        self,
        policy: BeatModePolicy,
        archetype_text: str,
        arc_pressure: str,
        react_block: str | None,
        emotional_block: str | None,
        callback_block: str | None,
        scene_block: str,
        move_block: str,
        banned_block: str,
        rhythm_block: str | None,
    ):
        """Assembled prompt markers always follow canonical order."""
        assume(len(archetype_text.strip()) > 0)
        assume(len(arc_pressure.strip()) > 0)
        assume(len(scene_block.strip()) > 0)
        assume(len(move_block.strip()) > 0)
        assume(len(banned_block.strip()) > 0)

        builder = SacredPromptBuilder()
        prompt = builder.build(
            policy=policy,
            archetype=archetype_text,
            arc_pressure=arc_pressure,
            react_block=react_block,
            emotional_block=emotional_block,
            callback_block=callback_block,
            scene_block=scene_block,
            move_block=move_block,
            banned_block=banned_block,
            rhythm_block=rhythm_block,
        )

        # Extract markers from assembled prompt
        markers_in_prompt = re.findall(r'\[([A-Z]+)\]', prompt)
        markers_with_brackets = [f"[{m}]" for m in markers_in_prompt]

        # Verify they are a valid subsequence of CANONICAL_ORDER
        canonical_positions = {m: i for i, m in enumerate(CANONICAL_ORDER)}
        prev_pos = -1
        for marker in markers_with_brackets:
            if marker in canonical_positions:
                pos = canonical_positions[marker]
                assert pos > prev_pos, (
                    f"Marker {marker} at position {pos} appears after a marker "
                    f"at position {prev_pos}. Order violated."
                )
                prev_pos = pos


# ---------------------------------------------------------------------------
# Property 2: No banned content in assembled prompts
# ---------------------------------------------------------------------------


class TestProperty2NoBannedContent:
    """Property 2: No banned content in assembled prompts.

    The assembled prompt must not contain: raw arc theme title, legacy
    generation phrase, VoiceDNA dumps, generic Elder phrasing, or unmarked blocks.

    Validates: Requirements 1.2, 1.3, 1.5, 3.4
    """

    BANNED_PATTERNS = [
        "Generate a single broadcast-quality banter line",
        "You are a parasite Elder who",
        "You are a prophet Elder who",
        "You are a trickster Elder who",
        "You are a sovereign Elder who",
        "You are a martyr Elder who",
        "You are a shadow Elder who",
        "You are a herald Elder who",
        "You are a keeper Elder who",
        "Recent exchange:",
    ]

    def test_no_banned_phrases_in_normal_prompt(self):
        """Normal mode prompt never contains banned phrases."""
        builder = SacredPromptBuilder()
        prompt = builder.build(
            policy=NORMAL_POLICY,
            archetype="You are Shade. Ancient parasite.",
            arc_pressure="How does scarcity expose truth?",
            react_block="The last thing keeper said was: 'test line'",
            emotional_block="Tension is high.",
            callback_block=None,
            scene_block="Scene energy: heated",
            move_block="Move: COUNTER.",
            banned_block="No internet slang.",
            rhythm_block=None,
        )

        for pattern in self.BANNED_PATTERNS:
            assert pattern not in prompt, f"Banned pattern found: '{pattern}'"

    def test_no_unmarked_content(self):
        """Every section of the prompt is preceded by a known marker."""
        builder = SacredPromptBuilder()
        prompt = builder.build(
            policy=NORMAL_POLICY,
            archetype="Test archetype text.",
            arc_pressure="Test arc pressure.",
            react_block=None,
            emotional_block=None,
            callback_block=None,
            scene_block="Scene: neutral.",
            move_block="Move: COUNTER.",
            banned_block="No bans.",
            rhythm_block=None,
        )

        # Each block should start with a [MARKER]\n prefix
        blocks = prompt.split("\n\n")
        for block in blocks:
            lines = block.strip().split("\n")
            first_line = lines[0] if lines else ""
            assert re.match(r'\[[A-Z]+\]', first_line), (
                f"Block does not start with a marker: '{first_line[:50]}'"
            )


# ---------------------------------------------------------------------------
# Property 3: Token budgets respected per block
# ---------------------------------------------------------------------------


class TestProperty3TokenBudgets:
    """Property 3: Token budgets respected per block.

    Each assembled PromptBlock must have a token count <= its max_tokens ceiling.

    Validates: Requirements 1.1, 1.4, 2.9
    """

    @given(
        long_text=st.lists(
            st.text(min_size=1, max_size=8, alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz")),
            min_size=220,
            max_size=320,
        ).map(" ".join)
    )
    @settings(max_examples=50, deadline=None)
    def test_oversized_blocks_are_truncated(self, long_text: str):
        """Blocks exceeding token budget are truncated, not rejected."""
        builder = SacredPromptBuilder()
        prompt = builder.build(
            policy=NORMAL_POLICY,
            archetype=long_text,  # Way over 220 token budget
            arc_pressure="Short arc pressure.",
            react_block=None,
            emotional_block=None,
            callback_block=None,
            scene_block="Scene: neutral.",
            move_block="Move: COUNTER.",
            banned_block="No bans.",
            rhythm_block=None,
        )

        # The prompt should exist (not crash)
        assert len(prompt) > 0

        # The [ARCHETYPE] section should be truncated
        # Find the archetype block
        blocks = prompt.split("\n\n")
        for block in blocks:
            if block.startswith("[ARCHETYPE]"):
                content = block[len("[ARCHETYPE]\n"):]
                tokens = estimate_tokens(content)
                assert tokens <= 220, (
                    f"Archetype block has {tokens} tokens, exceeds 220 budget"
                )


# ---------------------------------------------------------------------------
# Property 4: Arc pressure never contains theme title
# ---------------------------------------------------------------------------


class TestProperty4ArcPressure:
    """Property 4: Arc pressure never contains theme title.

    For any arc theme string, ArcContextBuilder.get_pressure(theme) must
    return text that does not contain the raw theme title.

    Validates: Requirements 3.1, 3.4
    """

    KNOWN_THEMES = [
        "scarcity_vs_flow",
        "market_cruelty",
        "betrayal_and_return",
        "power_and_legitimacy",
        "sacrifice_and_cost",
        "truth_and_performance",
        "survival_and_meaning",
    ]

    @given(theme=st.sampled_from(KNOWN_THEMES))
    @settings(max_examples=50)
    def test_known_themes_never_leak(self, theme: str):
        """Known themes never have their title in the pressure output."""
        builder = ArcContextBuilder()
        pressure = builder.get_pressure(theme)
        readable = theme.replace("_", " ")

        assert readable not in pressure.pressure.lower()
        assert readable not in pressure.world_stakes.lower()

    @given(
        theme=st.text(min_size=3, max_size=30, alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz "))
    )
    @settings(max_examples=100, deadline=None)
    def test_random_themes_never_leak(self, theme: str):
        """Random theme strings never leak into pressure output."""
        assume(len(theme.strip()) >= 3)
        builder = ArcContextBuilder()
        pressure = builder.get_pressure(theme.strip())
        readable = theme.strip().lower().replace(" ", "_").replace("-", "_").replace("_", " ")

        # The full theme title should not appear in pressure
        assert readable not in pressure.pressure.lower(), (
            f"Theme '{readable}' leaked into pressure: {pressure.pressure}"
        )


# ---------------------------------------------------------------------------
# Property 5: REACT block biconditional on opponent prior line
# ---------------------------------------------------------------------------


class TestProperty5ReactBiconditional:
    """Property 5: REACT block biconditional on opponent prior line.

    [REACT] appears whenever opponent has a prior line.
    [REACT] is omitted when no prior opponent line exists.
    "Recent exchange:" never appears.

    Validates: Requirements 4.4
    """

    def test_react_present_when_opponent_has_line(self):
        """[REACT] marker present when react_block is provided."""
        builder = SacredPromptBuilder()
        prompt = builder.build(
            policy=NORMAL_POLICY,
            archetype="Test archetype.",
            arc_pressure="Test pressure.",
            react_block="The last thing opponent said was: 'test'",
            emotional_block=None,
            callback_block=None,
            scene_block="Scene: neutral.",
            move_block="Move: COUNTER.",
            banned_block="No bans.",
            rhythm_block=None,
        )
        assert "[REACT]" in prompt

    def test_react_absent_when_no_opponent_line(self):
        """[REACT] marker absent when react_block is None."""
        builder = SacredPromptBuilder()
        prompt = builder.build(
            policy=NORMAL_POLICY,
            archetype="Test archetype.",
            arc_pressure="Test pressure.",
            react_block=None,
            emotional_block=None,
            callback_block=None,
            scene_block="Scene: neutral.",
            move_block="Move: COUNTER.",
            banned_block="No bans.",
            rhythm_block=None,
        )
        assert "[REACT]" not in prompt

    def test_no_recent_exchange_string(self):
        """The string 'Recent exchange:' never appears in prompts."""
        builder = SacredPromptBuilder()
        prompt = builder.build(
            policy=NORMAL_POLICY,
            archetype="Test archetype.",
            arc_pressure="Test pressure.",
            react_block="The last thing keeper said was: 'test'\nExchange history here.",
            emotional_block=None,
            callback_block=None,
            scene_block="Scene: neutral.",
            move_block="Move: COUNTER.",
            banned_block="No bans.",
            rhythm_block=None,
        )
        assert "Recent exchange:" not in prompt

    def test_archetype_omitted_in_crack_mode(self):
        """[ARCHETYPE] is skipped in CRACK mode per contract."""
        builder = SacredPromptBuilder()
        prompt = builder.build(
            policy=CRACK_POLICY,
            archetype="This should not appear.",
            arc_pressure="Test pressure.",
            react_block=None,
            emotional_block=None,
            callback_block=None,
            scene_block="Scene: neutral.",
            move_block="Move: CRACK.",
            banned_block="No bans.",
            rhythm_block=None,
        )
        assert "[ARCHETYPE]" not in prompt
        assert "This should not appear" not in prompt
