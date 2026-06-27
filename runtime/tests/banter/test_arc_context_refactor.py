"""Tests for refactored ArcContextBuilder (Task 3.1).

Validates:
- get_pressure() never returns the theme title
- Fallback uses the Section 3.3 format
- format_injection() uses Section 3.2 injection format
- Hard ban: no delivered line contains the raw title
"""

import pytest
from banter.arc_context import ArcContextBuilder, _derive_theme_noun, _normalize_theme


class TestArcContextRefactor:
    """Unit tests for the ArcContextBuilder refactor."""

    ALL_KNOWN_THEMES = [
        "scarcity_vs_flow",
        "market_cruelty",
        "betrayal_and_return",
        "power_and_legitimacy",
        "sacrifice_and_cost",
        "truth_and_performance",
        "survival_and_meaning",
    ]

    def setup_method(self):
        self.builder = ArcContextBuilder()

    # --- Sub-task 1: get_pressure never returns raw title ---

    @pytest.mark.parametrize(
        "theme",
        [
            "scarcity_vs_flow",
            "market_cruelty",
            "betrayal_and_return",
            "power_and_legitimacy",
            "sacrifice_and_cost",
            "truth_and_performance",
            "survival_and_meaning",
        ],
    )
    def test_known_theme_pressure_never_contains_title(self, theme):
        """Known themes: pressure text must not contain the readable theme title."""
        pressure = self.builder.get_pressure(theme)
        readable = theme.replace("_", " ")
        assert readable not in pressure.pressure.lower(), (
            f"Theme title '{readable}' leaked into pressure: {pressure.pressure}"
        )
        assert readable not in pressure.world_stakes.lower(), (
            f"Theme title '{readable}' leaked into world_stakes: {pressure.world_stakes}"
        )

    @pytest.mark.parametrize(
        "theme",
        [
            "dominance_and_submission",
            "Scarcity of Truth",
            "hidden-cost-ecology",
            "love and war",
            "the_meaning_of_silence",
            "absolute_power_corrupts",
        ],
    )
    def test_unknown_theme_pressure_never_contains_title(self, theme):
        """Unknown themes (fallback): pressure must not contain the readable theme title."""
        pressure = self.builder.get_pressure(theme)
        readable = _normalize_theme(theme).replace("_", " ")
        assert readable not in pressure.pressure.lower(), (
            f"Theme title '{readable}' leaked into pressure: {pressure.pressure}"
        )
        assert readable not in pressure.world_stakes.lower(), (
            f"Theme title '{readable}' leaked into world_stakes: {pressure.world_stakes}"
        )

    # --- Sub-task 2: Fallback uses Section 3.3 format ---

    def test_fallback_pressure_format(self):
        """Fallback must use Section 3.3 required format."""
        theme = "some_exotic_unknown_theme"
        pressure = self.builder.get_pressure(theme)
        # Should match: "how does {theme_noun} expose who is truly willing to pay the hidden cost in this ecology?"
        assert (
            "expose who is truly willing to pay the hidden cost in this ecology"
            in pressure.pressure
        )
        assert pressure.pressure.startswith("how does ")

    def test_fallback_world_stakes_format(self):
        """Fallback world_stakes must match Section 3.3."""
        theme = "some_exotic_unknown_theme"
        pressure = self.builder.get_pressure(theme)
        assert pressure.world_stakes == (
            "The Swarm is watching who flinches first. Patrons bet on conviction, not performance."
        )

    def test_fallback_uses_derived_noun_not_full_title(self):
        """Fallback theme_noun must be a derived concept, not the full title."""
        theme = "dominance_and_submission"
        noun = _derive_theme_noun(theme)
        readable = _normalize_theme(theme).replace("_", " ")
        # The noun must NOT be the full title
        assert noun != readable, (
            f"theme_noun '{noun}' is the full title — must be a paraphrased derivative"
        )

    # --- Sub-task 3: format_injection uses Section 3.2 format ---

    def test_format_injection_structure(self):
        """format_injection must match Section 3.2 injection format."""
        block = self.builder.format_injection("scarcity_vs_flow")
        lines = block.split("\n")
        assert lines[0] == "[ARC]"
        assert lines[1].startswith("The question burning through the Veil right now: ")
        assert lines[2].startswith("The cosmic stakes: ")
        assert lines[3] == "Take a position on this tension, directly or indirectly, in every line."
        assert lines[4] == "Do not quote or name this question. Embody it."

    def test_format_injection_no_title_leak(self):
        """format_injection must not contain the raw theme title."""
        for theme in self.ALL_KNOWN_THEMES:
            block = self.builder.format_injection(theme)
            readable = theme.replace("_", " ")
            assert readable not in block.lower(), (
                f"Theme title '{readable}' leaked into [ARC] block"
            )

    def test_format_injection_unknown_theme_no_leak(self):
        """format_injection for unknown themes must not contain the title."""
        theme = "dominance_and_submission"
        block = self.builder.format_injection(theme)
        readable = _normalize_theme(theme).replace("_", " ")
        assert readable not in block.lower()
        assert "[ARC]" in block
        assert "Embody it" in block

    # --- theme_noun derivation ---

    def test_derive_theme_noun_single_word_themes(self):
        """Single word themes produce a paraphrase to avoid leaking the title."""
        # Unknown single-word themes should use generic paraphrase
        noun = _derive_theme_noun("scarcity")
        assert noun == "this tension"

        noun = _derive_theme_noun("betrayal")
        assert noun == "this tension"

        # Known multi-word theme key (from noun table) uses curated noun
        noun = _derive_theme_noun("scarcity_vs_flow")
        assert noun == "scarcity"  # This is in the noun table

    def test_derive_theme_noun_multi_word_extracts_first_meaningful(self):
        """Multi-word unknown themes extract first meaningful word."""
        noun = _derive_theme_noun("absolute_power_corrupts")
        # Should be a single word like "absolute" not the full title
        full_title = "absolute power corrupts"
        assert noun != full_title
        assert " " not in noun or len(noun.split()) < len(full_title.split())

    def test_derive_theme_noun_single_word_unknown_never_leaks(self):
        """Single-word unknown themes: noun must not equal the theme title."""
        for theme in ["truth", "chaos", "faith", "greed", "fear"]:
            noun = _derive_theme_noun(theme)
            assert noun != theme, f"Single-word theme '{theme}' leaked as noun"
            # The pressure should not contain the theme title
            builder = ArcContextBuilder()
            pressure = builder.get_pressure(theme)
            assert theme not in pressure.pressure.lower(), (
                f"Theme '{theme}' leaked into fallback pressure"
            )

    # --- Input format normalization ---

    @pytest.mark.parametrize(
        "variant,expected_key",
        [
            ("Scarcity vs Flow", "scarcity_vs_flow"),
            ("scarcity-vs-flow", "scarcity_vs_flow"),
            ("MARKET_CRUELTY", "market_cruelty"),
            ("  betrayal_and_return  ", "betrayal_and_return"),
        ],
    )
    def test_theme_normalization(self, variant, expected_key):
        """Various theme input formats should normalize to the same key."""
        assert _normalize_theme(variant) == expected_key

    @pytest.mark.parametrize(
        "variant",
        [
            "Scarcity vs Flow",
            "scarcity-vs-flow",
            "SCARCITY_VS_FLOW",
            "  scarcity_vs_flow  ",
        ],
    )
    def test_known_theme_variants_resolve_correctly(self, variant):
        """All format variants of known themes should get the curated pressure."""
        pressure = self.builder.get_pressure(variant)
        expected = self.builder.get_pressure("scarcity_vs_flow")
        assert pressure == expected
