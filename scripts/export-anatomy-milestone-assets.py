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
    ActionLOD,
    AnatomyActionRequest,
    build_anatomy_motion_projection,
    build_anatomy_render_projection,
    build_m01_reference_graph,
    build_m02_reference_graph,
    build_m08_right_hand_digits_reference_graph,
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
    elif milestone in {"M04", "M05", "M06", "M07"}:
        graph = build_m02_reference_graph()
        focus_ids = (
            "body:human",
            "system:integumentary",
            "system:skeletal",
            "system:nervous",
            "system:cardiovascular",
            "region:head",
            "bone:skull",
            "organ:brain",
            "region:right_hand",
            "digit:right_pollex",
            "digit:right_index_finger",
            "joint:right_knee",
            "bone:right_femur",
            "bone:right_tibia",
            "bone:right_patella",
            "digit:right_hallux",
            "skin:right_hallux",
            "skin:forehead",
            "population:scalp_hair_follicles",
            "population:forehead_eccrine_sweat_glands",
            "render:forehead_sweat_proxy",
        )
    elif milestone == "M08":
        graph = build_m08_right_hand_digits_reference_graph()
        focus_ids = (
            "body:human",
            "region:right_upper_limb",
            "region:right_hand",
            "aggregate:right_carpals",
            "aggregate:right_metacarpals",
            "aggregate:right_hand_phalanges",
            "digit:right_pollex",
            "bone:right_first_metacarpal",
            "joint:right_first_carpometacarpal",
            "joint:right_first_metacarpophalangeal",
            "bone:right_pollex_proximal_phalanx",
            "joint:right_pollex_interphalangeal",
            "bone:right_pollex_distal_phalanx",
            "digit:right_index_finger",
            "bone:right_second_metacarpal",
            "joint:right_second_carpometacarpal",
            "joint:right_second_metacarpophalangeal",
            "bone:right_index_finger_proximal_phalanx",
            "joint:right_index_finger_proximal_interphalangeal",
            "bone:right_index_finger_middle_phalanx",
            "joint:right_index_finger_distal_interphalangeal",
            "bone:right_index_finger_distal_phalanx",
            "digit:right_middle_finger",
            "bone:right_third_metacarpal",
            "joint:right_third_carpometacarpal",
            "joint:right_third_metacarpophalangeal",
            "bone:right_middle_finger_proximal_phalanx",
            "joint:right_middle_finger_proximal_interphalangeal",
            "bone:right_middle_finger_middle_phalanx",
            "joint:right_middle_finger_distal_interphalangeal",
            "bone:right_middle_finger_distal_phalanx",
            "digit:right_ring_finger",
            "bone:right_fourth_metacarpal",
            "joint:right_fourth_carpometacarpal",
            "joint:right_fourth_metacarpophalangeal",
            "bone:right_ring_finger_proximal_phalanx",
            "joint:right_ring_finger_proximal_interphalangeal",
            "bone:right_ring_finger_middle_phalanx",
            "joint:right_ring_finger_distal_interphalangeal",
            "bone:right_ring_finger_distal_phalanx",
            "digit:right_little_finger",
            "bone:right_fifth_metacarpal",
            "joint:right_fifth_carpometacarpal",
            "joint:right_fifth_metacarpophalangeal",
            "bone:right_little_finger_proximal_phalanx",
            "joint:right_little_finger_proximal_interphalangeal",
            "bone:right_little_finger_middle_phalanx",
            "joint:right_little_finger_distal_interphalangeal",
            "bone:right_little_finger_distal_phalanx",
        )
    else:
        raise ValueError(f"Unsupported anatomy milestone: {milestone}")

    graph.assert_valid()
    working_set_root = "region:right_hand" if milestone == "M08" else "skin:forehead"
    working_set = graph.compile_working_set(working_set_root, max_depth=2)
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
    render_projection = {}
    motion_projection = {}
    if milestone in {"M04", "M05", "M06", "M07"}:
        compiled_bundles = _compile_reference_action_bundles(
            graph,
            include_sit=milestone == "M07",
        )
        action_bundles = [bundle.to_dict() for bundle in compiled_bundles]
        if milestone in {"M05", "M06", "M07"}:
            control_contract = _build_reference_control_contract(compiled_bundles[0])
        if milestone in {"M06", "M07"}:
            render_projection = build_anatomy_render_projection(graph).to_dict()
        if milestone == "M07":
            motion_projection = build_anatomy_motion_projection(compiled_bundles).to_dict()
    elif milestone == "M08":
        compiled_bundles = _compile_right_hand_digit_action_bundles(graph)
        action_bundles = [bundle.to_dict() for bundle in compiled_bundles]
        control_contract = _build_right_hand_digit_control_contract(compiled_bundles[0])
        render_projection = build_anatomy_render_projection(graph).to_dict()

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
            "render_layer_count": len(render_projection.get("layers", [])),
            "render_primitive_count": len(render_projection.get("primitives", [])),
            "render_missing_mapping_count": render_projection.get("missing_mapping_count", 0),
            "motion_plan_count": motion_projection.get("plan_count", 0),
            "motion_renderer_control_count": motion_projection.get("renderer_control_count", 0),
            "motion_simulation_hint_count": motion_projection.get("simulation_hint_count", 0),
            "motion_visual_cue_count": motion_projection.get("visual_cue_count", 0),
            "motion_diagnostic_count": motion_projection.get("diagnostic_count", 0),
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
        "render_projection": render_projection,
        "motion_projection": motion_projection,
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
    for milestone in ("M01", "M02", "M03", "M04", "M05", "M06", "M07", "M08"):
        payload = _milestone_payload(milestone)
        output = output_dir / f"{milestone.lower()}-graph.json"
        output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(output)
        if milestone == "M08":
            latest = output_dir / "latest-graph.json"
            latest.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            print(latest)
    return 0


def _compile_reference_action_bundles(graph, include_sit=False):
    run_seed_node_ids = (
        (
            "joint:right_knee",
            "digit:right_hallux",
            "region:right_foot",
            "system:muscular",
            "system:cardiovascular",
            "system:respiratory",
            "skin:forehead",
            "joint:right_ankle",
            "region:pelvis",
        )
        if include_sit
        else (
            "joint:right_knee",
            "digit:right_hallux",
            "system:muscular",
            "system:cardiovascular",
            "system:respiratory",
            "skin:forehead",
        )
    )
    bundles = [
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
        )
    ]
    if include_sit:
        bundles.append(
            compile_lod_action_bundle(
                graph,
                AnatomyActionRequest(
                    action="sit",
                    seed_node_ids=(
                        "joint:right_knee",
                        "region:right_foot",
                        "digit:right_hallux",
                        "joint:right_hip",
                        "region:pelvis",
                    ),
                    lod=ActionLOD.MESO,
                    max_nodes=16,
                    requested_capabilities=(
                        "flexion_extension",
                        "weight_bearing",
                        "ground_contact",
                    ),
                ),
            )
        )
    bundles.extend(
        [
            compile_lod_action_bundle(
                graph,
                AnatomyActionRequest(
                    action="run",
                    seed_node_ids=run_seed_node_ids,
                    lod=ActionLOD.MACRO,
                    max_nodes=16 if include_sit else 14,
                    requested_capabilities=("flexion_extension", "ground_contact")
                    if include_sit
                    else (),
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
    )
    return bundles


def _compile_right_hand_digit_action_bundles(graph):
    return [
        compile_lod_action_bundle(
            graph,
            AnatomyActionRequest(
                action="right_hand_digit_flexion",
                seed_node_ids=(
                    "region:right_hand",
                    "digit:right_pollex",
                    "digit:right_index_finger",
                    "digit:right_middle_finger",
                    "digit:right_ring_finger",
                    "digit:right_little_finger",
                    "joint:right_first_metacarpophalangeal",
                    "joint:right_pollex_interphalangeal",
                    "joint:right_second_metacarpophalangeal",
                    "joint:right_index_finger_proximal_interphalangeal",
                    "joint:right_index_finger_distal_interphalangeal",
                    "joint:right_third_metacarpophalangeal",
                    "joint:right_middle_finger_proximal_interphalangeal",
                    "joint:right_middle_finger_distal_interphalangeal",
                    "joint:right_fourth_metacarpophalangeal",
                    "joint:right_ring_finger_proximal_interphalangeal",
                    "joint:right_ring_finger_distal_interphalangeal",
                    "joint:right_fifth_metacarpophalangeal",
                    "joint:right_little_finger_proximal_interphalangeal",
                    "joint:right_little_finger_distal_interphalangeal",
                ),
                lod=ActionLOD.MESO,
                max_nodes=52,
            ),
        )
    ]


def _build_reference_control_contract(wave_bundle):
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
    return {
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


def _build_right_hand_digit_control_contract(hand_bundle):
    ollama_request = build_ollama_anatomy_control_request(
        model="llama3.1:8b",
        bundle=hand_bundle,
        user_goal=(
            "Curl and spread the right hand across thumb, index, middle, ring, "
            "and little finger using only source-backed digit and joint nodes."
        ),
    )
    plan = validate_anatomy_control_plan(
        {
            "schema": ANATOMY_CONTROL_SCHEMA_VERSION,
            "action": "right_hand_digit_flexion",
            "controls": [
                {
                    "node_id": "digit:right_pollex",
                    "capability": "opposition",
                    "value": 0.38,
                    "weight": 0.55,
                    "duration_ms": 700,
                    "rationale": "thumb opposes slightly instead of copying the long fingers",
                },
                {
                    "node_id": "digit:right_index_finger",
                    "capability": "finger_curl",
                    "value": 0.42,
                    "weight": 0.62,
                    "duration_ms": 700,
                    "rationale": "index ray joins the hand curl",
                },
                {
                    "node_id": "digit:right_middle_finger",
                    "capability": "finger_curl",
                    "value": 0.5,
                    "weight": 0.68,
                    "duration_ms": 700,
                    "rationale": "middle ray has the strongest visible curl",
                },
                {
                    "node_id": "digit:right_ring_finger",
                    "capability": "palm_cupping",
                    "value": 0.32,
                    "weight": 0.5,
                    "duration_ms": 700,
                    "rationale": "ring ray participates in palm cupping",
                },
                {
                    "node_id": "joint:right_fifth_metacarpophalangeal",
                    "capability": "flexion_extension",
                    "value": 0.45,
                    "weight": 0.7,
                    "duration_ms": 700,
                    "rationale": "base joint starts the little finger flexion",
                },
                {
                    "node_id": "joint:right_little_finger_proximal_interphalangeal",
                    "capability": "flexion_extension",
                    "value": 0.75,
                    "weight": 0.9,
                    "duration_ms": 700,
                    "rationale": "PIP joint bends the proximal-to-middle link",
                },
                {
                    "node_id": "joint:right_little_finger_distal_interphalangeal",
                    "capability": "flexion_extension",
                    "value": 0.55,
                    "weight": 0.75,
                    "duration_ms": 700,
                    "rationale": "DIP joint bends the distal segment",
                },
                {
                    "node_id": "digit:right_little_finger",
                    "capability": "palm_cupping",
                    "value": 0.42,
                    "weight": 0.62,
                    "duration_ms": 700,
                    "rationale": "little finger and fifth metacarpal help deepen the palm hollow",
                },
                {
                    "node_id": "bone:right_little_finger_fake_phalanx",
                    "capability": "flexion_extension",
                    "value": 1,
                    "weight": 1,
                    "duration_ms": 700,
                },
            ],
            "diagnostic_expectations": [
                "all five right-hand digits are available to the LLM bundle",
                "finger chains use source-backed MCP, IP, PIP, and DIP nodes",
                "invented phalanx controls are rejected",
            ],
        },
        hand_bundle,
    )
    return {
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


if __name__ == "__main__":
    raise SystemExit(main())
