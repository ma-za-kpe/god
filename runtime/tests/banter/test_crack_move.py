"""Tests for CRACK move (T4.1 vulnerability trigger).

Verifies requirements Section 8 acceptance criteria.
"""

import os
import sys

_src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
for _p in (_src_path, "/app/src"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import random
from unittest.mock import AsyncMock, MagicMock


from banter.engine import BanterEngine


def _make_pair_state(tension: int = 9, betrayal: bool = True):
    ps = MagicMock()
    ps.tension_level = tension
    ps.betrayal = betrayal
    ps.reconciliation_arc = False
    ps.reconciliation_remaining = 0
    return ps


def _make_minimal_engine():
    qj = AsyncMock(return_value=MagicMock(total=10, weak_dimensions=[]))
    rm = MagicMock()
    rm.get_significant_history = AsyncMock(return_value=[])
    rm.get_pair_state = AsyncMock(return_value=None)
    return BanterEngine(
        quality_judge=qj,
        move_selector=MagicMock(),
        fallback_pool=MagicMock(),
        relationship_memory=rm,
        scene_context=MagicMock(),
        model_router=MagicMock(),
        pacing_controller=MagicMock(),
        anti_repetition=MagicMock(),
    )


class TestShouldCrackConditions:
    """8.2 — Trigger conditions must ALL be true."""

    def test_requires_pair_state(self):
        engine = _make_minimal_engine()
        assert not engine._should_crack(10, None, 3)

    def test_requires_betrayal(self):
        engine = _make_minimal_engine()
        ps = _make_pair_state(tension=10, betrayal=False)
        assert not engine._should_crack(10, ps, 5)

    def test_requires_tension_above_8(self):
        engine = _make_minimal_engine()
        ps = _make_pair_state(tension=8, betrayal=True)
        assert not engine._should_crack(8, ps, 5)

    def test_requires_tension_strictly_above_8(self):
        engine = _make_minimal_engine()
        ps = _make_pair_state(tension=9, betrayal=True)
        # Can return True at tension 9 (all other conditions met)
        rng = MagicMock()
        rng.random = MagicMock(return_value=0.10)  # below 20% threshold
        assert engine._should_crack(9, ps, 3, rng)

    def test_requires_consecutive_counters_3_or_more(self):
        engine = _make_minimal_engine()
        ps = _make_pair_state(tension=9, betrayal=True)
        assert not engine._should_crack(9, ps, 0)
        assert not engine._should_crack(9, ps, 1)
        assert not engine._should_crack(9, ps, 2)

    def test_fires_at_3_consecutive_counters(self):
        engine = _make_minimal_engine()
        ps = _make_pair_state(tension=9, betrayal=True)
        rng = MagicMock()
        rng.random = MagicMock(return_value=0.10)
        assert engine._should_crack(9, ps, 3, rng)

    def test_20_percent_probability(self):
        engine = _make_minimal_engine()
        ps = _make_pair_state(tension=9, betrayal=True)
        rng = MagicMock()
        rng.random = MagicMock(return_value=0.19)
        assert engine._should_crack(9, ps, 3, rng)
        rng.random = MagicMock(return_value=0.20)
        assert not engine._should_crack(9, ps, 3, rng)

    def test_never_fires_at_tension_le_8_property(self):
        """Property: _should_crack NEVER returns True when tension <= 8."""
        engine = _make_minimal_engine()
        rng = random.Random(42)
        ps = _make_pair_state(tension=8, betrayal=True)
        for _ in range(1000):
            assert not engine._should_crack(8, ps, 10, rng), "CRACK must never fire at tension <= 8"

    def test_never_fires_without_betrayal_property(self):
        """Property: _should_crack NEVER returns True when betrayal=False."""
        engine = _make_minimal_engine()
        rng = random.Random(99)
        ps = _make_pair_state(tension=10, betrayal=False)
        for _ in range(1000):
            assert not engine._should_crack(10, ps, 10, rng), (
                "CRACK must never fire without betrayal"
            )


class TestCrackPromptContent:
    """8.3 — CRACK prompt injection text must contain override directive."""

    def test_crack_prompt_exists(self):
        engine = _make_minimal_engine()
        assert hasattr(engine, "_CRACK_PROMPT")
        assert "[CRACK" in engine._CRACK_PROMPT

    def test_crack_prompt_contains_override(self):
        engine = _make_minimal_engine()
        assert "OVERRIDE" in engine._CRACK_PROMPT

    def test_crack_prompt_tells_elder_not_to_perform_archetype(self):
        engine = _make_minimal_engine()
        assert (
            "do not defend your archetype" in engine._CRACK_PROMPT.lower()
            or "do not perform your role" in engine._CRACK_PROMPT.lower()
        )

    def test_snap_back_prompt_exists(self):
        engine = _make_minimal_engine()
        assert hasattr(engine, "_SNAP_BACK_PROMPT")
        assert "SNAP-BACK" in engine._SNAP_BACK_PROMPT

    def test_snap_back_tells_elder_to_recover(self):
        engine = _make_minimal_engine()
        assert "recover" in engine._SNAP_BACK_PROMPT.lower()


class TestCrackMoveTracking:
    """Engine state tracking for CRACK / snap-back."""

    def test_engine_initializes_crack_state(self):
        engine = _make_minimal_engine()
        assert engine._crack_active is False
        assert engine._next_move_override is None
        assert engine._consecutive_counters == 0

    def test_reset_session_clears_crack_state(self):
        engine = _make_minimal_engine()
        engine._crack_active = True
        engine._next_move_override = "COUNTER"
        engine._consecutive_counters = 4
        engine._reset_session()
        assert engine._crack_active is False
        assert engine._next_move_override is None
        assert engine._consecutive_counters == 0

    def test_crack_in_move_types(self):
        from banter.types import MOVE_TYPES

        # CRACK is in the type union — should be importable
        assert "CRACK" in str(MOVE_TYPES)
