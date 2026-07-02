"""Body-motion contract tests for the AI4AnimationPy pivot."""

from __future__ import annotations

import pytest

from avatar import (
    BODY_MOTION_SOURCE,
    build_alphabet_body_motion_plan,
    normalize_body_motion_plan,
    sanitize_body_motion_command,
)


def test_alphabet_body_motion_plan_targets_ai4animationpy_contract():
    plan = build_alphabet_body_motion_plan(
        agent_id="s-alpha",
        line="A B C D E F G.",
        duration_seconds=5.0,
        speaking=True,
    ).to_dict()

    assert plan["source"] == BODY_MOTION_SOURCE
    assert plan["target_runtime"] == "ai4animationpy"
    assert plan["agent_id"] == "s-alpha"
    assert "joint_rotations" in plan["pose_stream_contract"]
    assert any(command["type"] == "walk_to" for command in plan["commands"])
    assert any(command.get("name") == "counting_left_hand" for command in plan["commands"])


def test_idle_body_motion_plan_remains_controllable():
    plan = build_alphabet_body_motion_plan(agent_id="s-beta", speaking=False).to_dict()

    assert plan["status"] == "idle"
    assert plan["commands"][0]["type"] == "look_at"
    assert any(command.get("name") == "idle_shift" for command in plan["commands"])


def test_sanitize_body_motion_command_rejects_unknown_names():
    walk = sanitize_body_motion_command(
        {"type": "walk_to", "at_ms": -100, "duration_ms": 10, "x": 99, "z": -99}
    )

    assert walk.at_ms == 0
    assert walk.duration_ms == 250
    assert walk.x == 2.5
    assert walk.z == -2.5

    with pytest.raises(ValueError, match="unsupported_body_motion_command"):
        sanitize_body_motion_command({"type": "teleport"})
    with pytest.raises(ValueError, match="unsupported_body_motion_gesture"):
        sanitize_body_motion_command({"type": "gesture", "name": "freeform"})


def test_normalize_body_motion_plan_keeps_sidecar_metadata():
    plan = normalize_body_motion_plan(
        {
            "agent_id": "s-alpha",
            "duration_seconds": 8,
            "provider": "ai4animationpy-sidecar",
            "commands": [{"type": "turn_to", "yaw_degrees": 14}],
        }
    )

    assert plan.agent_id == "s-alpha"
    assert plan.provider == "ai4animationpy-sidecar"
    assert plan.commands[0].yaw_degrees == 14
