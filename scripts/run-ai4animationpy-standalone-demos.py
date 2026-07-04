#!/usr/bin/env python
"""Bounded local smoke runner for AI4AnimationPy demo programs.

Standalone AI4AnimationPy demos run until their Raylib window is closed. By
default this runner launches each demo from its own directory, waits for a
short startup window, then terminates the process tree. A demo that is still
alive at the deadline is treated as a successful startup smoke test.

Use --launch with a single --only filter to leave one demo running in its
native Standalone window for visual inspection.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "artifacts" / "ai4animationpy-src"
DEFAULT_ARTIFACT_DIR = ROOT / "artifacts" / "ai4animationpy-demo-smoke"


DEMO_PROGRAMS = [
    ("Actor", "Demos/Actor/Program.py", 8.0),
    ("AI/Autoencoder", "Demos/AI/Autoencoder/Program.py", 12.0),
    ("AI/MotionGrounding", "Demos/AI/MotionGrounding/Program.py", 12.0),
    ("AI/SequencePrediction", "Demos/AI/SequencePrediction/Program.py", 12.0),
    ("AI/ToyExample", "Demos/AI/ToyExample/Program.py", 8.0),
    ("ECS", "Demos/ECS/Program.py", 8.0),
    ("Empty", "Demos/Empty/Program.py", 5.0),
    ("InverseKinematics", "Demos/InverseKinematics/Program.py", 8.0),
    ("Locomotion/Biped", "Demos/Locomotion/Biped/Program.py", 25.0),
    ("Locomotion/Quadruped", "Demos/Locomotion/Quadruped/Program.py", 25.0),
    ("MotionEditor", "Demos/MotionEditor/Program.py", 10.0),
    ("MotionImport/BVH", "Demos/MotionImport/BVH/Program.py", 10.0),
    ("MotionImport/FBX", "Demos/MotionImport/FBX/Program.py", 10.0),
    ("MotionImport/GLB", "Demos/MotionImport/GLB/Program.py", 10.0),
    ("MotionImport/Import_LaFan", "Demos/MotionImport/Import_LaFan/Program.py", 10.0),
    ("MotionImport/Import_MANN", "Demos/MotionImport/Import_MANN/Program.py", 10.0),
]


RAYLIB6_COMPAT_OLD_IDS = """                raylib_mesh.boneIds = ffi.cast(
                    "unsigned char*", bone_ids.buffer_info()[0]
                )
                raylib_mesh.boneWeights = ffi.cast(
                    "float*", bone_weights.buffer_info()[0]
                )
                raylib_mesh.boneCount = boneCount
                raylib_mesh.vaoId = 0

                # Allocate bone matrices
                raylib_mesh.boneMatrices = MemAlloc(boneCount * ffi.sizeof(Matrix()))
                for i in range(boneCount):
                    raylib_mesh.boneMatrices[i] = MatrixIdentity()

                # Upload mesh with dynamic flag for bone updates
                UploadMesh(ffi.addressof(raylib_mesh), True)

                # Create Model for this chunk
                raylib_model = load_model_from_mesh(raylib_mesh)
                raylib_model.materials[0].maps[MATERIAL_MAP_DIFFUSE].color = WHITE
"""

RAYLIB6_COMPAT_NEW_IDS = """                if hasattr(raylib_mesh, "boneIds"):
                    raylib_mesh.boneIds = ffi.cast(
                        "unsigned char*", bone_ids.buffer_info()[0]
                    )
                else:
                    raylib_mesh.boneIndices = ffi.cast(
                        "unsigned char*", bone_ids.buffer_info()[0]
                    )
                raylib_mesh.boneWeights = ffi.cast(
                    "float*", bone_weights.buffer_info()[0]
                )
                raylib_mesh.boneCount = boneCount
                raylib_mesh.vaoId = 0

                # Upload mesh with dynamic flag for bone updates
                UploadMesh(ffi.addressof(raylib_mesh), True)

                # Create Model for this chunk
                raylib_model = load_model_from_mesh(raylib_mesh)
                raylib_model.boneMatrices = MemAlloc(boneCount * ffi.sizeof(Matrix()))
                for i in range(boneCount):
                    raylib_model.boneMatrices[i] = MatrixIdentity()
                raylib_model.materials[0].maps[MATERIAL_MAP_DIFFUSE].color = WHITE
"""

RAYLIB6_COMPAT_OLD_MATRICES = """                # Cache numpy view of bone matrices for efficient updates
                gpu_mesh = raylib_model.meshes[0]
                matView = np.frombuffer(
                    ffi.buffer(
                        gpu_mesh.boneMatrices,
                        gpu_mesh.boneCount * ffi.sizeof(Matrix()),
                    ),
                    dtype=np.float32,
                ).reshape(gpu_mesh.boneCount, 4, 4)
"""

RAYLIB6_COMPAT_NEW_MATRICES = """                # Cache numpy view of bone matrices for efficient updates
                matView = np.frombuffer(
                    ffi.buffer(
                        raylib_model.boneMatrices,
                        boneCount * ffi.sizeof(Matrix()),
                    ),
                    dtype=np.float32,
                ).reshape(boneCount, 4, 4)
"""

RAYLIB6_CPU_SKINNING_IMPORT_OLD = """    UnloadImage,
    UploadMesh,
"""

RAYLIB6_CPU_SKINNING_IMPORT_NEW = """    UnloadImage,
    UpdateMeshBuffer,
    UploadMesh,
"""

RAYLIB6_CPU_SKINNING_ATTRS_OLD = """        self.Models = []
        self.BoneMatrixViews = []
        self.Textures = []
"""

RAYLIB6_CPU_SKINNING_ATTRS_NEW = """        self.Models = []
        self.BoneMatrixViews = []
        self.CpuSkinningFallback = True
        self.CpuSkinnedChunks = []
        self.BufferRefs = []
        self.Textures = []
"""

RAYLIB6_CPU_SKINNING_BONES_OLD = """                # 4 bones per vertex
                boneIds = np.zeros((chunkVertexCount, 4), dtype=np.uint8)
                currentSkinBones = min(chunk_skin_indices.shape[1], 4)
                boneIds[:, :currentSkinBones] = chunk_skin_indices[
                    :, :currentSkinBones
                ].astype(np.uint8)
                bone_ids = array("B", boneIds.flatten())

                # Bone weights
                boneWeights = np.zeros((chunkVertexCount, 4), dtype=np.float32)
                boneWeights[:, :currentSkinBones] = chunk_skin_weights[
                    :, :currentSkinBones
                ]
                bone_weights = array("f", boneWeights.flatten())
"""

RAYLIB6_CPU_SKINNING_BONES_NEW = """                # 4 bones per vertex. Keep the real weights for CPU skinning, but
                # upload pass-through skinning data so Raylib 6 builds without GPU
                # skinning support can still draw the CPU-updated surface.
                cpuBoneIds = np.zeros((chunkVertexCount, 4), dtype=np.uint8)
                currentSkinBones = min(chunk_skin_indices.shape[1], 4)
                cpuBoneIds[:, :currentSkinBones] = chunk_skin_indices[
                    :, :currentSkinBones
                ].astype(np.uint8)

                boneIds = np.zeros((chunkVertexCount, 4), dtype=np.uint8)
                bone_ids = array("B", boneIds.flatten())

                # Bone weights
                cpuBoneWeights = np.zeros((chunkVertexCount, 4), dtype=np.float32)
                cpuBoneWeights[:, :currentSkinBones] = chunk_skin_weights[
                    :, :currentSkinBones
                ]
                boneWeights = np.zeros((chunkVertexCount, 4), dtype=np.float32)
                boneWeights[:, 0] = 1.0
                bone_weights = array("f", boneWeights.flatten())
"""

RAYLIB6_CPU_SKINNING_APPEND_OLD = """                self.Models.append(raylib_model)
"""

RAYLIB6_CPU_SKINNING_APPEND_NEW = """                self.Models.append(raylib_model)
                self.BufferRefs.append(
                    (vertices, normals, triangles, texcoords, bone_ids, bone_weights)
                )
                self.CpuSkinnedChunks.append(
                    {
                        "model": raylib_model,
                        "vertices": vertices,
                        "normals": normals,
                        "vertex_view": np.frombuffer(vertices, dtype=np.float32).reshape(
                            chunkVertexCount, 3
                        ),
                        "normal_view": np.frombuffer(normals, dtype=np.float32).reshape(
                            chunkVertexCount, 3
                        ),
                        "source_positions_h": np.concatenate(
                            [
                                np.asarray(chunk_positions, dtype=np.float32),
                                np.ones((chunkVertexCount, 1), dtype=np.float32),
                            ],
                            axis=1,
                        ),
                        "source_normals": np.asarray(chunk_normals, dtype=np.float32),
                        "bone_ids": cpuBoneIds,
                        "bone_weights": cpuBoneWeights,
                    }
                )
"""

RAYLIB6_CPU_SKINNING_UPDATE_OLD = """        for matView in self.BoneMatrixViews:
            matView[:] = transforms
"""

RAYLIB6_CPU_SKINNING_UPDATE_NEW = """        if self.CpuSkinningFallback:
            identity = np.eye(4, dtype=np.float32)
            for matView in self.BoneMatrixViews:
                matView[:] = identity
            for chunk in self.CpuSkinnedChunks:
                positions = np.zeros(
                    (chunk["source_positions_h"].shape[0], 3), dtype=np.float32
                )
                normals = np.zeros_like(chunk["source_normals"], dtype=np.float32)
                for influence in range(4):
                    weights = chunk["bone_weights"][:, influence : influence + 1]
                    if not np.any(weights):
                        continue
                    matrices = transforms[chunk["bone_ids"][:, influence]]
                    positions += weights * np.einsum(
                        "nij,nj->ni", matrices, chunk["source_positions_h"]
                    )[:, :3]
                    normals += weights * np.einsum(
                        "nij,nj->ni", matrices[:, :3, :3], chunk["source_normals"]
                    )

                normal_lengths = np.linalg.norm(normals, axis=1, keepdims=True)
                normals = np.divide(
                    normals,
                    np.maximum(normal_lengths, 1e-6),
                    out=np.zeros_like(normals),
                    where=normal_lengths > 0,
                )

                chunk["vertex_view"][:] = positions
                chunk["normal_view"][:] = normals
                UpdateMeshBuffer(
                    chunk["model"].meshes[0],
                    0,
                    ffi.cast("void*", chunk["vertices"].buffer_info()[0]),
                    len(chunk["vertices"]) * ffi.sizeof("float"),
                    0,
                )
                UpdateMeshBuffer(
                    chunk["model"].meshes[0],
                    2,
                    ffi.cast("void*", chunk["normals"].buffer_info()[0]),
                    len(chunk["normals"]) * ffi.sizeof("float"),
                    0,
                )
            return

        for matView in self.BoneMatrixViews:
            matView[:] = transforms
"""

RAYLIB6_CPU_RENDER_HELPER_OLD = """

class RenderPipeline(Component):
"""

RAYLIB6_CPU_RENDER_HELPER_NEW = """

def UsesCpuSkinningFallback(registered):
    return bool(
        registered.skinned_mesh
        and getattr(registered.skinned_mesh, "CpuSkinningFallback", False)
    )


class RenderPipeline(Component):
"""

RAYLIB6_CPU_RENDER_SHADOW_OLD = """            registered.Draw(
                self.SkinnedShadowShader
                if registered.skinned_mesh
                else self.ShadowShader
            )
"""

RAYLIB6_CPU_RENDER_SHADOW_NEW = """            registered.Draw(
                self.ShadowShader
                if UsesCpuSkinningFallback(registered) or not registered.skinned_mesh
                else self.SkinnedShadowShader
            )
"""

RAYLIB6_CPU_RENDER_GBUFFER_OLD = """            registered.Draw(
                self.SkinnedBasicShader if registered.skinned_mesh else self.GridShader
            )
"""

RAYLIB6_CPU_RENDER_GBUFFER_NEW = """            registered.Draw(
                self.BasicShader
                if UsesCpuSkinningFallback(registered)
                else self.SkinnedBasicShader
                if registered.skinned_mesh
                else self.GridShader
            )
"""

RAYLIB6_CPU_RENDER_FORWARD_OLD = """            shader = (
                self.SkinnedForwardShader
                if registered.skinned_mesh
                else self.ForwardShader
            )
"""

RAYLIB6_CPU_RENDER_FORWARD_NEW = """            shader = (
                self.ForwardShader
                if UsesCpuSkinningFallback(registered) or not registered.skinned_mesh
                else self.SkinnedForwardShader
            )
"""

RAYLIB6_CPU_RENDER_FORWARD_SHADOW_OLD = """        for registered in self.RegisteredModels:
            if registered.skinned_mesh:
                registered.Draw(self.SkinnedShadowShader)
"""

RAYLIB6_CPU_RENDER_FORWARD_SHADOW_NEW = """        for registered in self.RegisteredModels:
            if registered.skinned_mesh:
                registered.Draw(
                    self.ForwardShader
                    if UsesCpuSkinningFallback(registered)
                    else self.SkinnedShadowShader
                )
"""


DATASET_GATED = {
    "MotionImport/Import_LaFan": "Demos/MotionImport/Import_LaFan/bvh/NPZ",
    "MotionImport/Import_MANN": "Demos/MotionImport/Import_MANN/bvh/NPZ",
}

PYTHON_MODULE_GATED = {
    "MotionImport/FBX": "fbx",
}


@dataclass
class DemoResult:
    name: str
    program: str
    status: str
    exit_code: int | None
    elapsed_seconds: float
    log_path: str
    reason: str


def demo_entrypoint() -> str:
    return """
import runpy
import sys

try:
    import torch
except Exception:
    torch = None

if torch is not None:
    _torch_load = torch.load

    def _load_with_cpu_fallback(*args, **kwargs):
        if "map_location" not in kwargs and not torch.cuda.is_available():
            kwargs["map_location"] = "cpu"
        return _torch_load(*args, **kwargs)

    torch.load = _load_with_cpu_fallback

runpy.run_path(sys.argv[1], run_name="__main__")
""".strip()


def launch_entrypoint() -> str:
    return """
import os
import ast
import json
import math
import runpy
import sys
import threading
import time
import urllib.request

try:
    import torch
except Exception:
    torch = None

if torch is not None:
    _torch_load = torch.load

    def _load_with_cpu_fallback(*args, **kwargs):
        if "map_location" not in kwargs and not torch.cuda.is_available():
            kwargs["map_location"] = "cpu"
        return _torch_load(*args, **kwargs)

    torch.load = _load_with_cpu_fallback

program_dir = os.path.dirname(os.path.abspath(sys.argv[1]))
if program_dir not in sys.path:
    sys.path.insert(0, program_dir)

namespace = runpy.run_path(sys.argv[1], run_name="__ai4animationpy_demo__")
Program = namespace.get("Program")
AI4Animation = namespace.get("AI4Animation")
if Program is None or AI4Animation is None:
    runpy.run_path(sys.argv[1], run_name="__main__")
else:
    mode_map = {"free": 0, "fixed": 1, "third": 2, "orbit": 3}
    camera_mode = mode_map.get(os.environ.get("AI4ANIMATIONPY_CAMERA_MODE", "third"), 2)
    camera_distance = float(os.environ.get("AI4ANIMATIONPY_CAMERA_DISTANCE", "2.8"))
    autodrive = os.environ.get("AI4ANIMATIONPY_AUTODRIVE", "none")
    telemetry_interval = float(os.environ.get("AI4ANIMATIONPY_TELEMETRY_INTERVAL", "1.0"))
    ollama_url = os.environ.get("AI4ANIMATIONPY_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
    ollama_model = os.environ.get("AI4ANIMATIONPY_OLLAMA_MODEL", "llama3.1:8b")
    ollama_timeout = float(os.environ.get("AI4ANIMATIONPY_OLLAMA_TIMEOUT", "12.0"))
    ollama_num_ctx = int(os.environ.get("AI4ANIMATIONPY_OLLAMA_NUM_CTX", "8192"))
    ollama_plan_interval = float(os.environ.get("AI4ANIMATIONPY_OLLAMA_PLAN_INTERVAL", "5.0"))
    llm_trace_path = os.environ.get("AI4ANIMATIONPY_LLM_TRACE_PATH", "").strip()
    show_stage_props = os.environ.get("AI4ANIMATIONPY_STAGE_PROPS", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }
    soft_room_limit = None
    hard_room_limit = None
    stage_profile = {
        "show_title": "",
        "movement_vocabulary": [],
        "style_notes": [],
    }
    stage_targets = {}
    llm_control = {
        "last_plan_wall": 0.0,
        "move_x": 0.0,
        "move_z": 0.0,
        "speed": 0.0,
        "sprint": False,
        "style": "",
        "stage_target": "",
        "action_label": "",
        "rationale": "",
        "duration_seconds": 0.0,
        "action_expires_at": 0.0,
        "queue": [],
        "fatal_error": "",
        "planner_started": False,
        "boundary_recovery_requested": False,
        "plan_requested": False,
        "history": [],
    }
    replan_event = threading.Event()
    trace_error_reported = {"reported": False}

    def _trace_ready(value):
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, dict):
            return {str(key): _trace_ready(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [_trace_ready(item) for item in value]
        if hasattr(value, "tolist"):
            return _trace_ready(value.tolist())
        return repr(value)

    def _write_trace(event, **payload):
        if not llm_trace_path:
            return
        try:
            directory = os.path.dirname(llm_trace_path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            record = {
                "wall_time": time.time(),
                "monotonic_time": time.monotonic(),
                "event": event,
                "model": ollama_model,
                "payload": _trace_ready(payload),
            }
            with open(llm_trace_path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, sort_keys=True) + "\\n")
        except Exception as exc:
            if not trace_error_reported["reported"]:
                trace_error_reported["reported"] = True
                print(f"AI4_BIPED_TRACE_ERROR {type(exc).__name__}: {exc}", flush=True)

    def _request_json(url, payload=None):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=ollama_timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def _extract_json_object(text):
        stripped = text.strip()
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            start = stripped.find("{")
            end = stripped.rfind("}")
            if start < 0 or end <= start:
                raise
            return json.loads(stripped[start : end + 1])

    def _bounded_float(value, field, minimum, maximum):
        number = _finite_float(value, field)
        if number < minimum or number > maximum:
            raise ValueError(
                f"{field}_out_of_range: {number:.3f}; expected {minimum:.3f}..{maximum:.3f}"
            )
        return number

    def _normalise_style(style, guidance_names):
        lookup = {name.lower(): name for name in guidance_names}
        key = str(style).strip().lower()
        if key not in lookup:
            raise ValueError(
                f"ollama_style_not_available: {style!r}; available={guidance_names}"
            )
        return lookup[key]

    def _normalise_stage_target(stage_target):
        if stage_target is None or str(stage_target).strip() == "":
            return ""
        key = str(stage_target).strip().lower().replace("-", "_").replace(" ", "_")
        if key in stage_targets:
            return key
        raise ValueError(
            f"stage_target_not_available: {stage_target!r}; available={list(stage_targets)}"
        )

    def _parse_bool(value):
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        return str(value).strip().lower() in {"1", "true", "yes", "y", "sprint"}

    def _finite_float(value, field):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError(f"{field}_must_be_finite")
        return number

    def _normalise_id(value, field):
        text = str(value).strip().lower()
        normalised = "".join(char if char.isalnum() else "_" for char in text)
        normalised = "_".join(part for part in normalised.split("_") if part)
        if not normalised:
            raise ValueError(f"{field}_missing")
        return normalised[:48]

    def _target_position(target):
        if "position" in target:
            position = list(target["position"])
            if len(position) == 3:
                return [
                    _finite_float(position[0], "target_position_x"),
                    _finite_float(position[1], "target_position_y"),
                    _finite_float(position[2], "target_position_z"),
                ]
            raise ValueError("target_position_must_have_three_model_numbers")
        return [
            _finite_float(target["position_x"], "target_position_x"),
            _finite_float(target["position_y"], "target_position_y"),
            _finite_float(target["position_z"], "target_position_z"),
        ]

    def _normalise_movement_vocabulary(raw_items, guidance_names):
        if not isinstance(raw_items, list) or not raw_items:
            raise ValueError("movement_vocabulary_must_be_model_authored")
        vocabulary = []
        seen = set()
        for raw_item in raw_items:
            item = raw_item
            if isinstance(raw_item, str):
                try:
                    item = ast.literal_eval(raw_item)
                except Exception as exc:
                    raise ValueError(
                        f"movement_vocabulary_item_must_be_object: {raw_item!r}"
                    ) from exc
            if not isinstance(item, dict):
                raise ValueError(f"movement_vocabulary_item_must_be_object: {item!r}")
            movement_id = _normalise_id(
                item.get("id") or item.get("phrase") or item.get("label"),
                "movement_id",
            )
            if movement_id in seen:
                raise ValueError(f"duplicate_movement_id: {movement_id}")
            seen.add(movement_id)
            guidance_style = _normalise_style(
                item.get("guidance_style") or item.get("guidance") or item.get("style"),
                guidance_names,
            )
            vocabulary.append(
                {
                    "id": movement_id,
                    "label": str(item.get("label") or item.get("phrase") or movement_id).strip()[:80],
                    "guidance_style": guidance_style,
                    "prompt": str(item.get("prompt") or item.get("description") or "").strip()[:160],
                }
            )
        return vocabulary

    def _normalise_stage_profile(raw_profile, guidance_names, actor_floor_y):
        global soft_room_limit
        global hard_room_limit
        global stage_profile
        global stage_targets

        soft = _finite_float(raw_profile["soft_room_limit"], "soft_room_limit")
        hard = _finite_float(raw_profile["hard_room_limit"], "hard_room_limit")
        if soft <= 0.0 or hard <= soft:
            raise ValueError(
                f"invalid_model_room_limits soft={soft:.3f} hard={hard:.3f}"
            )
        floor_marker_y = _finite_float(raw_profile["floor_marker_y"], "floor_marker_y")
        camera_distance = _finite_float(raw_profile["camera_distance"], "camera_distance")
        floor_tolerance = 1.0
        if abs(floor_marker_y - actor_floor_y) > floor_tolerance:
            raise ValueError(
                f"floor_marker_y_must_match_actor_floor: "
                f"floor_marker_y={floor_marker_y:.3f} actor_floor_y={actor_floor_y:.3f}"
            )
        if camera_distance <= 0.0:
            raise ValueError("camera_distance_must_be_positive")

        raw_targets = raw_profile.get("stage_targets")
        if not isinstance(raw_targets, list) or not raw_targets:
            raise ValueError("stage_targets_must_be_non_empty_model_list")

        shape_names = {"cube", "sphere", "pillar", "ring", "marker"}
        targets = {}
        for raw_target in raw_targets:
            target_id = _normalise_id(raw_target["id"], "stage_target_id")
            if target_id in targets:
                raise ValueError(f"duplicate_stage_target_id: {target_id}")
            position = _target_position(raw_target)
            if abs(position[0]) > hard or abs(position[2]) > hard:
                raise ValueError(
                    f"stage_target_outside_model_hard_limit id={target_id} "
                    f"position=({position[0]:.3f},{position[2]:.3f}) hard={hard:.3f}"
                )
            horizontal_radius = math.sqrt((position[0] * position[0]) + (position[2] * position[2]))
            max_visible_radius = camera_distance * 1.5
            if horizontal_radius > max_visible_radius:
                raise ValueError(
                    f"stage_target_outside_camera_view id={target_id} "
                    f"radius={horizontal_radius:.3f} max_visible_radius={max_visible_radius:.3f} "
                    f"camera_distance={camera_distance:.3f}"
                )
            if abs(position[1] - actor_floor_y) > floor_tolerance:
                raise ValueError(
                    f"stage_target_y_must_match_actor_floor id={target_id} "
                    f"position_y={position[1]:.3f} actor_floor_y={actor_floor_y:.3f}"
                )
            shape = _normalise_id(raw_target["prop_shape"], "prop_shape")
            if shape not in shape_names:
                raise ValueError(f"unsupported_model_prop_shape: {shape}")
            raw_color = list(raw_target["color_rgb"])
            if len(raw_color) != 3:
                raise ValueError(f"color_rgb_must_have_three_model_numbers id={target_id}")
            color_rgb = [
                _finite_float(raw_color[0], "color_r"),
                _finite_float(raw_color[1], "color_g"),
                _finite_float(raw_color[2], "color_b"),
            ]
            if any(value < 0.0 or value > 255.0 for value in color_rgb):
                raise ValueError(
                    f"color_rgb_out_of_range id={target_id} color_rgb={color_rgb}"
                )
            scale = _finite_float(raw_target["scale"], "target_scale")
            height = _finite_float(raw_target["height"], "target_height")
            if scale <= 0.0 or height < 0.0:
                raise ValueError(
                    f"invalid_model_prop_size id={target_id} scale={scale:.3f} height={height:.3f}"
                )
            max_prop_extent = max(0.25, soft * 0.35)
            if scale > max_prop_extent or height > max_prop_extent:
                raise ValueError(
                    f"model_prop_too_large_for_stage id={target_id} "
                    f"scale={scale:.3f} height={height:.3f} max={max_prop_extent:.3f}"
                )
            targets[target_id] = {
                "label": str(raw_target["label"]).strip()[:80],
                "position": position,
                "purpose": str(raw_target["purpose"]).strip()[:180],
                "movement_prompt": str(raw_target["movement_prompt"]).strip()[:180],
                "prop_shape": shape,
                "color_rgb": color_rgb,
                "scale": scale,
                "height": height,
            }

        vocabulary = _normalise_movement_vocabulary(
            raw_profile.get("movement_vocabulary"),
            guidance_names,
        )

        soft_room_limit = soft
        hard_room_limit = hard
        stage_targets = targets
        stage_profile = {
            "show_title": str(raw_profile.get("show_title", "")).strip()[:100],
            "movement_vocabulary": vocabulary,
            "style_notes": [
                str(item).strip()[:120]
                for item in raw_profile.get("style_notes", [])
                if str(item).strip()
            ],
            "floor_marker_y": floor_marker_y,
            "max_command_duration_seconds": _finite_float(
                raw_profile["max_command_duration_seconds"],
                "max_command_duration_seconds",
            ),
            "camera_distance": camera_distance,
            "commands_per_batch": int(_finite_float(raw_profile["commands_per_batch"], "commands_per_batch")),
        }
        if stage_profile["max_command_duration_seconds"] <= 0.0:
            raise ValueError("max_command_duration_seconds_must_be_positive")
        if stage_profile["commands_per_batch"] <= 0:
            raise ValueError("commands_per_batch_must_be_positive")

    def _query_stage_profile(program):
        guidance_names = list(getattr(program, "GuidanceNames", []))
        actor = getattr(program, "Actor", None)
        actor_floor_y = 0.0
        if actor is not None:
            try:
                actor_floor_y = round(float(actor.GetRootPosition()[1]), 3)
            except Exception:
                actor_floor_y = 0.0
        schema = {
            "show_title": "short title",
            "soft_room_limit": "number you choose",
            "hard_room_limit": "larger number you choose",
            "floor_marker_y": "number you choose",
            "max_command_duration_seconds": "number you choose",
            "camera_distance": "number you choose",
            "commands_per_batch": "positive integer you choose",
            "movement_vocabulary": [
                {
                    "id": "snake_case_movement_id",
                    "label": "model-authored movement label",
                    "guidance_style": "one exact available AI4AnimationPy guidance style",
                    "prompt": "model-authored movement cue",
                }
            ],
            "style_notes": ["model-authored style note"],
            "stage_targets": [
                {
                    "id": "snake_case_id",
                    "label": "visible prop label",
                    "position_x": "number you choose",
                    "position_y": "number you choose",
                    "position_z": "number you choose",
                    "prop_shape": "cube|sphere|pillar|ring|marker",
                    "color_rgb": ["red number 0..255 you choose", "green number 0..255 you choose", "blue number 0..255 you choose"],
                    "scale": "number you choose",
                    "height": "number you choose",
                    "purpose": "why the avatar should visit this prop",
                    "movement_prompt": "how the model should move around this prop",
                }
            ],
        }
        prompt = chr(10).join(
            [
                "You are the live movement director for one AI4AnimationPy biped avatar.",
                "Author the complete stage contract as JSON. The program will not invent prop coordinates, prop sizes, target names, movement phrases, or room limits.",
                "The avatar is rendered in an existing checkered room. Choose a visible stage layout and camera_distance so the avatar and multiple props are clearly visible at the same time.",
                f"Coordinate contract: position_x and position_z are horizontal floor axes; position_y is vertical base height. Current actor floor/root y is {actor_floor_y}. Keep floor_marker_y and each position_y near that actor floor value so props stay visible.",
                "Visibility contract: choose target positions that fit inside the camera distance you author, so the avatar and props appear together in the Standalone view.",
                "Place targets so the avatar can travel between them without immediately hitting the soft boundary you choose.",
                "The user goal is a local avatar-control proof where the live model authors the stage, movement vocabulary, styles, commands, numbers, and durations.",
                "Use only available AI4AnimationPy guidance styles as later movement options; do not invent guidance names.",
                f"Available guidance styles: {guidance_names}",
                "Create stage targets with distinct positions and purposes. Include movement_vocabulary objects, and every vocabulary object must map to one exact available guidance style.",
                f"Return JSON only with this schema: {schema}",
            ]
        )
        last_error = ""
        for attempt in range(5):
            payload = {
                "model": ollama_model,
                "prompt": prompt
                if not last_error
                else chr(10).join(
                    [
                        prompt,
                        f"Your previous stage contract was invalid: {last_error}",
                        "Correct it now. Return JSON only. All stage numbers must be authored by you.",
                    ]
                ),
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0.95,
                    "num_ctx": ollama_num_ctx,
                },
            }
            try:
                _write_trace(
                    "ollama_stage_request",
                    attempt=attempt + 1,
                    prompt=payload["prompt"],
                    options=payload["options"],
                    schema=schema,
                )
                response = _request_json(f"{ollama_url}/api/generate", payload)
                _write_trace(
                    "ollama_stage_response_raw",
                    attempt=attempt + 1,
                    response=response,
                    raw_response=response.get("response", ""),
                )
                raw_profile = _extract_json_object(str(response.get("response", "")))
                _normalise_stage_profile(raw_profile, guidance_names, actor_floor_y)
                _write_trace(
                    "stage_profile_applied",
                    raw_profile=raw_profile,
                    stage_profile=stage_profile,
                    stage_targets=stage_targets,
                )
                print(
                    "AI4_BIPED_LLM_STAGE "
                    f"model={ollama_model} "
                    f"profile={json.dumps({'stage_profile': stage_profile, 'stage_targets': stage_targets}, sort_keys=True)}",
                    flush=True,
                )
                return
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                _write_trace(
                    "ollama_stage_rejected",
                    attempt=attempt + 1,
                    error=last_error,
                )
                print(
                    "AI4_BIPED_STAGE_RETRY "
                    f"model={ollama_model} attempt={attempt + 1} error={last_error}",
                    flush=True,
                )
        raise RuntimeError(f"ollama_stage_invalid_after_retries: {last_error}")

    def _assert_ollama_model_available():
        tags = _request_json(f"{ollama_url}/api/tags")
        models = tags.get("models", [])
        names = {item.get("name") or item.get("model") for item in models}
        if ollama_model not in names:
            raise RuntimeError(
                f"ollama_model_not_installed: {ollama_model}; installed={sorted(names)}"
            )

    def _build_ollama_prompt(program, reason):
        if soft_room_limit is None or hard_room_limit is None or not stage_targets:
            raise RuntimeError("model_stage_profile_not_ready")
        guidance_names = list(getattr(program, "GuidanceNames", []))
        root = [round(float(v), 3) for v in program.Actor.GetRootPosition()]
        history = llm_control["history"][-6:]
        outside_room = abs(root[0]) > hard_room_limit or abs(root[2]) > hard_room_limit
        near_boundary = abs(root[0]) > soft_room_limit or abs(root[2]) > soft_room_limit
        boundary_note = (
            "The avatar is outside the safe room bounds. The next command must move back toward root [0, 0, 0]."
            if outside_room
            else "The avatar is near a soft boundary. Choose model-authored velocity signs that reduce the boundary violation; do not stand still."
            if near_boundary
            else "Keep the avatar inside the soft stage zone."
        )
        boundary_hints = []
        if root[0] > soft_room_limit:
            boundary_hints.append(
                f"Boundary fact: root.x={root[0]} is high, so velocity_x must be negative and visibly inward."
            )
        if root[0] < -soft_room_limit:
            boundary_hints.append(
                f"Boundary fact: root.x={root[0]} is low, so velocity_x must be positive and visibly inward."
            )
        if root[2] > soft_room_limit:
            boundary_hints.append(
                f"Boundary fact: root.z={root[2]} is high, so velocity_z must be negative and visibly inward."
            )
        if root[2] < -soft_room_limit:
            boundary_hints.append(
                f"Boundary fact: root.z={root[2]} is low, so velocity_z must be positive and visibly inward."
            )
        if boundary_hints:
            inward_targets = []
            for target_id, target in stage_targets.items():
                target_x = float(target["position"][0])
                target_z = float(target["position"][2])
                x_inward = abs(root[0]) <= soft_room_limit or (
                    root[0] > soft_room_limit and target_x < root[0]
                ) or (root[0] < -soft_room_limit and target_x > root[0])
                z_inward = abs(root[2]) <= soft_room_limit or (
                    root[2] > soft_room_limit and target_z < root[2]
                ) or (root[2] < -soft_room_limit and target_z > root[2])
                if x_inward and z_inward:
                    inward_targets.append(target_id)
            boundary_hints.append(
                f"For boundary recovery, choose one of these model-authored inward targets when possible: {inward_targets}"
            )
        stage_target_lines = [
            (
                f"{name}: {target['label']} at x={target['position'][0]}, "
                f"z={target['position'][2]} for {target['purpose']}; movement_prompt={target['movement_prompt']}"
            )
            for name, target in stage_targets.items()
        ]
        model_authoring_contract = [
            "You decide the live performance. The program supplies only current state, available AI4 style names, renderer capabilities, and safety/serialization constraints.",
            "The program will not add, reorder, or invent choreography. It will only validate and apply your JSON.",
            f"Use the movement vocabulary you authored in the stage profile: {stage_profile['movement_vocabulary']}",
            f"Use the style notes you authored in the stage profile: {stage_profile['style_notes']}",
            "Author every action_label, stage_target, style, velocity_x, velocity_z, speed, sprint, and duration_seconds in this response.",
            "AI4AnimationPy Biped is grounded locomotion, so any vertical or airborne impression must be expressed through your chosen guidance style and ground velocity.",
        ]
        schema = {
            "commands": [
                {
                    "action_label": "short verb phrase you write",
                    "stage_target": "one available stage target",
                    "style": "one available guidance style",
                    "velocity_x": "number you choose",
                    "velocity_z": "number you choose",
                    "speed": "number you choose",
                    "sprint": "boolean you choose",
                    "duration_seconds": "number you choose",
                    "rationale": "brief reason",
                }
            ]
        }
        prompt_lines = [
            "You are controlling a real-time AI4AnimationPy humanoid biped in a checkered room with visible stage props.",
            "You must author the next batch of movement commands. The neural Biped controller handles gait, contacts, IK, and body motion.",
            "Do not describe speech or audio.",
            "The program will feed your velocity/style/sprint/duration numbers directly into the Biped controller.",
            "Never invent guidance styles. style must exactly match one listed available guidance style or one guidance_style from your model-authored movement vocabulary.",
            f"Available guidance styles: {guidance_names}",
            f"Available stage targets: {'; '.join(stage_target_lines)}",
            f"Model-authored stage profile: {stage_profile}",
            boundary_note,
            "Coordinate contract: velocity_x and velocity_z are room-space velocities from -1.0..1.0.",
            "Positive velocity_x increases root.x. Positive velocity_z increases root.z.",
            f"Soft stage limit is +/-{soft_room_limit}; hard wall limit is +/-{hard_room_limit}.",
            "If root.z is below the negative limit, choose positive velocity_z to return. If root.z is above the positive limit, choose negative velocity_z.",
            "If root.x is below the negative limit, choose positive velocity_x to return. If root.x is above the positive limit, choose negative velocity_x.",
            "Choose each command duration yourself. Shorter durations create faster variety; longer durations create travel.",
            f"You authored commands_per_batch={stage_profile['commands_per_batch']} in the stage profile; use your own live judgment for the response length.",
            "speed is 0.0..1.0 and scales the velocity vector. sprint=true requests the Biped controller's faster locomotion mode.",
            "style and stage_target must exactly match available values.",
        ]
        prompt_lines.extend(boundary_hints)
        prompt_lines.extend(model_authoring_contract)
        prompt_lines.extend(
            [
                f"Reason for command: {reason}",
                f"Current root position: {root}",
                f"Recent commands: {history}",
                f"Return JSON only with this schema: {schema}",
            ]
        )
        return chr(10).join(prompt_lines)

    def _validate_room_bounds(root, move_x, move_z, speed):
        root_x = float(root[0])
        root_z = float(root[2])
        velocity_x = move_x
        velocity_z = -move_z
        if abs(root_x) <= hard_room_limit and abs(root_z) <= hard_room_limit:
            x_outward = (
                (root_x > soft_room_limit and velocity_x > 0.05)
                or (root_x < -soft_room_limit and velocity_x < -0.05)
            )
            z_outward = (
                (root_z > soft_room_limit and velocity_z > 0.05)
                or (root_z < -soft_room_limit and velocity_z < -0.05)
            )
            if x_outward or z_outward:
                raise ValueError(
                    "near_boundary_requires_inward_or_lateral_motion "
                    f"root=({root_x:.3f},{root_z:.3f}) "
                    f"velocity=({velocity_x:.3f},{velocity_z:.3f})"
                )
            return
        if speed <= 0.05:
            raise ValueError(
                f"outside_room_requires_motion_toward_center root=({root_x:.3f},{root_z:.3f})"
            )
        x_ok = (
            abs(root_x) <= hard_room_limit
            or (root_x > hard_room_limit and velocity_x < -0.05)
            or (root_x < -hard_room_limit and velocity_x > 0.05)
        )
        z_ok = (
            abs(root_z) <= hard_room_limit
            or (root_z > hard_room_limit and velocity_z < -0.05)
            or (root_z < -hard_room_limit and velocity_z > 0.05)
        )
        if not x_ok or not z_ok:
            raise ValueError(
                "movement_not_returning_to_safe_room "
                f"root=({root_x:.3f},{root_z:.3f}) "
                f"velocity=({velocity_x:.3f},{velocity_z:.3f})"
            )

    def _guidance_from_movement_ref(value):
        if value is None or str(value).strip() == "":
            return None
        key = _normalise_id(value, "movement_ref")
        for item in stage_profile.get("movement_vocabulary", []):
            candidates = {
                item["id"],
                _normalise_id(item["label"], "movement_label"),
            }
            if key in candidates:
                return item["guidance_style"]
        return None

    def _current_command_moves_toward_room(program):
        try:
            _validate_room_bounds(
                program.Actor.GetRootPosition(),
                llm_control["move_x"],
                llm_control["move_z"],
                max(llm_control["speed"], abs(llm_control["move_x"]), abs(llm_control["move_z"])),
            )
            return True
        except ValueError:
            return False

    def _parse_model_command(raw_command, guidance_names):
        style_value = (
            raw_command.get("style")
            or raw_command.get("guidance_style")
            or raw_command.get("guidance")
        )
        movement_ref = (
            raw_command.get("movement_id")
            or raw_command.get("movement")
            or raw_command.get("action_label")
            or raw_command.get("action")
        )
        try:
            style = _normalise_style(style_value, guidance_names)
        except ValueError:
            mapped_style = _guidance_from_movement_ref(movement_ref or style_value)
            if mapped_style is None:
                raise
            style = mapped_style
        speed = _bounded_float(raw_command.get("speed"), "speed", 0.0, 1.0)
        velocity_x = _bounded_float(
            raw_command.get("velocity_x", raw_command.get("vx")),
            "velocity_x",
            -1.0,
            1.0,
        ) * speed
        velocity_z = _bounded_float(
            raw_command.get("velocity_z", raw_command.get("vz")),
            "velocity_z",
            -1.0,
            1.0,
        ) * speed
        duration_seconds = _finite_float(
            raw_command.get("duration_seconds", raw_command.get("duration")),
            "duration_seconds",
        )
        if duration_seconds <= 0.0:
            raise ValueError("duration_seconds_must_be_positive")
        max_duration = float(stage_profile.get("max_command_duration_seconds", 0.0) or 0.0)
        if max_duration > 0.0 and duration_seconds > max_duration:
            raise ValueError(
                f"duration_seconds_exceeds_model_stage_contract: "
                f"{duration_seconds:.3f} > {max_duration:.3f}"
            )
        velocity_magnitude = math.sqrt((velocity_x * velocity_x) + (velocity_z * velocity_z))
        if velocity_magnitude > 1.0:
            raise ValueError(
                f"velocity_magnitude_exceeds_controller_limit: {velocity_magnitude:.3f}"
            )
        return {
            "action_label": str(
                raw_command.get("action_label")
                or raw_command.get("action")
                or raw_command.get("movement")
            ).strip()[:80],
            "stage_target": _normalise_stage_target(
                raw_command.get(
                    "stage_target",
                    raw_command.get("target", raw_command.get("target_id")),
                )
            ),
            "style": style,
            "velocity_x": velocity_x,
            "velocity_z": velocity_z,
            "move_x": velocity_x,
            "move_z": -velocity_z,
            "speed": speed,
            "sprint": _parse_bool(raw_command.get("sprint", raw_command.get("is_sprint"))),
            "duration_seconds": duration_seconds,
            "rationale": str(raw_command.get("rationale", "")).strip()[:160],
        }

    def _extract_model_commands(plan, guidance_names):
        raw_commands = plan.get("commands")
        if not isinstance(raw_commands, list) or not raw_commands:
            raise ValueError("model_response_must_include_non_empty_commands_list")
        commands = [_parse_model_command(item, guidance_names) for item in raw_commands]
        return commands

    def _apply_model_command(program, command, reason):
        if not hasattr(program, "_set_guidance"):
            raise RuntimeError("biped_program_missing_set_guidance")
        _validate_room_bounds(
            program.Actor.GetRootPosition(),
            command["move_x"],
            command["move_z"],
            command["speed"],
        )
        guidance_names = list(getattr(program, "GuidanceNames", []))
        style = command["style"]
        program._set_guidance(guidance_names.index(style))
        llm_control.update(
            {
                "last_plan_wall": time.monotonic(),
                "move_x": command["move_x"],
                "move_z": command["move_z"],
                "speed": command["speed"],
                "sprint": command["sprint"],
                "style": style,
                "stage_target": command["stage_target"],
                "action_label": command["action_label"],
                "rationale": command["rationale"],
                "duration_seconds": command["duration_seconds"],
                "action_expires_at": time.monotonic() + command["duration_seconds"],
            }
        )
        llm_control["history"].append(
            {
                "action_label": command["action_label"],
                "stage_target": command["stage_target"],
                "style": style,
                "move_x": round(command["move_x"], 3),
                "move_z": round(command["move_z"], 3),
                "velocity_x": round(command["velocity_x"], 3),
                "velocity_z": round(command["velocity_z"], 3),
                "speed": round(command["speed"], 3),
                "sprint": command["sprint"],
                "duration_seconds": round(command["duration_seconds"], 3),
            }
        )
        _write_trace(
            "command_applied",
            reason=reason,
            command=command,
            queue_length=len(llm_control["queue"]),
            history=llm_control["history"][-10:],
        )
        print(
            "AI4_BIPED_LLM_PLAN "
            f"model={ollama_model} reason={reason} action={command['action_label']!r} "
            f"target={command['stage_target']} style={style} sprint={command['sprint']} "
            f"move=({command['move_x']:.3f},{command['move_z']:.3f}) "
            f"velocity=({command['velocity_x']:.3f},{command['velocity_z']:.3f}) "
            f"speed={command['speed']:.3f} duration={command['duration_seconds']:.3f} "
            f"queue={len(llm_control['queue'])} rationale={command['rationale']!r}",
            flush=True,
        )

    def _apply_next_queued_command(program):
        while llm_control["queue"]:
            command = llm_control["queue"].pop(0)
            try:
                _apply_model_command(program, command, "queued_model_command")
                return True
            except Exception as exc:
                _write_trace(
                    "command_rejected",
                    reason="queued_model_command",
                    command=command,
                    error=f"{type(exc).__name__}: {exc}",
                )
                print(
                    "AI4_BIPED_LLM_QUEUE_REJECTED "
                    f"{type(exc).__name__}: {exc}",
                    flush=True,
                )
        return False

    def _query_ollama_plan(program, reason):
        guidance_names = list(getattr(program, "GuidanceNames", []))
        last_error = ""
        for attempt in range(5):
            prompt = _build_ollama_prompt(program, reason)
            if last_error:
                prompt = chr(10).join(
                    [
                        prompt,
                        f"Your previous response was invalid: {last_error}",
                        "Correct yourself now. Return JSON only. commands must contain exact guidance styles and model-authored numbers.",
                    ]
                )
            payload = {
                "model": ollama_model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0.95,
                    "num_ctx": ollama_num_ctx,
                },
            }
            try:
                _write_trace(
                    "ollama_plan_request",
                    attempt=attempt + 1,
                    reason=reason,
                    prompt=prompt,
                    options=payload["options"],
                    current_state={
                        "action_label": llm_control["action_label"],
                        "stage_target": llm_control["stage_target"],
                        "style": llm_control["style"],
                        "move_x": llm_control["move_x"],
                        "move_z": llm_control["move_z"],
                        "speed": llm_control["speed"],
                        "sprint": llm_control["sprint"],
                        "history": llm_control["history"][-10:],
                    },
                )
                response = _request_json(f"{ollama_url}/api/generate", payload)
                _write_trace(
                    "ollama_plan_response_raw",
                    attempt=attempt + 1,
                    reason=reason,
                    response=response,
                    raw_response=response.get("response", ""),
                )
                plan = _extract_json_object(str(response.get("response", "")))
                _write_trace(
                    "ollama_plan_parsed",
                    attempt=attempt + 1,
                    reason=reason,
                    plan=plan,
                )
                commands = _extract_model_commands(plan, guidance_names)
                llm_control["queue"] = commands[1:]
                _apply_model_command(program, commands[0], reason)
                return
            except Exception as exc:
                llm_control["queue"] = []
                last_error = f"{type(exc).__name__}: {exc}"
                _write_trace(
                    "ollama_plan_rejected",
                    attempt=attempt + 1,
                    reason=reason,
                    error=last_error,
                )
                print(
                    "AI4_BIPED_LLM_RETRY "
                    f"model={ollama_model} attempt={attempt + 1} error={last_error}",
                    flush=True,
                )
        raise ValueError(f"ollama_plan_invalid_after_retries: {last_error}")

    def _start_ollama_planner_thread(program):
        if autodrive != "ollama" or llm_control["planner_started"]:
            return
        llm_control["planner_started"] = True

        def _consume_replan_reason():
            llm_control["plan_requested"] = False
            if llm_control.pop("boundary_recovery_requested", False):
                return "boundary_recovery"
            return "periodic_replan"

        def _planner_loop():
            while True:
                replan_event.wait(max(0.5, ollama_plan_interval))
                replan_event.clear()
                try:
                    _query_ollama_plan(program, _consume_replan_reason())
                except ValueError as exc:
                    _write_trace(
                        "planner_rejected_batch",
                        error=f"{type(exc).__name__}: {exc}",
                    )
                    print(
                        f"AI4_BIPED_LLM_REJECTED {type(exc).__name__}: {exc}",
                        flush=True,
                    )
                    continue
                except Exception as exc:
                    llm_control["fatal_error"] = f"{type(exc).__name__}: {exc}"
                    _write_trace("planner_fatal_error", error=llm_control["fatal_error"])
                    print(
                        f"AI4_BIPED_LLM_ERROR {llm_control['fatal_error']}",
                        flush=True,
                    )
                    return

        thread = threading.Thread(
            target=_planner_loop,
            name="ai4animationpy-ollama-planner",
            daemon=True,
        )
        thread.start()

    def _request_replan(boundary_recovery=False):
        if boundary_recovery:
            llm_control["boundary_recovery_requested"] = True
        if not llm_control["plan_requested"]:
            llm_control["plan_requested"] = True
            replan_event.set()

    def _pause_current_model_command(reason):
        if (
            abs(llm_control["move_x"]) > 0.0
            or abs(llm_control["move_z"]) > 0.0
            or llm_control["speed"] > 0.0
        ):
            _write_trace(
                "command_paused",
                reason=reason,
                action_label=llm_control["action_label"],
                stage_target=llm_control["stage_target"],
                style=llm_control["style"],
                move_x=llm_control["move_x"],
                move_z=llm_control["move_z"],
                speed=llm_control["speed"],
                sprint=llm_control["sprint"],
            )
            print(
                "AI4_BIPED_COMMAND_PAUSED "
                f"reason={reason} action={llm_control['action_label']!r} "
                f"move=({llm_control['move_x']:.3f},{llm_control['move_z']:.3f}) "
                f"speed={llm_control['speed']:.3f}",
                flush=True,
            )
        llm_control["move_x"] = 0.0
        llm_control["move_z"] = 0.0
        llm_control["speed"] = 0.0
        llm_control["sprint"] = False
        llm_control["action_expires_at"] = 0.0

    def _maybe_refresh_ollama_plan(program):
        if autodrive != "ollama":
            return
        if llm_control["fatal_error"]:
            raise RuntimeError(llm_control["fatal_error"])
        if not _current_command_moves_toward_room(program):
            if abs(llm_control["move_x"]) > 0.0 or abs(llm_control["move_z"]) > 0.0:
                _write_trace(
                    "boundary_brake",
                    action_label=llm_control["action_label"],
                    stage_target=llm_control["stage_target"],
                    style=llm_control["style"],
                    move_x=llm_control["move_x"],
                    move_z=llm_control["move_z"],
                    speed=llm_control["speed"],
                )
                print(
                    "AI4_BIPED_BOUNDARY_BRAKE "
                    f"action={llm_control['action_label']!r} "
                    f"move=({llm_control['move_x']:.3f},{llm_control['move_z']:.3f})",
                    flush=True,
                )
            _pause_current_model_command("boundary_brake")
            llm_control["queue"] = []
            _request_replan(boundary_recovery=True)
            return
        if llm_control["action_expires_at"] and time.monotonic() >= llm_control["action_expires_at"]:
            if _apply_next_queued_command(program):
                return
            _pause_current_model_command("expired_waiting_for_model")
            _request_replan(boundary_recovery=False)

    stage_draw_error = {"reported": False}

    def _draw_llm_overlay(program):
        if autodrive != "ollama":
            return
        draw = getattr(AI4Animation, "Draw", None)
        color = getattr(AI4Animation, "Color", None)
        if draw is None or color is None:
            return
        title = stage_profile.get("show_title", "")
        trace_name = os.path.basename(llm_trace_path) if llm_trace_path else ""
        lines = [
            f"LLM stream: {ollama_model}",
            f"Stage: {title}",
            f"Action: {llm_control.get('action_label', '')}",
            f"Style: {llm_control.get('style', '')}",
            f"Target: {llm_control.get('stage_target', '')}",
            f"Speed: {llm_control.get('speed', 0.0):.2f} Sprint: {llm_control.get('sprint', False)}",
            f"Queue: {len(llm_control.get('queue', []))}",
            f"Trace: {trace_name}",
        ]
        rationale = llm_control.get("rationale", "")
        if rationale:
            lines.append(f"Rationale: {rationale}")
        draw.Text("\\n".join(lines), 0.54, 0.58, 0.014, color.BLACK)

    def _draw_stage_props(program):
        if not show_stage_props:
            return
        np_mod = namespace.get("np")
        draw = getattr(AI4Animation, "Draw", None)
        color = getattr(AI4Animation, "Color", None)
        if np_mod is None or draw is None or color is None:
            return
        try:
            def _arr(values):
                return np_mod.array(values, dtype=float)

            floor_y = float(stage_profile["floor_marker_y"])
            draw.WireCircle(
                _arr([[0.0, floor_y, 0.0]]),
                size=soft_room_limit,
                color=color.LIGHTGRAY,
            )
            for name, target in stage_targets.items():
                x, y, z = target["position"]
                scale = float(target["scale"])
                height = float(target["height"])
                r, g, b = target["color_rgb"]
                target_color = color.GetColor(r / 255.0, g / 255.0, b / 255.0, 1.0)
                shape = target["prop_shape"]
                if shape == "cube":
                    draw.Cube(_arr([[x, y + (height / 2.0), z]]), size=scale, color=target_color)
                elif shape == "sphere":
                    draw.Sphere(_arr([[x, y + height, z]]), size=scale, color=target_color)
                elif shape == "pillar":
                    draw.Cylinder(
                        _arr([[x, y, z]]),
                        _arr([[x, y + height, z]]),
                        scale,
                        scale / 2.0,
                        resolution=12,
                        color=target_color,
                    )
                elif shape == "ring":
                    draw.WireCircle(_arr([[x, y, z]]), size=scale, color=target_color)
                elif shape == "marker":
                    draw.Cube(_arr([[x, y + (height / 2.0), z]]), size=scale, color=target_color)
                    draw.WireCircle(_arr([[x, y, z]]), size=scale * 2.0, color=target_color)
                if hasattr(draw, "Text3D"):
                    draw.Text3D(
                        target["label"],
                        _arr([[x, y + height + scale, z]]),
                        size=0.015,
                        color=target_color,
                    )

            selected = stage_targets.get(llm_control.get("stage_target"))
            actor = getattr(program, "Actor", None)
            if selected is not None and actor is not None:
                root = actor.GetRootPosition().reshape(1, 3)
                x, y, z = selected["position"]
                selected_r, selected_g, selected_b = selected["color_rgb"]
                selected_color = color.GetColor(
                    selected_r / 255.0,
                    selected_g / 255.0,
                    selected_b / 255.0,
                    1.0,
                )
                target_point = _arr([[x, y + selected["height"], z]])
                draw.Line(root, target_point, color=selected_color)
                draw.WireCircle(_arr([[x, y, z]]), size=selected["scale"], color=selected_color)
        except Exception as exc:
            if not stage_draw_error["reported"]:
                stage_draw_error["reported"] = True
                print(f"AI4_BIPED_STAGE_PROPS_ERROR {type(exc).__name__}: {exc}", flush=True)

    original_start = Program.Start if hasattr(Program, "Start") else None

    if original_start is not None:
        def _start_with_camera(self, *args, **kwargs):
            original_start(self, *args, **kwargs)
            standalone = getattr(AI4Animation, "Standalone", None)
            camera = getattr(standalone, "Camera", None)
            if camera is not None:
                camera.Mode = camera_mode
                camera.Distance = camera_distance
            actor = getattr(self, "Actor", None)
            if actor is not None and hasattr(actor, "ShowMesh"):
                actor.ShowMesh(True)
            if autodrive != "none":
                io = getattr(standalone, "IO", None)
                vector3 = namespace.get("Vector3")
                if io is not None and vector3 is not None:
                    def _autodrive_wasdqe():
                        if autodrive == "ollama":
                            return vector3.Create(
                                llm_control["move_x"],
                                0.0,
                                llm_control["move_z"],
                            )
                        return vector3.Create(0.0, 0.0, 0.0)

                    io.GetWASDQE = _autodrive_wasdqe
                    raylib = namespace.get("rl")
                    if autodrive == "ollama" and raylib is not None and hasattr(raylib, "IsKeyDown"):
                        original_is_key_down = raylib.IsKeyDown

                        def _ollama_is_key_down(key):
                            if key == getattr(raylib, "KEY_LEFT_SHIFT", object()):
                                return bool(llm_control["sprint"])
                            return original_is_key_down(key)

                        raylib.IsKeyDown = _ollama_is_key_down
                    if autodrive == "ollama":
                        if not llm_trace_path:
                            raise RuntimeError("ollama_control_requires_llm_trace_path")
                        _assert_ollama_model_available()
                        _query_stage_profile(self)
                        if camera is not None:
                            camera.Distance = stage_profile["camera_distance"]
                        _query_ollama_plan(self, "startup")
                        _start_ollama_planner_thread(self)
                        _write_trace(
                            "stream_started",
                            ollama_url=ollama_url,
                            ollama_model=ollama_model,
                            plan_interval=ollama_plan_interval,
                            soft_room_limit=soft_room_limit,
                            hard_room_limit=hard_room_limit,
                            stage_targets=list(stage_targets),
                        )
                        print(
                            "AI4_BIPED_OLLAMA_CONTROL enabled "
                            f"model={ollama_model} url={ollama_url} "
                            f"plan_interval={ollama_plan_interval} "
                            f"trace={llm_trace_path} "
                            f"soft_room_limit={soft_room_limit} "
                            f"hard_room_limit={hard_room_limit} "
                            f"stage_targets={list(stage_targets)}",
                            flush=True,
                        )
                    else:
                        print(f"AI4_BIPED_AUTODRIVE enabled mode={autodrive}", flush=True)
                else:
                    print("AI4_BIPED_CONTROL unavailable: missing IO or Vector3", flush=True)

        Program.Start = _start_with_camera

    original_update = Program.Update if hasattr(Program, "Update") else None
    if original_update is not None and telemetry_interval > 0:
        last_telemetry = {"wall": 0.0}

        def _update_with_telemetry(self, *args, **kwargs):
            _maybe_refresh_ollama_plan(self)
            result = original_update(self, *args, **kwargs)
            now = time.monotonic()
            if now - last_telemetry["wall"] >= telemetry_interval:
                last_telemetry["wall"] = now
                try:
                    root = getattr(self, "Actor").GetRootPosition()
                    sim = getattr(self, "SimulationObject", None)
                    sim_pos = sim.GetPosition(0) if sim is not None else None
                    sim_vel = sim.GetVelocity(0) if sim is not None else None
                    root_values = [round(float(v), 3) for v in root]
                    pos_values = [round(float(v), 3) for v in sim_pos] if sim_pos is not None else None
                    vel_values = [round(float(v), 3) for v in sim_vel] if sim_vel is not None else None
                    print(
                        "AI4_BIPED_TELEMETRY "
                        f"autodrive={autodrive} "
                        f"action={llm_control['action_label']!r} "
                        f"style={getattr(self, 'SelectedGuidance', 'unknown')} "
                        f"root={root_values} sim_pos={pos_values} sim_vel={vel_values}",
                        flush=True,
                    )
                    _write_trace(
                        "telemetry",
                        autodrive=autodrive,
                        action_label=llm_control["action_label"],
                        stage_target=llm_control["stage_target"],
                        style=llm_control["style"],
                        selected_guidance=getattr(self, "SelectedGuidance", "unknown"),
                        root=root_values,
                        sim_pos=pos_values,
                        sim_vel=vel_values,
                        move_x=llm_control["move_x"],
                        move_z=llm_control["move_z"],
                        speed=llm_control["speed"],
                        sprint=llm_control["sprint"],
                    )
                except Exception as exc:
                    print(f"AI4_BIPED_TELEMETRY_ERROR {type(exc).__name__}: {exc}", flush=True)
            return result

        Program.Update = _update_with_telemetry

    original_gui = Program.GUI if hasattr(Program, "GUI") else None
    if original_gui is not None:
        def _gui_with_llm_overlay(self, *args, **kwargs):
            result = original_gui(self, *args, **kwargs)
            _draw_llm_overlay(self)
            return result

        Program.GUI = _gui_with_llm_overlay

    original_draw = Program.Draw if hasattr(Program, "Draw") else None
    if original_draw is not None:
        def _draw_with_stage_props(self, *args, **kwargs):
            result = original_draw(self, *args, **kwargs)
            _draw_stage_props(self)
            return result

        Program.Draw = _draw_with_stage_props

    original_standalone = Program.Standalone if hasattr(Program, "Standalone") else None
    if original_standalone is not None:
        def _standalone_with_actor_debug(self, *args, **kwargs):
            original_standalone(self, *args, **kwargs)
            actor = getattr(self, "Actor", None)
            if actor is None:
                return
            if hasattr(actor, "ShowMesh"):
                actor.ShowMesh(True)
            for button_name in ("Button_Root", "Button_Skeleton"):
                button = getattr(actor, button_name, None)
                if button is not None:
                    button.Active = True

        Program.Standalone = _standalone_with_actor_debug

    AI4Animation(Program())
""".strip()


def demo_env(source_root: Path) -> dict[str, str]:
    env = os.environ.copy()
    source_text = str(source_root)
    env["PYTHONPATH"] = (
        source_text
        if not env.get("PYTHONPATH")
        else source_text + os.pathsep + env["PYTHONPATH"]
    )
    return env


def gate_reason(source_root: Path, name: str, program_path: Path) -> str:
    if not program_path.exists():
        return "program_missing"

    dataset_path = DATASET_GATED.get(name)
    if dataset_path and not (source_root / dataset_path).exists():
        return "dataset_missing"

    required_module = PYTHON_MODULE_GATED.get(name)
    if required_module and importlib.util.find_spec(required_module) is None:
        return f"python_module_missing:{required_module}"

    return ""


def ensure_raylib6_skinned_mesh_compat(source_root: Path) -> str:
    """Patch an external AI4AnimationPy checkout for Raylib 6 skinning fields."""
    target = source_root / "ai4animation" / "Standalone" / "SkinnedMesh.py"
    if not target.exists():
        return "skipped:no_skinned_mesh_file"

    text = target.read_text(encoding="utf-8")
    if "boneIndices" in text and "raylib_model.boneMatrices" in text:
        return "already_compatible"

    updated = text
    updated = updated.replace(RAYLIB6_COMPAT_OLD_IDS, RAYLIB6_COMPAT_NEW_IDS)
    updated = updated.replace(RAYLIB6_COMPAT_OLD_MATRICES, RAYLIB6_COMPAT_NEW_MATRICES)
    if updated == text:
        return "skipped:pattern_not_found"

    target.write_text(updated, encoding="utf-8")
    return "patched_raylib6_skinned_mesh"


def ensure_raylib6_shader_compat(source_root: Path) -> str:
    """Patch skinned shaders for Raylib 6 bone-index attribute naming."""
    shader_dir = source_root / "ai4animation" / "Standalone" / "resources" / "shaders"
    shader_names = (
        "skinnedBasic.vs",
        "skinnedShadow.vs",
        "forwardSkinned.vs",
        "forwardSkinnedShadow.vs",
    )
    missing = [name for name in shader_names if not (shader_dir / name).exists()]
    if missing:
        return "skipped:missing:" + ",".join(missing)

    changed = []
    for name in shader_names:
        path = shader_dir / name
        text = path.read_text(encoding="utf-8")
        updated = text.replace("vertexBoneIds", "vertexBoneIndices")
        if updated != text:
            path.write_text(updated, encoding="utf-8")
            changed.append(name)

    if changed:
        return "patched:" + ",".join(changed)
    return "already_compatible"


def ensure_raylib6_cpu_skinning_fallback(source_root: Path) -> str:
    """Patch AI4AnimationPy skinned meshes for Raylib builds without GPU skinning."""
    target = source_root / "ai4animation" / "Standalone" / "SkinnedMesh.py"
    if not target.exists():
        return "skipped:no_skinned_mesh_file"

    text = target.read_text(encoding="utf-8")
    if (
        "self.CpuSkinningFallback = True" in text
        and "UpdateMeshBuffer" in text
        and "self.CpuSkinnedChunks.append" in text
    ):
        return "already_compatible"

    updated = text
    replacements = (
        (RAYLIB6_CPU_SKINNING_IMPORT_OLD, RAYLIB6_CPU_SKINNING_IMPORT_NEW),
        (RAYLIB6_CPU_SKINNING_ATTRS_OLD, RAYLIB6_CPU_SKINNING_ATTRS_NEW),
        (RAYLIB6_CPU_SKINNING_BONES_OLD, RAYLIB6_CPU_SKINNING_BONES_NEW),
        (RAYLIB6_CPU_SKINNING_APPEND_OLD, RAYLIB6_CPU_SKINNING_APPEND_NEW),
        (RAYLIB6_CPU_SKINNING_UPDATE_OLD, RAYLIB6_CPU_SKINNING_UPDATE_NEW),
    )
    missed = []
    for old, new in replacements:
        if old in updated:
            updated = updated.replace(old, new, 1)
        elif new not in updated:
            missed.append(old.splitlines()[0].strip())

    if missed:
        return "skipped:pattern_not_found:" + ",".join(missed)
    if updated == text:
        return "already_compatible"

    target.write_text(updated, encoding="utf-8")
    return "patched_raylib6_cpu_skinning"


def ensure_raylib6_cpu_shader_selection(source_root: Path) -> str:
    """Route CPU-skinned meshes through non-skinned shaders."""
    target = source_root / "ai4animation" / "Standalone" / "RenderPipeline.py"
    if not target.exists():
        return "skipped:no_render_pipeline_file"

    text = target.read_text(encoding="utf-8")
    if (
        "def UsesCpuSkinningFallback" in text
        and "self.BasicShader\n                if UsesCpuSkinningFallback" in text
        and "self.ForwardShader\n                if UsesCpuSkinningFallback" in text
    ):
        return "already_compatible"

    updated = text
    replacements = (
        (RAYLIB6_CPU_RENDER_HELPER_OLD, RAYLIB6_CPU_RENDER_HELPER_NEW),
        (RAYLIB6_CPU_RENDER_SHADOW_OLD, RAYLIB6_CPU_RENDER_SHADOW_NEW),
        (RAYLIB6_CPU_RENDER_GBUFFER_OLD, RAYLIB6_CPU_RENDER_GBUFFER_NEW),
        (RAYLIB6_CPU_RENDER_FORWARD_OLD, RAYLIB6_CPU_RENDER_FORWARD_NEW),
        (RAYLIB6_CPU_RENDER_FORWARD_SHADOW_OLD, RAYLIB6_CPU_RENDER_FORWARD_SHADOW_NEW),
    )
    missed = []
    for old, new in replacements:
        if old in updated:
            updated = updated.replace(old, new, 1)
        elif new not in updated:
            missed.append(old.splitlines()[0].strip())

    if missed:
        return "skipped:pattern_not_found:" + ",".join(missed)
    if updated == text:
        return "already_compatible"

    target.write_text(updated, encoding="utf-8")
    return "patched_raylib6_cpu_shader_selection"


def kill_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if platform.system().lower().startswith("win"):
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        process.kill()


def run_demo(
    *,
    source_root: Path,
    artifact_dir: Path,
    name: str,
    program: str,
    timeout_seconds: float,
    python_executable: str,
) -> DemoResult:
    program_path = source_root / program
    log_path = artifact_dir / f"{name.replace('/', '_')}.log"
    start = time.monotonic()

    blocked = gate_reason(source_root, name, program_path)
    if blocked == "program_missing":
        log_path.write_text(f"Missing demo program: {program_path}\n", encoding="utf-8")
        return DemoResult(name, program, "failed", None, 0.0, str(log_path), "program_missing")
    if blocked == "dataset_missing":
        dataset_path = DATASET_GATED[name]
        log_path.write_text(
            f"Skipped: required dataset folder is absent: {source_root / dataset_path}\n",
            encoding="utf-8",
        )
        return DemoResult(name, program, "skipped", None, 0.0, str(log_path), "dataset_missing")
    if blocked.startswith("python_module_missing:"):
        required_module = blocked.split(":", 1)[1]
        log_path.write_text(
            f"Skipped: required Python module is absent: {required_module}\n",
            encoding="utf-8",
        )
        return DemoResult(
            name,
            program,
            "skipped",
            None,
            0.0,
            str(log_path),
            f"python_module_missing:{required_module}",
        )

    process = subprocess.Popen(
        [python_executable, "-c", demo_entrypoint(), str(program_path)],
        cwd=str(program_path.parent),
        env=demo_env(source_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        output, _ = process.communicate(timeout=timeout_seconds)
        elapsed = time.monotonic() - start
        log_path.write_text(output or "", encoding="utf-8")
        if process.returncode == 0:
            return DemoResult(name, program, "passed", 0, elapsed, str(log_path), "completed")
        return DemoResult(
            name,
            program,
            "failed",
            process.returncode,
            elapsed,
            str(log_path),
            "exited_before_startup_deadline",
        )
    except subprocess.TimeoutExpired:
        kill_process_tree(process)
        output, _ = process.communicate(timeout=5)
        elapsed = time.monotonic() - start
        log_path.write_text(output or "", encoding="utf-8")
        return DemoResult(name, program, "passed", None, elapsed, str(log_path), "startup_timeout_reached")


def launch_demo(
    *,
    source_root: Path,
    artifact_dir: Path,
    name: str,
    program: str,
    python_executable: str,
    launch_wait_seconds: float,
    camera_mode: str,
    camera_distance: float,
    autodrive: str,
    telemetry_interval: float,
    ollama_url: str,
    ollama_model: str,
    ollama_timeout: float,
    ollama_num_ctx: int,
    ollama_plan_interval: float,
    stage_props: str,
) -> DemoResult:
    program_path = source_root / program
    log_path = artifact_dir / f"{name.replace('/', '_')}.launch.log"
    start = time.monotonic()

    blocked = gate_reason(source_root, name, program_path)
    if blocked:
        log_path.write_text(f"Cannot launch {name}: {blocked}\n", encoding="utf-8")
        status = "skipped" if blocked != "program_missing" else "failed"
        return DemoResult(name, program, status, None, 0.0, str(log_path), blocked)

    creationflags = 0
    if platform.system().lower().startswith("win"):
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

    log_file = log_path.open("w", encoding="utf-8")
    env = demo_env(source_root)
    env["AI4ANIMATIONPY_CAMERA_MODE"] = camera_mode
    env["AI4ANIMATIONPY_CAMERA_DISTANCE"] = str(camera_distance)
    env["AI4ANIMATIONPY_AUTODRIVE"] = autodrive
    env["AI4ANIMATIONPY_TELEMETRY_INTERVAL"] = str(telemetry_interval)
    env["AI4ANIMATIONPY_OLLAMA_URL"] = ollama_url
    env["AI4ANIMATIONPY_OLLAMA_MODEL"] = ollama_model
    env["AI4ANIMATIONPY_OLLAMA_TIMEOUT"] = str(ollama_timeout)
    env["AI4ANIMATIONPY_OLLAMA_NUM_CTX"] = str(ollama_num_ctx)
    env["AI4ANIMATIONPY_OLLAMA_PLAN_INTERVAL"] = str(ollama_plan_interval)
    llm_trace_path = artifact_dir / f"{name.replace('/', '_')}.llm_trace.jsonl"
    env["AI4ANIMATIONPY_LLM_TRACE_PATH"] = str(llm_trace_path)
    env["AI4ANIMATIONPY_STAGE_PROPS"] = stage_props
    entrypoint_path = artifact_dir / f"{name.replace('/', '_')}.launch_entrypoint.py"
    entrypoint_path.write_text(launch_entrypoint() + "\n", encoding="utf-8")

    process = subprocess.Popen(
        [python_executable, str(entrypoint_path), str(program_path)],
        cwd=str(program_path.parent),
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True,
        creationflags=creationflags,
    )
    time.sleep(max(1.0, launch_wait_seconds))
    elapsed = time.monotonic() - start
    exit_code = process.poll()
    if exit_code is not None:
        log_file.close()
        return DemoResult(
            name,
            program,
            "failed",
            exit_code,
            elapsed,
            str(log_path),
            "exited_before_launch_deadline",
        )

    launch_payload = {
        "name": name,
        "program": program,
        "pid": process.pid,
        "log_path": str(log_path),
        "source_root": str(source_root),
        "camera_mode": camera_mode,
        "camera_distance": camera_distance,
        "autodrive": autodrive,
        "telemetry_interval": telemetry_interval,
        "ollama_url": ollama_url,
        "ollama_model": ollama_model,
        "ollama_timeout": ollama_timeout,
        "ollama_num_ctx": ollama_num_ctx,
        "ollama_plan_interval": ollama_plan_interval,
        "llm_trace_path": str(llm_trace_path),
        "stage_props": stage_props,
    }
    (artifact_dir / "launch.json").write_text(json.dumps(launch_payload, indent=2) + "\n", encoding="utf-8")
    return DemoResult(name, program, "passed", None, elapsed, str(log_path), f"running:pid={process.pid}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--timeout-scale", type=float, default=1.0)
    parser.add_argument("--only", action="append", default=[], help="Run demos whose name contains this text.")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--launch", action="store_true", help="Leave one selected Standalone demo running.")
    parser.add_argument("--launch-wait", type=float, default=8.0, help="Seconds to wait before declaring launch healthy.")
    parser.add_argument("--launch-camera-mode", choices=["free", "fixed", "third", "orbit"], default="third")
    parser.add_argument("--launch-camera-distance", type=float, default=2.8)
    parser.add_argument(
        "--launch-autodrive",
        choices=["none", "ollama"],
        default="none",
        help="Patch demo input during --launch. Use ollama for model-authored Biped commands.",
    )
    parser.add_argument(
        "--launch-telemetry-interval",
        type=float,
        default=1.0,
        help="Seconds between per-frame root/velocity telemetry lines during --launch.",
    )
    parser.add_argument("--launch-ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--launch-ollama-model", default=os.getenv("OLLAMA_MODEL", "llama3.1:8b"))
    parser.add_argument("--launch-ollama-timeout", type=float, default=12.0)
    parser.add_argument("--launch-ollama-num-ctx", type=int, default=8192)
    parser.add_argument(
        "--launch-ollama-plan-interval",
        type=float,
        default=5.0,
        help="Seconds between Ollama-authored Biped control plans.",
    )
    parser.add_argument(
        "--launch-stage-props",
        choices=["on", "off"],
        default="on",
        help="Draw local stage props and target markers in the Standalone room.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_root = args.source_root.resolve()
    artifact_dir = args.artifact_dir.resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    compat_status = ensure_raylib6_skinned_mesh_compat(source_root)
    shader_compat_status = ensure_raylib6_shader_compat(source_root)
    cpu_skinning_status = ensure_raylib6_cpu_skinning_fallback(source_root)
    cpu_shader_status = ensure_raylib6_cpu_shader_selection(source_root)

    selected = DEMO_PROGRAMS
    if args.only:
        filters = [item.lower() for item in args.only]
        selected = [
            demo
            for demo in selected
            if any(filter_text in demo[0].lower() for filter_text in filters)
        ]

    if args.launch:
        if len(selected) != 1:
            print(
                "ERROR: --launch requires exactly one selected demo; use --only Biped or another exact filter.",
                file=sys.stderr,
            )
            return 2
        name, program, _seconds = selected[0]
        results = [
            launch_demo(
                source_root=source_root,
                artifact_dir=artifact_dir,
                name=name,
                program=program,
                python_executable=args.python,
                launch_wait_seconds=args.launch_wait,
                camera_mode=args.launch_camera_mode,
                camera_distance=args.launch_camera_distance,
                autodrive=args.launch_autodrive,
                telemetry_interval=args.launch_telemetry_interval,
                ollama_url=args.launch_ollama_url,
                ollama_model=args.launch_ollama_model,
                ollama_timeout=args.launch_ollama_timeout,
                ollama_num_ctx=args.launch_ollama_num_ctx,
                ollama_plan_interval=args.launch_ollama_plan_interval,
                stage_props=args.launch_stage_props,
            )
        ]
    else:
        results = [
        run_demo(
            source_root=source_root,
            artifact_dir=artifact_dir,
            name=name,
            program=program,
            timeout_seconds=max(1.0, seconds * args.timeout_scale),
            python_executable=args.python,
        )
        for name, program, seconds in selected
        ]

    summary = {
        "source_root": str(source_root),
        "artifact_dir": str(artifact_dir),
        "compatibility": {
            "raylib6_skinned_mesh": compat_status,
            "raylib6_skinned_shader_attributes": shader_compat_status,
            "raylib6_cpu_skinning": cpu_skinning_status,
            "raylib6_cpu_shader_selection": cpu_shader_status,
        },
        "passed": sum(1 for result in results if result.status == "passed"),
        "failed": sum(1 for result in results if result.status == "failed"),
        "skipped": sum(1 for result in results if result.status == "skipped"),
        "results": [asdict(result) for result in results],
    }
    (artifact_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        for result in results:
            print(
                f"{result.status.upper():7} {result.name:28} "
                f"{result.reason:32} {result.elapsed_seconds:6.2f}s {result.log_path}"
            )
        print(
            f"Summary: {summary['passed']} passed, {summary['failed']} failed, "
            f"{summary['skipped']} skipped"
        )
        print(
            "Compatibility: "
            f"raylib6_skinned_mesh={compat_status}, "
            f"raylib6_skinned_shader_attributes={shader_compat_status}, "
            f"raylib6_cpu_skinning={cpu_skinning_status}, "
            f"raylib6_cpu_shader_selection={cpu_shader_status}"
        )

    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
