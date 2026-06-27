"""Runtime visual state updates for avatar reactions."""

from __future__ import annotations

import time
from typing import Any

try:  # pragma: no cover - runtime package import path
    from ..banter.types import Beat, PairState
except ImportError:  # pragma: no cover - flat test path
    from banter.types import Beat, PairState

MOVE_EXPRESSION_MAP: dict[str, str] = {
    "ESCALATE": "intense",
    "TAUNT": "angry",
    "CONCEDE": "calm",
    "DEFLECT": "playful",
    "QUESTION": "attentive",
    "PIVOT": "animated",
    "SILENCE": "calm",
    "CALLBACK": "playful",
    "COUNTER": "intense",
    "CRACK": "vulnerable",
}


def _now_epoch(current_epoch: int | None = None) -> int:
    return int(time.time()) if current_epoch is None else int(current_epoch)


def _default_visual_state() -> dict[str, Any]:
    return {
        "current_expression": "neutral",
        "expression_override": "",
        "override_expiry_epoch": 0,
        "scar_layers": [],
        "presentation_mode": "standard",
        "speaking": False,
        "mouth_open": 0.0,
    }


def _agent_record(agent: Any) -> dict[str, Any] | None:
    if isinstance(agent, dict):
        return agent
    if hasattr(agent, "identity") and getattr(agent, "identity") is not None:
        return getattr(agent, "identity")
    return agent if hasattr(agent, "visual_state") else None


def _visual_state(agent: Any) -> dict[str, Any]:
    record = _agent_record(agent)
    if record is None:
        return _default_visual_state()
    if isinstance(record, dict):
        return record.setdefault("visual_state", _default_visual_state())
    visual_state = getattr(record, "visual_state", None)
    if not isinstance(visual_state, dict):
        visual_state = _default_visual_state()
        setattr(record, "visual_state", visual_state)
    else:
        visual_state.setdefault("current_expression", "neutral")
        visual_state.setdefault("expression_override", "")
        visual_state.setdefault("override_expiry_epoch", 0)
        visual_state.setdefault("scar_layers", [])
        visual_state.setdefault("presentation_mode", "standard")
        visual_state.setdefault("speaking", False)
        visual_state.setdefault("mouth_open", 0.0)
    return visual_state


def _coerce_move(beat: Beat | dict[str, Any] | Any) -> str:
    if isinstance(beat, dict):
        return str(beat.get("move") or "").upper()
    return str(getattr(beat, "move", "") or "").upper()


def _coerce_speaker(beat: Beat | dict[str, Any] | Any) -> str:
    if isinstance(beat, dict):
        return str(beat.get("speaker") or "")
    return str(getattr(beat, "speaker", "") or "")


def _coerce_quality(beat: Beat | dict[str, Any] | Any) -> int:
    if isinstance(beat, dict):
        return int(beat.get("quality_score") or 0)
    return int(getattr(beat, "quality_score", 0) or 0)


class VisualReactor:
    """Update runtime visual state from banter beats."""

    def __init__(
        self,
        *,
        crack_expression_duration_seconds: int | None = None,
        flinch_expression_duration_seconds: int | None = None,
    ) -> None:
        self.crack_expression_duration_seconds = crack_expression_duration_seconds or int(
            __import__("os").getenv("CRACK_EXPRESSION_DURATION_SECONDS", "25")
        )
        self.flinch_expression_duration_seconds = flinch_expression_duration_seconds or int(
            __import__("os").getenv("FLINCH_EXPRESSION_DURATION_SECONDS", "8")
        )

    def on_beat_delivered(
        self,
        beat: Beat | dict[str, Any] | Any,
        pair_state: PairState | None,
        agents: dict[str, Any] | list[Any] | tuple[Any, ...] | None,
        *,
        current_epoch: int | None = None,
    ) -> str:
        """Update the speaker's visual state from a delivered beat."""
        speaker = _coerce_speaker(beat)
        move = _coerce_move(beat)
        quality_score = _coerce_quality(beat)
        now = _now_epoch(current_epoch)

        expression = MOVE_EXPRESSION_MAP.get(move, "attentive")
        tension = int(getattr(pair_state, "tension_level", 5) or 5)
        if tension > 7 and move in {"QUESTION", "DEFLECT", "CALLBACK"}:
            expression = "animated"
        elif tension > 7 and expression == "attentive":
            expression = "intense"

        agent = self._find_agent(agents, speaker)
        if agent is None:
            return expression

        visual_state = _visual_state(agent)
        override = str(visual_state.get("expression_override") or "")
        expiry = int(visual_state.get("override_expiry_epoch") or 0)
        if override and expiry > now:
            visual_state["current_expression"] = override
        else:
            if override and expiry <= now:
                visual_state["expression_override"] = ""
                visual_state["override_expiry_epoch"] = 0
            visual_state["current_expression"] = expression

        if move == "CRACK":
            visual_state["expression_override"] = "vulnerable"
            visual_state["override_expiry_epoch"] = now + self.crack_expression_duration_seconds
            visual_state["current_expression"] = "vulnerable"

        if quality_score > 12:
            visual_state.setdefault("scar_layers", [])
            if isinstance(visual_state["scar_layers"], list):
                visual_state["scar_layers"].append(
                    {
                        "type": "landed_hit",
                        "timestamp": now,
                        "source_soul_id": speaker,
                    }
                )

        return str(visual_state.get("current_expression") or expression)

    def on_landed_hit(
        self,
        beat: Beat | dict[str, Any] | Any,
        receiver_soul_id: str,
        agents: dict[str, Any] | list[Any] | tuple[Any, ...] | None,
        *,
        current_epoch: int | None = None,
    ) -> str | None:
        """Force a flinch expression on the receiver."""
        now = _now_epoch(current_epoch)
        agent = self._find_agent(agents, receiver_soul_id)
        if agent is None:
            return None
        visual_state = _visual_state(agent)
        visual_state["expression_override"] = "flinch"
        visual_state["override_expiry_epoch"] = now + self.flinch_expression_duration_seconds
        visual_state["current_expression"] = "flinch"
        visual_state.setdefault("scar_layers", [])
        if isinstance(visual_state["scar_layers"], list):
            visual_state["scar_layers"].append(
                {
                    "type": "flinch",
                    "timestamp": now,
                    "source_soul_id": _coerce_speaker(beat),
                }
            )
        return "flinch"

    def clear_expired_overrides(
        self,
        agents: dict[str, Any] | list[Any] | tuple[Any, ...] | None,
        *,
        current_epoch: int | None = None,
    ) -> int:
        """Clear expired overrides and return the number of agents updated."""
        now = _now_epoch(current_epoch)
        cleared = 0
        for agent in self._iter_agents(agents):
            visual_state = _visual_state(agent)
            expiry = int(visual_state.get("override_expiry_epoch") or 0)
            if visual_state.get("expression_override") and expiry and expiry <= now:
                visual_state["expression_override"] = ""
                visual_state["override_expiry_epoch"] = 0
                if not visual_state.get("current_expression"):
                    visual_state["current_expression"] = "neutral"
                cleared += 1
        return cleared

    def _iter_agents(
        self, agents: dict[str, Any] | list[Any] | tuple[Any, ...] | None
    ) -> list[Any]:
        if agents is None:
            return []
        if isinstance(agents, dict):
            return list(agents.values())
        return list(agents)

    def _find_agent(
        self, agents: dict[str, Any] | list[Any] | tuple[Any, ...] | None, soul_id: str
    ) -> Any | None:
        if not soul_id:
            return None
        for agent in self._iter_agents(agents):
            if isinstance(agent, dict):
                candidate = str(
                    agent.get("soul_id")
                    or agent.get("current_name")
                    or agent.get("identity", {}).get("soul_id")
                    or agent.get("identity", {}).get("current_name")
                    or ""
                )
                if candidate.lower() == soul_id.lower():
                    return agent
                continue
            identity = getattr(agent, "identity", None)
            if (
                identity is not None
                and str(
                    getattr(identity, "soul_id", "") or getattr(identity, "current_name", "") or ""
                ).lower()
                == soul_id.lower()
            ):
                return agent
            if (
                str(
                    getattr(agent, "soul_id", "") or getattr(agent, "current_name", "") or ""
                ).lower()
                == soul_id.lower()
            ):
                return agent
        return None
