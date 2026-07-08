"""Source-cited anatomy graph primitives.

This module owns graph shape and validation only. It intentionally contains no
human anatomy facts; facts enter through sourced seed/loaders.
"""

from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable

NODE_ID_RE = re.compile(r"^[a-z][a-z0-9_.:-]*$")


class AnatomyKind(str, Enum):
    BODY = "body"
    REGION = "region"
    SYSTEM = "system"
    ORGAN = "organ"
    TISSUE = "tissue"
    STRUCTURE = "structure"
    BONE = "bone"
    JOINT = "joint"
    MUSCLE = "muscle"
    TENDON = "tendon"
    LIGAMENT = "ligament"
    ARTERY = "artery"
    VEIN = "vein"
    NERVE = "nerve"
    LYMPHATIC = "lymphatic"
    GLAND = "gland"
    SKIN = "skin"
    HAIR = "hair"
    NAIL = "nail"
    CAPILLARY_BED = "capillary_bed"
    CELL_POPULATION = "cell_population"
    POPULATION_TEMPLATE = "population_template"
    RENDER_PROXY = "render_proxy"
    SIMULATION_PROXY = "simulation_proxy"


class MaterializationState(str, Enum):
    CANONICAL = "canonical"
    AGGREGATE = "aggregate"
    POPULATION_TEMPLATE = "population_template"
    VIRTUAL_INSTANCE = "virtual_instance"
    MATERIALIZED_INSTANCE = "materialized_instance"
    RENDER_PROXY = "render_proxy"
    SIMULATION_PROXY = "simulation_proxy"


class EdgeKind(str, Enum):
    PART_OF = "part_of"
    MEMBER_OF = "member_of"
    LOCATED_IN = "located_in"
    CONNECTS_TO = "connects_to"
    ADJACENT_TO = "adjacent_to"
    INNERVATES = "innervates"
    SUPPLIES = "supplies"
    DRAINS_TO = "drains_to"
    ORIGIN_ON = "origin_on"
    INSERTS_ON = "inserts_on"
    HAS_POPULATION = "has_population"
    MATERIALIZES_AS = "materializes_as"
    PROJECTS_TO_RENDER = "projects_to_render"
    PROJECTS_TO_SIMULATION = "projects_to_simulation"
    CONTROLS = "controls"


CHILD_TO_PARENT_EDGES = {
    EdgeKind.PART_OF,
    EdgeKind.MEMBER_OF,
    EdgeKind.LOCATED_IN,
}

PARENT_TO_CHILD_EDGES = {
    EdgeKind.HAS_POPULATION,
    EdgeKind.MATERIALIZES_AS,
    EdgeKind.PROJECTS_TO_RENDER,
    EdgeKind.PROJECTS_TO_SIMULATION,
    EdgeKind.CONTROLS,
}

DEFAULT_WORKING_SET_EDGES = CHILD_TO_PARENT_EDGES | PARENT_TO_CHILD_EDGES


@dataclass(frozen=True)
class SourceRef:
    source_id: str
    citation: str
    url: str
    version: str = ""
    license: str = ""
    confidence: float = 1.0


@dataclass(frozen=True)
class ValidationError:
    code: str
    subject: str
    message: str


class AnatomyGraphValidationError(ValueError):
    def __init__(self, errors: list[ValidationError]):
        self.errors = errors
        joined = "; ".join(f"{error.code}:{error.subject}" for error in errors)
        super().__init__(f"Anatomy graph validation failed: {joined}")


@dataclass
class AnatomyNode:
    id: str
    label: str
    kind: AnatomyKind | str
    sources: tuple[SourceRef, ...]
    materialization: MaterializationState | str = MaterializationState.CANONICAL
    aliases: tuple[str, ...] = ()
    properties: dict[str, Any] = field(default_factory=dict)
    control_channels: tuple[str, ...] = ()
    llm_visible: bool = False

    def __post_init__(self) -> None:
        self.kind = AnatomyKind(self.kind)
        self.materialization = MaterializationState(self.materialization)
        self.sources = tuple(self.sources)
        self.aliases = tuple(self.aliases)
        self.control_channels = tuple(self.control_channels)


@dataclass
class AnatomyEdge:
    from_id: str
    to_id: str
    kind: EdgeKind | str
    sources: tuple[SourceRef, ...]
    properties: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.kind = EdgeKind(self.kind)
        self.sources = tuple(self.sources)


@dataclass
class WorkingSet:
    root_id: str
    node_ids: tuple[str, ...]
    edge_indexes: tuple[int, ...]

    def contains(self, node_id: str) -> bool:
        return node_id in self.node_ids


class AnatomyGraph:
    def __init__(self) -> None:
        self.nodes: dict[str, AnatomyNode] = {}
        self.edges: list[AnatomyEdge] = []

    def add_node(self, node: AnatomyNode) -> None:
        if node.id in self.nodes:
            raise ValueError(f"Duplicate anatomy node id: {node.id}")
        self.nodes[node.id] = node

    def add_edge(self, edge: AnatomyEdge) -> None:
        self.edges.append(edge)

    def node(self, node_id: str) -> AnatomyNode:
        return self.nodes[node_id]

    def validate(self) -> list[ValidationError]:
        errors: list[ValidationError] = []
        part_of_parent_count: dict[str, int] = {}
        incoming_render_projection: set[str] = set()
        incoming_sim_projection: set[str] = set()

        for node in self.nodes.values():
            errors.extend(_validate_node(node))

        for index, edge in enumerate(self.edges):
            subject = f"edge[{index}]"
            errors.extend(_validate_sources(subject, edge.sources))
            if edge.from_id not in self.nodes:
                errors.append(
                    ValidationError("UNKNOWN_EDGE_FROM", subject, f"Unknown from_id {edge.from_id}")
                )
            if edge.to_id not in self.nodes:
                errors.append(ValidationError("UNKNOWN_EDGE_TO", subject, f"Unknown to_id {edge.to_id}"))
            if edge.from_id == edge.to_id:
                errors.append(ValidationError("SELF_EDGE", subject, "Anatomy edges cannot point to self"))
            if edge.kind == EdgeKind.PART_OF:
                part_of_parent_count[edge.from_id] = part_of_parent_count.get(edge.from_id, 0) + 1
            edge_from = self.nodes.get(edge.from_id)
            edge_to = self.nodes.get(edge.to_id)
            if (
                edge.kind == EdgeKind.PROJECTS_TO_RENDER
                and edge_from is not None
                and edge_to is not None
                and edge_from.kind != AnatomyKind.RENDER_PROXY
            ):
                incoming_render_projection.add(edge.to_id)
            if (
                edge.kind == EdgeKind.PROJECTS_TO_SIMULATION
                and edge_from is not None
                and edge_to is not None
                and edge_from.kind != AnatomyKind.SIMULATION_PROXY
            ):
                incoming_sim_projection.add(edge.to_id)

        for node_id, parent_count in part_of_parent_count.items():
            if parent_count > 1:
                errors.append(
                    ValidationError(
                        "MULTIPLE_PRIMARY_PART_OF",
                        node_id,
                        "Use member_of/located_in for additional relationships; keep one primary part_of.",
                    )
                )

        for node in self.nodes.values():
            if node.kind == AnatomyKind.RENDER_PROXY and node.id not in incoming_render_projection:
                errors.append(
                    ValidationError(
                        "ORPHAN_RENDER_PROXY",
                        node.id,
                        "Render proxy must be reached by projects_to_render from an anatomy node.",
                    )
                )
            if node.kind == AnatomyKind.SIMULATION_PROXY and node.id not in incoming_sim_projection:
                errors.append(
                    ValidationError(
                        "ORPHAN_SIMULATION_PROXY",
                        node.id,
                        "Simulation proxy must be reached by projects_to_simulation from an anatomy node.",
                    )
                )

        return errors

    def assert_valid(self) -> None:
        errors = self.validate()
        if errors:
            raise AnatomyGraphValidationError(errors)

    def compile_working_set(
        self,
        root_id: str,
        *,
        max_depth: int,
        edge_kinds: Iterable[EdgeKind | str] = DEFAULT_WORKING_SET_EDGES,
        expand_virtual: bool = False,
    ) -> WorkingSet:
        if root_id not in self.nodes:
            raise KeyError(f"Unknown anatomy root: {root_id}")
        allowed_edges = {EdgeKind(edge_kind) for edge_kind in edge_kinds}
        visited = {root_id}
        queue: deque[tuple[str, int]] = deque([(root_id, 0)])
        edge_indexes: set[int] = set()

        while queue:
            current_id, depth = queue.popleft()
            if depth >= max_depth:
                continue
            for edge_index, edge, neighbor_id in self._neighbors(current_id, allowed_edges):
                neighbor = self.nodes[neighbor_id]
                if (
                    neighbor.materialization == MaterializationState.VIRTUAL_INSTANCE
                    and not expand_virtual
                ):
                    continue
                edge_indexes.add(edge_index)
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    queue.append((neighbor_id, depth + 1))

        return WorkingSet(
            root_id=root_id,
            node_ids=tuple(sorted(visited)),
            edge_indexes=tuple(sorted(edge_indexes)),
        )

    def llm_control_registry(self) -> list[dict[str, Any]]:
        registry = []
        for node in sorted(self.nodes.values(), key=lambda item: item.id):
            if not node.llm_visible:
                continue
            registry.append(
                {
                    "id": node.id,
                    "label": node.label,
                    "kind": node.kind.value,
                    "materialization": node.materialization.value,
                    "control_channels": list(node.control_channels),
                    "source_ids": [source.source_id for source in node.sources],
                }
            )
        return registry

    def to_neo4j_nodes(self) -> list[dict[str, Any]]:
        records = []
        for node in sorted(self.nodes.values(), key=lambda item: item.id):
            labels = [
                "AnatomyNode",
                _pascal_label(node.kind.value),
                _pascal_label(node.materialization.value),
            ]
            records.append(
                {
                    "id": node.id,
                    "labels": labels,
                    "properties": {
                        "id": node.id,
                        "label": node.label,
                        "kind": node.kind.value,
                        "materialization": node.materialization.value,
                        "aliases": list(node.aliases),
                        "llm_visible": node.llm_visible,
                        "control_channels": list(node.control_channels),
                        "source_ids": [source.source_id for source in node.sources],
                    },
                }
            )
        return records

    def to_neo4j_relationships(self) -> list[dict[str, Any]]:
        records = []
        for edge in self.edges:
            records.append(
                {
                    "start_id": edge.from_id,
                    "end_id": edge.to_id,
                    "type": edge.kind.value.upper(),
                    "properties": {
                        "kind": edge.kind.value,
                        "source_ids": [source.source_id for source in edge.sources],
                        **edge.properties,
                    },
                }
            )
        return records

    @staticmethod
    def neo4j_constraints() -> tuple[str, ...]:
        return (
            "CREATE CONSTRAINT anatomy_node_id IF NOT EXISTS "
            "FOR (n:AnatomyNode) REQUIRE n.id IS UNIQUE",
            "CREATE INDEX anatomy_node_kind IF NOT EXISTS "
            "FOR (n:AnatomyNode) ON (n.kind)",
            "CREATE INDEX anatomy_node_materialization IF NOT EXISTS "
            "FOR (n:AnatomyNode) ON (n.materialization)",
        )

    def _neighbors(
        self, current_id: str, allowed_edges: set[EdgeKind]
    ) -> Iterable[tuple[int, AnatomyEdge, str]]:
        for edge_index, edge in enumerate(self.edges):
            if edge.kind not in allowed_edges:
                continue
            if edge.kind in CHILD_TO_PARENT_EDGES and edge.to_id == current_id:
                yield edge_index, edge, edge.from_id
            elif edge.kind in PARENT_TO_CHILD_EDGES and edge.from_id == current_id:
                yield edge_index, edge, edge.to_id


def _validate_node(node: AnatomyNode) -> list[ValidationError]:
    errors: list[ValidationError] = []
    if not NODE_ID_RE.match(node.id):
        errors.append(
            ValidationError(
                "INVALID_NODE_ID",
                node.id,
                "Use lowercase ids with letters, numbers, underscores, hyphens, periods, or colons.",
            )
        )
    if not node.label.strip():
        errors.append(ValidationError("MISSING_LABEL", node.id, "Node label is required"))
    errors.extend(_validate_sources(node.id, node.sources))
    if node.llm_visible and not node.control_channels:
        errors.append(
            ValidationError(
                "LLM_VISIBLE_WITHOUT_CONTROLS",
                node.id,
                "LLM-visible nodes must declare bounded control channels.",
            )
        )
    if node.kind == AnatomyKind.RENDER_PROXY and node.materialization != MaterializationState.RENDER_PROXY:
        errors.append(
            ValidationError(
                "RENDER_PROXY_STATE_MISMATCH",
                node.id,
                "Render proxy nodes must use render_proxy materialization.",
            )
        )
    if (
        node.kind == AnatomyKind.SIMULATION_PROXY
        and node.materialization != MaterializationState.SIMULATION_PROXY
    ):
        errors.append(
            ValidationError(
                "SIMULATION_PROXY_STATE_MISMATCH",
                node.id,
                "Simulation proxy nodes must use simulation_proxy materialization.",
            )
        )
    return errors


def _validate_sources(subject: str, sources: tuple[SourceRef, ...]) -> list[ValidationError]:
    errors: list[ValidationError] = []
    if not sources:
        return [ValidationError("MISSING_SOURCE", subject, "Source provenance is required")]
    for index, source in enumerate(sources):
        source_subject = f"{subject}.source[{index}]"
        if not source.source_id.strip():
            errors.append(ValidationError("MISSING_SOURCE_ID", source_subject, "source_id is required"))
        if not source.citation.strip():
            errors.append(ValidationError("MISSING_CITATION", source_subject, "citation is required"))
        if not source.url.strip():
            errors.append(ValidationError("MISSING_SOURCE_URL", source_subject, "url is required"))
        if not 0 <= source.confidence <= 1:
            errors.append(
                ValidationError(
                    "INVALID_SOURCE_CONFIDENCE",
                    source_subject,
                    "confidence must be between 0 and 1.",
                )
            )
    return errors


def _pascal_label(value: str) -> str:
    return "".join(part.capitalize() for part in value.split("_"))
