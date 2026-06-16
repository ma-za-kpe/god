"""NeMo director that refines the showrunner plan into stream-facing instructions."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .client import build_nemo_status
from .guardrails import NemoGuardrails
from .memory import NemoMemory
from .prompts import build_director_prompt


@dataclass(frozen=True)
class NemoDirective:
    """Structured stream directive from the NeMo layer."""

    mode: str
    scene: str
    speaker: str
    director_note: str
    audience_prompt: str
    guardrail_status: str = "ok"
    guardrail_reason: str = ""
    summary: str = ""
    cues: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    rationale: tuple[str, ...] = field(default_factory=tuple)
    evaluation: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class NemoDirector:
    """Compose a safe, concise live-stream instruction set."""

    def __init__(
        self,
        memory: NemoMemory | None = None,
        guardrails: NemoGuardrails | None = None,
    ):
        self.memory = memory or NemoMemory()
        self.guardrails = guardrails or NemoGuardrails()

    def compose(self, snapshot: dict[str, Any], showrunner_plan: dict[str, Any]) -> dict[str, Any]:
        status = build_nemo_status()
        prompt = build_director_prompt(snapshot, showrunner_plan)
        summary = self.memory.update(snapshot, headline=showrunner_plan.get("headline", ""))

        director_note = self._director_note(showrunner_plan, snapshot, summary)
        audience_prompt = str(showrunner_plan.get("audience_prompt") or "Watch closely.")
        validation = self.guardrails.validate(director_note, snapshot)
        prompt_validation = self.guardrails.validate(audience_prompt, snapshot)
        if not validation.ok:
            director_note = self._fallback_note(showrunner_plan, summary)
            validation = self.guardrails.validate(director_note, snapshot)
        if not prompt_validation.ok:
            audience_prompt = "Watch closely."
            prompt_validation = self.guardrails.validate(audience_prompt, snapshot)

        directive = NemoDirective(
            mode=status["mode"],
            scene=str(showrunner_plan.get("scene") or "world-wide"),
            speaker=str(showrunner_plan.get("speaker") or "Narrator"),
            director_note=validation.sanitized_text or director_note,
            audience_prompt=prompt_validation.sanitized_text or audience_prompt,
            guardrail_status="ok" if validation.ok and prompt_validation.ok else "blocked",
            guardrail_reason=validation.reason or prompt_validation.reason,
            summary=summary,
            cues=tuple(showrunner_plan.get("cues") or ()),
            rationale=tuple(showrunner_plan.get("reasoning") or ()),
            evaluation={},
        )
        payload = directive.to_dict()
        payload["prompt"] = prompt
        payload["status"] = status
        payload["memory"] = self.memory.to_dict()
        return payload

    def _director_note(
        self,
        showrunner_plan: dict[str, Any],
        snapshot: dict[str, Any],
        summary: str,
    ) -> str:
        headline = str(showrunner_plan.get("headline") or "The world keeps moving.")
        scene = str(showrunner_plan.get("scene") or "world-wide")
        speaker = str(showrunner_plan.get("speaker") or "Narrator")
        prompt = str(showrunner_plan.get("audience_prompt") or "Watch closely.")
        return (
            f"Scene {scene}: {headline} "
            f"Speaker {speaker}. "
            f"{prompt} "
            f"Summary: {summary}"
        )

    def _fallback_note(self, showrunner_plan: dict[str, Any], summary: str) -> str:
        return (
            f"Maintain scene {showrunner_plan.get('scene', 'world-wide')} "
            f"with speaker {showrunner_plan.get('speaker', 'Narrator')}. "
            f"Summary: {summary}"
        )


def build_nemo_directive(snapshot: dict[str, Any]) -> dict[str, Any]:
    try:
        from ..showrunner import build_showrunner_plan
    except ImportError:  # pragma: no cover - flat import path in tests
        from showrunner import build_showrunner_plan

    showrunner_plan = build_showrunner_plan(snapshot)
    director = NemoDirector()
    return director.compose(snapshot, showrunner_plan)
