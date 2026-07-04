"""Contracts for the local-only /one avatar control runtime."""

from __future__ import annotations

import importlib.util
import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "local_avatar_control_server.py"


def _module():
    spec = importlib.util.spec_from_file_location("local_avatar_control_server", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _persona() -> dict[str, object]:
    return {
        "soul_id": "local-vrm-agent-001",
        "current_name": "Kairo",
        "archetype": "embodied_controller",
        "persona": {"name": "Kairo", "summary": "test", "style": "test"},
        "provider": "ollama:llama3.1:8b",
    }


def test_local_control_snapshot_uses_ollama_body_commands_without_audio_or_video():
    module = _module()

    def fake_pose_stream(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {
            "schema_version": 1,
            "source": module.POSE_STREAM_SOURCE,
            "provider": "ai4animationpy:manual",
            "target_runtime": "ai4animationpy",
            "execution_mode": "Manual",
            "duration_seconds": 4,
            "frame_count": 2,
            "frames": [
                {
                    "timestamp_ms": 0,
                    "root_position": [0, 0, 0],
                    "root_rotation": [0, 0, 0, 1],
                    "joint_rotations": {"Spine": [0, 0, 0, 1]},
                    "contacts": {"LeftFoot": True, "RightFoot": True},
                    "gesture_label": "start",
                },
                {
                    "timestamp_ms": 1000,
                    "root_position": [0.1, 0, 0],
                    "root_rotation": [0, 0, 0, 1],
                    "joint_rotations": {"Spine": [0, 0.1, 0, 1]},
                    "contacts": {"LeftFoot": True, "RightFoot": False},
                    "gesture_label": "inspect_plant",
                },
            ],
        }

    def fake_ollama(_prompt: str) -> dict[str, object]:
        return {
            "intent": "cross the room and inspect the plant",
            "control_label": "inspect_plant",
            "duration_seconds": 4,
            "commands": [
                {"type": "walk_to", "at_ms": 0, "duration_ms": 1400, "x": -1.2, "z": 0.9},
                {"type": "turn_to", "at_ms": 1200, "duration_ms": 500, "yaw_degrees": -35},
                {"type": "gesture", "at_ms": 1500, "duration_ms": 1000, "name": "point"},
                {
                    "type": "expression",
                    "at_ms": 1500,
                    "duration_ms": 900,
                    "name": "focus",
                    "intensity": 0.7,
                },
            ],
        }

    module.build_ai4animationpy_pose_stream = fake_pose_stream
    state = module.ControlState(
        _persona(),
        ollama_url="http://localhost:11434",
        ollama_model="llama3.1:8b",
        ollama_timeout=1,
        decision_provider=fake_ollama,
    )
    state.ai4_status = {"available": True, "execution_mode": "Manual"}
    snapshot = state.snapshot()
    motion = snapshot["avatar"]["body_motion"]

    assert snapshot["world_id"] == "local-avatar-control"
    assert snapshot["stats"]["movement_source"] == "ollama"
    assert snapshot["voice"]["status"] == "disabled"
    assert snapshot["avatar"]["control_mode"] == "llm-avatar-control"
    assert motion["source"] == "ollama-llm-avatar-control"
    assert motion["execution_mode"] == "Manual"
    assert motion["target_runtime"] == "ai4animationpy"
    assert motion["motion_backend"] == "ai4animationpy-manual-pose-stream"
    assert motion["control_label"] == "inspect_plant"
    assert motion["root_start"] == [0.0, 0.0]
    assert motion["pose_stream"]["provider"] == "ai4animationpy:manual"
    assert [command["type"] for command in motion["commands"]] == [
        "walk_to",
        "turn_to",
        "expression",
        "gesture",
    ]
    assert motion["trajectory"][-1]["x"] == -1.2
    assert "video" not in snapshot["avatar"]
    assert "audio_url" not in snapshot["voice"]


def test_local_control_blocks_without_ai4animationpy_instead_of_browser_sampler():
    module = _module()
    raw = {
        "intent": "walk to the chair",
        "control_label": "chair_walk",
        "duration_seconds": 4,
        "commands": [{"type": "walk_to", "at_ms": 0, "duration_ms": 1200, "x": 1, "z": 1}],
    }

    plan = module.normalize_llm_control_plan(
        raw,
        agent_id="local-vrm-agent-001",
        started_at_ms=123,
        provider="ollama:llama3.1:8b",
        room=module.ROOM,
        current_position=[0.0, 0.0],
        current_yaw=0.0,
        ai4_status={"available": False, "reason": "ModuleNotFoundError"},
    )

    assert plan["status"] == "blocked"
    assert plan["motion_backend"] == "blocked-no-ai4animationpy"
    assert plan["blocked_reason"] == "ai4animationpy_unavailable"
    assert plan["commands"] == []
    assert "pose_stream" not in plan


def test_local_control_blocks_when_ollama_fails_instead_of_substitute_motion():
    module = _module()

    def failing_ollama(_prompt: str) -> dict[str, object]:
        raise RuntimeError("ollama unavailable")

    state = module.ControlState(
        _persona(),
        ollama_url="http://localhost:11434",
        ollama_model="llama3.1:8b",
        ollama_timeout=1,
        decision_provider=failing_ollama,
    )
    snapshot = state.snapshot()
    motion = snapshot["avatar"]["body_motion"]

    assert motion["status"] == "blocked"
    assert motion["control_label"] == "waiting_for_ollama"
    assert motion["commands"] == []
    assert snapshot["stats"]["ollama_error"] == "RuntimeError: ollama unavailable"


def test_local_control_schema_clamps_ollama_commands_to_room():
    module = _module()
    room = module.ROOM

    walk = module.normalize_command(
        {"type": "walk_to", "at_ms": -1, "duration_ms": 10, "x": 99, "z": -99},
        room,
    )
    expression = module.normalize_command(
        {"type": "expression", "name": "mouth_open", "intensity": 2},
        room,
    )

    assert walk == {"type": "walk_to", "at_ms": 0, "duration_ms": 300, "x": 4.2, "z": -2.8}
    assert expression["name"] == "mouth_open"
    assert expression["intensity"] == 1
    assert module.normalize_command({"type": "load_comfy_model"}, room) is None
