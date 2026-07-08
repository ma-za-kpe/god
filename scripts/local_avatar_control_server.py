"""Local-only Ollama movement controller for /one avatar control.

Hard constraints for this local loop:
- no Fish audio;
- no LipDub;
- no ComfyUI/LTX/Wan;
- no prerecorded MP4 avatar loops;
- no OBS/YouTube.

Ollama decides movement intent, trajectory, pose, gesture, expression, and
timing. This server only validates/clamps the schema, tracks room state, and
marks the optional AI4AnimationPy Manual-mode execution boundary.
"""

from __future__ import annotations

import argparse
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

AI4ANIMATIONPY_JOINTS = (
    "Hips",
    "Spine",
    "Spine1",
    "Neck",
    "Head",
    "LeftArm",
    "LeftForeArm",
    "RightArm",
    "RightForeArm",
    "LeftUpLeg",
    "LeftLeg",
    "RightUpLeg",
    "RightLeg",
)
POSE_STREAM_FPS = 20
POSE_STREAM_MAX_FRAMES = 180
POSE_STREAM_SOURCE = "ai4animationpy-manual-ollama"
RECOMMENDED_OLLAMA_MODELS = ("qwen3.5:14b", "qwen3.6:27b", "llama3.1:8b")
DEFAULT_OLLAMA_NUM_CTX = 8192

COMMAND_TYPES = {
    "idle",
    "look_at",
    "walk_to",
    "run_to",
    "turn_to",
    "gesture",
    "dance",
    "pose",
    "expression",
}
GESTURES = {
    "introduce",
    "emphasis_right_hand",
    "idle_shift",
    "wave",
    "point",
    "shake_head",
    "nod",
    "react",
    "shrug",
}
POSES = {"stand", "sit"}
EXPRESSIONS = {"neutral", "smile", "focus", "surprise", "mouth_open"}
LOOK_TARGETS = {"camera", "left", "right", "up", "down", "chair", "window", "plant", "floor"}

ROOM = {
    "name": "local_motion_room",
    "bounds": {"x": [-4.2, 4.2], "z": [-2.8, 2.8]},
    "spawn": {"x": 0.0, "z": 0.0, "yaw_degrees": 0.0},
    "waypoints": [
        {"id": "center", "x": 0.0, "z": 0.0, "use": "neutral stance"},
        {"id": "window", "x": -3.15, "z": -1.95, "use": "look out and react"},
        {"id": "chair", "x": 3.05, "z": -1.45, "use": "sit or gesture beside chair"},
        {"id": "plant", "x": -2.85, "z": 1.85, "use": "point or inspect"},
        {"id": "mark_a", "x": 2.65, "z": 1.95, "use": "turn and present"},
    ],
}


def now_ms() -> int:
    return int(time.time() * 1000)


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def clamp(value: Any, lower: float, upper: float, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    if not math.isfinite(parsed):
        parsed = default
    return max(lower, min(upper, parsed))


def clean_text(value: Any, default: str = "") -> str:
    text = str(value or default).replace("\n", " ").strip()
    return " ".join(text.split())[:220]


def slug(value: Any, default: str = "llm-motion") -> str:
    text = str(value or default).strip().lower().replace("-", "_").replace(" ", "_")
    text = "".join(ch for ch in text if ch.isalnum() or ch == "_").strip("_")
    return text[:48] or default


def room_bounds(room: dict[str, Any]) -> tuple[float, float, float, float]:
    bounds = room.get("bounds") or {}
    x_bounds = bounds.get("x") or [-4.2, 4.2]
    z_bounds = bounds.get("z") or [-2.8, 2.8]
    return float(x_bounds[0]), float(x_bounds[1]), float(z_bounds[0]), float(z_bounds[1])


def ai4animationpy_manual_status() -> dict[str, Any]:
    """Return optional AI4AnimationPy Manual-mode availability.

    This does not vendor or require AI4AnimationPy. When installed under the
    CC BY-NC 4.0 license, this branch can use it as the Manual-mode pose
    executor behind the same command contract.
    """

    try:
        import ai4animation  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on local optional package
        return {
            "available": False,
            "execution_mode": "Manual",
            "license_profile": "optional-research-noncommercial",
            "reason": f"{type(exc).__name__}: {exc}",
        }
    return {
        "available": True,
        "execution_mode": "Manual",
        "license_profile": "optional-research-noncommercial",
        "module": getattr(ai4animation, "__name__", "ai4animation"),
        "version": str(getattr(ai4animation, "__version__", "unknown")),
        "path": str(getattr(ai4animation, "__file__", "")),
    }


def _smoothstep(value: float) -> float:
    x = max(0.0, min(1.0, value))
    return x * x * (3.0 - 2.0 * x)


def _add_rotation(target: dict[str, list[float]], joint: str, rotation: tuple[float, float, float], weight: float = 1.0) -> None:
    current = target.setdefault(joint, [0.0, 0.0, 0.0])
    current[0] += rotation[0] * weight
    current[1] += rotation[1] * weight
    current[2] += rotation[2] * weight


def _command_progress(command: dict[str, Any], timestamp_ms: int) -> float | None:
    at_ms = int(command.get("at_ms", 0))
    if timestamp_ms < at_ms:
        return None
    duration_ms = max(1, int(command.get("duration_ms", 1)))
    return max(0.0, min(1.0, (timestamp_ms - at_ms) / duration_ms))


def _locomotion_at(commands: list[dict[str, Any]], timestamp_ms: int, start: list[float]) -> tuple[list[float], str, float, bool]:
    anchor = [float(start[0]), float(start[1])]
    position = [float(start[0]), float(start[1])]
    label = "manual_pose"
    phase = 0.0
    running = False
    for command in commands:
        if command.get("type") not in {"walk_to", "run_to"}:
            continue
        progress = _command_progress(command, timestamp_ms)
        if progress is None:
            continue
        eased = _smoothstep(progress)
        target = [float(command["x"]), float(command["z"])]
        position = [
            anchor[0] + (target[0] - anchor[0]) * eased,
            anchor[1] + (target[1] - anchor[1]) * eased,
        ]
        label = str(command.get("type") or "walk_to")
        running = command.get("type") == "run_to"
        phase = eased
        if progress >= 1.0:
            anchor = target
        else:
            break
    return position, label, phase, running


def _yaw_at(commands: list[dict[str, Any]], timestamp_ms: int, start_yaw: float) -> float:
    yaw = float(start_yaw)
    for command in commands:
        if command.get("type") != "turn_to":
            continue
        progress = _command_progress(command, timestamp_ms)
        if progress is None:
            continue
        yaw = yaw + (float(command.get("yaw_degrees", yaw)) - yaw) * _smoothstep(progress)
    return yaw


def _gesture_joints(name: str, progress: float) -> dict[str, list[float]]:
    joints: dict[str, list[float]] = {}
    wave = math.sin(max(0.0, min(1.0, progress)) * math.pi)
    arc = math.sin(max(0.0, min(1.0, progress)) * math.pi * 2.0)
    settle = _smoothstep(1.0 - abs(progress - 0.5) * 2.0)
    if name == "wave":
        _add_rotation(joints, "RightArm", (-60.0 + arc * 4.0, -16.0, -34.0), wave)
        _add_rotation(joints, "RightForeArm", (-31.0, math.sin(progress * math.pi * 8.0) * 13.0, 13.0), wave)
        _add_rotation(joints, "Spine1", (1.4, -4.5, 1.4), wave)
    elif name == "point":
        _add_rotation(joints, "RightArm", (-60.0, -29.0 + arc * 2.5, -10.0), wave)
        _add_rotation(joints, "RightForeArm", (-6.0, -5.0, 5.0), wave)
        _add_rotation(joints, "Spine1", (1.2, -8.0, 0.0), wave)
        _add_rotation(joints, "Head", (0.0, -8.0, 0.0), wave)
    elif name == "shake_head":
        _add_rotation(joints, "Head", (0.0, math.sin(progress * math.pi * 8.0) * 18.0, 1.2), wave)
        _add_rotation(joints, "Neck", (0.0, math.sin(progress * math.pi * 8.0) * 7.0, 0.0), wave)
    elif name == "nod":
        _add_rotation(joints, "Head", (math.sin(progress * math.pi * 6.0) * 14.0, 0.0, 0.0), wave)
    elif name == "react":
        _add_rotation(joints, "LeftArm", (-32.0 - settle * 7.0, 13.0, 28.0), wave)
        _add_rotation(joints, "RightArm", (-38.0, -11.0, -26.0), wave)
        _add_rotation(joints, "Spine1", (3.0, -2.0, 0.0), wave)
    elif name == "shrug":
        _add_rotation(joints, "LeftArm", (-22.0, 10.0, 18.0), wave)
        _add_rotation(joints, "RightArm", (-24.0, -10.0, -18.0), wave)
        _add_rotation(joints, "Head", (1.0, 0.0, 4.0), wave)
    elif name in {"introduce", "emphasis_right_hand"}:
        _add_rotation(joints, "RightArm", (-48.0, -10.0 + arc * 3.0, -26.0), wave)
        _add_rotation(joints, "RightForeArm", (-24.0 + arc * 5.0, 5.0, 7.0), wave)
        _add_rotation(joints, "Spine1", (2.0, -4.0, 2.0), wave)
    else:
        _add_rotation(joints, "Spine", (1.0, math.sin(progress * math.pi * 2.0) * 2.0, 2.0), wave)
    return joints


def _pose_joints(name: str, progress: float) -> dict[str, list[float]]:
    joints: dict[str, list[float]] = {}
    weight = _smoothstep(progress)
    if name == "sit":
        _add_rotation(joints, "LeftUpLeg", (64.0, 1.0, 5.0), weight)
        _add_rotation(joints, "RightUpLeg", (64.0, -1.0, -5.0), weight)
        _add_rotation(joints, "LeftLeg", (-57.0, 0.0, 0.0), weight)
        _add_rotation(joints, "RightLeg", (-57.0, 0.0, 0.0), weight)
        _add_rotation(joints, "Spine", (-4.5, 0.0, 0.0), weight)
        _add_rotation(joints, "Spine1", (5.0, 0.0, 0.0), weight)
    elif name == "stand":
        _add_rotation(joints, "Spine", (1.5, 0.0, 0.0), weight)
        _add_rotation(joints, "Head", (-1.0, 0.0, 0.0), weight)
    return joints


def _manual_joints_for_commands(commands: list[dict[str, Any]], timestamp_ms: int, phase: float, running: bool) -> tuple[dict[str, list[float]], dict[str, bool], str]:
    joints = {name: [0.0, 0.0, 0.0] for name in AI4ANIMATIONPY_JOINTS}
    label = "ai4_manual"
    contacts = {"LeftFoot": True, "RightFoot": True}
    if phase > 0.0:
        step = math.sin(phase * math.pi * (8.0 if running else 4.0))
        leg = 39.0 if running else 20.0
        arm = 20.0 if running else 10.0
        _add_rotation(joints, "LeftUpLeg", (step * leg, 0.0, 0.0))
        _add_rotation(joints, "RightUpLeg", (-step * leg, 0.0, 0.0))
        _add_rotation(joints, "LeftLeg", (-max(0.0, step) * leg * 0.55, 0.0, 0.0))
        _add_rotation(joints, "RightLeg", (min(0.0, step) * leg * 0.55, 0.0, 0.0))
        _add_rotation(joints, "LeftArm", (-step * arm, 0.0, 5.0))
        _add_rotation(joints, "RightArm", (step * arm, 0.0, -5.0))
        _add_rotation(joints, "Spine", (1.0, math.sin(phase * math.pi * 2.0) * 2.0, 0.0))
        contacts = {"LeftFoot": step <= 0.2, "RightFoot": step >= -0.2}
        label = "run_to" if running else "walk_to"
    for command in commands:
        progress = _command_progress(command, timestamp_ms)
        if progress is None:
            continue
        if command.get("type") in {"gesture", "dance"} and progress <= 1.0:
            for joint, rotation in _gesture_joints(str(command.get("name", "")), progress).items():
                _add_rotation(joints, joint, (rotation[0], rotation[1], rotation[2]))
            label = str(command.get("name") or command.get("type"))
        elif command.get("type") == "pose":
            for joint, rotation in _pose_joints(str(command.get("name", "")), progress).items():
                _add_rotation(joints, joint, (rotation[0], rotation[1], rotation[2]))
            label = str(command.get("name") or "pose")
        elif command.get("type") == "look_at" and progress <= 1.0:
            target = str(command.get("target") or "camera")
            yaw = {"left": 16.0, "right": -16.0, "plant": 12.0, "chair": -12.0}.get(target, 0.0)
            pitch = {"up": -10.0, "down": 10.0, "floor": 12.0}.get(target, 0.0)
            _add_rotation(joints, "Head", (pitch, yaw, 0.0), _smoothstep(progress))
            label = f"look_at_{target}"
    return joints, contacts, label


def _quat(ai4animation: Any, rotation_degrees: list[float]) -> list[float]:
    quaternion = ai4animation.Quaternion.Euler(rotation_degrees)
    return [round(float(value), 6) for value in quaternion.tolist()]


def build_ai4animationpy_pose_stream(
    plan: dict[str, Any],
    *,
    current_position: list[float],
    current_yaw: float,
) -> dict[str, Any] | None:
    try:
        import ai4animation  # type: ignore
    except Exception:
        return None
    commands = list(plan.get("commands") or [])
    duration_seconds = float(plan.get("duration_seconds") or 3.0)
    frame_count = max(2, min(POSE_STREAM_MAX_FRAMES, int(duration_seconds * POSE_STREAM_FPS) + 1))
    duration_ms = max(1, int(duration_seconds * 1000))
    frames: list[dict[str, Any]] = []
    for index in range(frame_count):
        timestamp_ms = round(duration_ms * index / (frame_count - 1))
        root_xz, label, phase, running = _locomotion_at(commands, timestamp_ms, current_position)
        yaw = _yaw_at(commands, timestamp_ms, current_yaw)
        joints, contacts, joint_label = _manual_joints_for_commands(commands, timestamp_ms, phase, running)
        if joint_label != "ai4_manual":
            label = joint_label
        frames.append(
            {
                "timestamp_ms": timestamp_ms,
                "root_position": [round(root_xz[0], 4), 0.0, round(root_xz[1], 4)],
                "root_rotation": _quat(ai4animation, [0.0, yaw, 0.0]),
                "joint_rotations": {joint: _quat(ai4animation, rotation) for joint, rotation in joints.items()},
                "contacts": contacts,
                "gesture_label": label,
            }
        )
    return {
        "schema_version": 1,
        "source": POSE_STREAM_SOURCE,
        "provider": "ai4animationpy:manual",
        "target_runtime": "ai4animationpy",
        "execution_mode": "Manual",
        "license_profile": "optional-research-noncommercial",
        "duration_seconds": duration_seconds,
        "frame_count": len(frames),
        "frames": frames,
    }


def _json_from_text(text: str) -> dict[str, Any] | None:
    cleaned = text.strip()
    if not cleaned:
        return None
    if "```" in cleaned:
        cleaned = cleaned.replace("```json", "```")
        parts = [part.strip() for part in cleaned.split("```") if part.strip()]
        cleaned = parts[0] if parts else cleaned
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            parsed = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError:
            return None
    return parsed if isinstance(parsed, dict) else None


def ollama_generate_json(base_url: str, model: str, prompt: str, timeout: float, num_ctx: int = DEFAULT_OLLAMA_NUM_CTX) -> dict[str, Any]:
    endpoint = urllib.parse.urljoin(base_url.rstrip("/") + "/", "api/generate")
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.55, "top_p": 0.9, "num_ctx": max(2048, int(num_ctx))},
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = json.loads(response.read().decode("utf-8"))
    parsed = _json_from_text(str(raw.get("response", "")))
    if not parsed:
        raise ValueError("ollama_returned_no_json")
    return parsed


def query_ollama_persona(base_url: str, model: str, timeout: float, num_ctx: int = DEFAULT_OLLAMA_NUM_CTX) -> dict[str, Any] | None:
    prompt = (
        "Create one local VRM avatar-control persona for a silent embodied character demo. "
        "The avatar lives in a small room and must make decisions about walking, turning, "
        "looking, gestures, expression, posture, and mouth openness without audio. "
        "Return JSON only with keys name, archetype, summary, style, movement_bias. "
        "Do not include a canned action sequence. Movement will be decided live "
        "each step by the model."
    )
    try:
        parsed = ollama_generate_json(base_url, model, prompt, timeout, num_ctx)
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return None
    name = clean_text(parsed.get("name"), "Kairo")[:48] or "Kairo"
    return {
        "soul_id": "local-vrm-agent-001",
        "current_name": name,
        "archetype": clean_text(parsed.get("archetype"), "embodied_controller")[:64],
        "persona": {
            "name": name,
            "summary": clean_text(parsed.get("summary"), "Local avatar-control persona."),
            "style": clean_text(parsed.get("style"), "physically expressive"),
            "movement_bias": clean_text(parsed.get("movement_bias"), "grounded, readable, room-aware motion"),
        },
        "provider": f"ollama:{model}",
    }


def control_prompt(
    *,
    persona: dict[str, Any],
    room: dict[str, Any],
    current_position: list[float],
    current_yaw: float,
    last_intent: str,
    operator_intent: str,
) -> str:
    return (
        "You are the movement brain for one silent VRM avatar in a small room. "
        "You must author the avatar's next 2-5 seconds of motion as JSON only. "
        "No audio, no video clips, no diffusion, no prerecorded loops. "
        "Use grounded room movement: choose real x/z targets inside bounds, avoid "
        "running in place, move between visible waypoints, include weight shift "
        "through pose/gesture/expression, and use arm gestures only when they "
        "match the intent. Do not repeat the previous action unless the operator "
        "explicitly asks for it. A good plan has one locomotion choice, one facing "
        "choice, and at most two expressive details.\n"
        f"Persona: {json.dumps(persona.get('persona', {}), separators=(',', ':'))}\n"
        f"Room: {json.dumps(room, separators=(',', ':'))}\n"
        f"Current position: x={current_position[0]:.2f}, z={current_position[1]:.2f}, "
        f"yaw_degrees={current_yaw:.1f}. Last intent: {last_intent or 'none'}. "
        f"Operator intent: {operator_intent or 'decide freely'}.\n"
        "Allowed command types: look_at, walk_to, run_to, turn_to, gesture, pose, expression. "
        f"Allowed gestures: {', '.join(sorted(GESTURES))}. "
        f"Allowed poses: {', '.join(sorted(POSES))}. "
        f"Allowed expressions: {', '.join(sorted(EXPRESSIONS))}. "
        "Return JSON with shape: "
        '{"intent":"short reason","control_label":"short_label","duration_seconds":4,'
        '"commands":[{"type":"walk_to","at_ms":0,"duration_ms":1200,"x":-1.2,"z":0.4},'
        '{"type":"turn_to","at_ms":1000,"duration_ms":500,"yaw_degrees":35},'
        '{"type":"gesture","at_ms":1200,"duration_ms":1100,"name":"point"},'
        '{"type":"expression","at_ms":1200,"duration_ms":900,"name":"focus","intensity":0.7}]}'
    )


def normalize_command(raw: dict[str, Any], room: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    command_type = slug(raw.get("type"), "")
    if command_type not in COMMAND_TYPES:
        return None
    at_ms = int(clamp(raw.get("at_ms", raw.get("atMs", 0)), 0, 120000, 0))
    duration_ms = int(clamp(raw.get("duration_ms", raw.get("durationMs", 0)), 0, 30000, 0))

    if command_type in {"walk_to", "run_to"}:
        min_x, max_x, min_z, max_z = room_bounds(room)
        return {
            "type": command_type,
            "at_ms": at_ms,
            "duration_ms": max(300, duration_ms),
            "x": round(clamp(raw.get("x"), min_x, max_x, 0.0), 3),
            "z": round(clamp(raw.get("z"), min_z, max_z, 0.0), 3),
        }
    if command_type == "turn_to":
        return {
            "type": command_type,
            "at_ms": at_ms,
            "duration_ms": max(150, duration_ms),
            "yaw_degrees": round(clamp(raw.get("yaw_degrees", raw.get("yawDegrees", 0)), -180, 180, 0), 2),
        }
    if command_type == "look_at":
        target = slug(raw.get("target"), "camera")
        return {
            "type": command_type,
            "at_ms": at_ms,
            "duration_ms": duration_ms,
            "target": target if target in LOOK_TARGETS else "camera",
        }
    if command_type == "gesture":
        name = slug(raw.get("name"), "")
        if name not in GESTURES:
            return None
        return {"type": command_type, "at_ms": at_ms, "duration_ms": max(250, duration_ms), "name": name}
    if command_type == "dance":
        name = slug(raw.get("name"), "idle_shift")
        if name not in GESTURES:
            name = "idle_shift"
        return {"type": command_type, "at_ms": at_ms, "duration_ms": max(250, duration_ms), "name": name}
    if command_type == "pose":
        name = slug(raw.get("name"), "")
        if name not in POSES:
            return None
        return {"type": command_type, "at_ms": at_ms, "duration_ms": max(250, duration_ms), "name": name}
    if command_type == "expression":
        name = slug(raw.get("name"), "")
        if name not in EXPRESSIONS:
            return None
        return {
            "type": command_type,
            "at_ms": at_ms,
            "duration_ms": max(150, duration_ms),
            "name": name,
            "intensity": round(clamp(raw.get("intensity", 1), 0, 1, 1), 3),
        }
    return {"type": command_type, "at_ms": at_ms, "duration_ms": duration_ms}


def normalize_llm_control_plan(
    raw: dict[str, Any] | None,
    *,
    agent_id: str,
    started_at_ms: int,
    provider: str,
    room: dict[str, Any],
    current_position: list[float],
    current_yaw: float,
    ai4_status: dict[str, Any],
) -> dict[str, Any]:
    parsed = raw if isinstance(raw, dict) else {}
    duration = clamp(parsed.get("duration_seconds", parsed.get("durationSeconds", 4.0)), 1.5, 8.0, 4.0)
    commands = [
        command
        for command in (normalize_command(item, room) for item in parsed.get("commands", []))
        if command is not None
    ][:10]
    commands.sort(key=lambda item: (item.get("at_ms", 0), item.get("type", "")))

    status = "ready" if commands else "blocked"
    intent = clean_text(parsed.get("intent"), "waiting for Ollama movement plan")
    control_label = slug(parsed.get("control_label"), "") or slug(intent, "llm-motion")
    if not commands:
        control_label = "waiting_for_ollama"
    trajectory = [{"x": round(current_position[0], 3), "z": round(current_position[1], 3), "label": "start"}]
    for command in commands:
        if command["type"] in {"walk_to", "run_to"}:
            trajectory.append(
                {
                    "x": command["x"],
                    "z": command["z"],
                    "label": command["type"],
                    "at_ms": command["at_ms"],
                }
            )

    block_reason = ""
    pose_stream = None
    if status == "ready" and not ai4_status.get("available"):
        block_reason = "ai4animationpy_unavailable"
        status = "blocked"
        control_label = block_reason
        intent = "AI4AnimationPy is required for local avatar control; no browser-side motion fallback is allowed"
        commands = []
        trajectory = [{"x": round(current_position[0], 3), "z": round(current_position[1], 3), "label": "start"}]
    elif status == "ready":
        pose_stream = build_ai4animationpy_pose_stream(
            {
                "duration_seconds": duration,
                "commands": commands,
            },
            current_position=current_position,
            current_yaw=current_yaw,
        )
        if pose_stream is None:
            block_reason = "ai4animationpy_pose_stream_unavailable"
            status = "blocked"
            control_label = block_reason
            intent = "AI4AnimationPy did not produce a pose stream; no browser-side motion fallback is allowed"
            commands = []
            trajectory = [{"x": round(current_position[0], 3), "z": round(current_position[1], 3), "label": "start"}]

    motion_backend = "ai4animationpy-manual-pose-stream" if pose_stream else "blocked-no-ai4animationpy"
    return {
        "schema_version": 1,
        "source": "ollama-llm-avatar-control",
        "provider": provider,
        "target_runtime": "ai4animationpy",
        "execution_mode": "Manual",
        "motion_backend": motion_backend,
        "ai4animationpy": ai4_status,
        "status": status,
        "agent_id": agent_id,
        "started_at_ms": started_at_ms,
        "duration_seconds": duration,
        "control_label": control_label,
        "intent": intent,
        "root_start": [round(current_position[0], 3), round(current_position[1], 3)],
        "room": room,
        "trajectory": trajectory,
        "commands": commands,
        **({"blocked_reason": block_reason} if block_reason else {}),
        **({"pose_stream": pose_stream} if pose_stream else {}),
    }


class ControlState:
    def __init__(
        self,
        persona: dict[str, Any],
        *,
        ollama_url: str,
        ollama_model: str,
        ollama_timeout: float,
        ollama_num_ctx: int = DEFAULT_OLLAMA_NUM_CTX,
        decision_provider: Callable[[str], dict[str, Any]] | None = None,
    ) -> None:
        self.persona = persona
        self.ollama_url = ollama_url
        self.ollama_model = ollama_model
        self.ollama_timeout = ollama_timeout
        self.ollama_num_ctx = max(2048, int(ollama_num_ctx))
        self.decision_provider = decision_provider
        self.room = ROOM
        spawn = self.room["spawn"]
        self.position = [float(spawn["x"]), float(spawn["z"])]
        self.yaw_degrees = float(spawn["yaw_degrees"])
        self.last_intent = ""
        self.operator_intent = ""
        self.current_plan: dict[str, Any] | None = None
        self.current_caption = ""
        self.plan_expires_ms = 0
        self.events: list[dict[str, Any]] = []
        self.ai4_status = ai4animationpy_manual_status()
        self.last_ollama_error = ""

    @property
    def agent(self) -> dict[str, Any]:
        return {
            "soul_id": self.persona["soul_id"],
            "current_name": self.persona["current_name"],
            "archetype": self.persona["archetype"],
            "is_alive": True,
            "avatar_control": True,
        }

    def set_operator_intent(self, intent: str) -> dict[str, Any]:
        self.operator_intent = clean_text(intent, "operator asks for movement")
        self.plan_expires_ms = 0
        event = {
            "event_id": f"operator:{now_ms()}",
            "event_type": "avatar.control.operator_intent",
            "timestamp": iso_now(),
            "intent": self.operator_intent,
        }
        self.events.insert(0, event)
        self.events = self.events[:40]
        return event

    def _ask_ollama(self, prompt: str) -> dict[str, Any]:
        if self.decision_provider:
            return self.decision_provider(prompt)
        return ollama_generate_json(
            self.ollama_url,
            self.ollama_model,
            prompt,
            self.ollama_timeout,
            self.ollama_num_ctx,
        )

    def _update_room_state_from_plan(self, plan: dict[str, Any]) -> None:
        for command in plan.get("commands", []):
            if command.get("type") in {"walk_to", "run_to"}:
                self.position = [float(command["x"]), float(command["z"])]
            elif command.get("type") == "turn_to":
                self.yaw_degrees = float(command.get("yaw_degrees", self.yaw_degrees))

    def ensure_plan(self) -> dict[str, Any]:
        current_ms = now_ms()
        if self.current_plan and current_ms < self.plan_expires_ms:
            return self.current_plan

        prompt = control_prompt(
            persona=self.persona,
            room=self.room,
            current_position=self.position,
            current_yaw=self.yaw_degrees,
            last_intent=self.last_intent,
            operator_intent=self.operator_intent,
        )
        try:
            raw_plan = self._ask_ollama(prompt)
            self.last_ollama_error = ""
        except Exception as exc:
            raw_plan = None
            self.last_ollama_error = f"{type(exc).__name__}: {exc}"

        plan = normalize_llm_control_plan(
            raw_plan,
            agent_id=self.persona["soul_id"],
            started_at_ms=current_ms,
            provider=f"ollama:{self.ollama_model}",
            room=self.room,
            current_position=self.position,
            current_yaw=self.yaw_degrees,
            ai4_status=self.ai4_status,
        )
        self.current_plan = plan
        self.last_intent = str(plan.get("intent") or "")
        self.current_caption = f"{self.persona['current_name']}: {self.last_intent}"
        self.plan_expires_ms = current_ms + int(float(plan.get("duration_seconds", 3.0)) * 1000)
        if plan.get("status") == "ready":
            self._update_room_state_from_plan(plan)
            self.operator_intent = ""
        return plan

    def snapshot(self) -> dict[str, Any]:
        plan = self.ensure_plan()
        agent_id = self.persona["soul_id"]
        return {
            "world_id": "local-avatar-control",
            "server_time": iso_now(),
            "agents": [self.agent],
            "events": list(self.events),
            "stats": {
                "agent_count": 1,
                "mode": "local-avatar-control",
                "movement_source": "ollama",
                "ollama_model": self.ollama_model,
                "ollama_num_ctx": self.ollama_num_ctx,
                "recommended_models": list(RECOMMENDED_OLLAMA_MODELS),
                "ollama_error": self.last_ollama_error,
                "ai4animationpy_manual": self.ai4_status,
                "audio": "disabled",
                "video_loops": "disabled",
            },
            "room": self.room,
            "avatar": {
                "control_mode": "llm-avatar-control",
                "control_provider": f"ollama:{self.ollama_model}",
                "control_label": plan.get("control_label", "llm-motion"),
                "control_started_at_ms": plan.get("started_at_ms", now_ms()),
                "controller_soul_id": agent_id,
                "agent_id": agent_id,
                "caption": self.current_caption,
                "persona": self.persona.get("persona", {}),
                "room_state": {
                    "position": {"x": round(self.position[0], 3), "z": round(self.position[1], 3)},
                    "yaw_degrees": round(self.yaw_degrees, 3),
                },
                "body_motion": plan,
                "life": {"breathing_phase": 0.5, "mouth_amplitude": 0, "blink_state": False},
            },
            "voice": {"status": "disabled", "reason": "local avatar control does not use Fish audio"},
            "last_dialogue_turn": None,
        }


class Handler(BaseHTTPRequestHandler):
    state: ControlState

    def _send_json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self._send_json({"ok": True})

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/":
            self._send_json(
                {
                    "ok": True,
                    "service": "local-avatar-control",
                    "observer_url": "http://127.0.0.1:5173/one?control=1",
                    "endpoints": ["/health", "/world/snapshot", "/agents", "/events", "/stats", "/control?intent=wave"],
                }
            )
            return
        if parsed.path == "/health":
            self._send_json(
                {
                    "ok": True,
                    "mode": "local-avatar-control",
                    "movement_source": "ollama",
                    "ollama_model": self.state.ollama_model,
                    "ollama_num_ctx": self.state.ollama_num_ctx,
                    "recommended_models": list(RECOMMENDED_OLLAMA_MODELS),
                    "ai4animationpy_manual": self.state.ai4_status,
                }
            )
            return
        if parsed.path == "/agents":
            self._send_json({"agents": [self.state.agent]})
            return
        if parsed.path == "/events":
            self._send_json({"events": list(self.state.events)})
            return
        if parsed.path == "/stats":
            self._send_json(self.state.snapshot()["stats"])
            return
        if parsed.path == "/world/snapshot":
            self._send_json(self.state.snapshot())
            return
        if parsed.path == "/control":
            query = urllib.parse.parse_qs(parsed.query)
            intent = (query.get("intent") or query.get("action") or ["move naturally in the room"])[0]
            event = self.state.set_operator_intent(intent)
            self._send_json({"ok": True, "event": event, "snapshot": self.state.snapshot()})
            return
        self._send_json({"error": "not_found", "path": parsed.path}, status=404)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/control":
            self._send_json({"error": "not_found", "path": parsed.path}, status=404)
            return
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            payload = {}
        intent = clean_text(payload.get("intent") or payload.get("action"), "move naturally in the room")
        event = self.state.set_operator_intent(intent)
        self._send_json({"ok": True, "event": event, "snapshot": self.state.snapshot()})

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[local-avatar-control] {self.address_string()} - {fmt % args}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--ollama-url", default="http://localhost:11434")
    parser.add_argument("--ollama-model", default="llama3.1:8b")
    parser.add_argument("--ollama-timeout", type=float, default=8.0)
    parser.add_argument("--ollama-num-ctx", type=int, default=DEFAULT_OLLAMA_NUM_CTX)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    persona = query_ollama_persona(args.ollama_url, args.ollama_model, args.ollama_timeout, args.ollama_num_ctx)
    if persona is None:
        raise SystemExit(
            "Ollama is required for local avatar control. Start Ollama and make "
            f"sure model {args.ollama_model!r} is available; no deterministic movement substitute is allowed."
        )
    Handler.state = ControlState(
        persona=persona,
        ollama_url=args.ollama_url,
        ollama_model=args.ollama_model,
        ollama_timeout=args.ollama_timeout,
        ollama_num_ctx=args.ollama_num_ctx,
    )
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(
        f"[local-avatar-control] serving http://{args.host}:{args.port} "
        f"with {persona['current_name']} via ollama:{args.ollama_model}"
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
