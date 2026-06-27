"""NeMo memory: lightweight summary state for the director layer."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class NemoMemory:
    """Minimal memory store for stream-aware summaries."""

    last_summary: str = ""
    last_event_ids: list[str] = field(default_factory=list)
    last_headline: str = ""

    def update(self, snapshot: dict[str, Any], headline: str = "") -> str:
        events = snapshot.get("events") or []
        top_events = [e for e in events[:3] if isinstance(e, dict)]
        pieces: list[str] = []
        for event in top_events:
            event_type = str(event.get("event_type") or "")
            narrative = str(
                event.get("narrative") or event.get("payload", {}).get("narrative") or ""
            )
            if narrative:
                pieces.append(narrative[:120])
            elif event_type:
                pieces.append(event_type)

        stats = snapshot.get("stats") or {}
        living = int(stats.get("living_count") or 0)
        transfers = int(stats.get("transfers_24h") or 0)
        purchases = int(stats.get("service_purchases_24h") or 0)

        summary_bits = [
            f"living={living}",
            f"events={int(stats.get('events_total') or 0)}",
            f"transfers_24h={transfers}",
            f"service_purchases_24h={purchases}",
        ]
        if headline:
            summary_bits.append(f"headline={headline[:96]}")
        if pieces:
            summary_bits.append("top=" + " | ".join(pieces[:3]))

        self.last_summary = "; ".join(summary_bits)
        self.last_event_ids = [
            str(event.get("event_id") or "") for event in top_events if event.get("event_id")
        ]
        self.last_headline = headline
        return self.last_summary

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
