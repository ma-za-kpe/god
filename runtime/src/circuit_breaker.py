"""
circuit_breaker.py — Per-agent rate limits (doc 07 circuit breakers).

Tripped breakers pause actions, not life. Repeated trips increase cooldown.
"""

import logging
import os
import time
from dataclasses import dataclass, field

log = logging.getLogger("god.breaker")

MAX_ACTIONS_PER_HOUR = int(os.getenv("MAX_ACTIONS_PER_HOUR", "60"))
MAX_MESSAGES_PER_HOUR = int(os.getenv("MAX_MESSAGES_PER_HOUR", "30"))
MAX_LLM_CALLS_PER_HOUR = int(os.getenv("MAX_LLM_CALLS_PER_HOUR", "180"))
BREAKER_COOLDOWN_S = int(os.getenv("BREAKER_COOLDOWN_S", "120"))


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


# Cardano risk extension (gap4 / 09): losing streaks from mock (or real) P&L demote/pause cardano tools.
# "Teaching pain" (extreme slippage/regime in OU) + this = agents learn sizing/buffers via failures (not crashes).
# Call from agent_runner after cardano_* if pnl < 0.
CARDANO_LOSS_STREAK_TRIP = 3


def record_cardano_pnl(soul_id: str, pnl: float) -> BreakerVerdict:
    """Track cardano-specific loss streaks. Negative pnl increments; positive resets. Trips on streak -> pause trading actions."""
    c = _get(soul_id)
    # reuse trips for streak (or could add c.cardano_streak)
    if pnl < -0.0001:
        c.trips += 1
        if c.trips >= CARDANO_LOSS_STREAK_TRIP:
            c.paused_until = time.time() + (
                BREAKER_COOLDOWN_S * 3
            )  # harsher for repeated cardano losses
            log.warning(f"Breaker CARDANO LOSS STREAK TRIP {soul_id[:8]} (streak~{c.trips})")
            return BreakerVerdict(False, "cardano_losing_streak")
    else:
        c.trips = max(0, c.trips - 1)
    return BreakerVerdict(True)
