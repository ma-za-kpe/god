"""Motion projection bridge for anatomy action bundles.

This module turns bounded anatomy action bundles into deterministic renderer
controls and simulation-backend hints. It does not invent anatomy nodes and it
does not pretend to run OpenSim or MuSkeMo locally; it prepares source-backed
bridge records those adapters can consume later.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .retrieval import ActionBundle


ANATOMY_MOTION_SCHEMA_VERSION = "god.anatomy_motion_projection.v1"


@dataclass(frozen=True)
class AnatomyMotionRendererControl:
    node_id: str
    adapter: str
    target: str
    channel: str
    value: dict[str, Any]
    duration_ms: int
    phase: str
    capability: str = ""
    source_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "adapter": self.adapter,
            "target": self.target,
            "channel": self.channel,
            "capability": self.capability,
            "value": dict(self.value),
            "duration_ms": self.duration_ms,
            "phase": self.phase,
            "source_ids": list(self.source_ids),
        }


@dataclass(frozen=True)
class AnatomyMotionSimulationHint:
    node_id: str
    backend: str
    component: str
    coordinate: str
    value: dict[str, Any]
    phase: str
    source_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "backend": self.backend,
            "component": self.component,
            "coordinate": self.coordinate,
            "value": dict(self.value),
            "phase": self.phase,
            "source_ids": list(self.source_ids),
        }


@dataclass(frozen=True)
class AnatomyMotionVisualCue:
    action: str
    node_id: str
    shape: str
    class_name: str
    geometry: dict[str, Any]
    label: str
    source_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "node_id": self.node_id,
            "shape": self.shape,
            "class_name": self.class_name,
            "geometry": dict(self.geometry),
            "label": self.label,
            "source_ids": list(self.source_ids),
        }


@dataclass(frozen=True)
class AnatomyMotionPlan:
    action: str
    renderer_controls: tuple[AnatomyMotionRendererControl, ...]
    simulation_hints: tuple[AnatomyMotionSimulationHint, ...]
    visual_cues: tuple[AnatomyMotionVisualCue, ...]
    source_bundle_node_ids: tuple[str, ...]
    diagnostics: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "status": "complete" if not self.diagnostics else "degraded",
            "renderer_controls": [control.to_dict() for control in self.renderer_controls],
            "simulation_hints": [hint.to_dict() for hint in self.simulation_hints],
            "visual_cues": [cue.to_dict() for cue in self.visual_cues],
            "source_bundle_node_ids": list(self.source_bundle_node_ids),
            "diagnostics": list(self.diagnostics),
            "renderer_control_count": len(self.renderer_controls),
            "simulation_hint_count": len(self.simulation_hints),
            "visual_cue_count": len(self.visual_cues),
        }


@dataclass(frozen=True)
class AnatomyMotionProjection:
    schema: str
    plans: tuple[AnatomyMotionPlan, ...]
    diagnostics: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "status": "complete" if not self.diagnostics else "degraded",
            "plans": [plan.to_dict() for plan in self.plans],
            "diagnostics": list(self.diagnostics),
            "plan_count": len(self.plans),
            "renderer_control_count": sum(len(plan.renderer_controls) for plan in self.plans),
            "simulation_hint_count": sum(len(plan.simulation_hints) for plan in self.plans),
            "visual_cue_count": sum(len(plan.visual_cues) for plan in self.plans),
            "diagnostic_count": len(self.diagnostics),
        }


def build_anatomy_motion_projection(
    action_bundles: tuple[ActionBundle, ...] | list[ActionBundle],
) -> AnatomyMotionProjection:
    """Compile deterministic motion bridge plans for supported action bundles."""

    bundle_by_action = {bundle.action: bundle for bundle in action_bundles}
    plans: list[AnatomyMotionPlan] = []
    diagnostics: list[str] = []
    for action in ("wave", "sit", "run"):
        bundle = bundle_by_action.get(action)
        if bundle is None:
            diagnostics.append(f"missing_motion_action:{action}")
            continue
        plan = _compile_motion_plan(bundle)
        plans.append(plan)
        diagnostics.extend(f"{action}:{diagnostic}" for diagnostic in plan.diagnostics)

    return AnatomyMotionProjection(
        schema=ANATOMY_MOTION_SCHEMA_VERSION,
        plans=tuple(plans),
        diagnostics=tuple(dict.fromkeys(diagnostics)),
    )


def _compile_motion_plan(bundle: ActionBundle) -> AnatomyMotionPlan:
    spec = _MOTION_SPECS.get(bundle.action, {})
    node_by_id = {node.id: node for node in bundle.nodes}
    diagnostics = list(bundle.diagnostics)
    renderer_controls: list[AnatomyMotionRendererControl] = []
    simulation_hints: list[AnatomyMotionSimulationHint] = []
    visual_cues: list[AnatomyMotionVisualCue] = []

    for node_id in spec.get("required_nodes", ()):
        if node_id not in node_by_id:
            diagnostics.append(f"missing_motion_node:{node_id}")

    for control_spec in spec.get("renderer_controls", ()):
        node = node_by_id.get(control_spec["node_id"])
        if node is None:
            continue
        capability = control_spec.get("capability", "")
        if capability and capability not in node.control_channels:
            diagnostics.append(f"unsupported_motion_capability:{node.id}:{capability}")
            continue
        renderer_controls.append(
            AnatomyMotionRendererControl(
                node_id=node.id,
                adapter=control_spec["adapter"],
                target=control_spec["target"],
                channel=control_spec["channel"],
                capability=capability,
                value=control_spec["value"],
                duration_ms=control_spec["duration_ms"],
                phase=control_spec["phase"],
                source_ids=node.source_ids,
            )
        )

    for hint_spec in spec.get("simulation_hints", ()):
        node = node_by_id.get(hint_spec["node_id"])
        if node is None:
            continue
        simulation_hints.append(
            AnatomyMotionSimulationHint(
                node_id=node.id,
                backend=hint_spec["backend"],
                component=hint_spec["component"],
                coordinate=hint_spec["coordinate"],
                value=hint_spec["value"],
                phase=hint_spec["phase"],
                source_ids=node.source_ids,
            )
        )

    for cue_spec in spec.get("visual_cues", ()):
        node = node_by_id.get(cue_spec["node_id"])
        if node is None:
            continue
        visual_cues.append(
            AnatomyMotionVisualCue(
                action=bundle.action,
                node_id=node.id,
                shape=cue_spec["shape"],
                class_name=cue_spec["class_name"],
                geometry=cue_spec["geometry"],
                label=node.label,
                source_ids=node.source_ids,
            )
        )

    return AnatomyMotionPlan(
        action=bundle.action,
        renderer_controls=tuple(renderer_controls),
        simulation_hints=tuple(simulation_hints),
        visual_cues=tuple(visual_cues),
        source_bundle_node_ids=tuple(node.id for node in bundle.nodes),
        diagnostics=tuple(dict.fromkeys(diagnostics)),
    )


_MOTION_SPECS: dict[str, dict[str, Any]] = {
    "wave": {
        "required_nodes": (
            "region:right_hand",
            "digit:right_pollex",
            "digit:right_index_finger",
            "joint:right_shoulder",
            "joint:right_elbow",
        ),
        "renderer_controls": (
            {
                "node_id": "region:right_hand",
                "capability": "open_close",
                "adapter": "browser_svg",
                "target": "right_arm",
                "channel": "wave_arc",
                "value": {"degrees": 30, "cycles": 2, "direction": "outward"},
                "duration_ms": 1400,
                "phase": "primary",
            },
            {
                "node_id": "digit:right_pollex",
                "capability": "opposition",
                "adapter": "browser_svg",
                "target": "right_thumb",
                "channel": "opposition",
                "value": {"weight": 0.35},
                "duration_ms": 900,
                "phase": "secondary",
            },
            {
                "node_id": "digit:right_index_finger",
                "capability": "flexion_extension",
                "adapter": "browser_svg",
                "target": "right_index_finger",
                "channel": "finger_relax",
                "value": {"extension": 0.55},
                "duration_ms": 900,
                "phase": "secondary",
            },
        ),
        "simulation_hints": (
            {
                "node_id": "region:right_hand",
                "backend": "muskemo",
                "component": "end_effector_trajectory",
                "coordinate": "right_hand_wave_arc",
                "value": {"path": "lateral_arc", "cycles": 2},
                "phase": "primary",
            },
            {
                "node_id": "digit:right_pollex",
                "backend": "opensim",
                "component": "coordinate_hint",
                "coordinate": "thumb_opposition_r",
                "value": {"normalized": 0.35},
                "phase": "secondary",
            },
            {
                "node_id": "digit:right_index_finger",
                "backend": "opensim",
                "component": "coordinate_hint",
                "coordinate": "index_flexion_r",
                "value": {"normalized": -0.2},
                "phase": "secondary",
            },
        ),
        "visual_cues": (
            {
                "node_id": "region:right_hand",
                "shape": "path",
                "class_name": "wave-arc",
                "geometry": {"d": "M316 525 C372 472 370 394 344 342"},
            },
        ),
    },
    "sit": {
        "required_nodes": (
            "joint:right_knee",
            "region:right_foot",
            "digit:right_hallux",
            "joint:right_hip",
            "region:pelvis",
        ),
        "renderer_controls": (
            {
                "node_id": "joint:right_knee",
                "capability": "flexion_extension",
                "adapter": "browser_svg",
                "target": "right_leg",
                "channel": "knee_flexion",
                "value": {"degrees": 68, "direction": "flex"},
                "duration_ms": 1100,
                "phase": "primary",
            },
            {
                "node_id": "region:right_foot",
                "capability": "weight_bearing",
                "adapter": "browser_svg",
                "target": "right_foot",
                "channel": "plantar_contact",
                "value": {"weight": 0.72},
                "duration_ms": 1100,
                "phase": "support",
            },
            {
                "node_id": "digit:right_hallux",
                "capability": "ground_contact",
                "adapter": "browser_svg",
                "target": "right_hallux",
                "channel": "toe_contact",
                "value": {"weight": 0.5},
                "duration_ms": 1100,
                "phase": "support",
            },
        ),
        "simulation_hints": (
            {
                "node_id": "joint:right_knee",
                "backend": "opensim",
                "component": "coordinate_hint",
                "coordinate": "knee_angle_r",
                "value": {"degrees": 68},
                "phase": "primary",
            },
            {
                "node_id": "region:right_foot",
                "backend": "muskemo",
                "component": "contact_constraint",
                "coordinate": "right_foot_ground_contact",
                "value": {"weight": 0.72},
                "phase": "support",
            },
        ),
        "visual_cues": (
            {
                "node_id": "joint:right_knee",
                "shape": "path",
                "class_name": "sit-knee",
                "geometry": {"d": "M248 456 C292 510 300 579 276 639"},
            },
        ),
    },
    "run": {
        "required_nodes": (
            "joint:right_knee",
            "digit:right_hallux",
            "region:right_foot",
            "system:cardiovascular",
            "system:respiratory",
            "skin:forehead",
            "joint:right_ankle",
            "region:pelvis",
        ),
        "renderer_controls": (
            {
                "node_id": "joint:right_knee",
                "capability": "flexion_extension",
                "adapter": "browser_svg",
                "target": "right_leg",
                "channel": "running_knee_cycle",
                "value": {"min_degrees": 12, "max_degrees": 64, "cycles": 3},
                "duration_ms": 1800,
                "phase": "primary",
            },
            {
                "node_id": "digit:right_hallux",
                "capability": "ground_contact",
                "adapter": "browser_svg",
                "target": "right_hallux",
                "channel": "toe_off",
                "value": {"weight": 0.85, "cycles": 3},
                "duration_ms": 1800,
                "phase": "push_off",
            },
            {
                "node_id": "skin:forehead",
                "capability": "sweat",
                "adapter": "browser_svg",
                "target": "forehead_skin",
                "channel": "sweat_pulse",
                "value": {"rate": 0.65},
                "duration_ms": 1800,
                "phase": "physiology",
            },
        ),
        "simulation_hints": (
            {
                "node_id": "joint:right_knee",
                "backend": "opensim_moco",
                "component": "motion_tracking_goal",
                "coordinate": "knee_angle_r",
                "value": {"pattern": "gait_cycle", "cycles": 3},
                "phase": "primary",
            },
            {
                "node_id": "digit:right_hallux",
                "backend": "opensim",
                "component": "contact_hint",
                "coordinate": "right_hallux_ground_force",
                "value": {"phase": "toe_off"},
                "phase": "push_off",
            },
            {
                "node_id": "system:cardiovascular",
                "backend": "muskemo",
                "component": "trajectory_annotation",
                "coordinate": "cardiovascular_response_proxy",
                "value": {"pulse": "increased"},
                "phase": "physiology",
            },
            {
                "node_id": "system:respiratory",
                "backend": "muskemo",
                "component": "trajectory_annotation",
                "coordinate": "respiratory_response_proxy",
                "value": {"breath_rate": "increased"},
                "phase": "physiology",
            },
        ),
        "visual_cues": (
            {
                "node_id": "joint:right_knee",
                "shape": "path",
                "class_name": "run-stride",
                "geometry": {"d": "M248 456 C312 500 321 610 278 688"},
            },
            {
                "node_id": "digit:right_hallux",
                "shape": "path",
                "class_name": "run-toe-off",
                "geometry": {"d": "M246 709 C277 733 322 717 344 690"},
            },
        ),
    },
}
