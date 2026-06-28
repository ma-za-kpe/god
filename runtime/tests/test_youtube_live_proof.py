"""YouTube live proof readiness report tests."""

from __future__ import annotations

from broadcast import build_youtube_live_proof_report


def _snapshot() -> dict:
    return {
        "epoch": 1234,
        "world_id": "local-dev-world-1",
        "agents": [
            {
                "soul_id": "alpha",
                "current_name": "Alpha",
                "avatar_cid": "bafyPortrait",
                "video_manifest": {
                    "assets": [
                        {
                            "cid": "bafyLoop",
                            "variant": "low_res_live",
                            "status": "ready",
                        }
                    ]
                },
            }
        ],
        "showrunner": {"speaker": "Alpha", "headline": "Alpha takes the stage."},
        "voice": {
            "provider": "local-tts",
            "plan": {
                "speaker": "Alpha",
                "line": "The world is still listening.",
                "utterance_id": "utt-1",
            },
            "synthesis": {
                "ok": True,
                "endpoint": "http://localhost:7860/v1/tts",
                "audio_present": True,
                "audio_byte_count": 1024,
                "mouth_amplitude": 0.41,
            },
        },
        "avatar": {
            "speaking": True,
            "mouth_open": 0.46,
            "life": {
                "breathing_phase": 0.33,
                "blink_state": False,
                "head_sway_x": 0.02,
                "mouth_amplitude": 0.46,
            },
            "plan": {"speaker": "Alpha", "speaking": True, "mouth_open": 0.46},
        },
        "broadcast": {
            "caption": {
                "headline": "Alpha takes the stage.",
                "subhead": "Chat can weigh in.",
                "lower_third": "Alpha - Ensemble Stage",
                "ticker_lines": ["Alpha takes the stage."],
            }
        },
    }


def test_youtube_proof_ready_when_fish_life_caption_and_video_are_visible():
    report = build_youtube_live_proof_report(
        _snapshot(),
        runtime_ready={"checks": {"comfyui": {"ok": True}}},
        gpu_diagnostics={"background_jobs_allowed": False, "queue_depth": 0},
    )

    assert report["status"] == "ready_for_private_test"
    assert report["ready_for_private_stream"] is True
    assert report["acceptance_complete"] is False
    assert report["operator_state"]["voice_mode"] == "fish_audio"
    assert report["operator_state"]["visual_mode"] == "video_loop"
    assert report["operator_state"]["black_screen_risk"] is False
    assert report["operator_state"]["silence_risk"] is False
    assert all(check["ok"] for check in report["checks"] if check["severity"] == "required")


def test_youtube_proof_allows_comfy_unavailable_with_portrait_fallback():
    snapshot = _snapshot()
    snapshot["agents"][0]["video_manifest"] = {"assets": []}
    report = build_youtube_live_proof_report(
        snapshot,
        runtime_ready={"checks": {"comfyui": {"ok": False, "reason": "connection_failed"}}},
        gpu_diagnostics={"background_jobs_allowed": False, "queue_depth": 0},
    )

    assert report["status"] == "degraded_private_test_ready"
    assert report["ready_for_private_stream"] is True
    assert report["operator_state"]["visual_mode"] == "portrait_fallback"
    assert report["operator_state"]["fallback_active"] is True
    assert report["operator_state"]["black_screen_risk"] is False
    assert report["operator_state"]["silence_risk"] is False
    assert report["evidence"]["comfy"]["mode"] == "fallback_only"


def test_youtube_proof_blocks_silent_or_non_fish_voice_path():
    snapshot = _snapshot()
    snapshot["voice"]["provider"] = "dry-run"
    snapshot["voice"]["synthesis"] = {"ok": False, "reason": "dry_run"}

    report = build_youtube_live_proof_report(snapshot)

    assert report["status"] == "blocked"
    assert report["ready_for_private_stream"] is False
    assert report["operator_state"]["silence_risk"] is True
    failed = {check["name"] for check in report["checks"] if not check["ok"]}
    assert "fish_voice_audio" in failed


def test_youtube_proof_recognizes_fish_base_endpoint_without_trailing_slash():
    snapshot = _snapshot()
    snapshot["voice"]["provider"] = "local-tts"
    snapshot["voice"]["synthesis"] = {
        "ok": False,
        "reason": "unhealthy_endpoint",
        "endpoint": "http://localhost:7860",
    }

    report = build_youtube_live_proof_report(snapshot)

    assert report["status"] == "blocked"
    assert report["evidence"]["voice"]["fish_configured"] is True
    assert report["evidence"]["voice"]["audio_present"] is False
    assert report["operator_state"]["silence_risk"] is True


def test_youtube_proof_blocks_missing_procedural_life_and_captions():
    snapshot = _snapshot()
    snapshot["avatar"]["life"] = {}
    snapshot["avatar"]["plan"] = {"speaker": "Alpha", "speaking": True}
    snapshot["broadcast"]["caption"] = {}

    report = build_youtube_live_proof_report(snapshot)

    assert report["status"] == "blocked"
    failed = {check["name"] for check in report["checks"] if not check["ok"]}
    assert "procedural_life_visible" in failed
    assert "captions_visible" in failed
