"""
agent_scheduler.py — Per-agent logical clocks spread cognition load.

Each agent runs on its own CYCLE_S interval, staggered by soul_id hash
so 5000 agents don't pile into one sequential burst.
"""
import logging
import os
import time
from typing import Optional

log = logging.getLogger("god.scheduler")

CYCLE_S = int(os.getenv("AGENT_CYCLE_SECONDS", "30"))

_next_run: dict[str, float] = {}


def is_due(soul_id: str, now: Optional[float] = None) -> bool:
    t = now if now is not None else time.time()
    due_at = _next_run.get(soul_id, 0.0)
    return t >= due_at


def mark_scheduled(soul_id: str, now: Optional[float] = None, cycle_s: int = CYCLE_S):
    """Schedule next run after full cycle period."""
    t = now if now is not None else time.time()
    _next_run[soul_id] = t + cycle_s


def bootstrap_agent(soul_id: str, now: Optional[float] = None, cycle_s: int = CYCLE_S):
    """
    First-time stagger: spread initial runs across [0, cycle_s) by hash.
    """
    if soul_id in _next_run:
        return
    t = now if now is not None else time.time()
    slot = (hash(soul_id) % 10000) / 10000.0 * cycle_s
    _next_run[soul_id] = t + slot


def prune_dead(soul_ids: set[str]):
    dead = [k for k in _next_run if k not in soul_ids]
    for k in dead:
        del _next_run[k]


def due_count(all_soul_ids: list[str], now: Optional[float] = None) -> int:
    t = now if now is not None else time.time()
    return sum(1 for sid in all_soul_ids if is_due(sid, t))


def force_wake_at(soul_id: str, wake_at: float):
    """Override next run time (e.g. scheduled wake job)."""
    _next_run[soul_id] = float(wake_at)