"""Async portrait evolution queue for scars, softening, and prestige marks."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class EvolutionEvent:
    soul_id: str
    event_type: str
    triggered_at: float
    metadata: dict[str, Any] = field(default_factory=dict)


class EvolutionEngine:
    """Lightweight queue that records evolution events."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[EvolutionEvent] = asyncio.Queue()
        self._last_processed: dict[str, float] = {}
        self._pending: dict[str, list[EvolutionEvent]] = {}

    async def on_betrayal(self, soul_id: str, pair_state: Any) -> None:
        await self._enqueue(
            EvolutionEvent(
                soul_id=soul_id,
                event_type="betrayal_scar",
                triggered_at=time.time(),
                metadata={"tension_level": getattr(pair_state, "tension_level", 0)},
            )
        )

    async def on_reconciliation(self, soul_id: str, pair_state: Any) -> None:
        await self._enqueue(
            EvolutionEvent(
                soul_id=soul_id,
                event_type="reconciliation_soften",
                triggered_at=time.time(),
                metadata={"reconciliation_arc": getattr(pair_state, "reconciliation_arc", False)},
            )
        )

    async def on_survival_milestone(self, soul_id: str, rent_cycles: int) -> None:
        await self._enqueue(
            EvolutionEvent(
                soul_id=soul_id,
                event_type="prestige_mark",
                triggered_at=time.time(),
                metadata={"rent_cycles": rent_cycles},
            )
        )

    async def _enqueue(self, event: EvolutionEvent) -> None:
        last = self._last_processed.get(event.soul_id, 0.0)
        if time.time() - last < 3600:
            self._pending.setdefault(event.soul_id, []).append(event)
            return
        await self._queue.put(event)
        self._last_processed[event.soul_id] = time.time()

    async def _process_queue(self) -> None:
        while not self._queue.empty():
            await self._queue.get()

