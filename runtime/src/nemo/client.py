"""NeMo client facade for director generation and status."""

from __future__ import annotations

import os
from typing import Any

from .evals import score_directive


def build_nemo_status() -> dict[str, Any]:
    return {
        "enabled": os.getenv("NEMO_ENABLED", "true").lower() in ("1", "true", "yes"),
        "provider": os.getenv("NEMO_PROVIDER", "stub"),
        "mode": os.getenv("NEMO_MODE", "director"),
        "guardrails": os.getenv("NEMO_GUARDRAILS", "enabled"),
        "memory": os.getenv("NEMO_MEMORY", "ephemeral"),
    }


class NemoClient:
    """Minimal local-first client wrapper."""

    def __init__(self):
        self.provider = os.getenv("NEMO_PROVIDER", "stub")
        self.mode = os.getenv("NEMO_MODE", "director")

    def status(self) -> dict[str, Any]:
        return build_nemo_status()

    def build_directive(self, snapshot: dict[str, Any], showrunner_plan: dict[str, Any]) -> dict[str, Any]:
        try:
            from .director import NemoDirector
        except ImportError:  # pragma: no cover - flat import path in tests
            from director import NemoDirector

        director = NemoDirector()
        directive = director.compose(snapshot, showrunner_plan)
        directive["evaluation"] = score_directive(directive, snapshot)
        return directive
