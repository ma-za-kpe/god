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
    if "digit:right_little_finger" in graph.nodes:
        return (
            (
                "pinky",
                "Right hand digits",
                _existing(
                    graph,
                    (
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
                    ),
                ),
            ),
        )

    system_ids = tuple(
        sorted(node.id for node in graph.nodes.values() if node.kind == AnatomyKind.SYSTEM)
    )
    layers = (
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
    return layers


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
    "region:right_upper_limb": {
        "layer_id": "pinky",
        "shape": "path",
        "class_name": "pinky-upper-limb-context",
        "geometry": {"d": "M169 720 C181 654 193 594 205 560 M251 720 C239 654 227 594 214 560"},
    },
    "region:right_hand": {
        "layer_id": "pinky",
        "shape": "path",
        "class_name": "pinky-hand-context",
        "geometry": {
            "d": "M142 559 C118 514 109 450 120 389 "
            "C124 354 132 310 129 276 C128 258 144 252 153 268 "
            "C160 286 160 329 157 356 C162 306 166 256 172 225 "
            "C176 205 195 206 198 227 C200 260 195 318 194 358 "
            "C201 294 206 236 213 204 C218 184 238 187 239 210 "
            "C239 255 230 319 229 359 C241 300 252 251 263 224 "
            "C272 204 291 211 289 234 C286 275 270 330 265 363 "
            "C281 324 297 292 313 270 C326 252 342 266 333 287 "
            "C320 319 300 352 286 389 C308 405 323 441 320 482 "
            "C317 531 284 563 229 568 C193 571 163 568 142 559 Z"
        },
    },
    "aggregate:right_carpals": {
        "layer_id": "pinky",
        "shape": "ellipse",
        "class_name": "pinky-carpals",
        "geometry": {"cx": 209, "cy": 538, "rx": 43, "ry": 24},
        "label_anchor": {"x": 130, "y": 556},
    },
    "aggregate:right_metacarpals": {
        "layer_id": "pinky",
        "shape": "path",
        "class_name": "pinky-metacarpal-fan",
        "geometry": {
            "d": "M182 519 L139 455 M195 514 L177 383 M209 512 L213 376 "
            "M223 514 L250 383 M235 520 L286 389"
        },
        "label_anchor": {"x": 122, "y": 382},
    },
    "aggregate:right_hand_phalanges": {
        "layer_id": "pinky",
        "shape": "path",
        "class_name": "pinky-phalange-fan",
        "geometry": {
            "d": "M139 455 C124 439 107 420 92 405 "
            "M177 383 C171 328 171 283 177 242 "
            "M213 376 C213 314 217 264 225 217 "
            "M250 383 C260 326 270 281 284 240 "
            "M286 389 C306 340 322 300 336 263"
        },
    },
    "digit:right_pollex": {
        "layer_id": "pinky",
        "shape": "path",
        "class_name": "hand-digit",
        "geometry": {"d": "M139 455 C124 439 107 420 92 405"},
        "label_anchor": {"x": 68, "y": 399},
    },
    "bone:right_first_metacarpal": {
        "layer_id": "pinky",
        "shape": "line",
        "class_name": "hand-metacarpal",
        "geometry": {"x1": 182, "y1": 519, "x2": 139, "y2": 455},
    },
    "joint:right_first_carpometacarpal": {
        "layer_id": "pinky",
        "shape": "circle",
        "class_name": "hand-cmc-joint",
        "geometry": {"cx": 182, "cy": 519, "r": 5},
    },
    "joint:right_first_metacarpophalangeal": {
        "layer_id": "pinky",
        "shape": "circle",
        "class_name": "hand-joint",
        "geometry": {"cx": 139, "cy": 455, "r": 6},
    },
    "bone:right_pollex_proximal_phalanx": {
        "layer_id": "pinky",
        "shape": "line",
        "class_name": "hand-phalanx",
        "geometry": {"x1": 136, "y1": 452, "x2": 112, "y2": 428},
    },
    "joint:right_pollex_interphalangeal": {
        "layer_id": "pinky",
        "shape": "circle",
        "class_name": "hand-joint",
        "geometry": {"cx": 108, "cy": 425, "r": 5},
    },
    "bone:right_pollex_distal_phalanx": {
        "layer_id": "pinky",
        "shape": "line",
        "class_name": "hand-phalanx",
        "geometry": {"x1": 105, "y1": 421, "x2": 92, "y2": 405},
    },
    "digit:right_index_finger": {
        "layer_id": "pinky",
        "shape": "path",
        "class_name": "hand-digit",
        "geometry": {"d": "M177 383 C171 328 171 283 177 242"},
        "label_anchor": {"x": 131, "y": 236},
    },
    "bone:right_second_metacarpal": {
        "layer_id": "pinky",
        "shape": "line",
        "class_name": "hand-metacarpal",
        "geometry": {"x1": 195, "y1": 514, "x2": 177, "y2": 383},
    },
    "joint:right_second_carpometacarpal": {
        "layer_id": "pinky",
        "shape": "circle",
        "class_name": "hand-cmc-joint",
        "geometry": {"cx": 195, "cy": 514, "r": 5},
    },
    "joint:right_second_metacarpophalangeal": {
        "layer_id": "pinky",
        "shape": "circle",
        "class_name": "hand-joint",
        "geometry": {"cx": 177, "cy": 383, "r": 6},
    },
    "bone:right_index_finger_proximal_phalanx": {
        "layer_id": "pinky",
        "shape": "line",
        "class_name": "hand-phalanx",
        "geometry": {"x1": 177, "y1": 376, "x2": 174, "y2": 327},
    },
    "joint:right_index_finger_proximal_interphalangeal": {
        "layer_id": "pinky",
        "shape": "circle",
        "class_name": "hand-joint",
        "geometry": {"cx": 173, "cy": 321, "r": 5},
    },
    "bone:right_index_finger_middle_phalanx": {
        "layer_id": "pinky",
        "shape": "line",
        "class_name": "hand-phalanx",
        "geometry": {"x1": 173, "y1": 315, "x2": 173, "y2": 284},
    },
    "joint:right_index_finger_distal_interphalangeal": {
        "layer_id": "pinky",
        "shape": "circle",
        "class_name": "hand-joint",
        "geometry": {"cx": 173, "cy": 278, "r": 4.5},
    },
    "bone:right_index_finger_distal_phalanx": {
        "layer_id": "pinky",
        "shape": "line",
        "class_name": "hand-phalanx",
        "geometry": {"x1": 174, "y1": 272, "x2": 177, "y2": 242},
    },
    "digit:right_middle_finger": {
        "layer_id": "pinky",
        "shape": "path",
        "class_name": "hand-digit",
        "geometry": {"d": "M213 376 C213 314 217 264 225 217"},
        "label_anchor": {"x": 230, "y": 213},
    },
    "bone:right_third_metacarpal": {
        "layer_id": "pinky",
        "shape": "line",
        "class_name": "hand-metacarpal",
        "geometry": {"x1": 209, "y1": 512, "x2": 213, "y2": 376},
    },
    "joint:right_third_carpometacarpal": {
        "layer_id": "pinky",
        "shape": "circle",
        "class_name": "hand-cmc-joint",
        "geometry": {"cx": 209, "cy": 512, "r": 5},
    },
    "joint:right_third_metacarpophalangeal": {
        "layer_id": "pinky",
        "shape": "circle",
        "class_name": "hand-joint",
        "geometry": {"cx": 213, "cy": 376, "r": 6},
    },
    "bone:right_middle_finger_proximal_phalanx": {
        "layer_id": "pinky",
        "shape": "line",
        "class_name": "hand-phalanx",
        "geometry": {"x1": 214, "y1": 369, "x2": 217, "y2": 312},
    },
    "joint:right_middle_finger_proximal_interphalangeal": {
        "layer_id": "pinky",
        "shape": "circle",
        "class_name": "hand-joint",
        "geometry": {"cx": 218, "cy": 306, "r": 5},
    },
    "bone:right_middle_finger_middle_phalanx": {
        "layer_id": "pinky",
        "shape": "line",
        "class_name": "hand-phalanx",
        "geometry": {"x1": 219, "y1": 300, "x2": 222, "y2": 260},
    },
    "joint:right_middle_finger_distal_interphalangeal": {
        "layer_id": "pinky",
        "shape": "circle",
        "class_name": "hand-joint",
        "geometry": {"cx": 223, "cy": 254, "r": 4.5},
    },
    "bone:right_middle_finger_distal_phalanx": {
        "layer_id": "pinky",
        "shape": "line",
        "class_name": "hand-phalanx",
        "geometry": {"x1": 224, "y1": 248, "x2": 225, "y2": 217},
    },
    "digit:right_ring_finger": {
        "layer_id": "pinky",
        "shape": "path",
        "class_name": "hand-digit",
        "geometry": {"d": "M250 383 C260 326 270 281 284 240"},
        "label_anchor": {"x": 289, "y": 235},
    },
    "bone:right_fourth_metacarpal": {
        "layer_id": "pinky",
        "shape": "line",
        "class_name": "hand-metacarpal",
        "geometry": {"x1": 223, "y1": 514, "x2": 250, "y2": 383},
    },
    "joint:right_fourth_carpometacarpal": {
        "layer_id": "pinky",
        "shape": "circle",
        "class_name": "hand-cmc-joint",
        "geometry": {"cx": 223, "cy": 514, "r": 5},
    },
    "joint:right_fourth_metacarpophalangeal": {
        "layer_id": "pinky",
        "shape": "circle",
        "class_name": "hand-joint",
        "geometry": {"cx": 250, "cy": 383, "r": 6},
    },
    "bone:right_ring_finger_proximal_phalanx": {
        "layer_id": "pinky",
        "shape": "line",
        "class_name": "hand-phalanx",
        "geometry": {"x1": 252, "y1": 376, "x2": 260, "y2": 326},
    },
    "joint:right_ring_finger_proximal_interphalangeal": {
        "layer_id": "pinky",
        "shape": "circle",
        "class_name": "hand-joint",
        "geometry": {"cx": 261, "cy": 320, "r": 5},
    },
    "bone:right_ring_finger_middle_phalanx": {
        "layer_id": "pinky",
        "shape": "line",
        "class_name": "hand-phalanx",
        "geometry": {"x1": 263, "y1": 314, "x2": 272, "y2": 281},
    },
    "joint:right_ring_finger_distal_interphalangeal": {
        "layer_id": "pinky",
        "shape": "circle",
        "class_name": "hand-joint",
        "geometry": {"cx": 274, "cy": 275, "r": 4.5},
    },
    "bone:right_ring_finger_distal_phalanx": {
        "layer_id": "pinky",
        "shape": "line",
        "class_name": "hand-phalanx",
        "geometry": {"x1": 276, "y1": 269, "x2": 284, "y2": 240},
    },
    "digit:right_little_finger": {
        "layer_id": "pinky",
        "shape": "path",
        "class_name": "pinky-digit",
        "geometry": {"d": "M286 389 C306 340 322 300 336 263"},
        "label_anchor": {"x": 299, "y": 252},
    },
    "bone:right_fifth_metacarpal": {
        "layer_id": "pinky",
        "shape": "line",
        "class_name": "pinky-metacarpal",
        "geometry": {"x1": 235, "y1": 520, "x2": 286, "y2": 389},
    },
    "joint:right_fifth_carpometacarpal": {
        "layer_id": "pinky",
        "shape": "circle",
        "class_name": "hand-cmc-joint",
        "geometry": {"cx": 235, "cy": 520, "r": 5},
    },
    "joint:right_fifth_metacarpophalangeal": {
        "layer_id": "pinky",
        "shape": "circle",
        "class_name": "pinky-joint",
        "geometry": {"cx": 286, "cy": 389, "r": 7},
    },
    "bone:right_little_finger_proximal_phalanx": {
        "layer_id": "pinky",
        "shape": "line",
        "class_name": "pinky-phalanx",
        "geometry": {"x1": 289, "y1": 382, "x2": 306, "y2": 340},
    },
    "joint:right_little_finger_proximal_interphalangeal": {
        "layer_id": "pinky",
        "shape": "circle",
        "class_name": "pinky-joint",
        "geometry": {"cx": 308, "cy": 334, "r": 5.5},
    },
    "bone:right_little_finger_middle_phalanx": {
        "layer_id": "pinky",
        "shape": "line",
        "class_name": "pinky-phalanx",
        "geometry": {"x1": 310, "y1": 328, "x2": 323, "y2": 297},
    },
    "joint:right_little_finger_distal_interphalangeal": {
        "layer_id": "pinky",
        "shape": "circle",
        "class_name": "pinky-joint",
        "geometry": {"cx": 325, "cy": 291, "r": 5},
    },
    "bone:right_little_finger_distal_phalanx": {
        "layer_id": "pinky",
        "shape": "line",
        "class_name": "pinky-phalanx",
        "geometry": {"x1": 327, "y1": 285, "x2": 336, "y2": 263},
    },
}
