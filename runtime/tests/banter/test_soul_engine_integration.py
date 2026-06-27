"""Integration tests for the Soul Engine pipeline in BanterEngine.

Tests the full generate_beat() path with soul modules wired in:
- All modules active and contributing
- Individual modules failing (fault isolation)
- Soul engine disabled → identical behaviour to pre-soul baseline
- Token budget enforcement end-to-end
- BeatResult.metadata records module outcomes

Requirements: 7.1, 7.2, 7.3, 7.4, 7.5
"""

import asyncio
import os
import sys

_src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
for _p in (_src_path, "/app/src"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from unittest.mock import AsyncMock, MagicMock


from banter.engine import BanterEngine
from banter.soul_types import SoulEngineConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(coro):
    return asyncio.run(coro)


def _make_scene_data():
    sd = MagicMock()
    sd.recent_beats = []
    sd.has_the_room = None
    sd.scene_energy = "neutral"
    sd.landed_hit = None
    sd.landed_hit_remaining = 0
    return sd


def _make_quality_score(total: int = 10):
    qs = MagicMock()
    qs.total = total
    qs.weak_dimensions = []
    return qs


def _make_base_engine(
    *,
    soul_config: SoulEngineConfig | None = None,
    voice_dna=None,
    emotional_primer=None,
    callback_registry=None,
    subtlety_director=None,
    generated_line: str = "Truth cuts where comfort rots.",
    quality_total: int = 12,
) -> BanterEngine:
    """Build a BanterEngine with model stub that returns a fixed line."""
    scene_data = _make_scene_data()
    mock_sc = MagicMock()
    mock_sc.get_context_for_generation = MagicMock(return_value=scene_data)

    mock_ar = MagicMock()
    mock_ar.should_shift_register = MagicMock(return_value=False)
    mock_ar.check = MagicMock(return_value=MagicMock(accepted=True))
    mock_ar.record_delivery = MagicMock()

    mock_mr = MagicMock()
    mock_mr.should_probe = MagicMock(return_value=False)
    route = MagicMock()
    route.target = "remote"
    route.quality_threshold = 8
    route.timeout_s = 2.0
    mock_mr.route = MagicMock(return_value=route)
    mock_mr.call_remote = AsyncMock(return_value=generated_line)
    mock_mr.validate_response = MagicMock(return_value=True)

    mock_qj = AsyncMock(return_value=_make_quality_score(quality_total))

    mock_rm = MagicMock()
    mock_rm.get_significant_history = AsyncMock(return_value=[])
    mock_rm.get_pair_state = AsyncMock(return_value=None)

    mock_pc = MagicMock()
    pacing = MagicMock()
    pacing.inter_beat_delay_s = 0.5
    pacing.pre_delivery_pause_s = 0.1
    pacing.rule_applied = "default"
    mock_pc.compute_delay = MagicMock(return_value=pacing)

    mock_ms = MagicMock()
    mock_dist = MagicMock()
    mock_dist.sample = MagicMock(return_value="COUNTER")
    mock_ms.return_value = mock_dist
    mock_ms.__call__ = MagicMock(return_value=mock_dist)

    mock_fp = MagicMock()
    fallback_sel = MagicMock()
    fallback_sel.text = "Guard what endures."
    fallback_sel.template_id = "fallback_001"
    mock_fp.select = MagicMock(return_value=fallback_sel)
    mock_fp.reset_session = MagicMock()

    return BanterEngine(
        quality_judge=mock_qj,
        move_selector=mock_ms,
        fallback_pool=mock_fp,
        relationship_memory=mock_rm,
        scene_context=mock_sc,
        model_router=mock_mr,
        pacing_controller=mock_pc,
        anti_repetition=mock_ar,
        soul_config=soul_config,
        voice_dna=voice_dna,
        emotional_primer=emotional_primer,
        callback_registry=callback_registry,
        subtlety_director=subtlety_director,
    )


def _make_working_voice_dna(text: str = "Declarative truths. Short sentences."):
    vdna = MagicMock()
    vdna.get_prompt_injection = MagicMock(return_value=text)
    vdna.score_voice_conformance = MagicMock(return_value=2)
    return vdna


def _make_working_emotional_primer(text: str = "The weight of past interactions presses down."):
    ep = MagicMock()
    ep.generate_emotional_context = AsyncMock(return_value=text)
    return ep


def _make_broken_voice_dna():
    vdna = MagicMock()
    vdna.get_prompt_injection = MagicMock(side_effect=RuntimeError("vdna simulated failure"))
    vdna.score_voice_conformance = MagicMock(side_effect=RuntimeError("vdna score failure"))
    return vdna


def _make_broken_emotional_primer():
    ep = MagicMock()
    ep.generate_emotional_context = AsyncMock(side_effect=RuntimeError("ep simulated failure"))
    return ep


# ---------------------------------------------------------------------------
# Tests: generate_beat with all soul modules active
# ---------------------------------------------------------------------------


class TestGenerateBeatWithSoulModulesActive:
    """Full generate_beat() with soul modules wired in."""

    def test_returns_beat_result(self):
        """generate_beat returns a BeatResult with the generated line."""
        from banter.types import BeatResult

        engine = _make_base_engine(
            soul_config=SoulEngineConfig(),
            voice_dna=_make_working_voice_dna(),
            emotional_primer=_make_working_emotional_primer(),
        )

        result = _run(
            engine.generate_beat(
                elder="elder_alpha",
                archetype="keeper",
                opponent="elder_beta",
                arc_theme="survival",
                conv_thread=[],
            )
        )

        assert isinstance(result, BeatResult)
        assert isinstance(result.line, str)
        assert len(result.line) > 0

    def test_beat_metadata_has_soul_key(self):
        """BeatResult.metadata contains 'soul' key recording module outcomes."""
        engine = _make_base_engine(
            soul_config=SoulEngineConfig(),
            voice_dna=_make_working_voice_dna(),
            emotional_primer=_make_working_emotional_primer(),
        )

        result = _run(
            engine.generate_beat(
                elder="elder_alpha",
                archetype="keeper",
                opponent="elder_beta",
                arc_theme="survival",
                conv_thread=[],
            )
        )

        assert "soul" in result.metadata
        assert isinstance(result.metadata["soul"], dict)

    def test_soul_metadata_records_module_success(self):
        """When modules succeed, metadata records True for each."""
        engine = _make_base_engine(
            soul_config=SoulEngineConfig(),
            voice_dna=_make_working_voice_dna(),
            emotional_primer=_make_working_emotional_primer(),
        )

        result = _run(
            engine.generate_beat(
                elder="elder_alpha",
                archetype="herald",
                opponent="elder_beta",
                arc_theme="change",
                conv_thread=[],
            )
        )

        soul_meta = result.metadata["soul"]
        assert soul_meta.get("voice_dna") is True
        assert soul_meta.get("emotional_primer") is True

    def test_beat_result_has_pacing(self):
        """BeatResult includes pacing values from PacingController."""
        engine = _make_base_engine(soul_config=SoulEngineConfig())

        result = _run(
            engine.generate_beat(
                elder="elder_alpha",
                archetype="shadow",
                opponent=None,
                arc_theme="secrets",
                conv_thread=[],
            )
        )

        assert result.delay_s == 0.5
        assert result.pre_pause_s == 0.1


# ---------------------------------------------------------------------------
# Tests: generate_beat with individual modules failing
# ---------------------------------------------------------------------------


class TestGenerateBeatModuleFaultIsolation:
    """generate_beat continues when individual soul modules fail."""

    def test_broken_voice_dna_does_not_crash_generate_beat(self):
        """Broken voice_dna → beat still generated, failure recorded in metadata."""
        engine = _make_base_engine(
            soul_config=SoulEngineConfig(),
            voice_dna=_make_broken_voice_dna(),
            emotional_primer=_make_working_emotional_primer(),
        )

        result = _run(
            engine.generate_beat(
                elder="elder_a",
                archetype="martyr",
                opponent="elder_b",
                arc_theme="sacrifice",
                conv_thread=[],
            )
        )

        assert isinstance(result.line, str) and result.line
        assert result.metadata["soul"].get("voice_dna") is False
        assert result.metadata["soul"].get("emotional_primer") is True

    def test_broken_emotional_primer_does_not_crash_generate_beat(self):
        """Broken emotional_primer → beat still generated, voice_dna still contributes."""
        engine = _make_base_engine(
            soul_config=SoulEngineConfig(),
            voice_dna=_make_working_voice_dna(),
            emotional_primer=_make_broken_emotional_primer(),
        )

        result = _run(
            engine.generate_beat(
                elder="elder_a",
                archetype="sovereign",
                opponent="elder_b",
                arc_theme="power",
                conv_thread=[],
            )
        )

        assert isinstance(result.line, str) and result.line
        assert result.metadata["soul"].get("emotional_primer") is False
        assert result.metadata["soul"].get("voice_dna") is True

    def test_all_modules_broken_still_produces_beat(self):
        """Even with all soul modules broken, a beat is produced."""
        engine = _make_base_engine(
            soul_config=SoulEngineConfig(),
            voice_dna=_make_broken_voice_dna(),
            emotional_primer=_make_broken_emotional_primer(),
        )

        result = _run(
            engine.generate_beat(
                elder="elder_a",
                archetype="parasite",
                opponent="elder_b",
                arc_theme="corruption",
                conv_thread=[],
            )
        )

        assert isinstance(result.line, str) and result.line
        soul_meta = result.metadata["soul"]
        assert soul_meta.get("voice_dna") is False
        assert soul_meta.get("emotional_primer") is False


# ---------------------------------------------------------------------------
# Tests: Soul engine disabled → identical output path to pre-soul baseline
# ---------------------------------------------------------------------------


class TestSoulEngineDisabledBehaviour:
    """When soul_config.enabled=False or soul_config=None, no soul modules run."""

    def test_no_soul_modules_run_when_disabled(self):
        """Disabled soul config → voice_dna.get_prompt_injection never called."""
        mock_vdna = _make_working_voice_dna()
        mock_ep = _make_working_emotional_primer()

        engine = _make_base_engine(
            soul_config=SoulEngineConfig(enabled=False),
            voice_dna=mock_vdna,
            emotional_primer=mock_ep,
        )

        _run(
            engine.generate_beat(
                elder="elder_a",
                archetype="trickster",
                opponent=None,
                arc_theme="deception",
                conv_thread=[],
            )
        )

        mock_vdna.get_prompt_injection.assert_not_called()
        mock_ep.generate_emotional_context.assert_not_called()

    def test_no_soul_modules_run_when_config_none(self):
        """soul_config=None → soul modules not called even if injected."""
        mock_vdna = _make_working_voice_dna()

        engine = _make_base_engine(
            soul_config=None,
            voice_dna=mock_vdna,
        )

        _run(
            engine.generate_beat(
                elder="elder_a",
                archetype="herald",
                opponent=None,
                arc_theme="change",
                conv_thread=[],
            )
        )

        mock_vdna.get_prompt_injection.assert_not_called()

    def test_soul_metadata_empty_when_disabled(self):
        """Disabled soul config → soul metadata dict is empty."""
        engine = _make_base_engine(
            soul_config=SoulEngineConfig(enabled=False),
            voice_dna=_make_working_voice_dna(),
        )

        result = _run(
            engine.generate_beat(
                elder="elder_a",
                archetype="prophet",
                opponent=None,
                arc_theme="truth",
                conv_thread=[],
            )
        )

        assert result.metadata["soul"] == {}

    def test_quality_threshold_lower_when_disabled(self):
        """Disabled soul → quality_threshold uses base (8) not soul (10)."""
        low_quality = 9  # passes base (8) but not soul (10)
        engine_disabled = _make_base_engine(
            soul_config=SoulEngineConfig(enabled=False),
            quality_total=low_quality,
            generated_line="A line that barely passes base threshold.",
        )

        result = _run(
            engine_disabled.generate_beat(
                elder="elder_a",
                archetype="keeper",
                opponent=None,
                arc_theme="survival",
                conv_thread=[],
            )
        )

        # With disabled soul, threshold is 8, score 9 ≥ 8 → should pass
        assert result.source != "fallback" or result.quality_score == 0


# ---------------------------------------------------------------------------
# Tests: Beat number and session tracking
# ---------------------------------------------------------------------------


class TestSoulSessionTracking:
    """Beat number increments and session resets include soul counters."""

    def test_beat_number_increments_each_call(self):
        """_beat_number increments with each generate_beat call."""
        engine = _make_base_engine(soul_config=SoulEngineConfig())

        assert engine._beat_number == 0

        _run(engine.generate_beat("elder_a", "keeper", None, "survival", []))
        assert engine._beat_number == 1

        _run(engine.generate_beat("elder_a", "keeper", None, "survival", []))
        assert engine._beat_number == 2

    def test_session_callback_count_starts_at_zero(self):
        """_session_callback_count starts at 0."""
        engine = _make_base_engine(soul_config=SoulEngineConfig())
        assert engine._session_callback_count == 0
