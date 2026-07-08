"""Neo4j projection helpers for the sourced anatomy graph.

The anatomy graph remains the source of truth. This module only owns the
Community-safe Neo4j schema and deterministic load/validation Cypher.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from .graph import AnatomyGraph, EdgeKind

LABEL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
RELATIONSHIP_TYPE_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")

COMMUNITY_UNSAFE_SCHEMA_MARKERS = (
    " IS NOT NULL",
    " IS NODE KEY",
    " IS RELATIONSHIP KEY",
    " IS TYPED",
    " IS ::",
)


def neo4j_schema_statements(edge_kinds: Iterable[EdgeKind | str] = EdgeKind) -> tuple[str, ...]:
    """Return idempotent schema statements that work on Neo4j Community.

    Neo4j Community supports uniqueness constraints and range/text indexes.
    Existence, type, and key constraints remain Enterprise-only, so required
    field checks stay in Python validation and M03 Cypher validation queries.
    """

    statements = [
        "CREATE CONSTRAINT anatomy_node_id_unique IF NOT EXISTS "
        "FOR (n:AnatomyNode) REQUIRE n.id IS UNIQUE",
        "CREATE INDEX anatomy_node_kind IF NOT EXISTS FOR (n:AnatomyNode) ON (n.kind)",
        "CREATE INDEX anatomy_node_materialization IF NOT EXISTS "
        "FOR (n:AnatomyNode) ON (n.materialization)",
        "CREATE INDEX anatomy_node_llm_visible IF NOT EXISTS "
        "FOR (n:AnatomyNode) ON (n.llm_visible)",
        "CREATE TEXT INDEX anatomy_node_label_text IF NOT EXISTS FOR (n:AnatomyNode) ON (n.label)",
    ]
    for edge_kind in sorted({EdgeKind(kind) for kind in edge_kinds}, key=lambda item: item.value):
        rel_type = edge_kind.value.upper()
        statements.append(
            f"CREATE CONSTRAINT anatomy_rel_{edge_kind.value}_graph_key IF NOT EXISTS "
            f"FOR ()-[r:{rel_type}]-() REQUIRE r.graph_key IS UNIQUE"
        )
    _assert_community_safe_schema(statements)
    return tuple(statements)


def neo4j_load_statements(graph: AnatomyGraph, *, reset: bool = False) -> tuple[str, ...]:
    """Return deterministic Cypher statements for loading a graph snapshot."""

    graph.assert_valid()
    statements: list[str] = []
    if reset:
        statements.append("MATCH (n:AnatomyNode) DETACH DELETE n")

    for record in graph.to_neo4j_nodes():
        labels = ":".join(_safe_label(label) for label in record["labels"])
        properties = _cypher_literal(record["properties"])
        node_id = _cypher_literal(record["id"])
        statements.append(f"MERGE (n:{labels} {{id: {node_id}}}) SET n = {properties}")

    for index, record in enumerate(graph.to_neo4j_relationships()):
        rel_type = _safe_relationship_type(record["type"])
        graph_key = _relationship_graph_key(record, index)
        properties = {"graph_key": graph_key, **record["properties"]}
        start_id = _cypher_literal(record["start_id"])
        end_id = _cypher_literal(record["end_id"])
        graph_key_literal = _cypher_literal(graph_key)
        properties_literal = _cypher_literal(properties)
        statements.append(
            f"MATCH (from:AnatomyNode {{id: {start_id}}}) "
            f"MATCH (to:AnatomyNode {{id: {end_id}}}) "
            f"MERGE (from)-[r:{rel_type} {{graph_key: {graph_key_literal}}}]->(to) "
            f"SET r += {properties_literal}"
        )

    return tuple(statements)


def neo4j_validation_queries(graph: AnatomyGraph) -> tuple[str, ...]:
    """Return Cypher checks for local M03 validation."""

    graph.assert_valid()
    return (
        "MATCH (n:AnatomyNode) "
        "WHERE n.id IS NULL OR n.label IS NULL OR n.kind IS NULL "
        "OR n.materialization IS NULL OR n.source_ids IS NULL "
        "RETURN count(n) AS invalid_node_count",
        "MATCH ()-[r]->() "
        "WHERE r.graph_key IS NULL OR r.kind IS NULL OR r.source_ids IS NULL "
        "RETURN count(r) AS invalid_relationship_count",
        f"MATCH (n:AnatomyNode) RETURN count(n) AS node_count, {len(graph.nodes)} AS expected_nodes",
        f"MATCH ()-[r]->() RETURN count(r) AS relationship_count, {len(graph.edges)} AS expected_relationships",
        "MATCH (n:AnatomyNode) "
        "WITH n.id AS id, count(n) AS copies "
        "WHERE copies > 1 "
        "RETURN count(id) AS duplicate_node_id_count",
    )


def neo4j_cypher_script(graph: AnatomyGraph, *, reset: bool = False) -> str:
    """Render schema and load statements as a cypher-shell compatible script."""

    sections = [
        "// Anatomy Neo4j schema",
        *(_with_semicolon(statement) for statement in neo4j_schema_statements()),
        "// Anatomy graph load",
        *(_with_semicolon(statement) for statement in neo4j_load_statements(graph, reset=reset)),
        "// Anatomy validation queries",
        *(_with_semicolon(statement) for statement in neo4j_validation_queries(graph)),
    ]
    return "\n".join(sections) + "\n"


def _relationship_graph_key(record: dict[str, Any], index: int) -> str:
    return f"{record['start_id']}|{record['type']}|{record['end_id']}|{index:06d}"


def _assert_community_safe_schema(statements: Iterable[str]) -> None:
    for statement in statements:
        if any(marker in statement for marker in COMMUNITY_UNSAFE_SCHEMA_MARKERS):
            raise ValueError(f"Neo4j Community-unsafe schema statement: {statement}")
        if "IF NOT EXISTS" not in statement:
            raise ValueError(f"Neo4j schema statement must be idempotent: {statement}")


def _safe_label(label: str) -> str:
    if not LABEL_RE.match(label):
        raise ValueError(f"Unsafe Neo4j label: {label}")
    return label


def _safe_relationship_type(relationship_type: str) -> str:
    if not RELATIONSHIP_TYPE_RE.match(relationship_type):
        raise ValueError(f"Unsafe Neo4j relationship type: {relationship_type}")
    return relationship_type


def _cypher_literal(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return repr(value)
    if isinstance(value, str):
        return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"
    if isinstance(value, list | tuple):
        return "[" + ", ".join(_cypher_literal(item) for item in value) + "]"
    if isinstance(value, dict):
        items = []
        for key in sorted(value):
            if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
                raise ValueError(f"Unsafe Cypher map key: {key}")
            items.append(f"{key}: {_cypher_literal(value[key])}")
        return "{" + ", ".join(items) + "}"
    raise TypeError(f"Unsupported Cypher literal type: {type(value)!r}")


def _with_semicolon(statement: str) -> str:
    stripped = statement.rstrip()
    return stripped if stripped.endswith(";") else f"{stripped};"
