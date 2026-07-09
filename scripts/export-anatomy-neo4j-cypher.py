#!/usr/bin/env python3
"""Export a cypher-shell script for the local anatomy Neo4j graph."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_SRC = ROOT / "runtime" / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))

from anatomy import build_m02_reference_graph, neo4j_cypher_script  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "artifacts" / "m03-anatomy-neo4j.cypher",
        help="Path to write the generated Cypher script.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing AnatomyNode data before loading the snapshot.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    graph = build_m02_reference_graph()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(neo4j_cypher_script(graph, reset=args.reset), encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
