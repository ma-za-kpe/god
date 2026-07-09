"""LLM anatomy control contract.

The LLM chooses semantic controls from a bounded action bundle. This module
owns the schema, clamps values, rejects invented nodes/capabilities, and emits
diagnostics for every degraded request.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .retrieval import ActionBundle, ActionBundleNode


ANATOMY_CONTROL_SCHEMA_VERSION = "god.body_control.v1"
MAX_CONTROLS = 64
MAX_DIAGNOSTIC_EXPECTATIONS = 16


@dataclass(frozen=True)
class AnatomyControl:
    node_id: str
    capability: str
    value: float
    weight: float = 1.0
    duration_ms: int = 1200
    rationale: str = ""
    source_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "capability": self.capability,
            "value": self.value,
            "weight": self.weight,
            "duration_ms": self.duration_ms,
            "rationale": self.rationale,
            "source_ids": list(self.source_ids),
        }


@dataclass(frozen=True)
class AnatomyControlPlan:
    schema: str
    action: str
    controls: tuple[AnatomyControl, ...]
    diagnostic_expectations: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()
    raw_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "action": self.action,
            "control_count": len(self.controls),
            "controls": [control.to_dict() for control in self.controls],
            "diagnostic_expectations": list(self.diagnostic_expectations),
            "diagnostics": list(self.diagnostics),
        }


def anatomy_control_json_schema(bundle: ActionBundle) -> dict[str, Any]:
    """Return the JSON Schema supplied to Ollama's structured output format."""

    node_ids = [node.id for node in bundle.nodes if node.control_channels]
    capabilities = sorted(
        {capability for node in bundle.nodes for capability in node.control_channels if capability}
    )
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["schema", "action", "controls", "diagnostic_expectations"],
        "properties": {
            "schema": {"type": "string", "const": ANATOMY_CONTROL_SCHEMA_VERSION},
            "action": {"type": "string", "enum": [bundle.action]},
            "controls": {
                "type": "array",
                "maxItems": MAX_CONTROLS,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["node_id", "capability", "value", "weight", "duration_ms"],
                    "properties": {
                        "node_id": {"type": "string", "enum": node_ids},
                        "capability": {"type": "string", "enum": capabilities},
                        "value": {"type": "number", "minimum": -1, "maximum": 1},
                        "weight": {"type": "number", "minimum": 0, "maximum": 1},
                        "duration_ms": {"type": "integer", "minimum": 0, "maximum": 12000},
                        "rationale": {"type": "string", "maxLength": 180},
                    },
                },
            },
            "diagnostic_expectations": {
                "type": "array",
                "maxItems": MAX_DIAGNOSTIC_EXPECTATIONS,
                "items": {"type": "string", "maxLength": 180},
            },
        },
    }


def build_anatomy_control_messages(
    bundle: ActionBundle,
    *,
    user_goal: str,
    previous_plan: AnatomyControlPlan | None = None,
) -> list[dict[str, str]]:
    """Build grounded messages for local LLM anatomy control."""

    schema = anatomy_control_json_schema(bundle)
    allowed_nodes = [
        _node_prompt_descriptor(node) for node in bundle.nodes if node.control_channels
    ]
    previous = previous_plan.to_dict() if previous_plan else None
    system = (
        "You are the anatomy control planner for one human avatar body. "
        "Return exactly one JSON object and no markdown. "
        "Use only node_id and capability pairs listed in the action bundle. "
        "Do not invent anatomy nodes, renderer nodes, capabilities, wardrobe meshes, or sources. "
        "The code will reject invalid controls; choose only source-backed controls that support the goal."
    )
    user = "\n".join(
        [
            f"User goal: {str(user_goal).strip()}",
            f"Action: {bundle.action}",
            f"LOD: {bundle.lod.value}",
            f"Max bundle nodes: {bundle.max_nodes}",
            f"Bundle diagnostics already known: {json.dumps(list(bundle.diagnostics))}",
            f"Allowed control nodes: {json.dumps(allowed_nodes, sort_keys=True)}",
            f"Previous valid plan: {json.dumps(previous, sort_keys=True) if previous else 'null'}",
            f"Required JSON schema: {json.dumps(schema, sort_keys=True)}",
            "Every control must use a node_id from Allowed control nodes and a capability listed on that same node.",
            "Prefer a small coherent set of controls over noisy over-control.",
            "diagnostic_expectations should describe visible/passive effects that must be checked later.",
        ]
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def build_ollama_anatomy_control_request(
    *,
    model: str,
    bundle: ActionBundle,
    user_goal: str,
    previous_plan: AnatomyControlPlan | None = None,
) -> dict[str, Any]:
    """Build an Ollama /api/chat request using structured-output JSON Schema."""

    return {
        "model": model,
        "stream": False,
        "format": anatomy_control_json_schema(bundle),
        "keep_alive": "10m",
        "options": {
            "temperature": 0,
            "num_predict": 420,
            "top_p": 0.9,
            "repeat_penalty": 1.05,
        },
        "messages": build_anatomy_control_messages(
            bundle,
            user_goal=user_goal,
            previous_plan=previous_plan,
        ),
    }


def parse_anatomy_control_response(payload: Any, bundle: ActionBundle) -> AnatomyControlPlan:
    """Parse and validate an LLM response against a bounded action bundle."""

    raw_text = _extract_response_text(payload)
    parsed: Any
    try:
        parsed = json.loads(_first_json_object(raw_text))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        return AnatomyControlPlan(
            schema=ANATOMY_CONTROL_SCHEMA_VERSION,
            action=bundle.action,
            controls=(),
            diagnostics=tuple([*bundle.diagnostics, f"invalid_json:{type(exc).__name__}"]),
            raw_text=raw_text,
        )
    return validate_anatomy_control_plan(parsed, bundle, raw_text=raw_text)


def validate_anatomy_control_plan(
    raw_plan: dict[str, Any],
    bundle: ActionBundle,
    *,
    raw_text: str = "",
) -> AnatomyControlPlan:
    """Clamp and validate a model-authored anatomy control plan."""

    if not isinstance(raw_plan, dict):
        raw_plan = {}
    diagnostics = list(bundle.diagnostics)
    if raw_plan.get("schema") != ANATOMY_CONTROL_SCHEMA_VERSION:
        diagnostics.append("schema_mismatch")
    if raw_plan.get("action") != bundle.action:
        diagnostics.append(f"action_mismatch:{raw_plan.get('action', '')}")

    bundle_nodes = {node.id: node for node in bundle.nodes}
    controls: list[AnatomyControl] = []
    for item in _as_list(raw_plan.get("controls"))[:MAX_CONTROLS]:
        control = item if isinstance(item, dict) else {}
        node_id = _clean_id(control.get("node_id"))
        capability = _clean_capability(control.get("capability"))
        node = bundle_nodes.get(node_id)
        if node is None:
            diagnostics.append(f"rejected_unknown_node:{node_id}")
            continue
        if not node.source_ids:
            diagnostics.append(f"rejected_unsourced_node:{node_id}")
            continue
        if capability not in node.control_channels:
            diagnostics.append(f"rejected_unsupported_capability:{node_id}:{capability}")
            continue
        controls.append(
            AnatomyControl(
                node_id=node.id,
                capability=capability,
                value=_clamp(control.get("value", 0), -1, 1),
                weight=_clamp(control.get("weight", 1), 0, 1),
                duration_ms=round(_clamp(control.get("duration_ms", 1200), 0, 12000)),
                rationale=str(control.get("rationale", "")).replace("\n", " ").strip()[:180],
                source_ids=node.source_ids,
            )
        )
    if not controls:
        diagnostics.append("empty_valid_controls")

    diagnostic_expectations = tuple(
        str(item).replace("\n", " ").strip()[:180]
        for item in _as_list(raw_plan.get("diagnostic_expectations"))[:MAX_DIAGNOSTIC_EXPECTATIONS]
        if str(item).strip()
    )
    return AnatomyControlPlan(
        schema=ANATOMY_CONTROL_SCHEMA_VERSION,
        action=bundle.action,
        controls=tuple(controls),
        diagnostic_expectations=diagnostic_expectations,
        diagnostics=tuple(dict.fromkeys(diagnostics)),
        raw_text=raw_text,
    )


def _node_prompt_descriptor(node: ActionBundleNode) -> dict[str, Any]:
    return {
        "id": node.id,
        "label": node.label,
        "kind": node.kind,
        "role": node.role.value,
        "materialization": node.materialization,
        "control_channels": list(node.control_channels),
        "source_ids": list(node.source_ids),
    }


def _extract_response_text(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    if not isinstance(payload, dict):
        return ""
    message = payload.get("message")
    if isinstance(message, dict) and isinstance(message.get("content"), str):
        return message["content"]
    if isinstance(payload.get("response"), str):
        return payload["response"]
    return ""


def _first_json_object(text: str) -> str:
    raw = str(text or "").strip()
    if raw.startswith("{"):
        return raw
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        return raw[start : end + 1]
    raise ValueError("no-json-object")


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _clamp(value: Any, lower: float, upper: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = lower
    return max(lower, min(upper, parsed))


def _clean_id(value: Any) -> str:
    return "".join(ch for ch in str(value or "").strip() if ch.isalnum() or ch in "_.:-")[:128]


def _clean_capability(value: Any) -> str:
    return "".join(ch for ch in str(value or "").strip() if ch.isalnum() or ch in "_:-")[:96]
