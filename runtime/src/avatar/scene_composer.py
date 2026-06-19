"""Multi-Elder scene composition helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

try:  # pragma: no cover - runtime package import path
    from ..banter.types import Beat, SceneContextData
except ImportError:  # pragma: no cover - flat test path
    from banter.types import Beat, SceneContextData


@dataclass(frozen=True)
class ElderLayout:
    soul_id: str
    position: tuple[float, float]
    scale: float
    z_order: int
    expression: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SceneLayout:
    elders: list[ElderLayout] = field(default_factory=list)
    transition_duration_s: float = 2.0
    composition_type: str = "duo"

    def to_dict(self) -> dict[str, Any]:
        return {
            "elders": [elder.to_dict() for elder in self.elders],
            "transition_duration_s": self.transition_duration_s,
            "composition_type": self.composition_type,
        }


class SceneComposer:
    """Compute stable layout specs for 2-4 Elder scenes."""

    BASE_LAYOUTS: dict[int, list[tuple[float, float]]] = {
        2: [(0.30, 0.55), (0.70, 0.55)],
        3: [(0.20, 0.58), (0.50, 0.42), (0.80, 0.58)],
        4: [(0.18, 0.60), (0.38, 0.42), (0.62, 0.42), (0.82, 0.60)],
    }

    def __init__(self) -> None:
        self._last_has_the_room: str | None = None
        self._last_layout: SceneLayout | None = None

    def compose_scene(
        self,
        scene_ctx: SceneContextData | dict[str, Any],
        pair_states: dict[Any, Any] | None,
        visual_states: dict[str, Any] | None,
    ) -> SceneLayout:
        scene_ctx = self._coerce_scene_ctx(scene_ctx)
        visual_states = visual_states or {}
        speakers = self._ordered_speakers(scene_ctx)
        if not speakers:
            return SceneLayout()

        composition_size = min(max(len(speakers), 2), 4)
        base_positions = self.BASE_LAYOUTS[composition_size]
        dominant = scene_ctx.has_the_room or speakers[0]

        transition = 2.0
        if self._last_has_the_room and self._last_has_the_room != dominant:
            transition = 3.0
        if len(scene_ctx.recent_beats) and scene_ctx.scene_energy == "heated":
            transition = min(4.0, transition + 0.5)

        layouts: list[ElderLayout] = []
        for index, soul_id in enumerate(speakers[:composition_size]):
            pos = base_positions[min(index, len(base_positions) - 1)]
            expression = self._expression_for(visual_states, soul_id)
            z_order = self._z_order(scene_ctx.recent_beats, soul_id, default=index)
            scale = 0.82 if soul_id != dominant else 1.0
            x, y = self._apply_tension_pull(
                soul_id=soul_id,
                position=pos,
                pair_states=pair_states or {},
            )
            if soul_id == dominant:
                x, y, scale, z_order = 0.50, 0.50, 1.0, max(z_order, 3)
            layouts.append(
                ElderLayout(
                    soul_id=soul_id,
                    position=(round(x, 3), round(y, 3)),
                    scale=round(scale, 3),
                    z_order=int(z_order),
                    expression=expression,
                )
            )

        layout = SceneLayout(
            elders=layouts,
            transition_duration_s=transition,
            composition_type={2: "duo", 3: "trio", 4: "quad"}[composition_size],
        )
        self._last_has_the_room = dominant
        self._last_layout = layout
        return layout

    def _coerce_scene_ctx(self, scene_ctx: SceneContextData | dict[str, Any]) -> SceneContextData:
        if isinstance(scene_ctx, SceneContextData):
            return scene_ctx
        ctx = SceneContextData()
        recent_beats = scene_ctx.get("recent_beats") or []
        if recent_beats:
            ctx.recent_beats.clear()
            for beat in recent_beats:
                if isinstance(beat, Beat):
                    ctx.recent_beats.append(beat)
                elif isinstance(beat, dict):
                    ctx.recent_beats.append(Beat(**beat))
        ctx.has_the_room = scene_ctx.get("has_the_room")
        ctx.landed_hit = scene_ctx.get("landed_hit")
        ctx.landed_hit_remaining = int(scene_ctx.get("landed_hit_remaining") or 0)
        ctx.scene_energy = str(scene_ctx.get("scene_energy") or "neutral")
        return ctx

    def _ordered_speakers(self, scene_ctx: SceneContextData) -> list[str]:
        ordered: list[str] = []
        for beat in scene_ctx.recent_beats:
            if beat.speaker not in ordered:
                ordered.append(beat.speaker)
        if scene_ctx.has_the_room and scene_ctx.has_the_room not in ordered:
            ordered.insert(0, scene_ctx.has_the_room)
        return ordered

    def _expression_for(self, visual_states: dict[str, Any], soul_id: str) -> str:
        state = visual_states.get(soul_id) or {}
        if isinstance(state, dict):
            return str(
                state.get("expression_override")
                or state.get("current_expression")
                or "neutral"
            )
        return "neutral"

    def _z_order(self, beats: Any, soul_id: str, default: int) -> int:
        active = None
        previous = None
        for beat in reversed(list(beats)):
            if active is None:
                active = beat.speaker
            elif previous is None and beat.speaker != active:
                previous = beat.speaker
                break
        if soul_id == active:
            return 3
        if soul_id == previous:
            return 2
        return max(0, 1 + default)

    def _apply_tension_pull(
        self,
        *,
        soul_id: str,
        position: tuple[float, float],
        pair_states: dict[Any, Any],
    ) -> tuple[float, float]:
        x, y = position
        strongest = self._strongest_pair_tension(soul_id, pair_states)
        if strongest is None or strongest <= 7:
            return x, y
        pull = min(0.12, 0.02 * (strongest - 7))
        if x < 0.5:
            x += pull
        else:
            x -= pull
        if y < 0.5:
            y += pull / 2
        else:
            y -= pull / 2
        return x, y

    def _strongest_pair_tension(self, soul_id: str, pair_states: dict[Any, Any]) -> int | None:
        strongest: int | None = None
        for key, pair_state in pair_states.items():
            if not self._pair_mentions_soul(key, soul_id):
                continue
            tension = int(getattr(pair_state, "tension_level", 0) or 0)
            if strongest is None or tension > strongest:
                strongest = tension
        return strongest

    def _pair_mentions_soul(self, key: Any, soul_id: str) -> bool:
        if isinstance(key, (tuple, list, set, frozenset)):
            return soul_id in {str(part) for part in key}
        return soul_id in str(key)
