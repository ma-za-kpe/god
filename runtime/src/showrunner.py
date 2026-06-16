"""showrunner.py - deterministic live broadcast planner for the world runtime."""

from __future__ import annotations

from dataclasses import replace
import hashlib
from typing import Any

try:  # pragma: no cover - package import path in runtime
    from .showrunner_rules import audience_prompt_for, event_to_cue, select_scene, speaker_for
    from .showrunner_state import ShowrunnerPlan, ShowrunnerState
except ImportError:  # pragma: no cover - flat import path in tests
    from showrunner_rules import audience_prompt_for, event_to_cue, select_scene, speaker_for
    from showrunner_state import ShowrunnerPlan, ShowrunnerState


class Showrunner:
    """Build a stable broadcast plan from a world snapshot."""

    def __init__(self, state: ShowrunnerState | None = None):
        self._state = state or ShowrunnerState()

    @property
    def state(self) -> ShowrunnerState:
        return self._state

    def build_plan(self, snapshot: dict[str, Any]) -> ShowrunnerPlan:
        cues = self._collect_cues(snapshot)
        stats = snapshot.get("stats") or {}
        epoch = int(snapshot.get("epoch") or 0)
        signature = self._signature(snapshot, cues)

        if self._state.last_signature == signature and self._state.last_plan:
            return self._state.last_plan

        scene = select_scene(cues, snapshot)
        speaker = speaker_for(cues, snapshot)
        headline = self._headline(cues, stats)
        audience_prompt = audience_prompt_for(cues, snapshot)
        reasoning = self._reasoning(cues, snapshot, scene, speaker)

        plan = ShowrunnerPlan(
            mode="live-weave",
            scene=scene,
            speaker=speaker,
            headline=headline,
            audience_prompt=audience_prompt,
            cues=tuple(cues[:5]),
            reasoning=tuple(reasoning),
            source_epoch=epoch,
            source_agent_count=int(snapshot.get("agent_count") or len(snapshot.get("agents") or [])),
        )
        self._state = replace(self._state, last_epoch=epoch, last_signature=signature, last_plan=plan)
        return plan

    def build_plan_dict(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        return self.build_plan(snapshot).to_dict()

    def _collect_cues(self, snapshot: dict[str, Any]) -> list:
        cues = []
        for event in snapshot.get("events") or []:
            cue = event_to_cue(event)
            if cue:
                cues.append(cue)
        cues.sort(key=lambda cue: (cue.priority, cue.cue_type, cue.agent_name, cue.agent_id), reverse=True)
        return cues

    def _headline(self, cues, stats: dict[str, Any]) -> str:
        if cues:
            top = cues[0]
            if top.agent_name and top.headline:
                return f"{top.agent_name}: {top.headline}"
            return top.headline or top.cue_type
        if int(stats.get("living_count") or 0) == 0:
            return "The world is silent."
        if int(stats.get("transfers_24h") or 0) > 0:
            return "The market is moving."
        return "The world is holding."

    def _reasoning(self, cues, snapshot: dict[str, Any], scene: str, speaker: str) -> list[str]:
        stats = snapshot.get("stats") or {}
        audience = snapshot.get("audience") or {}
        notes = [
            f"scene={scene}",
            f"speaker={speaker}",
            f"living={int(stats.get('living_count') or 0)}",
            f"events_24h={int(stats.get('events_total') or 0)}",
        ]
        if cues:
            notes.append(f"top_cue={cues[0].cue_type}")
        if int(stats.get("transfers_24h") or 0) > 0:
            notes.append("economy_active")
        if int(stats.get("service_purchases_24h") or 0) > 0:
            notes.append("patronage_visible")
        if float(audience.get("patronage_index") or 0) >= 12:
            notes.append("audience_funded")
        if int(audience.get("raid_waves_24h") or 0) > 0:
            notes.append("raid_pressure")
        if int(audience.get("chat_pressure") or 0) >= 8:
            notes.append("chat_drives_scene")
        return notes

    def _signature(self, snapshot: dict[str, Any], cues) -> str:
        payload = {
            "epoch": snapshot.get("epoch"),
            "agent_count": snapshot.get("agent_count"),
            "stats": snapshot.get("stats") or {},
            "cues": [cue.to_dict() for cue in cues[:5]],
        }
        raw = repr(payload).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


_DEFAULT_SHOWRUNNER = Showrunner()


def build_showrunner_plan(snapshot: dict[str, Any]) -> dict[str, Any]:
    return _DEFAULT_SHOWRUNNER.build_plan_dict(snapshot)


def get_showrunner_state() -> dict[str, Any]:
    return _DEFAULT_SHOWRUNNER.state.to_dict()
