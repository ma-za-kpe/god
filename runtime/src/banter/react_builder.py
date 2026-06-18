"""ReactBlockBuilder — forced response block assembly for pair-filtered context.

Implements Section 4 of the contract: every opponent beat must be causally
answered. The Elder may ignore the topic but cannot ignore the prior line.

This module produces the [REACT] block text using the Section 4.3 injection
format, or returns None when the opponent has no prior line.

The string "Recent exchange:" is explicitly banned from output.

Requirements: 4.1, 4.2, 4.3, 4.4
"""

from __future__ import annotations

from typing import Any


class ReactBlockBuilder:
    """Builds the [REACT] block for forced response directives.

    The [REACT] block ensures every opponent beat is causally answered.
    It extracts pair-filtered context (last 4 relevant entries) and
    formats the injection using the Section 4.3 format.

    Returns None if the opponent has no prior line in the conversation
    thread, which signals to the SacredPromptBuilder to omit [REACT].

    Contract guarantees:
    - Returns formatted text whenever opponent has a prior line.
    - Returns None when opponent has no prior line.
    - Never produces the string "Recent exchange:" in output.
    - Uses only the Section 4.3 injection format.
    """

    def build(
        self,
        conv_thread: list[dict[str, Any]],
        elder: str,
        opponent: str,
    ) -> str | None:
        """Build the [REACT] block text from conversation context.

        Args:
            conv_thread: Full conversation thread. Each entry is a dict
                with at least "speaker" and "content" keys. May also
                contain "target" for directed speech.
            elder: The name of the Elder generating a response.
            opponent: The name of the opponent Elder being responded to.

        Returns:
            The formatted [REACT] block text (without the [REACT] marker
            itself, as the SacredPromptBuilder adds it), or None if the
            opponent has no prior line.
        """
        # Find the last opponent line
        last_opponent_line = self._find_last_opponent_line(conv_thread, opponent)

        if last_opponent_line is None:
            return None

        # Extract pair-filtered context (Section 4.2)
        pair_thread = self._extract_pair_thread(conv_thread, elder, opponent)

        # Format the exchange history
        pair_thread_formatted = self._format_pair_thread(pair_thread)

        # Assemble using Section 4.3 injection format
        react_text = self._format_react_block(
            opponent=opponent,
            last_opponent_line=last_opponent_line,
            pair_thread_formatted=pair_thread_formatted,
        )

        return react_text

    def _find_last_opponent_line(
        self,
        conv_thread: list[dict[str, Any]],
        opponent: str,
    ) -> str | None:
        """Find the most recent line spoken by the opponent.

        Searches backward through the conversation thread for the last
        entry where the speaker is the opponent.

        Returns:
            The content of the last opponent line, or None if not found.
        """
        for entry in reversed(conv_thread):
            if entry.get("speaker") == opponent:
                content = entry.get("content", "")
                if content:
                    return content
        return None

    def _extract_pair_thread(
        self,
        conv_thread: list[dict[str, Any]],
        elder: str,
        opponent: str,
    ) -> list[dict[str, Any]]:
        """Extract pair-filtered context per Section 4.2.

        Filters the conversation thread to entries where either the
        speaker or target is one of the pair (elder, opponent), then
        takes the last 4 entries.

        The filter logic from Section 4.2:
            pair_thread = [
                t for t in conv_thread
                if t.get("speaker") in (elder, opponent)
                or t.get("target") in (elder, opponent)
            ][-4:]
        """
        pair_thread = [
            t
            for t in conv_thread
            if t.get("speaker") in (elder, opponent)
            or t.get("target") in (elder, opponent)
        ][-4:]

        return pair_thread

    def _format_pair_thread(
        self,
        pair_thread: list[dict[str, Any]],
    ) -> str:
        """Format the pair thread entries for inclusion in the block.

        Each entry is formatted as:
            {speaker}: "{content}"

        Returns an empty string if the pair thread is empty.
        """
        if not pair_thread:
            return ""

        lines = []
        for entry in pair_thread:
            speaker = entry.get("speaker", "unknown")
            content = entry.get("content", "")
            lines.append(f'{speaker}: "{content}"')

        return "\n".join(lines)

    def _format_react_block(
        self,
        opponent: str,
        last_opponent_line: str,
        pair_thread_formatted: str,
    ) -> str:
        """Assemble the [REACT] block using Section 4.3 injection format.

        The output does NOT include the [REACT] marker itself — that is
        added by the SacredPromptBuilder when assembling PromptBlock objects.

        The string "Recent exchange:" is explicitly never used.
        """
        block = (
            f'The last thing {opponent} said was: "{last_opponent_line}"\n'
            "\n"
            "You are responding directly to this. You must do one of:\n"
            "- Escalate it.\n"
            "- Undercut it.\n"
            "- Twist it.\n"
            "- Concede one inch, then take three back.\n"
            "\n"
            "You cannot ignore the prior line. Reference it directly or by implication.\n"
            "\n"
            "[EXCHANGE SO FAR]\n"
            f"{pair_thread_formatted}"
        )

        return block
