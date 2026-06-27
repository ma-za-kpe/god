"""Unit tests for ReactBlockBuilder — forced response block assembly.

Tests the [REACT] block biconditional: present when opponent has prior line,
absent when not. Also validates pair-filtered context extraction and the
Section 4.3 injection format.

Requirements: 4.1, 4.2, 4.3, 4.4
"""

import os
import sys

_src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
for _p in (_src_path, "/app/src"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest

from banter.react_builder import ReactBlockBuilder


@pytest.fixture
def builder() -> ReactBlockBuilder:
    return ReactBlockBuilder()


class TestReactBlockPresence:
    """[REACT] appears when opponent has prior line, None otherwise."""

    def test_returns_none_when_empty_thread(self, builder: ReactBlockBuilder):
        result = builder.build(conv_thread=[], elder="prophet", opponent="keeper")
        assert result is None

    def test_returns_none_when_opponent_has_no_line(self, builder: ReactBlockBuilder):
        thread = [
            {"speaker": "prophet", "content": "The ledger remembers."},
            {"speaker": "trickster", "content": "Does it though?"},
        ]
        result = builder.build(conv_thread=thread, elder="prophet", opponent="keeper")
        assert result is None

    def test_returns_text_when_opponent_has_line(self, builder: ReactBlockBuilder):
        thread = [
            {"speaker": "keeper", "content": "Nothing free stays free."},
            {"speaker": "prophet", "content": "The ledger remembers."},
        ]
        result = builder.build(conv_thread=thread, elder="prophet", opponent="keeper")
        assert result is not None
        assert isinstance(result, str)
        assert len(result) > 0

    def test_returns_none_when_opponent_line_is_empty(self, builder: ReactBlockBuilder):
        thread = [
            {"speaker": "keeper", "content": ""},
        ]
        result = builder.build(conv_thread=thread, elder="prophet", opponent="keeper")
        assert result is None


class TestReactBlockFormat:
    """Validates the Section 4.3 injection format."""

    def test_contains_last_opponent_line(self, builder: ReactBlockBuilder):
        thread = [
            {"speaker": "keeper", "content": "Nothing free stays free."},
        ]
        result = builder.build(conv_thread=thread, elder="prophet", opponent="keeper")
        assert result is not None
        assert 'The last thing keeper said was: "Nothing free stays free."' in result

    def test_contains_response_directives(self, builder: ReactBlockBuilder):
        thread = [
            {"speaker": "keeper", "content": "Nothing free stays free."},
        ]
        result = builder.build(conv_thread=thread, elder="prophet", opponent="keeper")
        assert result is not None
        assert "You are responding directly to this." in result
        assert "- Escalate it." in result
        assert "- Undercut it." in result
        assert "- Twist it." in result
        assert "- Concede one inch, then take three back." in result

    def test_contains_cannot_ignore_directive(self, builder: ReactBlockBuilder):
        thread = [
            {"speaker": "keeper", "content": "Nothing free stays free."},
        ]
        result = builder.build(conv_thread=thread, elder="prophet", opponent="keeper")
        assert result is not None
        assert "You cannot ignore the prior line." in result

    def test_contains_exchange_so_far_header(self, builder: ReactBlockBuilder):
        thread = [
            {"speaker": "keeper", "content": "Nothing free stays free."},
        ]
        result = builder.build(conv_thread=thread, elder="prophet", opponent="keeper")
        assert result is not None
        assert "[EXCHANGE SO FAR]" in result

    def test_never_contains_recent_exchange(self, builder: ReactBlockBuilder):
        """Contract: "Recent exchange:" must never appear."""
        thread = [
            {"speaker": "keeper", "content": "Nothing free stays free."},
            {"speaker": "prophet", "content": "The ledger remembers."},
            {"speaker": "keeper", "content": "That's exactly why I hold."},
        ]
        result = builder.build(conv_thread=thread, elder="prophet", opponent="keeper")
        assert result is not None
        assert "Recent exchange:" not in result


class TestPairFilteredContext:
    """Validates pair-filtered context extraction (Section 4.2)."""

    def test_filters_to_pair_relevant_entries(self, builder: ReactBlockBuilder):
        thread = [
            {"speaker": "prophet", "content": "Line 1"},
            {"speaker": "trickster", "content": "Irrelevant line"},
            {"speaker": "keeper", "content": "Line 2"},
            {"speaker": "sovereign", "content": "Another irrelevant"},
            {"speaker": "prophet", "content": "Line 3"},
            {"speaker": "keeper", "content": "Line 4"},
        ]
        result = builder.build(conv_thread=thread, elder="prophet", opponent="keeper")
        assert result is not None
        # Only prophet and keeper lines should appear in exchange
        assert "trickster" not in result.split("[EXCHANGE SO FAR]")[1]
        assert "sovereign" not in result.split("[EXCHANGE SO FAR]")[1]

    def test_limits_to_last_4_entries(self, builder: ReactBlockBuilder):
        thread = [
            {"speaker": "prophet", "content": "Old line 1"},
            {"speaker": "keeper", "content": "Old line 2"},
            {"speaker": "prophet", "content": "Old line 3"},
            {"speaker": "keeper", "content": "Mid line 4"},
            {"speaker": "prophet", "content": "Recent line 5"},
            {"speaker": "keeper", "content": "Recent line 6"},
            {"speaker": "prophet", "content": "Recent line 7"},
            {"speaker": "keeper", "content": "Latest line 8"},
        ]
        result = builder.build(conv_thread=thread, elder="prophet", opponent="keeper")
        assert result is not None
        exchange_section = result.split("[EXCHANGE SO FAR]")[1]
        # Should contain last 4 pair-relevant entries
        assert "Recent line 5" in exchange_section
        assert "Recent line 6" in exchange_section
        assert "Recent line 7" in exchange_section
        assert "Latest line 8" in exchange_section
        # Should NOT contain older entries
        assert "Old line 1" not in exchange_section
        assert "Old line 2" not in exchange_section
        assert "Old line 3" not in exchange_section
        assert "Mid line 4" not in exchange_section

    def test_includes_targeted_entries(self, builder: ReactBlockBuilder):
        """Entries where target is one of the pair should be included."""
        thread = [
            {"speaker": "trickster", "target": "prophet", "content": "Directed at prophet"},
            {"speaker": "keeper", "content": "Keeper speaks"},
            {"speaker": "prophet", "content": "Prophet responds"},
        ]
        result = builder.build(conv_thread=thread, elder="prophet", opponent="keeper")
        assert result is not None
        exchange_section = result.split("[EXCHANGE SO FAR]")[1]
        # trickster's line targeted at prophet should be included
        assert "Directed at prophet" in exchange_section

    def test_uses_last_opponent_line_not_first(self, builder: ReactBlockBuilder):
        """Should use the LAST opponent line, not the first."""
        thread = [
            {"speaker": "keeper", "content": "First thing I said."},
            {"speaker": "prophet", "content": "My response."},
            {"speaker": "keeper", "content": "The actual last thing."},
        ]
        result = builder.build(conv_thread=thread, elder="prophet", opponent="keeper")
        assert result is not None
        assert 'The last thing keeper said was: "The actual last thing."' in result

    def test_formats_pair_thread_entries_correctly(self, builder: ReactBlockBuilder):
        thread = [
            {"speaker": "keeper", "content": "Nothing free."},
            {"speaker": "prophet", "content": "The ledger knows."},
        ]
        result = builder.build(conv_thread=thread, elder="prophet", opponent="keeper")
        assert result is not None
        exchange_section = result.split("[EXCHANGE SO FAR]")[1]
        assert 'keeper: "Nothing free."' in exchange_section
        assert 'prophet: "The ledger knows."' in exchange_section


class TestEdgeCases:
    """Edge cases for ReactBlockBuilder."""

    def test_single_opponent_line_only(self, builder: ReactBlockBuilder):
        thread = [
            {"speaker": "keeper", "content": "Just me."},
        ]
        result = builder.build(conv_thread=thread, elder="prophet", opponent="keeper")
        assert result is not None
        assert 'The last thing keeper said was: "Just me."' in result

    def test_opponent_same_as_elder_returns_none(self, builder: ReactBlockBuilder):
        """Edge case: if elder == opponent, still returns text if opponent spoke."""
        thread = [
            {"speaker": "prophet", "content": "Talking to myself."},
        ]
        # This is a degenerate case but should not crash
        result = builder.build(conv_thread=thread, elder="prophet", opponent="prophet")
        assert result is not None

    def test_thread_with_missing_speaker_key(self, builder: ReactBlockBuilder):
        """Entries without speaker key are handled gracefully."""
        thread = [
            {"content": "No speaker here"},
            {"speaker": "keeper", "content": "Valid entry."},
        ]
        result = builder.build(conv_thread=thread, elder="prophet", opponent="keeper")
        assert result is not None
        assert 'The last thing keeper said was: "Valid entry."' in result

    def test_thread_with_missing_content_key(self, builder: ReactBlockBuilder):
        """Entries without content key are handled gracefully."""
        thread = [
            {"speaker": "keeper"},  # no content
            {"speaker": "keeper", "content": "Has content."},
        ]
        result = builder.build(conv_thread=thread, elder="prophet", opponent="keeper")
        assert result is not None
        assert 'The last thing keeper said was: "Has content."' in result
