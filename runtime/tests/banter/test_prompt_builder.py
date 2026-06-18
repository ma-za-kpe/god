"""Unit tests for SacredPromptBuilder — canonical marker order and token validation.

Tests cover:
- Canonical marker order assembly
- CRACK mode skips [ARCHETYPE]
- [REACT] included only when opponent has prior line
- Optional blocks omitted when None
- Token budget enforcement (truncation)
- Marker order validation raises PromptContractError
- Unknown marker rejection
- No unmarked content in output
- All mandatory blocks always present

Requirements: 1.1, 1.3, 12.1
"""

import pytest

from banter.mode_types import (
    BeatMode,
    BeatModePolicy,
    CRACK_POLICY,
    NORMAL_POLICY,
    CHAOS_POLICY,
    PromptBlock,
)
from banter.prompt_builder import (
    PromptContractError,
    SacredPromptBuilder,
    estimate_tokens,
    truncate_to_budget,
)


@pytest.fixture
def builder() -> SacredPromptBuilder:
    return SacredPromptBuilder()


@pytest.fixture
def minimal_args() -> dict:
    """Minimal valid arguments for build() — no optional blocks."""
    return {
        "policy": NORMAL_POLICY,
        "archetype": "You are Shade. Ancient parasite.",
        "arc_pressure": "The question burning through the Veil.",
        "react_block": None,
        "emotional_block": None,
        "callback_block": None,
        "scene_block": "Scene is heated.",
        "move_block": "COUNTER this beat.",
        "banned_block": "No arc title leaks.",
        "rhythm_block": None,
    }


@pytest.fixture
def full_args() -> dict:
    """Full arguments for build() — all optional blocks present."""
    return {
        "policy": NORMAL_POLICY,
        "archetype": "You are Shade. Ancient parasite.",
        "arc_pressure": "The question burning through the Veil.",
        "react_block": "The last thing Lore said was: 'Rent comes due.'",
        "emotional_block": "Tension is high. Recent betrayal detected.",
        "callback_block": "Earlier you said something about rent.",
        "scene_block": "Scene is heated.",
        "move_block": "COUNTER this beat.",
        "banned_block": "No arc title leaks.",
        "rhythm_block": "This line may trail off.",
    }


class TestBuildCanonicalOrder:
    """Tests for canonical marker order in assembled prompts."""

    def test_minimal_prompt_has_mandatory_markers(
        self, builder: SacredPromptBuilder, minimal_args: dict
    ):
        """Minimal prompt must contain [MODE], [ARC], [SCENE], [MOVE], [BANNED]."""
        result = builder.build(**minimal_args)

        assert "[MODE]" in result
        assert "[ARCHETYPE]" in result  # NORMAL mode includes archetype
        assert "[ARC]" in result
        assert "[SCENE]" in result
        assert "[MOVE]" in result
        assert "[BANNED]" in result

    def test_minimal_prompt_excludes_optional_markers(
        self, builder: SacredPromptBuilder, minimal_args: dict
    ):
        """When optional blocks are None, their markers are absent."""
        result = builder.build(**minimal_args)

        assert "[REACT]" not in result
        assert "[EMOTIONAL]" not in result
        assert "[CALLBACK]" not in result
        assert "[RHYTHM]" not in result

    def test_full_prompt_has_all_markers(
        self, builder: SacredPromptBuilder, full_args: dict
    ):
        """Full prompt must contain all 10 markers in order."""
        result = builder.build(**full_args)

        for marker in SacredPromptBuilder.CANONICAL_ORDER:
            assert marker in result

    def test_marker_order_preserved_in_full_prompt(
        self, builder: SacredPromptBuilder, full_args: dict
    ):
        """Markers appear in canonical order in the assembled prompt."""
        result = builder.build(**full_args)

        positions = []
        for marker in SacredPromptBuilder.CANONICAL_ORDER:
            pos = result.find(marker)
            assert pos >= 0, f"Marker {marker} not found"
            positions.append(pos)

        assert positions == sorted(positions), "Markers are not in canonical order"

    def test_marker_order_preserved_with_partial_optionals(
        self, builder: SacredPromptBuilder, minimal_args: dict
    ):
        """Partial optionals still maintain canonical order."""
        minimal_args["emotional_block"] = "Some emotional context."
        minimal_args["rhythm_block"] = "Trailing rule."
        result = builder.build(**minimal_args)

        present_markers = [
            m for m in SacredPromptBuilder.CANONICAL_ORDER if m in result
        ]
        expected = [
            "[MODE]",
            "[ARCHETYPE]",
            "[ARC]",
            "[EMOTIONAL]",
            "[SCENE]",
            "[MOVE]",
            "[BANNED]",
            "[RHYTHM]",
        ]
        assert present_markers == expected


class TestCRACKMode:
    """Tests for CRACK mode — [ARCHETYPE] is skipped."""

    def test_crack_mode_skips_archetype(
        self, builder: SacredPromptBuilder, minimal_args: dict
    ):
        """CRACK mode must not include [ARCHETYPE] block."""
        minimal_args["policy"] = CRACK_POLICY
        result = builder.build(**minimal_args)

        assert "[ARCHETYPE]" not in result
        assert "[MODE]" in result
        assert "[ARC]" in result

    def test_non_crack_modes_include_archetype(
        self, builder: SacredPromptBuilder, minimal_args: dict
    ):
        """Non-CRACK modes must include [ARCHETYPE]."""
        for policy in [NORMAL_POLICY, CHAOS_POLICY]:
            minimal_args["policy"] = policy
            result = builder.build(**minimal_args)
            assert "[ARCHETYPE]" in result


class TestReactBlock:
    """Tests for [REACT] block — biconditional on opponent prior line."""

    def test_react_included_when_present(
        self, builder: SacredPromptBuilder, minimal_args: dict
    ):
        """[REACT] appears when react_block is not None."""
        minimal_args["react_block"] = "Last thing opponent said."
        result = builder.build(**minimal_args)
        assert "[REACT]" in result

    def test_react_excluded_when_none(
        self, builder: SacredPromptBuilder, minimal_args: dict
    ):
        """[REACT] is absent when react_block is None."""
        result = builder.build(**minimal_args)
        assert "[REACT]" not in result


class TestTokenBudgets:
    """Tests for token budget enforcement."""

    def test_short_text_not_truncated(self, builder: SacredPromptBuilder):
        """Text within budget is not modified."""
        text = "Short text here."
        assert estimate_tokens(text) <= 40
        result = truncate_to_budget(text, 40)
        assert result == text

    def test_long_text_truncated(self, builder: SacredPromptBuilder):
        """Text exceeding budget is truncated."""
        # Create text that exceeds 40 tokens (roughly 31+ words)
        long_text = " ".join(["word"] * 50)
        assert estimate_tokens(long_text) > 40
        result = truncate_to_budget(long_text, 40)
        assert estimate_tokens(result) <= 40

    def test_build_truncates_over_budget_blocks(
        self, builder: SacredPromptBuilder, minimal_args: dict
    ):
        """build() truncates blocks that exceed their token ceiling."""
        # [MODE] has 40 token budget — create a policy with long text
        # Use a very long banned_block (40 token budget)
        minimal_args["banned_block"] = " ".join(["forbidden"] * 50)
        result = builder.build(**minimal_args)

        # Extract the banned block content
        banned_start = result.find("[BANNED]\n") + len("[BANNED]\n")
        banned_end = result.find("\n\n", banned_start)
        if banned_end == -1:
            banned_content = result[banned_start:]
        else:
            banned_content = result[banned_start:banned_end]

        assert estimate_tokens(banned_content) <= 40

    def test_empty_text_zero_tokens(self):
        """Empty text has 0 tokens."""
        assert estimate_tokens("") == 0

    def test_estimate_tokens_word_based(self):
        """Token estimation uses words * 1.3."""
        text = "one two three four five"
        assert estimate_tokens(text) == int(5 * 1.3)


class TestValidateOrder:
    """Tests for validate_order() raising PromptContractError."""

    def test_valid_order_passes(self, builder: SacredPromptBuilder):
        """Blocks in canonical order pass validation."""
        blocks = [
            PromptBlock(marker="[MODE]", text="test", max_tokens=40),
            PromptBlock(marker="[ARC]", text="test", max_tokens=80),
            PromptBlock(marker="[SCENE]", text="test", max_tokens=80),
        ]
        # Should not raise
        builder.validate_order(blocks)

    def test_reordered_markers_raises(self, builder: SacredPromptBuilder):
        """Reordered markers raise PromptContractError."""
        blocks = [
            PromptBlock(marker="[ARC]", text="test", max_tokens=80),
            PromptBlock(marker="[MODE]", text="test", max_tokens=40),  # out of order
        ]
        with pytest.raises(PromptContractError, match="Marker order violation"):
            builder.validate_order(blocks)

    def test_unknown_marker_raises(self, builder: SacredPromptBuilder):
        """Unknown markers raise PromptContractError."""
        blocks = [
            PromptBlock(marker="[MODE]", text="test", max_tokens=40),
            PromptBlock(marker="[UNKNOWN]", text="test", max_tokens=50),
        ]
        with pytest.raises(PromptContractError, match="Unknown marker"):
            builder.validate_order(blocks)

    def test_empty_blocks_passes(self, builder: SacredPromptBuilder):
        """Empty block list passes validation."""
        builder.validate_order([])

    def test_duplicate_marker_raises(self, builder: SacredPromptBuilder):
        """Duplicate markers are treated as order violation."""
        blocks = [
            PromptBlock(marker="[MODE]", text="test", max_tokens=40),
            PromptBlock(marker="[MODE]", text="test2", max_tokens=40),
        ]
        with pytest.raises(PromptContractError, match="Marker order violation"):
            builder.validate_order(blocks)


class TestNoUnmarkedContent:
    """Tests ensuring no unmarked content in assembled prompts."""

    def test_output_only_contains_known_markers(
        self, builder: SacredPromptBuilder, full_args: dict
    ):
        """Every section in the output starts with a known marker."""
        result = builder.build(**full_args)
        sections = result.split("\n\n")

        known_markers = set(SacredPromptBuilder.CANONICAL_ORDER)
        for section in sections:
            first_line = section.split("\n")[0]
            assert first_line in known_markers, (
                f"Section starts with '{first_line}', not a known marker"
            )


class TestFormatMode:
    """Tests for _format_mode() producing concise mode descriptors."""

    def test_normal_mode_format(self, builder: SacredPromptBuilder):
        """NORMAL mode includes quality threshold and refinement."""
        text = builder._format_mode(NORMAL_POLICY)
        assert "NORMAL" in text
        assert "9/18" in text
        assert "enabled" in text

    def test_chaos_mode_format(self, builder: SacredPromptBuilder):
        """CHAOS mode includes move override."""
        text = builder._format_mode(CHAOS_POLICY)
        assert "CHAOS" in text
        assert "ESCALATE" in text
        assert "disabled" in text.lower()

    def test_crack_mode_format(self, builder: SacredPromptBuilder):
        """CRACK mode shows correct threshold."""
        text = builder._format_mode(CRACK_POLICY)
        assert "CRACK" in text
        assert "5/18" in text
