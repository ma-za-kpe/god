#!/usr/bin/env python3
"""Export anatomy milestone graph evidence for the browser lab."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_SRC = ROOT / "runtime" / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))

from anatomy import (  # noqa: E402
    ANATOMY_CONTROL_SCHEMA_VERSION,
    build_m01_reference_graph,
    build_m02_reference_graph,
    ActionLOD,
    AnatomyActionRequest,
    build_ollama_anatomy_control_request,
    compile_lod_action_bundle,
    neo4j_schema_statements,
    neo4j_validation_queries,
    validate_anatomy_control_plan,
)


def _milestone_payload(milestone: str) -> dict:
    if milestone == "M01":
        graph = build_m01_reference_graph()
        focus_ids = (
            "skin:forehead",
            "population:forehead_eccrine_sweat_glands",
            "render:forehead_sweat_proxy",
        )
    elif milestone == "M02":
        graph = build_m02_reference_graph()
        focus_ids = (
            "region:head",
            "bone:skull",
            "region:right_hand",
            "digit:right_pollex",
            "joint:right_knee",
            "bone:right_femur",
            "bone:right_tibia",
            "bone:right_patella",
            "region:right_foot",
            "digit:right_hallux",
            "skin:right_hallux",
            "skin:forehead",
        )
    elif milestone == "M03":
        graph = build_m02_reference_graph()
        focus_ids = (
            "region:head",
            "bone:skull",
            "region:right_hand",
            "joint:right_knee",
            "region:right_foot",
            "digit:right_hallux",
            "skin:forehead",
        )
    elif milestone in {"M04", "M05"}:
        graph = build_m02_reference_graph()
        focus_ids = (
            "region:right_hand",
            "digit:right_pollex",
            "digit:right_index_finger",
            "joint:right_knee",
            "digit:right_hallux",
            "skin:forehead",
            "population:forehead_eccrine_sweat_glands",
            "render:forehead_sweat_proxy",
        )
    else:
        raise ValueError(f"Unsupported anatomy milestone: {milestone}")

    graph.assert_valid()
    working_set = graph.compile_working_set("skin:forehead", max_depth=2)
    focus_nodes = [
        {
            "id": node_id,
            "label": graph.node(node_id).label,
            "kind": graph.node(node_id).kind.value,
            "materialization": graph.node(node_id).materialization.value,
        }
        for node_id in focus_ids
        if node_id in graph.nodes
    ]

    action_bundles = []
    control_contract = {}
    if milestone in {"M04", "M05"}:
        compiled_bundles = _compile_reference_action_bundles(graph)
        action_bundles = [bundle.to_dict() for bundle in compiled_bundles]
        if milestone == "M05":
            wave_bundle = compiled_bundles[0]
            ollama_request = build_ollama_anatomy_control_request(
                model="llama3.1:8b",
                bundle=wave_bundle,
                user_goal="Wave with the right hand while keeping unsupported anatomy explicit.",
            )
            plan = validate_anatomy_control_plan(
                {
                    "schema": ANATOMY_CONTROL_SCHEMA_VERSION,
                    "action": "wave",
                    "controls": [
                        {
                            "node_id": "region:right_hand",
                            "capability": "open_close",
                            "value": 0.82,
                            "weight": 0.9,
                            "duration_ms": 900,
                            "rationale": "open the right hand for the visible wave",
                        },
                        {
                            "node_id": "region:right_hand",
                            "capability": "finger_curl",
                            "value": 0.18,
                            "weight": 0.65,
                            "duration_ms": 900,
                            "rationale": "keep fingers relaxed rather than clenched",
                        },
                        {
                            "node_id": "digit:right_pollex",
                            "capability": "opposition",
                            "value": 0.35,
                            "weight": 0.45,
                            "duration_ms": 700,
                            "rationale": "thumb participates subtly",
                        },
                        {
                            "node_id": "joint:right_knee",
                            "capability": "flexion_extension",
                            "value": 1,
                            "weight": 1,
                            "duration_ms": 900,
                        },
                        {
                            "node_id": "bone:made_up",
                            "capability": "rotate_joint",
                            "value": 1,
                            "weight": 1,
                            "duration_ms": 900,
                        },
                    ],
                    "diagnostic_expectations": [
                        "right hand opens and curls within the source-backed wave bundle",
                        "unsupported knee and invented bone controls are rejected",
                    ],
                },
                wave_bundle,
            )
            control_contract = {
                "schema": ANATOMY_CONTROL_SCHEMA_VERSION,
                "validated_plan": plan.to_dict(),
                "ollama": {
                    "endpoint": "/api/chat",
                    "model": ollama_request["model"],
                    "stream": ollama_request["stream"],
                    "format_type": ollama_request["format"]["type"],
                    "temperature": ollama_request["options"]["temperature"],
                    "message_count": len(ollama_request["messages"]),
                    "allowed_node_count": len(
                        ollama_request["format"]["properties"]["controls"]["items"]["properties"][
                            "node_id"
                        ]["enum"]
                    ),
                },
            }

    return {
        "milestone": milestone,
        "status": "complete",
        "summary": {
            "node_count": len(graph.nodes),
            "edge_count": len(graph.edges),
            "llm_handle_count": len(graph.llm_control_registry()),
            "working_set_root": working_set.root_id,
            "working_set_node_count": len(working_set.node_ids),
            "focus_node_count": len(focus_nodes),
            "action_bundle_count": len(action_bundles),
            "max_action_bundle_node_count": max(
                (bundle["node_count"] for bundle in action_bundles),
                default=0,
            ),
            "control_plan_count": len(
                control_contract.get("validated_plan", {}).get("controls", [])
            ),
            "control_rejection_count": len(
                [
                    diagnostic
                    for diagnostic in control_contract.get("validated_plan", {}).get(
                        "diagnostics", []
                    )
                    if diagnostic.startswith("rejected_")
                ]
            ),
        },
        "nodes": [
            {
                "id": node.id,
                "label": node.label,
                "kind": node.kind.value,
                "materialization": node.materialization.value,
                "llm_visible": node.llm_visible,
                "control_channels": list(node.control_channels),
                "source_ids": [source.source_id for source in node.sources],
            }
            for node in sorted(graph.nodes.values(), key=lambda item: item.id)
        ],
        "llm_registry": graph.llm_control_registry(),
        "forehead_working_set": [
            {
                "id": node_id,
                "label": graph.node(node_id).label,
                "kind": graph.node(node_id).kind.value,
                "materialization": graph.node(node_id).materialization.value,
            }
            for node_id in working_set.node_ids
        ],
        "focus_nodes": focus_nodes,
        "action_bundles": action_bundles,
        "control_contract": control_contract,
        "neo4j": {
            "node_records": len(graph.to_neo4j_nodes()),
            "relationship_records": len(graph.to_neo4j_relationships()),
            "schema_statement_count": len(neo4j_schema_statements()),
            "validation_query_count": len(neo4j_validation_queries(graph)),
            "constraints": list(neo4j_schema_statements()),
        },
    }


def main() -> int:
    output_dir = ROOT / "observer" / "public" / "assets" / "anatomy"
    output_dir.mkdir(parents=True, exist_ok=True)
    for milestone in ("M01", "M02", "M03", "M04", "M05"):
        payload = _milestone_payload(milestone)
        output = output_dir / f"{milestone.lower()}-graph.json"
        output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(output)
        if milestone == "M05":
            latest = output_dir / "latest-graph.json"
            latest.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            print(latest)
    return 0


def _compile_reference_action_bundles(graph):
    return [
        compile_lod_action_bundle(
            graph,
            AnatomyActionRequest(
                action="wave",
                seed_node_ids=(
                    "region:right_hand",
                    "digit:right_pollex",
                    "digit:right_index_finger",
                ),
                lod=ActionLOD.MESO,
                max_nodes=16,
                requested_capabilities=("open_close", "finger_curl"),
            ),
        ),
        compile_lod_action_bundle(
            graph,
            AnatomyActionRequest(
                action="run",
                seed_node_ids=(
                    "joint:right_knee",
                    "digit:right_hallux",
                    "system:muscular",
                    "system:cardiovascular",
                    "system:respiratory",
                    "skin:forehead",
                ),
                lod=ActionLOD.MACRO,
                max_nodes=14,
            ),
        ),
        compile_lod_action_bundle(
            graph,
            AnatomyActionRequest(
                action="sweat_forehead",
                seed_node_ids=(
                    "skin:forehead",
                    "population:forehead_eccrine_sweat_glands",
                    "render:forehead_sweat_proxy",
                ),
                lod=ActionLOD.MICRO,
                max_nodes=12,
                requested_capabilities=("sweat",),
            ),
        ),
    ]


if __name__ == "__main__":
    raise SystemExit(main())
