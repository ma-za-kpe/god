"""Bounded anatomy GraphRAG/LOD compilation.

The LLM owns semantic intent and supplies structured seed nodes. This module
validates those seeds, expands a bounded graph working set, and reports gaps.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .graph import (
    DEFAULT_WORKING_SET_EDGES,
    AnatomyGraph,
    AnatomyKind,
    MaterializationState,
)


class ActionLOD(str, Enum):
    MACRO = "macro"
    MESO = "meso"
    MICRO = "micro"


class ActionRole(str, Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    PASSIVE = "passive"
    DIAGNOSTIC = "diagnostic"


@dataclass(frozen=True)
class AnatomyActionRequest:
    action: str
    seed_node_ids: tuple[str, ...]
    lod: ActionLOD | str = ActionLOD.MESO
    max_nodes: int = 24
    requested_capabilities: tuple[str, ...] = ()
    source: str = "llm_structured_intent"

    def __post_init__(self) -> None:
        object.__setattr__(self, "lod", ActionLOD(self.lod))
        object.__setattr__(self, "seed_node_ids", tuple(dict.fromkeys(self.seed_node_ids)))
        object.__setattr__(self, "requested_capabilities", tuple(self.requested_capabilities))
        if self.max_nodes < 1:
            raise ValueError("max_nodes must be positive")


@dataclass(frozen=True)
class ActionBundleNode:
    id: str
    label: str
    kind: str
    materialization: str
    role: ActionRole
    control_channels: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "kind": self.kind,
            "materialization": self.materialization,
            "role": self.role.value,
            "control_channels": list(self.control_channels),
            "source_ids": list(self.source_ids),
        }


@dataclass(frozen=True)
class ActionBundle:
    action: str
    lod: ActionLOD
    max_nodes: int
    nodes: tuple[ActionBundleNode, ...]
    diagnostics: tuple[str, ...] = ()
    cypher: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "lod": self.lod.value,
            "max_nodes": self.max_nodes,
            "node_count": len(self.nodes),
            "nodes": [node.to_dict() for node in self.nodes],
            "diagnostics": list(self.diagnostics),
            "cypher": self.cypher,
            "parameters": self.parameters,
        }


def compile_lod_action_bundle(graph: AnatomyGraph, request: AnatomyActionRequest) -> ActionBundle:
    """Compile a structured LLM action request into a bounded graph bundle."""

    graph.assert_valid()
    depth = _lod_depth(request.lod)
    diagnostics: list[str] = []
    missing_seed_ids = [node_id for node_id in request.seed_node_ids if node_id not in graph.nodes]
    diagnostics.extend(f"missing_seed_node:{node_id}" for node_id in missing_seed_ids)

    candidate_ids: list[str] = []
    for seed_id in request.seed_node_ids:
        if seed_id not in graph.nodes:
            continue
        candidate_ids.append(seed_id)
        candidate_ids.extend(_expand_without_hub_fanout(graph, seed_id, depth))

    ordered_ids = _dedupe(candidate_ids)
    sorted_ids = sorted(
        ordered_ids, key=lambda node_id: _node_priority(graph, node_id, request.seed_node_ids)
    )
    if len(sorted_ids) > request.max_nodes:
        diagnostics.append(f"truncated:{len(sorted_ids) - request.max_nodes}")
    bounded_ids = tuple(sorted_ids[: request.max_nodes])

    nodes = tuple(
        _bundle_node(graph, node_id, _role_for_node(graph, node_id, request.seed_node_ids))
        for node_id in bounded_ids
    )
    diagnostics.extend(_capability_diagnostics(graph, request))

    return ActionBundle(
        action=request.action,
        lod=request.lod,
        max_nodes=request.max_nodes,
        nodes=nodes,
        diagnostics=tuple(diagnostics),
        cypher=neo4j_lod_retrieval_cypher(depth),
        parameters={
            "seed_node_ids": [
                node_id for node_id in request.seed_node_ids if node_id in graph.nodes
            ],
            "max_nodes": request.max_nodes,
        },
    )


def neo4j_lod_retrieval_cypher(depth: int) -> str:
    """Return the Cypher traversal used after semantic/vector seed selection."""

    if depth < 0:
        raise ValueError("depth must be non-negative")
    relationship_types = "|".join(
        edge.value.upper() for edge in sorted(DEFAULT_WORKING_SET_EDGES, key=str)
    )
    return (
        "MATCH (seed:AnatomyNode) "
        "WHERE seed.id IN $seed_node_ids "
        "MATCH path=(seed)-[:" + relationship_types + f"*0..{depth}]-(node:AnatomyNode) "
        "WHERE length(path) < 2 "
        "OR all(interior IN nodes(path)[1..length(path)] "
        "WHERE NOT interior.kind IN ['body', 'system']) "
        "WITH node, min(length(path)) AS depth "
        "RETURN node.id AS id, node.label AS label, node.kind AS kind, "
        "node.materialization AS materialization, depth "
        "ORDER BY depth ASC, id ASC "
        "LIMIT $max_nodes"
    )


def _lod_depth(lod: ActionLOD) -> int:
    if lod == ActionLOD.MACRO:
        return 1
    if lod == ActionLOD.MESO:
        return 2
    return 3


def _dedupe(node_ids: list[str]) -> list[str]:
    return list(dict.fromkeys(node_ids))


def _expand_without_hub_fanout(
    graph: AnatomyGraph, seed_id: str, max_depth: int
) -> tuple[str, ...]:
    visited = {seed_id}
    queue = [(seed_id, 0)]
    while queue:
        current_id, depth = queue.pop(0)
        if depth >= max_depth:
            continue
        current = graph.node(current_id)
        if current_id != seed_id and current.kind in {AnatomyKind.BODY, AnatomyKind.SYSTEM}:
            continue
        for neighbor_id in _neighbor_ids(graph, current_id):
            if neighbor_id in visited:
                continue
            visited.add(neighbor_id)
            queue.append((neighbor_id, depth + 1))
    return tuple(sorted(visited))


def _neighbor_ids(graph: AnatomyGraph, current_id: str) -> tuple[str, ...]:
    neighbor_ids: list[str] = []
    for edge in graph.edges:
        if edge.kind not in DEFAULT_WORKING_SET_EDGES:
            continue
        if edge.from_id == current_id:
            neighbor_ids.append(edge.to_id)
        elif edge.to_id == current_id:
            neighbor_ids.append(edge.from_id)
    return tuple(neighbor_ids)


def _node_priority(graph: AnatomyGraph, node_id: str, seed_ids: tuple[str, ...]) -> tuple[int, str]:
    node = graph.node(node_id)
    if node_id in seed_ids:
        return (0, node_id)
    if node.llm_visible:
        return (1, node_id)
    if node.kind in (AnatomyKind.RENDER_PROXY, AnatomyKind.POPULATION_TEMPLATE):
        return (2, node_id)
    if node.kind == AnatomyKind.SYSTEM:
        return (4, node_id)
    return (3, node_id)


def _role_for_node(graph: AnatomyGraph, node_id: str, seed_ids: tuple[str, ...]) -> ActionRole:
    node = graph.node(node_id)
    if node_id in seed_ids:
        return ActionRole.PRIMARY
    if node.kind == AnatomyKind.RENDER_PROXY:
        return ActionRole.PASSIVE
    if node.materialization in {
        MaterializationState.POPULATION_TEMPLATE,
        MaterializationState.RENDER_PROXY,
        MaterializationState.SIMULATION_PROXY,
    }:
        return ActionRole.PASSIVE
    return ActionRole.SECONDARY


def _bundle_node(graph: AnatomyGraph, node_id: str, role: ActionRole) -> ActionBundleNode:
    node = graph.node(node_id)
    return ActionBundleNode(
        id=node.id,
        label=node.label,
        kind=node.kind.value,
        materialization=node.materialization.value,
        role=role,
        control_channels=node.control_channels,
        source_ids=tuple(source.source_id for source in node.sources),
    )


def _capability_diagnostics(graph: AnatomyGraph, request: AnatomyActionRequest) -> tuple[str, ...]:
    diagnostics = []
    for seed_id in request.seed_node_ids:
        if seed_id not in graph.nodes:
            continue
        node = graph.node(seed_id)
        for capability in request.requested_capabilities:
            if capability not in node.control_channels:
                diagnostics.append(f"unsupported_capability:{seed_id}:{capability}")
    return tuple(diagnostics)
