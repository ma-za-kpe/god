"""Pose-stream evaluation tests for the AI4AnimationPy pivot."""

from __future__ import annotations

import copy
import json
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from avatar import (
    POSE_STREAM_LICENSE_PROFILE,
    POSE_STREAM_SOURCE,
    build_pose_stream_from_arrays,
    iter_pose_stream_ndjson,
    load_npz_pose_stream,
    normalize_pose_stream,
    pose_stream_summary,
)


ROOT = Path(__file__).resolve().parents[2]


def test_load_npz_pose_stream_normalizes_motion_contract(tmp_path: Path):
    motion_path = _write_motion_npz(tmp_path / "tiny_motion.npz")

    stream = load_npz_pose_stream(motion_path, agent_id="fish", max_frames=3)
    payload = stream.to_dict()

    assert payload["source"] == POSE_STREAM_SOURCE
    assert payload["license_profile"] == POSE_STREAM_LICENSE_PROFILE
    assert payload["target_runtime"] == "ai4animationpy"
    assert payload["agent_id"] == "fish"
    assert payload["frame_count"] == 3
    assert payload["frames"][0]["joint_rotations"]["joint_0"] == [0.0, 0.0, 0.0, 1.0]
    assert payload["frames"][1]["root_position"] == [0.1, 0.0, 0.0]
    assert payload["frames"][2]["contacts"]["contact_1"] is True

    summary = pose_stream_summary(stream)
    assert summary["joint_count"] == 2
    assert summary["contact_names"] == ["contact_0", "contact_1"]
    assert summary["root_bounds"]["max"] == [0.2, 0.0, 0.0]

    lines = [json.loads(line) for line in iter_pose_stream_ndjson(stream)]
    assert lines[0]["type"] == "pose_stream"
    assert lines[1]["type"] == "pose_frame"
    assert lines[-1]["timestamp_ms"] == 80


def test_build_pose_stream_from_arrays_accepts_common_ai4animationpy_aliases():
    stream = build_pose_stream_from_arrays(
        {
            "rotations": [
                [[0, 0, 0, 1], [0, 0.25, 0, 1]],
                [[0, 0, 0, 1], [0.1, 0.2, 0.3, 1]],
            ],
            "positions": [
                [[1, 0, 0], [1, 1, 0]],
                [[1.2, 0, 0], [1.2, 1, 0]],
            ],
            "times": [0.0, 0.5],
        },
        agent_id="sidecar-eval",
    )

    assert stream.frames[0].root_position == (1.0, 0.0, 0.0)
    assert stream.frames[1].timestamp_ms == 500
    assert stream.frames[0].joint_rotations["joint_1"][3] < 1.0


def test_normalize_pose_stream_rejects_malformed_sidecar_output():
    valid = {
        "frames": [
            _frame(0),
            _frame(40, root_position=[0.1, 0.0, 0.0]),
        ]
    }
    assert normalize_pose_stream(valid).duration_seconds == 0.04

    non_monotonic = copy.deepcopy(valid)
    non_monotonic["frames"][1]["timestamp_ms"] = 0
    with pytest.raises(ValueError, match="timestamps_must_increase"):
        normalize_pose_stream(non_monotonic)

    unbounded_root = copy.deepcopy(valid)
    unbounded_root["frames"][0]["root_position"] = [101, 0, 0]
    with pytest.raises(ValueError, match="root_position_out_of_bounds"):
        normalize_pose_stream(unbounded_root)

    zero_quaternion = copy.deepcopy(valid)
    zero_quaternion["frames"][0]["joint_rotations"]["hips"] = [0, 0, 0, 0]
    with pytest.raises(ValueError, match="joint_rotation_must_not_be_zero"):
        normalize_pose_stream(zero_quaternion)


def test_build_pose_stream_from_arrays_rejects_ragged_motion_arrays():
    with pytest.raises(ValueError, match="arrays_must_be_rectangular"):
        build_pose_stream_from_arrays(
            {
                "joint_rotations": [
                    [[0, 0, 0, 1]],
                    [[0, 0, 0, 1], [0, 0, 0, 1]],
                ],
            }
        )


def test_load_npz_pose_stream_rejects_oversized_member_count(tmp_path: Path):
    motion_path = tmp_path / "too_many_members.npz"
    with zipfile.ZipFile(motion_path, "w") as archive:
        for index in range(33):
            archive.writestr(
                f"extra_{index}.npy",
                _npy_bytes([index], shape=(1,), descr="<i4"),
            )

    with pytest.raises(ValueError, match="too_many_members"):
        load_npz_pose_stream(motion_path)


def test_load_npz_pose_stream_rejects_duplicate_members(tmp_path: Path):
    motion_path = tmp_path / "duplicate_members.npz"
    with zipfile.ZipFile(motion_path, "w") as archive:
        archive.writestr("joint_rotations.npy", _npy_bytes([0, 0, 0, 1], shape=(1, 1, 4), descr="<f8"))
        with pytest.warns(UserWarning, match="Duplicate name"):
            archive.writestr(
                "joint_rotations.npy",
                _npy_bytes([0, 0, 0, 1], shape=(1, 1, 4), descr="<f8"),
            )

    with pytest.raises(ValueError, match="duplicate_members"):
        load_npz_pose_stream(motion_path)


def test_eval_ai4animationpy_motion_cli_emits_summary(tmp_path: Path):
    motion_path = _write_motion_npz(tmp_path / "tiny_motion.npz")

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "eval-ai4animationpy-motion.py"),
            "--npz",
            str(motion_path),
            "--agent-id",
            "fish",
            "--format",
            "summary",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["agent_id"] == "fish"
    assert payload["source"] == POSE_STREAM_SOURCE
    assert payload["frame_count"] == 3
    assert payload["license_profile"] == POSE_STREAM_LICENSE_PROFILE


def _frame(
    timestamp_ms: int,
    *,
    root_position: list[float] | None = None,
) -> dict[str, object]:
    return {
        "timestamp_ms": timestamp_ms,
        "root_position": root_position or [0.0, 0.0, 0.0],
        "root_rotation": [0, 0, 0, 1],
        "joint_rotations": {"hips": [0, 0, 0, 1], "spine": [0.1, 0, 0, 1]},
        "contacts": {"left_foot": True},
        "gesture_label": "motion_import",
    }


def _write_motion_npz(path: Path) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "timestamps_ms.npy",
            _npy_bytes([0, 40, 80], shape=(3,), descr="<i4"),
        )
        archive.writestr(
            "root_position.npy",
            _npy_bytes(
                [
                    0.0,
                    0.0,
                    0.0,
                    0.1,
                    0.0,
                    0.0,
                    0.2,
                    0.0,
                    0.0,
                ],
                shape=(3, 3),
                descr="<f8",
            ),
        )
        archive.writestr(
            "joint_rotations.npy",
            _npy_bytes(
                [
                    0,
                    0,
                    0,
                    1,
                    0,
                    0.1,
                    0,
                    1,
                    0,
                    0,
                    0,
                    1,
                    0.1,
                    0.2,
                    0,
                    1,
                    0,
                    0,
                    0,
                    1,
                    0,
                    0.3,
                    0,
                    1,
                ],
                shape=(3, 2, 4),
                descr="<f8",
            ),
        )
        archive.writestr(
            "contacts.npy",
            _npy_bytes(
                [True, False, False, True, True, True],
                shape=(3, 2),
                descr="|b1",
            ),
        )
    return path


def _npy_bytes(values: list[object], *, shape: tuple[int, ...], descr: str) -> bytes:
    header = {"descr": descr, "fortran_order": False, "shape": shape}
    header_text = repr(header)
    padding = 16 - ((10 + len(header_text) + 1) % 16)
    header_bytes = (header_text + (" " * padding) + "\n").encode("latin1")
    data = struct.pack("<H", len(header_bytes))
    return b"\x93NUMPY\x01\x00" + data + header_bytes + _pack_values(values, descr)


def _pack_values(values: list[object], descr: str) -> bytes:
    if descr == "<f8":
        return struct.pack("<" + ("d" * len(values)), *values)
    if descr == "<i4":
        return struct.pack("<" + ("i" * len(values)), *values)
    if descr == "|b1":
        return struct.pack("<" + ("?" * len(values)), *values)
    raise AssertionError(f"unsupported test dtype: {descr}")
