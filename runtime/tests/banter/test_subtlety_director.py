"""Unit tests for SubtletyDirector — Requirements 6.1-6.6.

Tests cover:
- 6.1: Activation logic (tension 4-8, DEFLECT/QUESTION moves, sore spot)
- 6.2: Deactivation overrides (tension < 2, CONCEDE, no relationship history)
- 6.3: Technique variety constraint (same technique <= 2 in 5 consecutive uses per Elder)
- 6.4: Token budget enforcement (<= 150 tokens)
- 6.5: Subtext depth scoring (0-3 integer)
- 6.6: Exception safety — generate_subtext_instruction returns None on error, never raises
"""

import os
import sys
from collections import Counter

_src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
for _p in (_src_path, "/app/src"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest
from hypothesis import given
from hypothesis import strategies as st

from banter.subtlety_director import SubtletyDirector, _estimate_token_count
from banter.soul_types import SoulEngineConfig, SoreSpot, SubtextInstruction


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def config() -> SoulEngineConfig:
    return SoulEngineConfig()


@pytest.fixture
def director(config: SoulEngineConfig) -> SubtletyDirector:
    return SubtletyDirector(config, seed=42)


@pytest.fixture
def sore_spot() -> SoreSpot:
    return SoreSpot(
        elder_name="keeper",
        topic="legacy",
        trigger_phrase="what you built",
        tension_delta=2,
    )


def _fresh_director(seed: int = 0) -> SubtletyDirector:
    return SubtletyDirector(SoulEngineConfig(), seed=seed)


# ---------------------------------------------------------------------------
# 6.2: should_inject_subtext — deactivation overrides
# ---------------------------------------------------------------------------


class TestDeactivationOverrides:
    """Requirements 6.2: Hard blocks always prevent activation."""

    def test_tension_below_2_blocks_all(self, director: SubtletyDirector) -> None:
        for tension in [0, 1]:
            assert (
                director.should_inject_subtext(
                    tension=tension, move="DEFLECT", has_sore_spot=True, has_history=True
                )
                is False
            ), f"Expected False for tension={tension}"

    def test_concede_move_is_hard_block(self, director: SubtletyDirector) -> None:
        for tension in [4, 5, 6, 7, 8]:
            assert (
                director.should_inject_subtext(
                    tension=tension, move="CONCEDE", has_sore_spot=True, has_history=True
                )
                is False
            ), f"Expected False for CONCEDE at tension={tension}"

    def test_no_history_is_hard_block(self, director: SubtletyDirector) -> None:
        for tension in [4, 5, 6]:
            assert (
                director.should_inject_subtext(
                    tension=tension, move="DEFLECT", has_sore_spot=True, has_history=False
                )
                is False
            )

    def test_low_tension_overrides_trigger_move(self, director: SubtletyDirector) -> None:
        assert director.should_inject_subtext(1, "DEFLECT", True, True) is False

    def test_concede_overrides_sore_spot_and_tension(self, director: SubtletyDirector) -> None:
        assert director.should_inject_subtext(6, "CONCEDE", True, True) is False

    def test_no_history_overrides_all_activation(self, director: SubtletyDirector) -> None:
        assert director.should_inject_subtext(5, "QUESTION", True, False) is False


# ---------------------------------------------------------------------------
# 6.1: should_inject_subtext — activation conditions
# ---------------------------------------------------------------------------


class TestActivationConditions:
    """Requirements 6.1: At least one activation condition required."""

    def test_tension_4_to_8_inclusive_activates(self, director: SubtletyDirector) -> None:
        for tension in [4, 5, 6, 7, 8]:
            result = director.should_inject_subtext(
                tension=tension, move="COUNTER", has_sore_spot=False, has_history=True
            )
            assert result is True, f"Expected True for tension={tension}"

    def test_deflect_move_activates(self, director: SubtletyDirector) -> None:
        assert (
            director.should_inject_subtext(
                tension=3, move="DEFLECT", has_sore_spot=False, has_history=True
            )
            is True
        )

    def test_question_move_activates(self, director: SubtletyDirector) -> None:
        assert (
            director.should_inject_subtext(
                tension=3, move="QUESTION", has_sore_spot=False, has_history=True
            )
            is True
        )

    def test_sore_spot_activates(self, director: SubtletyDirector) -> None:
        assert (
            director.should_inject_subtext(
                tension=3, move="COUNTER", has_sore_spot=True, has_history=True
            )
            is True
        )

    def test_no_activation_condition_returns_false(self, director: SubtletyDirector) -> None:
        """tension=3, non-triggering move, no sore spot — all activation conditions false."""
        assert (
            director.should_inject_subtext(
                tension=3, move="COUNTER", has_sore_spot=False, has_history=True
            )
            is False
        )

    def test_boundary_tension_4_inclusive(self, director: SubtletyDirector) -> None:
        assert director.should_inject_subtext(4, "COUNTER", False, True) is True

    def test_boundary_tension_8_inclusive(self, director: SubtletyDirector) -> None:
        assert director.should_inject_subtext(8, "COUNTER", False, True) is True

    def test_tension_3_below_range(self, director: SubtletyDirector) -> None:
        assert director.should_inject_subtext(3, "COUNTER", False, True) is False

    def test_tension_9_above_range_with_neutral_move(self, director: SubtletyDirector) -> None:
        """tension > 8, COUNTER move, no sore spot — no activation condition met → False."""
        assert director.should_inject_subtext(9, "COUNTER", False, True) is False


# ---------------------------------------------------------------------------
# 6.1: should_inject_subtext — high tension (> 8) 20% rate reduction
# ---------------------------------------------------------------------------


class TestHighTensionRateReduction:
    """Requirements 6.1 / 6.3: tension > 8 reduces probability to 20%."""

    def test_high_tension_produces_mixed_results(self) -> None:
        d = SubtletyDirector(SoulEngineConfig(), seed=0)
        results = [d.should_inject_subtext(9, "DEFLECT", False, True) for _ in range(100)]
        assert any(results), "Expected some True at 20% rate"
        assert not all(results), "Expected some False at 20% rate"

    def test_rate_approximately_20pct(self) -> None:
        d = SubtletyDirector(SoulEngineConfig(), seed=1234)
        n = 1000
        count = sum(d.should_inject_subtext(9, "DEFLECT", True, True) for _ in range(n))
        rate = count / n
        assert 0.10 <= rate <= 0.30, f"Expected ~20% rate, got {rate:.2%}"

    def test_tension_10_also_uses_20pct_rate(self) -> None:
        d = SubtletyDirector(SoulEngineConfig(), seed=7)
        results = [d.should_inject_subtext(10, "QUESTION", True, True) for _ in range(50)]
        assert any(results)
        assert not all(results)

    def test_same_seed_produces_same_sequence(self) -> None:
        d1 = SubtletyDirector(SoulEngineConfig(), seed=99)
        d2 = SubtletyDirector(SoulEngineConfig(), seed=99)
        seq1 = [d1.should_inject_subtext(9, "DEFLECT", True, True) for _ in range(20)]
        seq2 = [d2.should_inject_subtext(9, "DEFLECT", True, True) for _ in range(20)]
        assert seq1 == seq2


# ---------------------------------------------------------------------------
# 6.1 + 6.3: generate_subtext_instruction — basic contract
# ---------------------------------------------------------------------------


class TestGenerateSubtextInstructionBasic:
    """Requirements 6.1, 6.3: generate_subtext_instruction returns valid instructions."""

    def test_returns_subtext_instruction(
        self, director: SubtletyDirector, sore_spot: SoreSpot
    ) -> None:
        result = director.generate_subtext_instruction(
            elder="prophet",
            target="keeper",
            tension=5,
            sore_spot=sore_spot,
            arc_theme="Should the weak be protected?",
        )
        assert isinstance(result, SubtextInstruction)

    def test_all_fields_non_empty(self, director: SubtletyDirector) -> None:
        result = director.generate_subtext_instruction(
            elder="prophet",
            target="keeper",
            tension=5,
            sore_spot=None,
            arc_theme="survival",
        )
        assert result is not None
        assert result.surface_meaning
        assert result.implied_meaning
        assert result.technique
        assert result.context_hint

    def test_technique_is_known(self, director: SubtletyDirector) -> None:
        result = director.generate_subtext_instruction(
            elder="trickster",
            target="sovereign",
            tension=6,
            sore_spot=None,
            arc_theme="power",
        )
        assert result is not None
        assert result.technique in SubtletyDirector.TECHNIQUES

    def test_no_unfilled_placeholders_without_sore_spot(self, director: SubtletyDirector) -> None:
        result = director.generate_subtext_instruction(
            elder="martyr",
            target="herald",
            tension=5,
            sore_spot=None,
            arc_theme="sacrifice",
        )
        assert result is not None
        for field_val in (result.surface_meaning, result.implied_meaning, result.context_hint):
            assert "{" not in field_val, f"Unfilled placeholder in: {field_val!r}"

    def test_no_unfilled_placeholders_with_sore_spot(
        self, director: SubtletyDirector, sore_spot: SoreSpot
    ) -> None:
        result = director.generate_subtext_instruction(
            elder="shadow",
            target="keeper",
            tension=6,
            sore_spot=sore_spot,
            arc_theme="legacy and loss",
        )
        assert result is not None
        for field_val in (result.surface_meaning, result.implied_meaning, result.context_hint):
            assert "{" not in field_val, f"Unfilled placeholder in: {field_val!r}"

    def test_target_placeholder_is_filled(self, director: SubtletyDirector) -> None:
        """The raw {target} placeholder must never appear in generated output."""
        result = director.generate_subtext_instruction(
            elder="prophet",
            target="XenolithTarget",
            tension=5,
            sore_spot=None,
            arc_theme="competition",
        )
        assert result is not None
        full_text = f"{result.surface_meaning} {result.implied_meaning} {result.context_hint}"
        assert "{target}" not in full_text

    def test_arc_theme_appears_in_surface_meaning(self, director: SubtletyDirector) -> None:
        arc = "the nature of scarcity"
        result = director.generate_subtext_instruction(
            elder="hoarder",
            target="builder",
            tension=5,
            sore_spot=None,
            arc_theme=arc,
        )
        assert result is not None
        assert arc in result.surface_meaning

    def test_sore_spot_topic_appears_in_context_hint(
        self, director: SubtletyDirector, sore_spot: SoreSpot
    ) -> None:
        result = director.generate_subtext_instruction(
            elder="prophet",
            target="keeper",
            tension=5,
            sore_spot=sore_spot,
            arc_theme="legacy",
        )
        assert result is not None
        assert sore_spot.topic in result.context_hint


# ---------------------------------------------------------------------------
# 6.3: Technique variety constraint
# ---------------------------------------------------------------------------


class TestTechniqueVariety:
    """Requirements 6.3: same technique <= 2 in any window of 5 consecutive uses per Elder."""

    def test_no_technique_exceeds_twice_in_window_of_five(self) -> None:
        d = _fresh_director(seed=0)
        techniques: list[str] = []
        for _ in range(30):
            result = d.generate_subtext_instruction(
                elder="prophet",
                target="keeper",
                tension=5,
                sore_spot=None,
                arc_theme="dominance",
            )
            if result:
                techniques.append(result.technique)

        for i in range(len(techniques) - 4):
            window = techniques[i : i + 5]
            counts = Counter(window)
            for technique, count in counts.items():
                assert count <= 2, (
                    f"Technique '{technique}' appeared {count} times in window {window} "
                    f"starting at index {i}"
                )

    def test_elder_histories_are_independent(self) -> None:
        d = _fresh_director(seed=0)
        for _ in range(10):
            d.generate_subtext_instruction(
                elder="prophet", target="keeper", tension=5, sore_spot=None, arc_theme="power"
            )
        result_b = d.generate_subtext_instruction(
            elder="keeper", target="prophet", tension=5, sore_spot=None, arc_theme="power"
        )
        assert result_b is not None

    def test_select_technique_respects_saturated_window(self) -> None:
        """When 2 techniques each appear twice in the window, remaining 3 are selectable."""
        d = _fresh_director(seed=42)
        h = d._get_technique_history("test_elder")
        h.extend(
            [
                "loaded_question",
                "loaded_question",
                "double_entendre",
                "double_entendre",
                "callback_inversion",
            ]
        )
        # loaded_question(2) and double_entendre(2) are blocked; others available
        technique = d._select_technique("test_elder")
        assert technique is not None
        assert technique in ("callback_inversion", "strategic_omission", "damning_praise")

    def test_technique_history_per_elder_is_deque_maxlen_5(self) -> None:
        d = _fresh_director(seed=0)
        h = d._get_technique_history("zephyr")
        # maxlen=5 so oldest entry is evicted when 6th item appended
        h.extend(["a", "b", "c", "d", "e"])
        h.append("f")
        assert list(h) == ["b", "c", "d", "e", "f"]
        assert len(h) == 5

    def test_variety_rotates_across_many_calls(self) -> None:
        d = _fresh_director(seed=77)
        seen = set()
        for _ in range(50):
            result = d.generate_subtext_instruction(
                elder="trickster",
                target="sovereign",
                tension=6,
                sore_spot=None,
                arc_theme="manipulation",
            )
            if result:
                seen.add(result.technique)
        assert len(seen) >= 3, "Expected at least 3 distinct techniques used over 50 calls"


# ---------------------------------------------------------------------------
# 6.4: Token budget enforcement
# ---------------------------------------------------------------------------


class TestTokenBudget:
    """Requirements 6.4: Output <= subtlety_token_budget tokens."""

    def test_default_budget_respected(self) -> None:
        budget = 150
        config = SoulEngineConfig(subtlety_token_budget=budget)
        d = SubtletyDirector(config, seed=0)
        result = d.generate_subtext_instruction(
            elder="prophet", target="keeper", tension=5, sore_spot=None, arc_theme="survival"
        )
        assert result is not None
        total = (
            f"{result.surface_meaning} {result.implied_meaning} "
            f"{result.technique} {result.context_hint}"
        )
        assert _estimate_token_count(total) <= budget

    def test_generous_budget_always_returns_instruction(self) -> None:
        config = SoulEngineConfig(subtlety_token_budget=500)
        d = SubtletyDirector(config, seed=1)
        result = d.generate_subtext_instruction(
            elder="martyr", target="shadow", tension=5, sore_spot=None, arc_theme="loss"
        )
        assert result is not None

    def test_very_tight_budget_does_not_raise(self) -> None:
        config = SoulEngineConfig(subtlety_token_budget=10)
        d = SubtletyDirector(config, seed=0)
        try:
            result = d.generate_subtext_instruction(
                elder="herald", target="keeper", tension=6, sore_spot=None, arc_theme="call"
            )
            # May be None or trimmed — must not raise
            assert result is None or isinstance(result, SubtextInstruction)
        except Exception as exc:
            pytest.fail(f"generate_subtext_instruction raised with tight budget: {exc}")

    def test_trim_to_budget_produces_shorter_instruction(self) -> None:
        config = SoulEngineConfig(subtlety_token_budget=150)
        d = SubtletyDirector(config, seed=0)
        full = SubtextInstruction(
            surface_meaning="word " * 40,
            implied_meaning="word " * 40,
            technique="loaded_question",
            context_hint="word " * 40,
        )
        trimmed = d._trim_to_budget(full)
        total = (
            f"{trimmed.surface_meaning} {trimmed.implied_meaning} "
            f"{trimmed.technique} {trimmed.context_hint}"
        )
        assert _estimate_token_count(total) <= 150


# ---------------------------------------------------------------------------
# 6.5: score_subtext_depth
# ---------------------------------------------------------------------------


class TestScoreSubtextDepth:
    """Requirements 6.5: score_subtext_depth returns int in [0, 3]."""

    @staticmethod
    def _instruction(technique: str = "loaded_question") -> SubtextInstruction:
        return SubtextInstruction(
            surface_meaning="Ask about power as if genuinely curious.",
            implied_meaning="The question presumes keeper guilt or weakness.",
            technique=technique,
            context_hint="Brush against their sensitivity without naming it.",
        )

    def test_empty_candidate_scores_zero(self, director: SubtletyDirector) -> None:
        assert director.score_subtext_depth("", self._instruction()) == 0

    def test_whitespace_only_scores_zero(self, director: SubtletyDirector) -> None:
        assert director.score_subtext_depth("   ", self._instruction()) == 0

    def test_score_always_in_0_to_3(self, director: SubtletyDirector) -> None:
        candidates = [
            "",
            "Simple.",
            "The question about power reveals everything.",
            "Ask about power? The question presumes keeper's weakness.",
        ]
        for c in candidates:
            score = director.score_subtext_depth(c, self._instruction())
            assert 0 <= score <= 3, f"Score {score} out of range for {c!r}"

    def test_max_score_clamped_at_3(self, director: SubtletyDirector) -> None:
        instr = SubtextInstruction(
            surface_meaning="ask question power",
            implied_meaning="question presumes guilt weakness",
            technique="loaded_question",
            context_hint="hint",
        )
        verbose = "Ask about the power question presumes guilt and weakness — curious, no?"
        assert director.score_subtext_depth(verbose, instr) <= 3

    def test_rich_candidate_scores_higher_than_generic(self, director: SubtletyDirector) -> None:
        instr = self._instruction("loaded_question")
        # Contains question mark (technique) + surface word (ask) + implied word (question/presumes)
        rich = "Do you ask about power? The question presumes your weakness."
        weak = "Nice weather today."
        assert director.score_subtext_depth(rich, instr) >= director.score_subtext_depth(
            weak, instr
        )

    def test_loaded_question_detected_by_question_mark(self, director: SubtletyDirector) -> None:
        instr = self._instruction("loaded_question")
        with_q = director.score_subtext_depth("Is it true that you lied?", instr)
        without_q = director.score_subtext_depth("You lied to everyone", instr)
        # question mark contributes the technique marker point
        assert with_q >= without_q

    def test_damning_praise_detected_by_praise_word(self, director: SubtletyDirector) -> None:
        instr = self._instruction("damning_praise")
        candidate = "I truly admire your dedication to this position."
        score = director.score_subtext_depth(candidate, instr)
        assert score >= 1

    def test_damning_praise_detected_by_undermine_word(self, director: SubtletyDirector) -> None:
        instr = self._instruction("damning_praise")
        candidate = "You are consistent, however that consistency blinds you."
        assert director.score_subtext_depth(candidate, instr) >= 1

    def test_callback_inversion_detected_by_echo_marker(self, director: SubtletyDirector) -> None:
        instr = self._instruction("callback_inversion")
        candidate = "You said that yourself — remember? Your words condemn you now."
        assert director.score_subtext_depth(candidate, instr) >= 1

    def test_double_entendre_detected_by_quotation_mark(self, director: SubtletyDirector) -> None:
        instr = self._instruction("double_entendre")
        candidate = 'He spoke "plainly" — sure he did.'
        assert director.score_subtext_depth(candidate, instr) >= 1

    def test_strategic_omission_detected_by_short_candidate(
        self, director: SubtletyDirector
    ) -> None:
        instr = self._instruction("strategic_omission")
        short_candidate = "Interesting."  # < 10 words
        assert director.score_subtext_depth(short_candidate, instr) >= 1

    def test_strategic_omission_detected_by_ellipsis(self, director: SubtletyDirector) -> None:
        instr = self._instruction("strategic_omission")
        candidate = "The facts are clear... or most of them."
        assert director.score_subtext_depth(candidate, instr) >= 1

    def test_all_three_points_achievable(self, director: SubtletyDirector) -> None:
        """Score 3: surface overlap + implied overlap + technique marker."""
        instr = SubtextInstruction(
            surface_meaning="Ask about legacy as if genuinely curious.",
            implied_meaning="The question presumes target guilt or weakness.",
            technique="loaded_question",
            context_hint="Let the subtext brush against sensitivity.",
        )
        # "ask" → surface overlap; "question" + "presumes" → implied overlap; "?" → technique
        candidate = (
            "I simply ask about legacy — but the question of your guilt remains, does it not?"
        )
        assert director.score_subtext_depth(candidate, instr) == 3

    def test_empty_instruction_fields_score_zero_or_low(self, director: SubtletyDirector) -> None:
        instr = SubtextInstruction(
            surface_meaning="",
            implied_meaning="",
            technique="loaded_question",
            context_hint="",
        )
        score = director.score_subtext_depth("Any candidate text here.", instr)
        # Surface and implied overlap must both be 0 (empty key_words → 0.0 ratio)
        # Technique can still score if candidate has "?"
        assert score <= 1

    def test_estimate_token_count_helper(self) -> None:
        assert _estimate_token_count("") == 0
        # Single word ≈ 1.3 tokens → int(1.3) = 1
        assert _estimate_token_count("word") == 1
        # 10 words → int(10 * 1.3) = 13
        assert _estimate_token_count("a b c d e f g h i j") == 13


# ---------------------------------------------------------------------------
# 6.6: Exception safety and None-return contract
# ---------------------------------------------------------------------------


class TestExceptionSafety:
    """Requirements 6.6: Never raises; returns None gracefully on failure."""

    def test_none_arc_theme_does_not_raise(self) -> None:
        d = _fresh_director()
        try:
            result = d.generate_subtext_instruction(
                elder="prophet",
                target="keeper",
                tension=5,
                sore_spot=None,
                arc_theme=None,  # type: ignore[arg-type]
            )
            assert result is None or isinstance(result, SubtextInstruction)
        except Exception as exc:
            pytest.fail(f"generate_subtext_instruction raised with arc_theme=None: {exc}")

    def test_empty_string_inputs_do_not_raise(self) -> None:
        d = _fresh_director()
        try:
            result = d.generate_subtext_instruction(
                elder="", target="", tension=0, sore_spot=None, arc_theme=""
            )
            assert result is None or isinstance(result, SubtextInstruction)
        except Exception as exc:
            pytest.fail(f"generate_subtext_instruction raised with empty strings: {exc}")

    def test_score_subtext_depth_with_empty_instruction_fields(
        self, director: SubtletyDirector
    ) -> None:
        instr = SubtextInstruction(
            surface_meaning="",
            implied_meaning="",
            technique="loaded_question",
            context_hint="",
        )
        try:
            score = director.score_subtext_depth("Some candidate.", instr)
            assert 0 <= score <= 3
        except Exception as exc:
            pytest.fail(f"score_subtext_depth raised with empty instruction: {exc}")

    def test_disabled_config_does_not_prevent_construction(self) -> None:
        config = SoulEngineConfig(enabled=False, subtlety_director_enabled=False)
        d = SubtletyDirector(config, seed=0)
        # should_inject_subtext still operates on the logic — config flags are checked upstream
        result = d.should_inject_subtext(5, "DEFLECT", True, True)
        assert isinstance(result, bool)

    def test_no_seed_is_non_deterministic_across_instances(self) -> None:
        """Two unseeded directors may produce different sequences (not guaranteed, but possible)."""
        d1 = SubtletyDirector(SoulEngineConfig())
        d2 = SubtletyDirector(SoulEngineConfig())
        # Just verify they can be created and used without error
        r1 = d1.should_inject_subtext(5, "DEFLECT", True, True)
        r2 = d2.should_inject_subtext(5, "DEFLECT", True, True)
        assert isinstance(r1, bool)
        assert isinstance(r2, bool)


# ---------------------------------------------------------------------------
# Hypothesis property tests
# ---------------------------------------------------------------------------


@given(
    tension=st.integers(min_value=0, max_value=10),
    move=st.sampled_from(
        ["COUNTER", "ESCALATE", "DEFLECT", "TAUNT", "QUESTION", "PIVOT", "CONCEDE", "CALLBACK"]
    ),
    has_sore_spot=st.booleans(),
    has_history=st.booleans(),
)
def test_property_should_inject_always_returns_bool(
    tension: int, move: str, has_sore_spot: bool, has_history: bool
) -> None:
    """Property: should_inject_subtext always returns bool, never raises."""
    d = _fresh_director()
    result = d.should_inject_subtext(tension, move, has_sore_spot, has_history)
    assert isinstance(result, bool)


@given(
    tension=st.integers(min_value=0, max_value=1),
    move=st.sampled_from(
        ["COUNTER", "ESCALATE", "DEFLECT", "TAUNT", "QUESTION", "PIVOT", "CALLBACK"]
    ),
    has_sore_spot=st.booleans(),
)
def test_property_tension_below_2_always_false(
    tension: int, move: str, has_sore_spot: bool
) -> None:
    """Property 6.2: tension < 2 is always a hard block."""
    d = _fresh_director()
    assert d.should_inject_subtext(tension, move, has_sore_spot, has_history=True) is False


@given(
    tension=st.integers(min_value=2, max_value=10),
    has_sore_spot=st.booleans(),
    has_history=st.booleans(),
)
def test_property_concede_always_false(
    tension: int, has_sore_spot: bool, has_history: bool
) -> None:
    """Property 6.2: CONCEDE is always a hard block."""
    d = _fresh_director()
    assert d.should_inject_subtext(tension, "CONCEDE", has_sore_spot, has_history) is False


@given(
    tension=st.integers(min_value=4, max_value=8),
    move=st.sampled_from(
        ["COUNTER", "ESCALATE", "DEFLECT", "TAUNT", "QUESTION", "PIVOT", "CALLBACK"]
    ),
    has_sore_spot=st.booleans(),
)
def test_property_mid_tension_with_history_activates(
    tension: int, move: str, has_sore_spot: bool
) -> None:
    """Property 6.1: tension 4-8 with history always activates (tension_in_range is sufficient)."""
    d = _fresh_director()
    assert d.should_inject_subtext(tension, move, has_sore_spot, has_history=True) is True


@given(
    elder=st.text(min_size=1, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz"),
    target=st.text(min_size=1, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz"),
    tension=st.integers(min_value=0, max_value=10),
    arc_theme=st.text(min_size=1, max_size=50, alphabet="abcdefghijklmnopqrstuvwxyz "),
)
def test_property_generate_instruction_never_raises(
    elder: str, target: str, tension: int, arc_theme: str
) -> None:
    """Property 6.6: generate_subtext_instruction never raises for valid string inputs."""
    d = _fresh_director()
    try:
        result = d.generate_subtext_instruction(
            elder=elder, target=target, tension=tension, sore_spot=None, arc_theme=arc_theme
        )
        assert result is None or isinstance(result, SubtextInstruction)
    except Exception as exc:
        pytest.fail(f"generate_subtext_instruction raised: {exc}")


@given(
    candidate=st.text(max_size=300, alphabet="abcdefghijklmnopqrstuvwxyz ?\"'—.! "),
    technique=st.sampled_from(SubtletyDirector.TECHNIQUES),
)
def test_property_score_depth_always_in_range(candidate: str, technique: str) -> None:
    """Property 6.5: score_subtext_depth always returns int in [0, 3]."""
    d = _fresh_director()
    instr = SubtextInstruction(
        surface_meaning="Ask about the arc theme as if curious.",
        implied_meaning="The question presumes target guilt or weakness.",
        technique=technique,
        context_hint="Let the subtext brush against sensitivity.",
    )
    score = d.score_subtext_depth(candidate, instr)
    assert isinstance(score, int)
    assert 0 <= score <= 3
