"""Neutral avatar pose-stream contract for optional motion sidecars.

The AI4AnimationPy pivot is license-sensitive, so this module owns only GOD's
data boundary. It can read a small NPZ motion export for evaluation, but it does
not import or vendor AI4AnimationPy.
"""

from __future__ import annotations

import ast
import json
import math
import struct
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


POSE_STREAM_SCHEMA_VERSION = 1
POSE_STREAM_SOURCE = "ai4animationpy-eval"
POSE_STREAM_LICENSE_PROFILE = "optional-research-noncommercial"

MAX_POSE_FRAMES = 3_600
MAX_POSE_JOINTS = 256
MAX_ROOT_ABS_METERS = 100.0
MAX_NPZ_BYTES = 128 * 1024 * 1024
MAX_NPY_MEMBER_BYTES = 64 * 1024 * 1024
MAX_NPZ_MEMBERS = 32
MAX_NPY_HEADER_BYTES = 16 * 1024

_JOINT_ROTATION_KEYS = (
    "joint_rotations",
    "local_rotations",
    "bone_rotations",
    "quaternions",
    "rotations",
)
_ROOT_POSITION_KEYS = ("root_position", "root_positions", "root_translation", "root_translations")
_ROOT_ROTATION_KEYS = ("root_rotation", "root_rotations", "root_orientation", "root_orientations")
_POSITION_KEYS = ("joint_positions", "bone_positions", "positions")
_TIMESTAMP_MS_KEYS = ("timestamps_ms", "time_ms", "frame_times_ms")
_TIMESTAMP_SECOND_KEYS = ("timestamps", "times", "time_seconds")
_JOINT_NAME_KEYS = ("joint_names", "bone_names", "names")
_CONTACT_NAME_KEYS = ("contact_names", "contacts_names")
_FRAMERATE_KEYS = ("framerate", "fps")
_RELEVANT_NPZ_KEYS = frozenset(
    (
        *_JOINT_ROTATION_KEYS,
        *_ROOT_POSITION_KEYS,
        *_ROOT_ROTATION_KEYS,
        *_POSITION_KEYS,
        *_TIMESTAMP_MS_KEYS,
        *_TIMESTAMP_SECOND_KEYS,
        *_JOINT_NAME_KEYS,
        *_CONTACT_NAME_KEYS,
        *_FRAMERATE_KEYS,
        "contacts",
        "contact_states",
        "gesture_label",
        "gesture_labels",
    )
)


@dataclass(frozen=True)
class PoseStreamFrame:
    timestamp_ms: int
    root_position: tuple[float, float, float]
    root_rotation: tuple[float, float, float, float]
    joint_rotations: dict[str, tuple[float, float, float, float]]
    contacts: dict[str, bool]
    gesture_label: str = "motion_import"

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp_ms": self.timestamp_ms,
            "root_position": list(self.root_position),
            "root_rotation": list(self.root_rotation),
            "joint_rotations": {
                name: list(rotation) for name, rotation in self.joint_rotations.items()
            },
            "contacts": dict(self.contacts),
            "gesture_label": self.gesture_label,
        }


@dataclass(frozen=True)
class PoseStream:
    agent_id: str
    duration_seconds: float
    frames: tuple[PoseStreamFrame, ...]
    source: str = POSE_STREAM_SOURCE
    target_runtime: str = "ai4animationpy"
    provider: str = "god-motion-eval-harness"
    license_profile: str = POSE_STREAM_LICENSE_PROFILE
    schema_version: int = POSE_STREAM_SCHEMA_VERSION

    def to_dict(self, *, include_frames: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": self.schema_version,
            "source": self.source,
            "provider": self.provider,
            "target_runtime": self.target_runtime,
            "license_profile": self.license_profile,
            "agent_id": self.agent_id,
            "duration_seconds": self.duration_seconds,
            "frame_count": len(self.frames),
        }
        if include_frames:
            payload["frames"] = [frame.to_dict() for frame in self.frames]
        return payload


def load_npz_pose_stream(
    path: str | Path,
    *,
    agent_id: str = "",
    source: str = POSE_STREAM_SOURCE,
    target_runtime: str = "ai4animationpy",
    max_frames: int = MAX_POSE_FRAMES,
    stride: int = 1,
    fps: float = 30.0,
) -> PoseStream:
    """Load a motion NPZ into GOD's neutral pose-stream contract.

    The loader accepts the field names used by this branch and common aliases
    used by motion-export tools. If NumPy is installed it uses ``numpy.load``;
    otherwise it falls back to a small NPY reader that supports numeric arrays.
    """

    arrays = _load_npz_arrays(Path(path))
    return build_pose_stream_from_arrays(
        arrays,
        agent_id=agent_id,
        source=source,
        target_runtime=target_runtime,
        max_frames=max_frames,
        stride=stride,
        fps=fps,
    )


def build_pose_stream_from_arrays(
    arrays: dict[str, Any],
    *,
    agent_id: str = "",
    source: str = POSE_STREAM_SOURCE,
    target_runtime: str = "ai4animationpy",
    max_frames: int = MAX_POSE_FRAMES,
    stride: int = 1,
    fps: float = 30.0,
) -> PoseStream:
    """Normalize decoded motion arrays into a validated pose stream."""

    if not arrays:
        raise ValueError("pose_stream_npz_has_no_arrays")
    stride = max(1, int(stride))
    max_frames = max(1, min(int(max_frames), MAX_POSE_FRAMES))
    fps = _resolve_fps(arrays, fallback=fps)
    if fps <= 0:
        raise ValueError("pose_stream_fps_must_be_positive")

    joint_rotations_raw = _first_present(arrays, _JOINT_ROTATION_KEYS)
    if joint_rotations_raw is None:
        raise ValueError("pose_stream_missing_joint_rotations")
    joint_rotations = _as_nested_list(joint_rotations_raw)
    shape = _shape(joint_rotations)
    if len(shape) != 3 or shape[2] != 4:
        raise ValueError("pose_stream_joint_rotations_must_be_frames_by_joints_by_quat")

    total_frames = shape[0]
    joint_count = shape[1]
    if total_frames <= 0:
        raise ValueError("pose_stream_has_no_frames")
    if joint_count <= 0:
        raise ValueError("pose_stream_has_no_joints")
    if joint_count > MAX_POSE_JOINTS:
        raise ValueError("pose_stream_has_too_many_joints")

    frame_indexes = list(range(0, total_frames, stride))[:max_frames]
    joint_names = _names_for_count(_first_present(arrays, _JOINT_NAME_KEYS), joint_count, "joint")
    contact_values = _first_present(arrays, ("contacts", "contact_states"))
    contact_names: list[str] = []
    if contact_values is not None:
        contact_shape = _shape(_as_nested_list(contact_values))
        if len(contact_shape) != 2 or contact_shape[0] != total_frames:
            raise ValueError("pose_stream_contacts_must_be_frames_by_contacts")
        contact_names = _names_for_count(
            _first_present(arrays, _CONTACT_NAME_KEYS), contact_shape[1], "contact"
        )

    timestamps_ms = _resolve_timestamps(arrays, total_frames=total_frames, fps=fps)
    root_positions = _resolve_root_positions(arrays, total_frames=total_frames)
    root_rotations = _resolve_root_rotations(arrays, joint_rotations, total_frames=total_frames)
    gesture_labels = _resolve_gesture_labels(arrays, total_frames=total_frames)

    frames = tuple(
        _frame_from_arrays(
            frame_index=index,
            timestamp_ms=timestamps_ms[index],
            root_position=root_positions[index],
            root_rotation=root_rotations[index],
            joint_names=joint_names,
            joint_rotations=joint_rotations[index],
            contact_names=contact_names,
            contact_values=contact_values[index] if contact_values is not None else None,
            gesture_label=gesture_labels[index],
        )
        for index in frame_indexes
    )
    return normalize_pose_stream(
        {
            "agent_id": str(agent_id or ""),
            "source": source,
            "target_runtime": target_runtime,
            "duration_seconds": frames[-1].timestamp_ms / 1000.0 if frames else 0.0,
            "frames": [frame.to_dict() for frame in frames],
        }
    )


def normalize_pose_stream(raw: dict[str, Any] | None) -> PoseStream:
    """Validate and normalize a pose-stream payload from a sidecar or fixture."""

    if not isinstance(raw, dict):
        raise ValueError("invalid_pose_stream")
    raw_frames = raw.get("frames")
    if not isinstance(raw_frames, list) or not raw_frames:
        raise ValueError("pose_stream_has_no_frames")
    if len(raw_frames) > MAX_POSE_FRAMES:
        raise ValueError("pose_stream_has_too_many_frames")

    frames: list[PoseStreamFrame] = []
    previous_timestamp = -1
    for raw_frame in raw_frames:
        frame = normalize_pose_stream_frame(raw_frame)
        if frame.timestamp_ms <= previous_timestamp:
            raise ValueError("pose_stream_timestamps_must_increase")
        previous_timestamp = frame.timestamp_ms
        frames.append(frame)

    declared_duration = _finite_float(raw.get("duration_seconds", 0.0), field="duration_seconds")
    inferred_duration = frames[-1].timestamp_ms / 1000.0
    duration_seconds = max(declared_duration, inferred_duration)

    return PoseStream(
        agent_id=str(raw.get("agent_id") or ""),
        source=str(raw.get("source") or POSE_STREAM_SOURCE),
        target_runtime=str(raw.get("target_runtime") or "ai4animationpy"),
        provider=str(raw.get("provider") or "god-motion-eval-harness"),
        license_profile=str(raw.get("license_profile") or POSE_STREAM_LICENSE_PROFILE),
        duration_seconds=round(duration_seconds, 6),
        frames=tuple(frames),
    )


def normalize_pose_stream_frame(raw: dict[str, Any] | None) -> PoseStreamFrame:
    """Validate and normalize one pose frame."""

    if not isinstance(raw, dict):
        raise ValueError("invalid_pose_stream_frame")
    timestamp_ms = int(round(_finite_float(raw.get("timestamp_ms", 0), field="timestamp_ms")))
    if timestamp_ms < 0:
        raise ValueError("pose_stream_timestamp_must_be_nonnegative")

    root_position = _vector3(raw.get("root_position"), field="root_position")
    for value in root_position:
        if abs(value) > MAX_ROOT_ABS_METERS:
            raise ValueError("pose_stream_root_position_out_of_bounds")

    root_rotation = _quaternion(raw.get("root_rotation"), field="root_rotation")
    joint_rotations_raw = raw.get("joint_rotations")
    if not isinstance(joint_rotations_raw, dict) or not joint_rotations_raw:
        raise ValueError("pose_stream_frame_has_no_joint_rotations")
    if len(joint_rotations_raw) > MAX_POSE_JOINTS:
        raise ValueError("pose_stream_frame_has_too_many_joints")
    joint_rotations = {
        _safe_name(name, fallback=f"joint_{index}"): _quaternion(value, field="joint_rotation")
        for index, (name, value) in enumerate(joint_rotations_raw.items())
    }

    contacts_raw = raw.get("contacts", {})
    if contacts_raw is None:
        contacts_raw = {}
    if not isinstance(contacts_raw, dict):
        raise ValueError("pose_stream_contacts_must_be_object")
    contacts = {
        _safe_name(name, fallback=f"contact_{index}"): bool(value)
        for index, (name, value) in enumerate(contacts_raw.items())
    }

    gesture_label = _safe_name(
        raw.get("gesture_label") or "motion_import", fallback="motion_import"
    )
    return PoseStreamFrame(
        timestamp_ms=timestamp_ms,
        root_position=root_position,
        root_rotation=root_rotation,
        joint_rotations=joint_rotations,
        contacts=contacts,
        gesture_label=gesture_label,
    )


def pose_stream_summary(stream: PoseStream) -> dict[str, Any]:
    """Return diagnostics suitable for PR comments and field proof logs."""

    frames = stream.frames
    joint_names = set()
    contact_names = set()
    root_min = [math.inf, math.inf, math.inf]
    root_max = [-math.inf, -math.inf, -math.inf]
    for frame in frames:
        joint_names.update(frame.joint_rotations)
        contact_names.update(frame.contacts)
        for index, value in enumerate(frame.root_position):
            root_min[index] = min(root_min[index], value)
            root_max[index] = max(root_max[index], value)
    return {
        "schema_version": stream.schema_version,
        "source": stream.source,
        "target_runtime": stream.target_runtime,
        "license_profile": stream.license_profile,
        "agent_id": stream.agent_id,
        "frame_count": len(frames),
        "duration_seconds": stream.duration_seconds,
        "first_timestamp_ms": frames[0].timestamp_ms if frames else None,
        "last_timestamp_ms": frames[-1].timestamp_ms if frames else None,
        "joint_count": len(joint_names),
        "contact_count": len(contact_names),
        "contact_names": sorted(contact_names),
        "root_bounds": {
            "min": [round(value, 6) for value in root_min],
            "max": [round(value, 6) for value in root_max],
        },
    }


def iter_pose_stream_ndjson(stream: PoseStream) -> Iterable[str]:
    """Yield metadata and frame records as NDJSON lines."""

    metadata = stream.to_dict(include_frames=False)
    metadata["type"] = "pose_stream"
    yield json.dumps(metadata, sort_keys=True)
    for frame in stream.frames:
        payload = frame.to_dict()
        payload["type"] = "pose_frame"
        yield json.dumps(payload, sort_keys=True)


def _frame_from_arrays(
    *,
    frame_index: int,
    timestamp_ms: int,
    root_position: Any,
    root_rotation: Any,
    joint_names: list[str],
    joint_rotations: Any,
    contact_names: list[str],
    contact_values: Any,
    gesture_label: str,
) -> PoseStreamFrame:
    contacts = {
        name: bool(_finite_float(value, field="contact"))
        for name, value in zip(contact_names, _as_sequence(contact_values))
    }
    return normalize_pose_stream_frame(
        {
            "timestamp_ms": timestamp_ms,
            "root_position": root_position,
            "root_rotation": root_rotation,
            "joint_rotations": {
                name: rotation for name, rotation in zip(joint_names, _as_sequence(joint_rotations))
            },
            "contacts": contacts,
            "gesture_label": gesture_label or f"motion_import_{frame_index}",
        }
    )


def _load_npz_arrays(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"pose_stream_npz_not_found:{path}")
    _validate_npz_container(path)
    try:
        import numpy as np  # type: ignore
    except ModuleNotFoundError:
        return _load_npz_arrays_without_numpy(path)

    arrays: dict[str, Any] = {}
    with np.load(path, allow_pickle=False) as data:
        for name in data.files:
            key = Path(name).stem
            if key not in _RELEVANT_NPZ_KEYS:
                continue
            try:
                arrays[key] = data[name].tolist()
            except ValueError as exc:
                if "Object arrays cannot be loaded" not in str(exc):
                    raise
    return arrays


def _load_npz_arrays_without_numpy(path: Path) -> dict[str, Any]:
    arrays: dict[str, Any] = {}
    with zipfile.ZipFile(path) as archive:
        for member in archive.namelist():
            if not member.endswith(".npy"):
                continue
            key = Path(member).stem
            if key not in _RELEVANT_NPZ_KEYS:
                continue
            try:
                arrays[key] = _read_npy_subset(archive.read(member))
            except ValueError as exc:
                if "pose_stream_npy_dtype_not_supported" not in str(exc):
                    raise
    return arrays


def _validate_npz_container(path: Path) -> None:
    if path.stat().st_size > MAX_NPZ_BYTES:
        raise ValueError("pose_stream_npz_too_large")
    with zipfile.ZipFile(path) as archive:
        members = [member for member in archive.infolist() if member.filename.endswith(".npy")]
        if not members:
            raise ValueError("pose_stream_npz_has_no_npy_members")
        if len(members) > MAX_NPZ_MEMBERS:
            raise ValueError("pose_stream_npz_has_too_many_members")
        names = set()
        total_size = 0
        for member in members:
            if member.filename in names:
                raise ValueError("pose_stream_npz_has_duplicate_members")
            names.add(member.filename)
            total_size += member.file_size
            if member.file_size > MAX_NPY_MEMBER_BYTES:
                raise ValueError("pose_stream_npy_member_too_large")
        if total_size > MAX_NPZ_BYTES:
            raise ValueError("pose_stream_npz_uncompressed_size_too_large")


def _read_npy_subset(data: bytes) -> Any:
    if not data.startswith(b"\x93NUMPY"):
        raise ValueError("pose_stream_npy_has_bad_magic")
    major = data[6]
    if major == 1:
        header_len = struct.unpack("<H", data[8:10])[0]
        offset = 10
    elif major == 2:
        header_len = struct.unpack("<I", data[8:12])[0]
        offset = 12
    else:
        raise ValueError("pose_stream_npy_version_not_supported")
    if header_len > MAX_NPY_HEADER_BYTES:
        raise ValueError("pose_stream_npy_header_too_large")

    header = ast.literal_eval(data[offset : offset + header_len].decode("latin1").strip())
    body = data[offset + header_len :]
    descr = str(header.get("descr"))
    shape = tuple(int(item) for item in header.get("shape", ()))
    if header.get("fortran_order"):
        raise ValueError("pose_stream_npy_fortran_order_not_supported")

    fmt, item_size = _struct_format_for_descr(descr)
    count = math.prod(shape) if shape else 1
    expected_bytes = count * item_size
    if len(body) < expected_bytes:
        raise ValueError("pose_stream_npy_truncated")
    values = list(struct.unpack("<" + fmt * count, body[:expected_bytes]))
    return _reshape(values, shape)


def _struct_format_for_descr(descr: str) -> tuple[str, int]:
    if descr.startswith(">"):
        raise ValueError(f"pose_stream_npy_dtype_not_supported:{descr}")
    type_code = descr[-2:]
    if type_code == "f8":
        return "d", 8
    if type_code == "f4":
        return "f", 4
    if type_code == "i8":
        return "q", 8
    if type_code == "i4":
        return "i", 4
    if type_code == "i2":
        return "h", 2
    if type_code == "u8":
        return "Q", 8
    if type_code == "u4":
        return "I", 4
    if type_code == "u2":
        return "H", 2
    if descr == "|b1" or type_code == "b1":
        return "?", 1
    raise ValueError(f"pose_stream_npy_dtype_not_supported:{descr}")


def _reshape(values: list[Any], shape: tuple[int, ...]) -> Any:
    if not shape:
        return values[0]
    if len(shape) == 1:
        return values[: shape[0]]
    step = math.prod(shape[1:])
    return [
        _reshape(values[index : index + step], shape[1:]) for index in range(0, len(values), step)
    ]


def _first_present(arrays: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in arrays:
            return arrays[key]
    return None


def _resolve_timestamps(arrays: dict[str, Any], *, total_frames: int, fps: float) -> list[int]:
    timestamp_ms = _first_present(arrays, _TIMESTAMP_MS_KEYS)
    if timestamp_ms is not None:
        values = [int(round(_finite_float(value, field="timestamp_ms"))) for value in timestamp_ms]
    else:
        timestamp_seconds = _first_present(arrays, _TIMESTAMP_SECOND_KEYS)
        if timestamp_seconds is not None:
            values = [
                int(round(_finite_float(value, field="timestamp_seconds") * 1000.0))
                for value in timestamp_seconds
            ]
        else:
            values = [int(round(index * 1000.0 / fps)) for index in range(total_frames)]
    if len(values) != total_frames:
        raise ValueError("pose_stream_timestamps_must_match_frames")
    return values


def _resolve_fps(arrays: dict[str, Any], *, fallback: float) -> float:
    source_fps = _first_present(arrays, _FRAMERATE_KEYS)
    if source_fps is None:
        return _finite_float(fallback, field="fps")
    values = _as_sequence(source_fps)
    if not values:
        return _finite_float(fallback, field="fps")
    return _finite_float(values[0], field="framerate")


def _resolve_root_positions(arrays: dict[str, Any], *, total_frames: int) -> list[Any]:
    root_positions = _first_present(arrays, _ROOT_POSITION_KEYS)
    if root_positions is not None:
        values = _as_nested_list(root_positions)
    else:
        positions = _first_present(arrays, _POSITION_KEYS)
        values = (
            [frame[0] for frame in _as_nested_list(positions)] if positions is not None else None
        )
    if values is None:
        values = [[0.0, 0.0, 0.0] for _ in range(total_frames)]
    if len(values) != total_frames:
        raise ValueError("pose_stream_root_positions_must_match_frames")
    return values


def _resolve_root_rotations(
    arrays: dict[str, Any], joint_rotations: list[Any], *, total_frames: int
) -> list[Any]:
    root_rotations = _first_present(arrays, _ROOT_ROTATION_KEYS)
    values = (
        _as_nested_list(root_rotations)
        if root_rotations is not None
        else [frame[0] for frame in joint_rotations]
    )
    if len(values) != total_frames:
        raise ValueError("pose_stream_root_rotations_must_match_frames")
    return values


def _resolve_gesture_labels(arrays: dict[str, Any], *, total_frames: int) -> list[str]:
    raw = _first_present(arrays, ("gesture_label", "gesture_labels"))
    if raw is None:
        return ["motion_import" for _ in range(total_frames)]
    values = _as_sequence(raw)
    if len(values) == 1:
        return [str(values[0]) for _ in range(total_frames)]
    if len(values) != total_frames:
        raise ValueError("pose_stream_gesture_labels_must_match_frames")
    return [str(value) for value in values]


def _names_for_count(raw_names: Any, count: int, prefix: str) -> list[str]:
    names = [
        _safe_name(name, fallback=f"{prefix}_{index}")
        for index, name in enumerate(_as_sequence(raw_names))
    ]
    if not names:
        names = [f"{prefix}_{index}" for index in range(count)]
    if len(names) != count:
        raise ValueError(f"pose_stream_{prefix}_names_must_match_count")
    return names


def _shape(value: Any) -> tuple[int, ...]:
    if isinstance(value, tuple):
        value = list(value)
    if not isinstance(value, list):
        return ()
    if not value:
        return (0,)
    child_shape = _shape(value[0])
    if any(_shape(item) != child_shape for item in value[1:]):
        raise ValueError("pose_stream_arrays_must_be_rectangular")
    return (len(value), *child_shape)


def _as_nested_list(value: Any) -> Any:
    if hasattr(value, "tolist"):
        return value.tolist()
    return value


def _as_sequence(value: Any) -> list[Any]:
    if value is None:
        return []
    value = _as_nested_list(value)
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, list):
        return value
    return [value]


def _vector3(value: Any, *, field: str) -> tuple[float, float, float]:
    values = _as_sequence(value)
    if len(values) != 3:
        raise ValueError(f"{field}_must_have_three_values")
    return tuple(_finite_float(item, field=field) for item in values)  # type: ignore[return-value]


def _quaternion(value: Any, *, field: str) -> tuple[float, float, float, float]:
    values = _as_sequence(value)
    if len(values) != 4:
        raise ValueError(f"{field}_must_have_four_values")
    parsed = [_finite_float(item, field=field) for item in values]
    length = math.sqrt(sum(item * item for item in parsed))
    if length <= 0.000001:
        raise ValueError(f"{field}_must_not_be_zero")
    return tuple(round(item / length, 9) for item in parsed)  # type: ignore[return-value]


def _finite_float(value: Any, *, field: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field}_must_be_finite") from None
    if not math.isfinite(parsed):
        raise ValueError(f"{field}_must_be_finite")
    return parsed


def _safe_name(value: Any, *, fallback: str) -> str:
    name = str(value or "").strip()
    return name[:80] if name else fallback
