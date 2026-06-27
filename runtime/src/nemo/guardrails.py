"""Guardrails for stream-facing NeMo director output."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

try:  # pragma: no cover - runtime package import path
    from ..grounding import validate_grounded_text
except ImportError:  # pragma: no cover - tests import via flat path
    from grounding import validate_grounded_text


@dataclass(frozen=True)
class GuardrailResult:
    ok: bool
    reason: str = ""
    sanitized_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class NemoGuardrails:
    """Deterministic safety gate for public stream text."""

    def __init__(self, max_length: int = 240):
        self.max_length = max_length

    def build_state(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        agents = snapshot.get("agents") or []
        peers = [
            {"name": a.get("current_name"), "soul_id": a.get("soul_id")}
            for a in agents
            if a.get("current_name") and a.get("soul_id")
        ]
        stats = snapshot.get("stats") or {}
        return {
            "name": "NemoDirector",
            "archetype": "builder",
            "balance_usdc": float(stats.get("avg_balance") or 0),
            "rent_amount": 0.001,
            "peers": peers,
            "inbox": [],
        }

    def validate(self, text: str, snapshot: dict[str, Any]) -> GuardrailResult:
        if not text or not str(text).strip():
            return GuardrailResult(ok=False, reason="empty_text")

        text = str(text).strip()
        if len(text) > self.max_length:
            text = text[: self.max_length].rstrip()

        ok, reason = validate_grounded_text(text, self.build_state(snapshot))
        if not ok:
            return GuardrailResult(ok=False, reason=reason, sanitized_text=text)
        if any(token in text.lower() for token in ('action":', "send_message", "register_service")):
            return GuardrailResult(ok=False, reason="action_json_leak", sanitized_text=text)
        return GuardrailResult(ok=True, reason="", sanitized_text=text)

    def sanitize(self, text: str, snapshot: dict[str, Any]) -> str:
        result = self.validate(text, snapshot)
        return result.sanitized_text if result.ok else ""
