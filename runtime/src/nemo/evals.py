"""Evaluation helpers for stream-facing NeMo outputs."""

from __future__ import annotations

from typing import Any


def score_directive(directive: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    cues = directive.get("cues") or []
    stats = snapshot.get("stats") or {}
    score = 0
    if directive.get("guardrail_status") == "ok":
        score += 40
    if directive.get("scene"):
        score += 15
    if directive.get("speaker"):
        score += 10
    if directive.get("director_note"):
        score += 15
    if int(stats.get("living_count") or 0) > 0:
        score += 10
    if cues:
        score += min(10, len(cues) * 2)
    if stats.get("service_purchases_24h"):
        score += 5
    if stats.get("transfers_24h"):
        score += 5

    return {
        "score": min(score, 100),
        "cue_count": len(cues),
        "living_count": int(stats.get("living_count") or 0),
        "events_total": int(stats.get("events_total") or 0),
    }
