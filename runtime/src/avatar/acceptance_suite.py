"""Persona and use-case acceptance matrix for live avatar embodiment."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


AUDIT_MATRIX_LINK = "docs/90-fish-comfyui-integration-audit.md#issue-103-avatar-acceptance-suite"


class AcceptanceMode(str, Enum):
    AUTOMATED = "automated_test"
    MANUAL_VOD = "manual_vod_check"
    BENCHMARK = "benchmark_or_field_report"


REQUIRED_PERSONAS = {
    "live_speaker",
    "listener",
    "emotional_reactor",
    "cinematic_cutaway",
    "highlight_producer",
    "operator",
}

REQUIRED_USE_CASES = {
    "agent_speaks_normally",
    "agent_listens_silently_30s",
    "emotional_beat_changes_expression_within_1s",
    "fish_failure_degrades_gracefully",
    "comfy_video_failure_remains_alive",
    "background_asset_job_does_not_block_fish",
    "observer_switches_visual_sources",
    "offline_highlight_clip_export",
    "operator_reads_health_fallback_queue_and_source",
}

REQUIRED_FAILURE_USE_CASES = {
    "fish_failure_degrades_gracefully",
    "comfy_video_failure_remains_alive",
    "background_asset_job_does_not_block_fish",
    "observer_switches_visual_sources",
}


@dataclass(frozen=True)
class AcceptanceCase:
    case_id: str
    persona: str
    use_case: str
    modes: tuple[AcceptanceMode, ...]
    success_criteria: tuple[str, ...]
    automated_tests: tuple[str, ...] = field(default_factory=tuple)
    manual_vod_checklist: tuple[str, ...] = field(default_factory=tuple)
    required_evidence: tuple[str, ...] = field(default_factory=tuple)
    failure_path: bool = False
    notes: str = ""

    def has_evidence_path(self) -> bool:
        return bool(self.automated_tests or self.manual_vod_checklist or self.required_evidence)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["modes"] = [mode.value for mode in self.modes]
        payload["has_evidence_path"] = self.has_evidence_path()
        return payload


ACCEPTANCE_CASES: tuple[AcceptanceCase, ...] = (
    AcceptanceCase(
        case_id="speaker-fish-mouth-live",
        persona="live_speaker",
        use_case="agent_speaks_normally",
        modes=(AcceptanceMode.AUTOMATED, AcceptanceMode.MANUAL_VOD),
        success_criteria=(
            "Fish audio evidence is present.",
            "Mouth state reacts while the speaker is active.",
            "No dead air or frozen avatar during the spoken line.",
        ),
        automated_tests=(
            "runtime/tests/test_youtube_live_proof.py::test_youtube_proof_ready_when_fish_life_caption_and_video_are_visible",
            "runtime/tests/test_avatar_components.py::test_avatar_surface_uses_expression_override",
        ),
        manual_vod_checklist=(
            "Record one normal line and confirm audible Fish playback.",
            "Confirm visible mouth or face motion begins with the line.",
        ),
        required_evidence=("vod_segment", "fish_audio_state", "mouth_open_state"),
    ),
    AcceptanceCase(
        case_id="listener-idle-life-30s",
        persona="listener",
        use_case="agent_listens_silently_30s",
        modes=(AcceptanceMode.AUTOMATED, AcceptanceMode.MANUAL_VOD),
        success_criteria=(
            "Breathing, blink, and head-sway signals continue while not speaking.",
            "Mouth remains closed unless audio/speech is active.",
            "Thirty-second listener VOD segment does not look frozen.",
        ),
        automated_tests=(
            "runtime/tests/test_avatar_life_signals.py::test_generate_life_state_is_deterministic_with_injected_time",
            "runtime/tests/test_avatar_life_signals.py::test_mouth_amplitude_uses_audio_rms_and_speaking_fallback",
        ),
        manual_vod_checklist=(
            "Hold a listener on stage for 30 seconds.",
            "Confirm breathing/blinking/head movement remains visible.",
        ),
        required_evidence=("30s_vod_segment", "life_state"),
    ),
    AcceptanceCase(
        case_id="reactor-beat-expression",
        persona="emotional_reactor",
        use_case="emotional_beat_changes_expression_within_1s",
        modes=(AcceptanceMode.AUTOMATED, AcceptanceMode.MANUAL_VOD),
        success_criteria=(
            "CRACK, TAUNT, CONCEDE, ESCALATE, and SILENCE have defined visual outcomes.",
            "The visible expression changes within one second of the beat.",
        ),
        automated_tests=(
            "runtime/tests/test_avatar_components.py::test_visual_reactor_sets_crack_override",
            "runtime/tests/test_avatar_components.py::test_avatar_surface_uses_expression_override",
        ),
        manual_vod_checklist=(
            "Trigger CRACK, TAUNT, CONCEDE, ESCALATE, and SILENCE beats.",
            "Timestamp beat emission and first visible expression change.",
        ),
        required_evidence=("beat_timestamp", "expression_state", "vod_segment"),
    ),
    AcceptanceCase(
        case_id="cutaway-background-safe",
        persona="cinematic_cutaway",
        use_case="background_asset_job_does_not_block_fish",
        modes=(AcceptanceMode.AUTOMATED, AcceptanceMode.BENCHMARK, AcceptanceMode.MANUAL_VOD),
        success_criteria=(
            "Background video work uses queue policy.",
            "Live voice gets priority over LTX/Wan/offline jobs.",
            "Cutaway playback is optional and never blocks live dialogue.",
        ),
        automated_tests=(
            "runtime/tests/test_gpu_job_queue.py::test_live_voice_runs_before_queued_background_job",
            "runtime/tests/test_gpu_job_queue.py::test_live_voice_requests_active_background_cancellation",
            "runtime/tests/test_video_generator_quality.py::test_wan_quality_clip_registers_highlight_manifest_asset",
        ),
        manual_vod_checklist=(
            "Run a background clip job while live mode is active or simulated.",
            "Confirm Fish remains audible and queue diagnostics show live priority.",
        ),
        required_evidence=("gpu_queue_diagnostics", "fish_success_rate", "clip_asset_record"),
        failure_path=True,
    ),
    AcceptanceCase(
        case_id="highlight-offline-export",
        persona="highlight_producer",
        use_case="offline_highlight_clip_export",
        modes=(AcceptanceMode.AUTOMATED, AcceptanceMode.BENCHMARK, AcceptanceMode.MANUAL_VOD),
        success_criteria=(
            "Offline highlight generation records source audio and portrait inputs.",
            "Generated clip is registered as a highlight asset.",
            "Highlight work stays out of the live voice path.",
        ),
        automated_tests=(
            "runtime/tests/test_video_generator_quality.py::test_ltx_lipdub_highlight_records_audio_source_and_offline_priority",
            "runtime/tests/test_video_manifest.py::test_live_selection_is_deterministic_and_prefers_cached_matching_loop",
        ),
        manual_vod_checklist=(
            "Select one moment after a test stream.",
            "Generate/export an offline clip and record output quality notes.",
        ),
        required_evidence=("highlight_manifest_asset", "source_audio_cid", "field_notes"),
    ),
    AcceptanceCase(
        case_id="operator-proof-surface",
        persona="operator",
        use_case="operator_reads_health_fallback_queue_and_source",
        modes=(AcceptanceMode.AUTOMATED, AcceptanceMode.MANUAL_VOD),
        success_criteria=(
            "Operator can see live vs fallback state.",
            "Operator can see voice, caption, visual source, fallback, and queue state.",
            "Acceptance remains incomplete until VOD and benchmark notes are attached.",
        ),
        automated_tests=(
            "runtime/tests/test_youtube_live_proof.py::test_youtube_proof_ready_when_fish_life_caption_and_video_are_visible",
            "runtime/tests/test_gpu_job_queue.py::test_gpu_diagnostics_endpoint_reports_queue_state",
        ),
        manual_vod_checklist=(
            "Open /broadcast/youtube-proof before stream.",
            "Capture report JSON beside the 5-10 minute VOD notes.",
        ),
        required_evidence=("youtube_proof_report", "gpu_diagnostics", "vod_notes"),
    ),
    AcceptanceCase(
        case_id="fish-failure-visible-degrade",
        persona="operator",
        use_case="fish_failure_degrades_gracefully",
        modes=(AcceptanceMode.AUTOMATED, AcceptanceMode.MANUAL_VOD),
        success_criteria=(
            "Silent or non-Fish voice path is marked blocked before live proof.",
            "Visual stage continues to show fallback state.",
            "Operator can identify silence risk.",
        ),
        automated_tests=(
            "runtime/tests/test_youtube_live_proof.py::test_youtube_proof_blocks_silent_or_non_fish_voice_path",
            "runtime/tests/test_resilience_surface.py::test_resilience_status_reports_local_first_defaults",
        ),
        manual_vod_checklist=(
            "Disable or simulate failed Fish and capture readiness output.",
            "Confirm stage stays visible and the operator sees silence risk.",
        ),
        required_evidence=("readiness_blocker", "fallback_visual_state"),
        failure_path=True,
    ),
    AcceptanceCase(
        case_id="comfy-video-failure-alive",
        persona="operator",
        use_case="comfy_video_failure_remains_alive",
        modes=(AcceptanceMode.AUTOMATED, AcceptanceMode.MANUAL_VOD),
        success_criteria=(
            "Comfy/video unavailable degrades to portrait or generated fallback.",
            "No black stage while Fish and procedural life are available.",
        ),
        automated_tests=(
            "runtime/tests/test_youtube_live_proof.py::test_youtube_proof_allows_comfy_unavailable_with_portrait_fallback",
            "runtime/tests/test_video_manifest.py::test_ipfs_retrieval_failure_falls_back_to_static_portrait",
            "runtime/tests/test_video_manifest.py::test_expired_assets_are_skipped_with_static_fallback",
        ),
        manual_vod_checklist=(
            "Run private stream proof with Comfy/video unavailable.",
            "Confirm portrait/generated fallback remains visible with Fish audio.",
        ),
        required_evidence=("fallback_visual_state", "vod_segment"),
        failure_path=True,
    ),
    AcceptanceCase(
        case_id="observer-source-switching",
        persona="operator",
        use_case="observer_switches_visual_sources",
        modes=(AcceptanceMode.AUTOMATED, AcceptanceMode.MANUAL_VOD),
        success_criteria=(
            "Observer selects procedural/static fallback when media is missing.",
            "Observer can prefer loop and cinematic sources when available.",
            "Switching never produces an accepted black stage.",
        ),
        automated_tests=(
            "observer/tests/avatarSource.test.mjs",
            "runtime/tests/test_video_manifest.py::test_live_selection_is_deterministic_and_prefers_cached_matching_loop",
        ),
        manual_vod_checklist=(
            "Switch one agent through procedural, loop, cinematic, and static fallback states.",
            "Record any black-frame or buffering interval.",
        ),
        required_evidence=("observer_source_status", "vod_switch_notes"),
        failure_path=True,
    ),
)


def validate_acceptance_suite(cases: tuple[AcceptanceCase, ...] = ACCEPTANCE_CASES) -> list[str]:
    gaps: list[str] = []
    personas = {case.persona for case in cases}
    use_cases = {case.use_case for case in cases}
    failure_use_cases = {case.use_case for case in cases if case.failure_path}

    for persona in sorted(REQUIRED_PERSONAS - personas):
        gaps.append(f"missing_persona:{persona}")
    for use_case in sorted(REQUIRED_USE_CASES - use_cases):
        gaps.append(f"missing_use_case:{use_case}")
    for use_case in sorted(REQUIRED_FAILURE_USE_CASES - failure_use_cases):
        gaps.append(f"missing_failure_path:{use_case}")
    for case in cases:
        if not case.has_evidence_path():
            gaps.append(f"missing_evidence_path:{case.case_id}")
        if not case.success_criteria:
            gaps.append(f"missing_success_criteria:{case.case_id}")
    return gaps


def build_acceptance_suite_report(
    cases: tuple[AcceptanceCase, ...] = ACCEPTANCE_CASES,
) -> dict[str, Any]:
    gaps = validate_acceptance_suite(cases)
    manual_cases = [case.case_id for case in cases if case.manual_vod_checklist]
    automated_cases = [case.case_id for case in cases if case.automated_tests]
    return {
        "status": "complete" if not gaps else "incomplete",
        "audit_link": AUDIT_MATRIX_LINK,
        "personas": sorted({case.persona for case in cases}),
        "use_cases": sorted({case.use_case for case in cases}),
        "failure_use_cases": sorted({case.use_case for case in cases if case.failure_path}),
        "automated_case_count": len(automated_cases),
        "manual_vod_case_count": len(manual_cases),
        "validation_gaps": gaps,
        "cases": [case.to_dict() for case in cases],
    }
