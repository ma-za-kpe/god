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

from anatomy import build_m01_reference_graph, build_m02_reference_graph  # noqa: E402


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
        "neo4j": {
            "node_records": len(graph.to_neo4j_nodes()),
            "relationship_records": len(graph.to_neo4j_relationships()),
            "constraints": list(graph.neo4j_constraints()),
        },
    }


def main() -> int:
    output_dir = ROOT / "observer" / "public" / "assets" / "anatomy"
    output_dir.mkdir(parents=True, exist_ok=True)
    for milestone in ("M01", "M02"):
        payload = _milestone_payload(milestone)
        output = output_dir / f"{milestone.lower()}-graph.json"
        output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(output)
        if milestone == "M02":
            latest = output_dir / "latest-graph.json"
            latest.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print(latest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
