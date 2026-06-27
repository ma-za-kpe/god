"""Priority GPU job coordinator for live and background workloads."""

from __future__ import annotations

import asyncio
import inspect
import time
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass, field
from enum import IntEnum
from typing import Any, AsyncIterator, Awaitable, Callable


class JobPriority(IntEnum):
    LIVE_VOICE = 0
    LIVE_LLM = 1
    OBSERVER_RENDER = 2
    OBSERVER = 2
    REAL_TIME_EMBODIMENT = 3
    LTX_BACKGROUND = 4
    WAN_BACKGROUND = 5
    OFFLINE_HIGHLIGHT = 6
    OFFLINE = 6


BACKGROUND_PRIORITIES = {
    JobPriority.LTX_BACKGROUND,
    JobPriority.WAN_BACKGROUND,
    JobPriority.OFFLINE_HIGHLIGHT,
}


class GPUJobRejected(RuntimeError):
    """Raised when a job is rejected by the active GPU policy."""


@dataclass
class GPUJobLease:
    """Lease yielded to GPU work while it holds the queue slot."""

    job_id: int
    priority: JobPriority
    job_name: str
    requested_at: float
    started_at: float = 0.0
    finished_at: float = 0.0
    cancellation_requested: bool = False
    cancel_reason: str = ""

    @property
    def priority_name(self) -> str:
        return self.priority.name.lower()

    @property
    def is_background(self) -> bool:
        return self.priority in BACKGROUND_PRIORITIES

    def request_cancel(self, reason: str) -> None:
        if not self.cancellation_requested:
            self.cancellation_requested = True
            self.cancel_reason = reason

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "priority": self.priority_name,
            "job_name": self.job_name,
            "requested_at": self.requested_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "cancellation_requested": self.cancellation_requested,
            "cancel_reason": self.cancel_reason,
        }


GPUQueueHook = Callable[[GPUJobLease], Awaitable[None] | None]


@dataclass
class GPUQueueHooks:
    """Optional adapter hooks for model unload/reload behavior."""

    before_start: GPUQueueHook | None = None
    after_finish: GPUQueueHook | None = None
    on_cancel_requested: GPUQueueHook | None = None


@dataclass
class GPUJobStats:
    current_job: str | None = None
    total_completed: int = 0
    total_cancelled: int = 0
    total_failed: int = 0
    total_rejected: int = 0
    total_preemptions_requested: int = 0
    last_error: str = ""
    last_rejection: str = ""
    last_cancel_reason: str = ""
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


@dataclass
class _PendingRequest:
    sequence: int
    lease: GPUJobLease


class GPUJobQueue:
    """Serialize heavy GPU work with strict priority and diagnostics."""

    def __init__(
        self,
        *,
        max_concurrent: int = 1,
        background_jobs_allowed: bool = True,
        hooks: GPUQueueHooks | None = None,
    ) -> None:
        self.max_concurrent = max(1, max_concurrent)
        self._background_jobs_allowed = background_jobs_allowed
        self._hooks = hooks or GPUQueueHooks()
        self._condition = asyncio.Condition()
        self._stats = GPUJobStats()
        self._pending: list[_PendingRequest] = []
        self._active: dict[int, GPUJobLease] = {}
        self._sequence = 0

    @asynccontextmanager
    async def acquire(
        self, priority: JobPriority, *, job_name: str | None = None
    ) -> AsyncIterator[GPUJobLease]:
        lease = await self._start(priority, job_name=job_name)
        completed = False
        cancelled = False
        error: BaseException | None = None
        try:
            yield lease
            completed = True
        except asyncio.CancelledError as exc:
            cancelled = True
            error = exc
            raise
        except BaseException as exc:
            error = exc
            raise
        finally:
            await self._finish(lease, completed=completed, cancelled=cancelled, error=error)

    def set_background_jobs_allowed(self, allowed: bool, *, reason: str = "") -> None:
        self._background_jobs_allowed = allowed
        if not allowed:
            for lease in list(self._active.values()):
                if lease.is_background:
                    self._request_cancel(lease, reason or "background_jobs_disabled")
        self._notify_waiters()

    def enter_live_mode(self, *, reason: str = "live_mode") -> None:
        self.set_background_jobs_allowed(False, reason=reason)

    def exit_live_mode(self) -> None:
        self.set_background_jobs_allowed(True)

    def diagnostics(self) -> dict[str, Any]:
        active_jobs = [lease.to_dict() for lease in self._active.values()]
        pending_jobs = [pending.lease.to_dict() for pending in self._sorted_pending()]
        payload = self._stats.to_dict()
        payload.update(
            {
                "max_concurrent": self.max_concurrent,
                "background_jobs_allowed": self._background_jobs_allowed,
                "active_jobs": active_jobs,
                "pending_jobs": pending_jobs,
                "queue_depth": len(self._pending),
                "queue_depth_by_priority": self._queue_depth_by_priority(),
                "current_job": active_jobs[0]["job_name"] if active_jobs else None,
            }
        )
        return payload

    async def _start(self, priority: JobPriority, *, job_name: str | None) -> GPUJobLease:
        priority = JobPriority(priority)
        async with self._condition:
            if self._is_rejected_background(priority):
                self._reject_locked(priority, "background_jobs_disabled")
            self._sequence += 1
            lease = GPUJobLease(
                job_id=self._sequence,
                priority=priority,
                job_name=job_name or priority.name.lower(),
                requested_at=time.time(),
            )
            pending = _PendingRequest(sequence=self._sequence, lease=lease)
            self._pending.append(pending)
            if priority == JobPriority.LIVE_VOICE:
                self._request_background_cancellations_locked("live_voice_requested")
            self._condition.notify_all()

            try:
                while not self._can_start_locked(pending):
                    if self._is_rejected_background(priority):
                        self._pending.remove(pending)
                        self._reject_locked(priority, "background_jobs_disabled")
                    await self._condition.wait()
            except BaseException:
                if pending in self._pending:
                    self._pending.remove(pending)
                    self._condition.notify_all()
                raise

            self._pending.remove(pending)
            lease.started_at = time.time()
            self._active[lease.job_id] = lease
            self._record_wait_locked(lease)
            self._stats.current_job = lease.job_name
            self._stats.last_started_at = lease.started_at
            self._condition.notify_all()

        try:
            await self._call_hook(self._hooks.before_start, lease)
        except BaseException as exc:
            await self._finish(lease, completed=False, cancelled=False, error=exc)
            raise
        return lease

    async def _finish(
        self,
        lease: GPUJobLease,
        *,
        completed: bool,
        cancelled: bool,
        error: BaseException | None,
    ) -> None:
        lease.finished_at = time.time()
        async with self._condition:
            self._active.pop(lease.job_id, None)
            self._record_run_locked(lease)
            if completed:
                self._stats.total_completed += 1
            elif cancelled:
                self._stats.total_cancelled += 1
                self._stats.last_cancel_reason = lease.cancel_reason or "task_cancelled"
            elif error is not None:
                self._stats.total_failed += 1
                self._stats.last_error = str(error) or error.__class__.__name__
            self._stats.last_finished_at = lease.finished_at
            self._stats.current_job = (
                next(iter(self._active.values())).job_name if self._active else None
            )
            self._condition.notify_all()
        try:
            await self._call_hook(self._hooks.after_finish, lease)
        except Exception as exc:
            self._stats.last_error = str(exc) or exc.__class__.__name__

    def _can_start_locked(self, pending: _PendingRequest) -> bool:
        if len(self._active) >= self.max_concurrent:
            return False
        return self._sorted_pending()[0] is pending

    def _sorted_pending(self) -> list[_PendingRequest]:
        return sorted(self._pending, key=lambda item: (int(item.lease.priority), item.sequence))

    def _queue_depth_by_priority(self) -> dict[str, int]:
        depths: dict[str, int] = {}
        for pending in self._pending:
            depths[pending.lease.priority_name] = depths.get(pending.lease.priority_name, 0) + 1
        return depths

    def _is_rejected_background(self, priority: JobPriority) -> bool:
        return priority in BACKGROUND_PRIORITIES and not self._background_jobs_allowed

    def _reject_locked(self, priority: JobPriority, reason: str) -> None:
        self._stats.total_rejected += 1
        self._stats.last_rejection = f"{priority.name.lower()}:{reason}"
        raise GPUJobRejected(self._stats.last_rejection)

    def _request_background_cancellations_locked(self, reason: str) -> None:
        for lease in list(self._active.values()):
            if lease.is_background:
                self._request_cancel(lease, reason)

    def _request_cancel(self, lease: GPUJobLease, reason: str) -> None:
        if lease.cancellation_requested:
            return
        lease.request_cancel(reason)
        self._stats.total_preemptions_requested += 1
        self._stats.last_cancel_reason = reason
        self._schedule_hook(self._hooks.on_cancel_requested, lease)

    def _record_wait_locked(self, lease: GPUJobLease) -> None:
        self._stats.wait_seconds_by_priority.setdefault(lease.priority_name, []).append(
            lease.started_at - lease.requested_at
        )

    def _record_run_locked(self, lease: GPUJobLease) -> None:
        self._stats.run_seconds_by_priority.setdefault(lease.priority_name, []).append(
            max(0.0, lease.finished_at - lease.started_at)
        )

    def _notify_waiters(self) -> None:
        async def _notify() -> None:
            async with self._condition:
                self._condition.notify_all()

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(_notify())

    def _schedule_hook(self, hook: GPUQueueHook | None, lease: GPUJobLease) -> None:
        if hook is None:
            return

        async def _runner() -> None:
            try:
                await self._call_hook(hook, lease)
            except Exception as exc:
                self._stats.last_error = str(exc) or exc.__class__.__name__

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(_runner())

    async def _call_hook(self, hook: GPUQueueHook | None, lease: GPUJobLease) -> None:
        if hook is None:
            return
        result = hook(lease)
        if inspect.isawaitable(result):
            await result


_GPU_JOB_QUEUE = GPUJobQueue()


def get_gpu_job_queue() -> GPUJobQueue:
    return _GPU_JOB_QUEUE
