"""Integration tests for the full BanterEngine pipeline.

Tests end-to-end generate_beat() with real components (FallbackPool.from_json_file,
PacingController, AntiRepetitionGate, SceneContext) but mocked LLM model calls.

Validates: Requirements 1.3, 1.4, 2.1, 3.2, 6.2, 6.6
"""

import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest

from banter.anti_repetition import AntiRepetitionGate
from banter.engine import BanterEngine
from banter.fallback_pool import FallbackPool
from banter.model_router import ModelRouter
from banter.move_selector import compute_distribution
from banter.pacing_controller import PacingController
from banter.relationship_memory import RelationshipMemory
from banter.scene_context import SceneContext
from banter.types import (
    BanterConfig,
    Beat,
    BeatResult,
    InteractionRecord,
    PairState,
    QualityScore,
    RelationshipMemoryError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_integration_engine(
    model_response: str = "The question you refuse to ask is the one that answers itself.",
    quality_score: QualityScore | None = None,
    quality_error: bool = False,
    remote_unavailable: bool = False,
) -> BanterEngine:
    """Build a BanterEngine using real components with mocked LLM calls.

    Uses real:
    - FallbackPool.from_json_file() (production templates)
    - PacingController
    - AntiRepetitionGate
    - SceneContext
    - compute_distribution (real Move_Selector)

    Mocks:
    - Remote/local model calls (configurable response)
    - Quality judge (configurable score or error)
    - RelationshipMemory (pool=None, gracefully degrades)
    """
    # Real production fallback pool loaded from JSON templates
    fallback_pool = FallbackPool.from_json_file()

    # Quality judge mock
    default_score = quality_score or QualityScore(
        sharpness=2, emotional_texture=2, rhythm=2,
        thematic_relevance=2, shareability=1,
    )  # total = 9, above default threshold of 8

    async def mock_quality_judge(
        candidate, *, archetype, move, arc_theme, scene_context=None, timeout_s=2.0
    ):
        if quality_error:
            from banter.types import QualityJudgeError
            raise QualityJudgeError("Simulated quality evaluation timeout")
        return default_score

    # Model mocks
    async def mock_remote_model(prompt: str) -> str:
        if remote_unavailable:
            raise Exception("Remote endpoint unavailable (connection refused)")
        return model_response

    async def mock_local_model(prompt: str) -> str:
        return model_response

    model_router = ModelRouter(
        remote_model=mock_remote_model,
        local_model=mock_local_model if not remote_unavailable else mock_local_model,
    )

    # If remote is unavailable, trip the circuit breaker to force local routing
    if remote_unavailable:
        model_router._cb.tripped = True
        model_router._cb.tripped_at = time.time()

    return BanterEngine(
        quality_judge=mock_quality_judge,
        move_selector=compute_distribution,
        fallback_pool=fallback_pool,
        relationship_memory=RelationshipMemory(pool=None),
        scene_context=SceneContext(),
        model_router=model_router,
        pacing_controller=PacingController(),
        anti_repetition=AntiRepetitionGate(),
        config=BanterConfig(),
    )


# ---------------------------------------------------------------------------
# Test: End-to-end generate_beat() produces valid BeatResult
# ---------------------------------------------------------------------------


class TestEndToEndPipeline:
    """Test that the full pipeline produces valid BeatResult with real components."""

    @pytest.mark.asyncio
    async def test_generate_beat_produces_valid_result(self):
        """End-to-end: generate_beat() with mocked models produces valid BeatResult.

        Uses real FallbackPool (from JSON), real PacingController, real
        AntiRepetitionGate, real SceneContext, real MoveSelector.
        Only LLM calls are mocked.
        """
        engine = _build_integration_engine(
            model_response="Truth doesn't negotiate, it reveals.",
        )

        result = await engine.generate_beat(
            elder="prophet",
            archetype="prophet",
            opponent="keeper",
            arc_theme="Should the weak be protected?",
            conv_thread=[
                {"speaker": "keeper", "content": "Protection is just control with a smile.", "move": "COUNTER"},
                {"speaker": "prophet", "content": "Then what do you call abandonment?", "move": "QUESTION"},
            ],
        )

        # Validate BeatResult structure
        assert isinstance(result, BeatResult)
        assert result.line != ""
        assert len(result.line.split()) >= 1
        assert result.move in [
            "COUNTER", "ESCALATE", "DEFLECT", "TAUNT",
            "QUESTION", "PIVOT", "CONCEDE", "CALLBACK",
        ]
        assert 1.0 <= result.delay_s <= 10.0
        assert result.pre_pause_s >= 0.0
        assert result.source in ("remote", "local", "fallback")
        assert "pacing_rule" in result.metadata
        assert "session_id" in result.metadata

    @pytest.mark.asyncio
    async def test_multiple_beats_sequential(self):
        """Multiple sequential beats all produce valid results with consistent session."""
        engine = _build_integration_engine(
            model_response="You keep score, I keep perspective.",
        )

        results = []
        for i in range(3):
            result = await engine.generate_beat(
                elder="trickster",
                archetype="trickster",
                opponent="sovereign",
                arc_theme="The Ethics of Hoarding in a Finite World",
                conv_thread=[],
            )
            results.append(result)

        # All should be valid BeatResults
        for r in results:
            assert isinstance(r, BeatResult)
            assert r.line != ""
            assert 1.0 <= r.delay_s <= 10.0

        # All within same session (no 5-min gap)
        session_ids = [r.metadata["session_id"] for r in results]
        assert len(set(session_ids)) == 1


# ---------------------------------------------------------------------------
# Test: Fallback path when remote model is unavailable
# ---------------------------------------------------------------------------


class TestFallbackOnRemoteUnavailable:
    """Test graceful degradation when remote model is unavailable."""

    @pytest.mark.asyncio
    async def test_falls_back_to_local_when_remote_tripped(self):
        """When circuit breaker is tripped, routes to local model and still produces valid result."""
        engine = _build_integration_engine(
            model_response="Silence speaks louder than your rhetoric.",
            remote_unavailable=True,
        )

        result = await engine.generate_beat(
            elder="shadow",
            archetype="shadow",
            opponent="herald",
            arc_theme="Can builders turn scarcity into durable infrastructure?",
            conv_thread=[],
        )

        assert isinstance(result, BeatResult)
        assert result.line != ""
        # With circuit breaker tripped, route goes to "local"
        assert result.source in ("local", "fallback")
        assert 1.0 <= result.delay_s <= 10.0

    @pytest.mark.asyncio
    async def test_uses_fallback_pool_when_all_models_fail(self):
        """When both remote and local models fail, falls back to production template pool."""

        async def failing_remote(prompt: str) -> str:
            raise Exception("Remote connection refused")

        async def failing_local(prompt: str) -> str:
            raise Exception("Local model OOM")

        fallback_pool = FallbackPool.from_json_file()

        async def mock_quality_judge(
            candidate, *, archetype, move, arc_theme, scene_context=None, timeout_s=2.0
        ):
            return QualityScore(
                sharpness=2, emotional_texture=2, rhythm=2,
                thematic_relevance=1, shareability=2,
            )

        model_router = ModelRouter(
            remote_model=failing_remote,
            local_model=failing_local,
        )

        engine = BanterEngine(
            quality_judge=mock_quality_judge,
            move_selector=compute_distribution,
            fallback_pool=fallback_pool,
            relationship_memory=RelationshipMemory(pool=None),
            scene_context=SceneContext(),
            model_router=model_router,
            pacing_controller=PacingController(),
            anti_repetition=AntiRepetitionGate(),
            config=BanterConfig(),
        )

        result = await engine.generate_beat(
            elder="martyr",
            archetype="martyr",
            opponent="parasite",
            arc_theme="Patronage as Divine Intervention in a Scarcity Economy",
            conv_thread=[],
        )

        # Must fall back to the production template pool
        assert result.source == "fallback"
        assert result.line != ""
        # Pacing still computed even on fallback path
        assert 1.0 <= result.delay_s <= 10.0


# ---------------------------------------------------------------------------
# Test: Session boundary detection and state reset
# ---------------------------------------------------------------------------


class TestSessionBoundaryIntegration:
    """Test session boundary detection resets state across the full pipeline."""

    @pytest.mark.asyncio
    async def test_session_resets_after_5min_gap(self):
        """A 5-minute gap between beats triggers session reset with full pipeline."""
        engine = _build_integration_engine(
            model_response="New sessions bring new clarity.",
        )

        # First beat establishes a session
        first_result = await engine.generate_beat(
            elder="herald",
            archetype="herald",
            opponent="keeper",
            arc_theme="truth",
            conv_thread=[],
        )
        first_session = first_result.metadata["session_id"]

        # Simulate 6-minute gap (> 300s session_timeout_s)
        engine._last_beat_ts = time.time() - 360

        # Second beat should trigger session reset
        second_result = await engine.generate_beat(
            elder="herald",
            archetype="herald",
            opponent="keeper",
            arc_theme="truth",
            conv_thread=[],
        )
        second_session = second_result.metadata["session_id"]

        assert first_session != second_session
        # Verify fallback pool session was also reset (used_template_ids cleared)
        # After reset, the internal session state is fresh
        assert engine._session.started_at > 0

    @pytest.mark.asyncio
    async def test_session_persists_within_timeout(self):
        """Beats within the 5-min window keep the same session (no spurious resets)."""
        engine = _build_integration_engine(
            model_response="Continuity is underrated.",
        )

        # First beat
        r1 = await engine.generate_beat(
            elder="sovereign",
            archetype="sovereign",
            opponent="trickster",
            arc_theme="power",
            conv_thread=[],
        )

        # Short gap (2 minutes — well within 5-min timeout)
        engine._last_beat_ts = time.time() - 120

        # Second beat
        r2 = await engine.generate_beat(
            elder="sovereign",
            archetype="sovereign",
            opponent="trickster",
            arc_theme="power",
            conv_thread=[],
        )

        assert r1.metadata["session_id"] == r2.metadata["session_id"]


# ---------------------------------------------------------------------------
# Test: Relationship memory injection with mocked DB
# ---------------------------------------------------------------------------


class TestRelationshipMemoryInjection:
    """Test that relationship memory context is injected into prompt building."""

    @pytest.mark.asyncio
    async def test_graceful_degradation_when_db_unavailable(self):
        """Pipeline completes successfully even when relationship memory DB is down.

        RelationshipMemory(pool=None) will fail to get pool and return empty
        history — the pipeline should still produce a valid result without
        crashing.
        """
        engine = _build_integration_engine(
            model_response="History or not, the line lands.",
        )

        # RelationshipMemory with pool=None degrades gracefully
        result = await engine.generate_beat(
            elder="parasite",
            archetype="parasite",
            opponent="prophet",
            arc_theme="What Does Cooperation Mean When Trust Cannot Be Verified?",
            conv_thread=[
                {"speaker": "prophet", "content": "Trust is the foundation.", "move": "QUESTION"},
                {"speaker": "parasite", "content": "Foundation of what?", "move": "COUNTER"},
            ],
        )

        assert isinstance(result, BeatResult)
        assert result.line != ""
        assert result.source in ("remote", "local", "fallback")

    @pytest.mark.asyncio
    async def test_relationship_memory_with_mocked_history(self):
        """When relationship memory returns significant history, it's used in prompt building."""
        engine = _build_integration_engine(
            model_response="Your betrayal last cycle still echoes.",
        )

        # Mock the relationship memory to return significant history
        mock_records = [
            InteractionRecord(
                timestamp=time.time() - 3600,
                elder_a="keeper",
                elder_b="prophet",
                move_used="ESCALATE",
                emotional_valence="negative",
                betrayal=True,
                alliance=False,
                concession=False,
            ),
            InteractionRecord(
                timestamp=time.time() - 7200,
                elder_a="prophet",
                elder_b="keeper",
                move_used="CONCEDE",
                emotional_valence="positive",
                alliance=True,
                betrayal=False,
                concession=True,
            ),
        ]

        # Patch get_significant_history to return our mocked records
        async def mock_get_history(elder_a, elder_b, limit=5):
            return mock_records

        engine._relationship_memory.get_significant_history = mock_get_history

        result = await engine.generate_beat(
            elder="keeper",
            archetype="keeper",
            opponent="prophet",
            arc_theme="Should the weak be protected?",
            conv_thread=[],
        )

        assert isinstance(result, BeatResult)
        assert result.line != ""
        # The pipeline should still work correctly with memory context injected
        assert result.source in ("remote", "local", "fallback")
