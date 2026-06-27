"""Minimal async GPU job coordinator.

This is a foundation skeleton. It serializes declared GPU work and records
basic diagnostics; model-specific unload/preemption hooks are intentionally
left for the next implementation pass.
"""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass, field
from enum import IntEnum
from typing import Any, AsyncIterator


class JobPriority(IntEnum):
    LIVE_VOICE = 0
    LIVE_LLM = 1
    OBSERVER = 2
    REAL_TIME_EMBODIMENT = 3
    LTX_BACKGROUND = 4
    WAN_BACKGROUND = 5
    OFFLINE = 6


@dataclass
class GPUJobStats:
    current_job: str | None = None
    total_completed: int = 0
    total_cancelled: int = 0
    last_error: str = ""
    last_started_at: float = 0.0
    last_finished_at: float = 0.0
    wait_seconds_by_priority: dict[str, list[float]] = field(default_factory=dict)
    run_seconds_by_priority: dict[str, list[float]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["average_wait_seconds"] = {
            key: (sum(values) / len(values)) if values else 0.0
            for key, values in self.wait_seconds_by_priority.items()
        }
        payload["average_run_seconds"] = {
            key: (sum(values) / len(values)) if values else 0.0
            for key, values in self.run_seconds_by_priority.items()
        }
        return payload


class GPUJobQueue:
    """Serialize heavy GPU work and expose lightweight diagnostics."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._stats = GPUJobStats()

    @asynccontextmanager
    async def acquire(
        self, priority: JobPriority, *, job_name: str | None = None
    ) -> AsyncIterator[None]:
        requested_at = time.time()
        async with self._lock:
            started_at = time.time()
            priority_name = priority.name.lower()
            self._stats.wait_seconds_by_priority.setdefault(priority_name, []).append(
                started_at - requested_at
            )
            self._stats.current_job = job_name or priority_name
            self._stats.last_started_at = started_at
            try:
                yield
            except asyncio.CancelledError:
                self._stats.total_cancelled += 1
                raise
            except Exception as exc:
                self._stats.last_error = str(exc)
                raise
            finally:
                finished_at = time.time()
                self._stats.run_seconds_by_priority.setdefault(priority_name, []).append(
                    finished_at - started_at
                )
                self._stats.total_completed += 1
                self._stats.last_finished_at = finished_at
                self._stats.current_job = None

    def diagnostics(self) -> dict[str, Any]:
        return self._stats.to_dict()


_GPU_JOB_QUEUE = GPUJobQueue()


def get_gpu_job_queue() -> GPUJobQueue:
    return _GPU_JOB_QUEUE
