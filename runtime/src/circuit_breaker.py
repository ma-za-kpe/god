"""
circuit_breaker.py — Per-agent rate limits (doc 07 circuit breakers).

Tripped breakers pause actions, not life. Repeated trips increase cooldown.
"""

import logging
import os
import time
from dataclasses import dataclass, field

log = logging.getLogger("god.breaker")

MAX_ACTIONS_PER_HOUR = int(os.getenv("MAX_ACTIONS_PER_HOUR", "120"))
MAX_MESSAGES_PER_HOUR = int(os.getenv("MAX_MESSAGES_PER_HOUR", "120"))
MAX_LLM_CALLS_PER_HOUR = int(os.getenv("MAX_LLM_CALLS_PER_HOUR", "360"))
BREAKER_COOLDOWN_S = int(os.getenv("BREAKER_COOLDOWN_S", "45"))


@dataclass
class _AgentCounters:
    window_start: float = field(default_factory=time.time)
    actions: int = 0
    messages: int = 0
    llm_calls: int = 0
    trips: int = 0
    paused_until: float = 0.0


_counters: dict[str, _AgentCounters] = {}


def _get(soul_id: str) -> _AgentCounters:
    now = time.time()
    c = _counters.setdefault(soul_id, _AgentCounters())
    if now - c.window_start > 3600:
        c.window_start = now
        c.actions = c.messages = c.llm_calls = 0
    return c


@dataclass(frozen=True)
class BreakerVerdict:
    allowed: bool
    reason: str = ""


def check_agent(soul_id: str) -> BreakerVerdict:
    c = _get(soul_id)
    now = time.time()
    if now < c.paused_until:
        return BreakerVerdict(False, f"circuit_breaker_cooldown ({int(c.paused_until - now)}s)")
    return BreakerVerdict(True)


def record_action(soul_id: str) -> BreakerVerdict:
    c = _get(soul_id)
    verdict = check_agent(soul_id)
    if not verdict.allowed:
        return verdict
    c.actions += 1
    if c.actions > MAX_ACTIONS_PER_HOUR:
        c.trips += 1
        c.paused_until = time.time() + BREAKER_COOLDOWN_S * c.trips
        log.warning(f"Breaker TRIP {soul_id[:8]}: actions/hour exceeded")
        return BreakerVerdict(False, "max_actions_per_hour")
    return BreakerVerdict(True)


def record_message(soul_id: str) -> BreakerVerdict:
    c = _get(soul_id)
    verdict = check_agent(soul_id)
    if not verdict.allowed:
        return verdict
    c.messages += 1
    if c.messages > MAX_MESSAGES_PER_HOUR:
        c.trips += 1
        c.paused_until = time.time() + BREAKER_COOLDOWN_S * c.trips
        log.warning(f"Breaker TRIP {soul_id[:8]}: messages/hour exceeded")
        return BreakerVerdict(False, "max_messages_per_hour")
    return BreakerVerdict(True)


def record_llm_call(soul_id: str) -> BreakerVerdict:
    c = _get(soul_id)
    verdict = check_agent(soul_id)
    if not verdict.allowed:
        return verdict
    c.llm_calls += 1
    if c.llm_calls > MAX_LLM_CALLS_PER_HOUR:
        c.trips += 1
        c.paused_until = time.time() + BREAKER_COOLDOWN_S * c.trips
        log.warning(f"Breaker TRIP {soul_id[:8]}: llm_calls/hour exceeded")
        return BreakerVerdict(False, "max_llm_calls_per_hour")
    return BreakerVerdict(True)
