"""
physics_gate.py — Law 0 pre-cycle enforcement.

Rent must gate cognition before agent code runs. Missed payments throttle
compute (50% → 10%) per Physics Laws v2 / doc 14.
"""
import logging
import os
from dataclasses import dataclass

log = logging.getLogger("god.physics")

MAX_MISSES = int(os.getenv("MAX_MISSED_PAYMENTS", "3"))


@dataclass(frozen=True)
class PhysicsGateResult:
    allow_cognition: bool
    compute_capacity: float   # 1.0 | 0.5 | 0.1 | 0.0
    throttle_level: str       # "none" | "throttled" | "severe" | "blocked"
    reason: str


def evaluate_physics_gate(agent: dict) -> PhysicsGateResult:
    """
    Evaluate whether an agent may run a full cognition cycle.
    Uses cumulative rent_miss_count from rent_payments aggregate.
    """
    misses = int(agent.get("rent_miss_count") or 0)

    if misses >= MAX_MISSES:
        return PhysicsGateResult(
            allow_cognition=False,
            compute_capacity=0.0,
            throttle_level="blocked",
            reason=f"rent_default_pending_death ({misses} misses)",
        )

    if misses == 2:
        return PhysicsGateResult(
            allow_cognition=True,
            compute_capacity=0.1,
            throttle_level="severe",
            reason="missed_rent_2_severe_throttle",
        )

    if misses == 1:
        return PhysicsGateResult(
            allow_cognition=True,
            compute_capacity=0.5,
            throttle_level="throttled",
            reason="missed_rent_1_throttle",
        )

    return PhysicsGateResult(
        allow_cognition=True,
        compute_capacity=1.0,
        throttle_level="none",
        reason="ok",
    )


def effective_llm(llm, gate: PhysicsGateResult, soul_id: str, cycle_tick: int):
    """
    Return the LLM client to use for this agent this cycle.
    Severe throttle → no LLM. Standard throttle → skip half of cycles.
    """
    if llm is None:
        return None
    if gate.compute_capacity <= 0.0:
        return None
    if gate.compute_capacity <= 0.1:
        return None
    if gate.compute_capacity <= 0.5:
        # Deterministic 50% duty cycle per agent
        if (hash(soul_id) + cycle_tick) % 2 == 0:
            return None
    return llm