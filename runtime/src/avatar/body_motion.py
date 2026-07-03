"""Body-motion command contract for avatar locomotion sidecars.

The first AI4AnimationPy track uses this as the stable boundary between GOD and a
motion runtime. The deterministic plan is intentionally small: it lets the
observer prove controllable body motion now, while a future sidecar can replace
the command executor with AI4AnimationPy pose inference.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


BODY_MOTION_SCHEMA_VERSION = 1
BODY_MOTION_SOURCE = "ai4animationpy-contract"

ALLOWED_COMMAND_TYPES = {
    "idle",
    "look_at",
    "walk_to",
    "turn_to",
    "gesture",
    "dance",
}
ALLOWED_GESTURES = {
    "introduce",
    "counting_left_hand",
    "emphasis_right_hand",
    "alphabet_sweep",
    "idle_shift",
}


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _number(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed == parsed else default


def _int_ms(value: Any, default: int, lower: int, upper: int) -> int:
    return int(_clamp(round(_number(value, default)), lower, upper))


def _safe_duration(duration_seconds: float | int | str | None, line: str = "") -> float:
    parsed = _number(duration_seconds, 0.0)
    if parsed > 0:
        return _clamp(parsed, 1.0, 120.0)
    letters = [ch for ch in str(line or "").upper() if "A" <= ch <= "Z"]
    return max(3.8, len(letters or range(26)) * 0.14)


@dataclass(frozen=True)
class BodyMotionCommand:
    type: str
    at_ms: int
    duration_ms: int = 0
    x: float = 0.0
    z: float = 0.0
    yaw_degrees: float = 0.0
    target: str = ""
    name: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": self.type,
            "at_ms": self.at_ms,
            "duration_ms": self.duration_ms,
        }
        if self.type == "walk_to":
            payload.update({"x": self.x, "z": self.z})
        elif self.type == "turn_to":
            payload["yaw_degrees"] = self.yaw_degrees
        elif self.type == "look_at":
            payload["target"] = self.target or "camera"
        elif self.type in {"gesture", "dance"}:
            payload["name"] = self.name
        return payload


@dataclass(frozen=True)
class BodyMotionPlan:
    agent_id: str
    duration_seconds: float
    commands: tuple[BodyMotionCommand, ...]
    status: str = "ready"
    source: str = BODY_MOTION_SOURCE
    target_runtime: str = "ai4animationpy"
    provider: str = "god-deterministic-motion-contract"
    schema_version: int = BODY_MOTION_SCHEMA_VERSION
    pose_stream_contract: tuple[str, ...] = field(
        default=(
            "timestamp_ms",
            "root_position",
            "root_rotation",
            "joint_rotations",
            "contacts",
            "gesture_label",
        )
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source": self.source,
            "provider": self.provider,
            "target_runtime": self.target_runtime,
            "status": self.status,
            "agent_id": self.agent_id,
            "duration_seconds": self.duration_seconds,
            "pose_stream_contract": list(self.pose_stream_contract),
            "commands": [command.to_dict() for command in self.commands],
        }


def sanitize_body_motion_command(raw: dict[str, Any]) -> BodyMotionCommand:
    """Validate and normalize a high-level body command."""

    command_type = str(raw.get("type") or "").strip().lower()
    if command_type not in ALLOWED_COMMAND_TYPES:
        raise ValueError(f"unsupported_body_motion_command:{command_type or 'missing'}")

    at_ms = _int_ms(raw.get("at_ms", raw.get("atMs")), 0, 0, 120_000)
    duration_default = 900 if command_type in {"walk_to", "gesture", "dance"} else 0
    duration_ms = _int_ms(
        raw.get("duration_ms", raw.get("durationMs")),
        duration_default,
        0,
        30_000,
    )

    if command_type == "walk_to":
        return BodyMotionCommand(
            type=command_type,
            at_ms=at_ms,
            duration_ms=max(duration_ms, 250),
            x=_clamp(_number(raw.get("x")), -2.5, 2.5),
            z=_clamp(_number(raw.get("z")), -2.5, 2.5),
        )
    if command_type == "turn_to":
        return BodyMotionCommand(
            type=command_type,
            at_ms=at_ms,
            duration_ms=max(duration_ms, 150),
            yaw_degrees=_clamp(_number(raw.get("yaw_degrees", raw.get("yawDegrees"))), -180, 180),
        )
    if command_type == "look_at":
        target = str(raw.get("target") or "camera").strip().lower()
        if target not in {"camera", "audience", "opponent", "stage_left", "stage_right"}:
            raise ValueError(f"unsupported_body_motion_target:{target or 'missing'}")
        return BodyMotionCommand(
            type=command_type,
            at_ms=at_ms,
            duration_ms=duration_ms,
            target=target,
        )
    if command_type in {"gesture", "dance"}:
        name = str(raw.get("name") or ("alphabet_sweep" if command_type == "dance" else "")).strip()
        if name not in ALLOWED_GESTURES:
            raise ValueError(f"unsupported_body_motion_gesture:{name or 'missing'}")
        return BodyMotionCommand(
            type=command_type,
            at_ms=at_ms,
            duration_ms=max(duration_ms, 250),
            name=name,
        )
    return BodyMotionCommand(type=command_type, at_ms=at_ms, duration_ms=duration_ms)


def build_alphabet_body_motion_plan(
    *,
    agent_id: str = "",
    line: str = "",
    duration_seconds: float | int | str | None = None,
    speaking: bool = True,
) -> BodyMotionPlan:
    """Build the deterministic A-Z body-motion proof plan.

    The command names intentionally match what an AI4AnimationPy sidecar should
    later accept: high-level intent in, normalized pose stream out.
    """

    duration = _safe_duration(duration_seconds, line)
    duration_ms = int(duration * 1000)
    if not speaking:
        return BodyMotionPlan(
            agent_id=str(agent_id or ""),
            duration_seconds=duration,
            status="idle",
            commands=(
                BodyMotionCommand(type="look_at", at_ms=0, target="camera"),
                BodyMotionCommand(type="gesture", at_ms=0, duration_ms=1200, name="idle_shift"),
            ),
        )

    commands = (
        BodyMotionCommand(type="look_at", at_ms=0, target="camera"),
        BodyMotionCommand(type="gesture", at_ms=120, duration_ms=900, name="introduce"),
        BodyMotionCommand(type="walk_to", at_ms=650, duration_ms=1300, x=-0.34, z=0.0),
        BodyMotionCommand(
            type="gesture",
            at_ms=max(900, int(duration_ms * 0.28)),
            duration_ms=1500,
            name="counting_left_hand",
        ),
        BodyMotionCommand(
            type="walk_to",
            at_ms=max(1800, int(duration_ms * 0.48)),
            duration_ms=1400,
            x=0.34,
            z=0.0,
        ),
        BodyMotionCommand(
            type="gesture",
            at_ms=max(2200, int(duration_ms * 0.58)),
            duration_ms=1200,
            name="emphasis_right_hand",
        ),
        BodyMotionCommand(
            type="turn_to",
            at_ms=max(2600, int(duration_ms * 0.68)),
            duration_ms=900,
            yaw_degrees=8.0,
        ),
        BodyMotionCommand(
            type="dance",
            at_ms=max(3000, int(duration_ms * 0.76)),
            duration_ms=max(800, min(1800, duration_ms // 5)),
            name="alphabet_sweep",
        ),
        BodyMotionCommand(
            type="walk_to", at_ms=max(3400, int(duration_ms * 0.84)), duration_ms=1000, x=0.0, z=0.0
        ),
    )
    return BodyMotionPlan(
        agent_id=str(agent_id or ""),
        duration_seconds=duration,
        commands=commands,
    )


def normalize_body_motion_plan(raw: dict[str, Any] | None) -> BodyMotionPlan:
    """Validate a body-motion plan received from config or a sidecar."""

    if not isinstance(raw, dict):
        raise ValueError("invalid_body_motion_plan")
    duration = _safe_duration(raw.get("duration_seconds"))
    commands = tuple(
        sanitize_body_motion_command(command)
        for command in raw.get("commands", [])
        if isinstance(command, dict)
    )
    if not commands:
        raise ValueError("body_motion_plan_has_no_commands")
    return BodyMotionPlan(
        agent_id=str(raw.get("agent_id") or ""),
        duration_seconds=duration,
        commands=commands,
        status=str(raw.get("status") or "ready"),
        source=str(raw.get("source") or BODY_MOTION_SOURCE),
        target_runtime=str(raw.get("target_runtime") or "ai4animationpy"),
        provider=str(raw.get("provider") or "external"),
    )
