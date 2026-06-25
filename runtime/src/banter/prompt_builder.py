"""Sacred Prompt Builder — structured prompt assembly with contract enforcement.

Assembles PromptBlock objects in canonical marker order (Section 1),
validates marker sequence, enforces token budgets per block, and rejects
any unmarked content.

The prompt builder is the single canonical assembly path for all generation
prompts in the banter engine. No ad hoc string assembly is permitted.

Requirements: 1.1, 1.3, 12.1
"""

from __future__ import annotations

from .mode_types import BeatMode, BeatModePolicy, PromptBlock


# ---------------------------------------------------------------------------
# PromptContractError
# ---------------------------------------------------------------------------


class PromptContractError(Exception):
    """Raised when prompt assembly violates the sacred contract.

    This indicates a programming bug, not a runtime condition.
    Marker order violations and unknown markers trigger this error.
    """

    pass


# ---------------------------------------------------------------------------
# Token estimation
# ---------------------------------------------------------------------------


def estimate_tokens(text: str) -> int:
    """Estimate token count using word-based approximation.

    Uses words * 1.3 as a simple heuristic. This is a conservative
    estimate that works well for English prose without requiring
    tiktoken as a dependency.
    """
    if not text:
        return 0
    word_count = len(text.split())
    return int(word_count * 1.3)


def truncate_to_budget(text: str, max_tokens: int) -> str:
    """Truncate text to fit within a token budget.

    Removes words from the end until the estimated token count
    is within budget. Returns the original text if already within budget.
    """
    if estimate_tokens(text) <= max_tokens:
        return text

    words = text.split()
    while words and estimate_tokens(" ".join(words)) > max_tokens:
        words.pop()

    return " ".join(words)


# ---------------------------------------------------------------------------
# SacredPromptBuilder
# ---------------------------------------------------------------------------


class SacredPromptBuilder:
    """Assembles generation prompts in canonical marker order.

    The canonical order is sacred — markers may be omitted (when their
    content is not applicable) but never reordered. Any attempt to
    reorder markers raises PromptContractError.

    Token budgets are enforced per block. Blocks exceeding their ceiling
    are truncated with a warning logged.

    No unmarked content is permitted in the assembled prompt.

    Requirements: 1.1, 1.3, 12.1
    """

    CANONICAL_ORDER: list[str] = [
        "[MODE]",
        "[ARCHETYPE]",
        "[ARC]",
        "[REACT]",
        "[EMOTIONAL]",
        "[CALLBACK]",
        "[SCENE]",
        "[MOVE]",
        "[BANNED]",
        "[RHYTHM]",
    ]

    # Token budget ceilings per marker
    TOKEN_BUDGETS: dict[str, int] = {
        "[MODE]": 40,
        "[ARCHETYPE]": 220,
        "[ARC]": 80,
        "[REACT]": 80,
        "[EMOTIONAL]": 150,
        "[CALLBACK]": 100,
        "[SCENE]": 80,
        "[MOVE]": 80,
        "[BANNED]": 40,
        "[RHYTHM]": 30,
    }

    def build(
        self,
        policy: BeatModePolicy,
        archetype: str,
        arc_pressure: str,
        react_block: str | None,
        emotional_block: str | None,
        callback_block: str | None,
        scene_block: str,
        move_block: str,
        banned_block: str,
        rhythm_block: str | None,
    ) -> str:
        """Assemble a generation prompt in canonical marker order.

        Args:
            policy: The resolved BeatModePolicy for this beat.
            archetype: Archetype system prompt text.
            arc_pressure: Arc pressure directive text.
            react_block: Forced response text, or None if no opponent prior line.
            emotional_block: Emotional/relationship context, or None if unavailable.
            callback_block: Callback/subtext text, or None if unavailable.
            scene_block: Scene state text.
            move_block: Move instruction and mode policy text.
            banned_block: Hard bans reminder text.
            rhythm_block: Rhythm directive text, or None if not applicable.

        Returns:
            The fully assembled prompt string with markers and content.

        Raises:
            PromptContractError: If marker order is violated (programming bug).
        """
        blocks: list[PromptBlock] = []

        # 1. Always: [MODE]
        mode_text = self._format_mode(policy)
        blocks.append(PromptBlock(marker="[MODE]", text=mode_text, max_tokens=40))

        # 2. [ARCHETYPE] — skip for CRACK mode
        if policy.mode != BeatMode.CRACK:
            blocks.append(PromptBlock(marker="[ARCHETYPE]", text=archetype, max_tokens=220))

        # 3. Always: [ARC]
        blocks.append(PromptBlock(marker="[ARC]", text=arc_pressure, max_tokens=80))

        # 4. [REACT] — only when opponent has prior line
        if react_block is not None:
            blocks.append(PromptBlock(marker="[REACT]", text=react_block, max_tokens=80))

        # 5. [EMOTIONAL] — only when available
        if emotional_block is not None:
            blocks.append(PromptBlock(marker="[EMOTIONAL]", text=emotional_block, max_tokens=150))

        # 6. [CALLBACK] — only when available
        if callback_block is not None:
            blocks.append(PromptBlock(marker="[CALLBACK]", text=callback_block, max_tokens=100))

        # 7. Always: [SCENE]
        blocks.append(PromptBlock(marker="[SCENE]", text=scene_block, max_tokens=80))

        # 8. Always: [MOVE]
        blocks.append(PromptBlock(marker="[MOVE]", text=move_block, max_tokens=80))

        # 9. Always: [BANNED]
        blocks.append(PromptBlock(marker="[BANNED]", text=banned_block, max_tokens=40))

        # 10. [RHYTHM] — only when applicable
        if rhythm_block is not None:
            blocks.append(PromptBlock(marker="[RHYTHM]", text=rhythm_block, max_tokens=30))

        # Validate and enforce contract
        self.validate_order(blocks)
        self.validate_budgets(blocks)

        # Assemble final prompt — no unmarked content permitted
        return "\n\n".join(f"{b.marker}\n{b.text}" for b in blocks)

    def validate_order(self, blocks: list[PromptBlock]) -> None:
        """Validate that blocks follow canonical marker order.

        Markers may be omitted but never reordered. This method checks
        that the sequence of markers in the provided blocks is a valid
        subsequence of CANONICAL_ORDER.

        Args:
            blocks: List of PromptBlock objects to validate.

        Raises:
            PromptContractError: If markers are out of canonical order,
                or if an unknown marker is encountered.
        """
        if not blocks:
            return

        # Check for unknown markers
        known_markers = set(self.CANONICAL_ORDER)
        for block in blocks:
            if block.marker not in known_markers:
                raise PromptContractError(
                    f"Unknown marker '{block.marker}' — unmarked content is not "
                    f"permitted. Known markers: {self.CANONICAL_ORDER}"
                )

        # Verify canonical subsequence ordering
        canonical_indices = {marker: idx for idx, marker in enumerate(self.CANONICAL_ORDER)}

        prev_index = -1
        prev_marker = None
        for block in blocks:
            current_index = canonical_indices[block.marker]
            if current_index <= prev_index:
                raise PromptContractError(
                    f"Marker order violation: '{block.marker}' (position "
                    f"{current_index}) appears after '{prev_marker}' (position "
                    f"{prev_index}). Canonical order: {self.CANONICAL_ORDER}"
                )
            prev_index = current_index
            prev_marker = block.marker

    def validate_budgets(self, blocks: list[PromptBlock]) -> None:
        """Enforce token budget ceilings on all blocks.

        Blocks exceeding their max_tokens ceiling are truncated in place.
        This mutates the blocks list by replacing over-budget blocks with
        truncated versions.

        Note: PromptBlock is frozen, so we replace elements in the list
        rather than mutating them.

        Args:
            blocks: List of PromptBlock objects to validate and truncate.
        """
        for i, block in enumerate(blocks):
            token_count = estimate_tokens(block.text)
            if token_count > block.max_tokens:
                truncated_text = truncate_to_budget(block.text, block.max_tokens)
                blocks[i] = PromptBlock(
                    marker=block.marker,
                    text=truncated_text,
                    max_tokens=block.max_tokens,
                )

    def _format_mode(self, policy: BeatModePolicy) -> str:
        """Format the [MODE] block content from a BeatModePolicy.

        Produces a concise mode descriptor with relevant policy settings.
        """
        lines = [f"Mode: {policy.mode.value.upper()}"]

        if policy.quality_threshold is not None:
            lines.append(f"Quality threshold: {policy.quality_threshold}/18")

        if policy.refinement_allowed:
            lines.append("Refinement: enabled")
        else:
            lines.append("Refinement: disabled")

        if policy.move_override:
            lines.append(f"Move override: {policy.move_override}")

        lines.append(f"Word count: {policy.word_count_min}-{policy.word_count_max}")

        return "\n".join(lines)
