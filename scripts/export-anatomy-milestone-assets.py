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

from anatomy import build_m01_reference_graph  # noqa: E402


def main() -> int:
    graph = build_m01_reference_graph()
    graph.assert_valid()
    working_set = graph.compile_working_set("skin:forehead", max_depth=2)

    payload = {
        "milestone": "M01",
        "status": "complete",
        "summary": {
            "node_count": len(graph.nodes),
            "edge_count": len(graph.edges),
            "llm_handle_count": len(graph.llm_control_registry()),
            "working_set_root": working_set.root_id,
            "working_set_node_count": len(working_set.node_ids),
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
        "neo4j": {
            "node_records": len(graph.to_neo4j_nodes()),
            "relationship_records": len(graph.to_neo4j_relationships()),
            "constraints": list(graph.neo4j_constraints()),
        },
    }

    output = ROOT / "observer" / "public" / "assets" / "anatomy" / "m01-graph.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
