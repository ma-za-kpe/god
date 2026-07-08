"""Browser render projection for sourced anatomy graph nodes.

The anatomy graph remains the source of truth. This module only compiles a
small browser-inspection projection: which graph nodes can be drawn now, which
layer they belong to, and which real graph nodes are still degraded because the
renderer has no mapping for them yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .graph import AnatomyGraph, AnatomyKind


ANATOMY_RENDER_SCHEMA_VERSION = "god.anatomy_render_projection.v1"


@dataclass(frozen=True)
class AnatomyRenderPrimitive:
    node_id: str
    layer_id: str
    shape: str
    geometry: dict[str, Any]
    class_name: str
    label_anchor: dict[str, float] | None = None
    source_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "layer_id": self.layer_id,
            "shape": self.shape,
            "geometry": dict(self.geometry),
            "class_name": self.class_name,
            "label_anchor": dict(self.label_anchor) if self.label_anchor else None,
            "source_ids": list(self.source_ids),
        }


@dataclass(frozen=True)
class AnatomyRenderLayer:
    id: str
    label: str
    target_node_ids: tuple[str, ...]
    mapped_node_ids: tuple[str, ...]
    missing_node_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "target_node_ids": list(self.target_node_ids),
            "mapped_node_ids": list(self.mapped_node_ids),
            "missing_node_ids": list(self.missing_node_ids),
            "target_count": len(self.target_node_ids),
            "mapped_count": len(self.mapped_node_ids),
            "missing_count": len(self.missing_node_ids),
            "status": "complete" if not self.missing_node_ids else "degraded",
        }


@dataclass(frozen=True)
class AnatomyRenderProjection:
    schema: str
    layers: tuple[AnatomyRenderLayer, ...]
    primitives: tuple[AnatomyRenderPrimitive, ...]
    diagnostics: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "status": "complete" if not self.diagnostics else "degraded",
            "layers": [layer.to_dict() for layer in self.layers],
            "primitives": [primitive.to_dict() for primitive in self.primitives],
            "diagnostics": list(self.diagnostics),
            "layer_count": len(self.layers),
            "primitive_count": len(self.primitives),
            "missing_mapping_count": len(
                [
                    diagnostic
                    for diagnostic in self.diagnostics
                    if diagnostic.startswith("missing_render_mapping:")
                ]
            ),
        }


def build_anatomy_render_projection(graph: AnatomyGraph) -> AnatomyRenderProjection:
    """Compile graph nodes into the current browser-inspection projection."""

    graph.assert_valid()
    layer_targets = _layer_targets(graph)
    primitives: list[AnatomyRenderPrimitive] = []
    layers: list[AnatomyRenderLayer] = []
    diagnostics: list[str] = []

    for layer_id, label, target_node_ids in layer_targets:
        mapped_node_ids: list[str] = []
        missing_node_ids: list[str] = []
        for node_id in target_node_ids:
            primitive_spec = _PRIMITIVES_BY_NODE_ID.get(node_id)
            if primitive_spec and primitive_spec["layer_id"] == layer_id:
                node = graph.node(node_id)
                mapped_node_ids.append(node_id)
                primitives.append(
                    AnatomyRenderPrimitive(
                        node_id=node_id,
                        layer_id=layer_id,
                        shape=primitive_spec["shape"],
                        geometry=primitive_spec["geometry"],
                        class_name=primitive_spec["class_name"],
                        label_anchor=primitive_spec.get("label_anchor"),
                        source_ids=tuple(source.source_id for source in node.sources),
                    )
                )
            else:
                missing_node_ids.append(node_id)
                diagnostics.append(f"missing_render_mapping:{layer_id}:{node_id}")
        layers.append(
            AnatomyRenderLayer(
                id=layer_id,
                label=label,
                target_node_ids=target_node_ids,
                mapped_node_ids=tuple(mapped_node_ids),
                missing_node_ids=tuple(missing_node_ids),
            )
        )

    return AnatomyRenderProjection(
        schema=ANATOMY_RENDER_SCHEMA_VERSION,
        layers=tuple(layers),
        primitives=tuple(primitives),
        diagnostics=tuple(diagnostics),
    )


def _layer_targets(graph: AnatomyGraph) -> tuple[tuple[str, str, tuple[str, ...]], ...]:
    system_ids = tuple(
        sorted(node.id for node in graph.nodes.values() if node.kind == AnatomyKind.SYSTEM)
    )
    return (
        ("body", "Body", _existing(graph, ("body:human",))),
        ("systems", "Systems", system_ids),
        (
            "head",
            "Head",
            _existing(
                graph,
                (
                    "region:head",
                    "bone:skull",
                    "organ:brain",
                    "skin:forehead",
                    "population:scalp_hair_follicles",
                    "population:forehead_eccrine_sweat_glands",
                ),
            ),
        ),
        (
            "knee",
            "Right knee",
            _existing(
                graph,
                (
                    "joint:right_knee",
                    "bone:right_femur",
                    "bone:right_tibia",
                    "bone:right_patella",
                    "ligament:right_acl",
                    "ligament:right_pcl",
                    "ligament:right_mcl",
                    "ligament:right_lcl",
                ),
            ),
        ),
        (
            "toe",
            "Right hallux",
            _existing(
                graph,
                (
                    "digit:right_hallux",
                    "skin:right_hallux",
                    "bone:right_hallux_proximal_phalanx",
                    "bone:right_hallux_distal_phalanx",
                ),
            ),
        ),
    )


def _existing(graph: AnatomyGraph, node_ids: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(node_id for node_id in node_ids if node_id in graph.nodes)


_PRIMITIVES_BY_NODE_ID: dict[str, dict[str, Any]] = {
    "body:human": {
        "layer_id": "body",
        "shape": "path",
        "class_name": "body-outline",
        "geometry": {
            "d": "M210 70 C151 70 133 142 142 204 C98 248 76 347 73 433 "
            "C70 520 101 640 132 707 C177 732 244 732 288 707 "
            "C319 640 350 520 347 433 C344 347 322 248 278 204 "
            "C287 142 269 70 210 70 Z"
        },
        "label_anchor": {"x": 44, "y": 64},
    },
    "system:integumentary": {
        "layer_id": "systems",
        "shape": "path",
        "class_name": "system-integumentary",
        "geometry": {"d": "M151 210 C169 188 250 188 269 210 L289 432 C255 466 165 466 131 432 Z"},
        "label_anchor": {"x": 294, "y": 274},
    },
    "system:skeletal": {
        "layer_id": "systems",
        "shape": "path",
        "class_name": "system-skeletal",
        "geometry": {
            "d": "M210 112 V436 M169 264 C192 248 228 248 251 264 "
            "M162 304 C192 288 228 288 258 304 M151 224 L79 424 "
            "M269 224 L346 424 M174 454 L143 688 M246 454 L278 688"
        },
        "label_anchor": {"x": 298, "y": 314},
    },
    "system:nervous": {
        "layer_id": "systems",
        "shape": "path",
        "class_name": "system-nervous",
        "geometry": {
            "d": "M191 114 C195 88 226 88 230 114 C235 143 184 143 191 114 "
            "M210 146 V440 M204 246 L180 318 M216 246 L241 318"
        },
        "label_anchor": {"x": 246, "y": 154},
    },
    "system:cardiovascular": {
        "layer_id": "systems",
        "shape": "path",
        "class_name": "system-cardiovascular",
        "geometry": {
            "d": "M210 281 C195 260 166 279 184 304 C196 320 210 331 210 331 "
            "C210 331 224 320 236 304 C254 279 225 260 210 281 "
            "M210 331 V430 M210 331 C178 372 132 393 94 427 "
            "M210 331 C242 372 288 393 326 427"
        },
        "label_anchor": {"x": 247, "y": 366},
    },
    "region:head": {
        "layer_id": "head",
        "shape": "circle",
        "class_name": "head-region",
        "geometry": {"cx": 210, "cy": 119, "r": 57},
        "label_anchor": {"x": 271, "y": 90},
    },
    "bone:skull": {
        "layer_id": "head",
        "shape": "path",
        "class_name": "head-skull",
        "geometry": {"d": "M174 115 C174 73 246 73 246 115 C246 154 174 154 174 115 Z"},
        "label_anchor": {"x": 263, "y": 118},
    },
    "organ:brain": {
        "layer_id": "head",
        "shape": "path",
        "class_name": "head-brain",
        "geometry": {
            "d": "M185 112 C184 92 204 86 211 98 C221 84 242 94 237 117 "
            "C235 137 210 139 202 128 C194 139 181 130 185 112 Z"
        },
        "label_anchor": {"x": 251, "y": 142},
    },
    "skin:forehead": {
        "layer_id": "head",
        "shape": "path",
        "class_name": "head-forehead",
        "geometry": {"d": "M176 101 C188 76 233 76 246 101 C228 92 194 92 176 101 Z"},
    },
    "population:scalp_hair_follicles": {
        "layer_id": "head",
        "shape": "path",
        "class_name": "head-hair-population",
        "geometry": {"d": "M165 108 C166 55 254 54 257 109 C243 86 184 84 165 108 Z"},
    },
    "population:forehead_eccrine_sweat_glands": {
        "layer_id": "head",
        "shape": "circle",
        "class_name": "head-sweat-population",
        "geometry": {"cx": 211, "cy": 94, "r": 8},
    },
    "joint:right_knee": {
        "layer_id": "knee",
        "shape": "circle",
        "class_name": "knee-joint",
        "geometry": {"cx": 267, "cy": 560, "r": 24},
        "label_anchor": {"x": 305, "y": 558},
    },
    "bone:right_femur": {
        "layer_id": "knee",
        "shape": "line",
        "class_name": "knee-bone",
        "geometry": {"x1": 246, "y1": 454, "x2": 267, "y2": 542},
    },
    "bone:right_tibia": {
        "layer_id": "knee",
        "shape": "line",
        "class_name": "knee-bone",
        "geometry": {"x1": 267, "y1": 578, "x2": 278, "y2": 685},
    },
    "bone:right_patella": {
        "layer_id": "knee",
        "shape": "circle",
        "class_name": "knee-patella",
        "geometry": {"cx": 256, "cy": 560, "r": 7},
    },
    "ligament:right_acl": {
        "layer_id": "knee",
        "shape": "line",
        "class_name": "knee-ligament",
        "geometry": {"x1": 257, "y1": 546, "x2": 277, "y2": 574},
    },
    "ligament:right_pcl": {
        "layer_id": "knee",
        "shape": "line",
        "class_name": "knee-ligament",
        "geometry": {"x1": 277, "y1": 546, "x2": 257, "y2": 574},
    },
    "ligament:right_mcl": {
        "layer_id": "knee",
        "shape": "line",
        "class_name": "knee-ligament",
        "geometry": {"x1": 245, "y1": 546, "x2": 247, "y2": 574},
    },
    "ligament:right_lcl": {
        "layer_id": "knee",
        "shape": "line",
        "class_name": "knee-ligament",
        "geometry": {"x1": 289, "y1": 546, "x2": 287, "y2": 574},
    },
    "digit:right_hallux": {
        "layer_id": "toe",
        "shape": "ellipse",
        "class_name": "toe-digit",
        "geometry": {"cx": 278, "cy": 690, "rx": 25, "ry": 13},
        "label_anchor": {"x": 314, "y": 722},
    },
    "skin:right_hallux": {
        "layer_id": "toe",
        "shape": "ellipse",
        "class_name": "toe-skin",
        "geometry": {"cx": 278, "cy": 690, "rx": 32, "ry": 17},
    },
    "bone:right_hallux_proximal_phalanx": {
        "layer_id": "toe",
        "shape": "line",
        "class_name": "toe-bone",
        "geometry": {"x1": 257, "y1": 686, "x2": 277, "y2": 689},
    },
    "bone:right_hallux_distal_phalanx": {
        "layer_id": "toe",
        "shape": "line",
        "class_name": "toe-bone",
        "geometry": {"x1": 278, "y1": 690, "x2": 299, "y2": 694},
    },
}
