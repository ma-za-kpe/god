"""Shared data models for the Broadcast-Quality Banter Engine.

All typed dataclasses and custom exceptions used across banter pipeline
components are defined here to avoid circular imports and provide a single
source of truth.
"""

from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field
from typing import Literal


# ---------------------------------------------------------------------------
# Move type literal
# ---------------------------------------------------------------------------

MOVE_TYPES = Literal[
    "COUNTER",
    "ESCALATE",
    "DEFLECT",
    "TAUNT",
    "QUESTION",
    "PIVOT",
    "CONCEDE",
    "CALLBACK",
    "CRACK",
]


# ---------------------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------------------


class QualityJudgeError(Exception):
    """Raised when the Quality Judge fails to evaluate a candidate line.

    This includes timeouts (>2s), malformed score output, and any
    unexpected exceptions during scoring. The pipeline handles this
    by applying the word-count acceptance rule (4-30 words = accept,
    otherwise fallback).
    """

    pass


class RelationshipMemoryError(Exception):
    """Raised when the Relationship Memory store is unavailable.

    This includes DB connection failures, slow queries exceeding
    the 500ms budget, and corrupted pair state. The pipeline handles
    this by falling back to the current conversation thread (6-turn window).
    """

    pass


class ModelRouterError(Exception):
    """Raised when the Model Router cannot complete a generation request.

    This includes remote timeouts (>4s), connection errors, invalid
    responses, and circuit breaker activation. The pipeline handles
    this by falling back to the local model or Fallback_Pool.
    """

    pass


# ---------------------------------------------------------------------------
# Quality Judge types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class QualityScore:
    """Multi-dimensional quality evaluation of a candidate banter line.

    Each dimension is scored on a 0-3 integer scale:
        0 = absent, 1 = weak, 2 = present, 3 = strong.
    """

    sharpness: int  # conciseness, punch, rhetorical clarity
    emotional_texture: int  # vulnerability, tension, warmth
    rhythm: int  # cadence, clause variety, pause points
    thematic_relevance: int  # connection to arc_theme
    shareability: int  # quotability, clip-worthiness

    @property
    def total(self) -> int:
        """Combined score across all dimensions (0-15)."""
        return (
            self.sharpness
            + self.emotional_texture
            + self.rhythm
            + self.thematic_relevance
            + self.shareability
        )

    @property
    def weak_dimensions(self) -> list[tuple[str, int]]:
        """Dimensions scoring 1 or below, for refinement feedback."""
        return [(name, val) for name, val in self.as_dict().items() if val <= 1]

    def as_dict(self) -> dict[str, int]:
        """Return all dimension scores as a dictionary."""
        return {
            "sharpness": self.sharpness,
            "emotional_texture": self.emotional_texture,
            "rhythm": self.rhythm,
            "thematic_relevance": self.thematic_relevance,
            "shareability": self.shareability,
        }


# ---------------------------------------------------------------------------
# Move Selector types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MoveDistribution:
    """Probability distribution over conversational move types.

    Invariants:
    - Sum of probabilities == 1.0 (±0.01)
    - Signature move <= 0.40
    - Every non-signature move >= 0.02
    """

    probabilities: dict[str, float]  # move_type -> probability (0.0-1.0)

    def sample(self) -> str:
        """Weighted random selection from the distribution."""
        moves = list(self.probabilities.keys())
        weights = list(self.probabilities.values())
        return random.choices(moves, weights=weights, k=1)[0]


@dataclass(frozen=True)
class MoveContext:
    """All inputs needed for move selection."""

    archetype: str
    last_3_moves: list[str]
    tension_level: int | None  # 0-10 or None if unavailable
    momentum: str | None  # "escalating" | "cooling" | "stalemate" | "shifting" | None
    arc_theme: str
    fear_keywords: list[str]
    consecutive_counters_in_pair: int
    consecutive_low_scores: int  # for "losing the room" detection


# ---------------------------------------------------------------------------
# Fallback Pool types
# ---------------------------------------------------------------------------


@dataclass
class FallbackTemplate:
    """A single curated fallback line template."""

    template_id: str
    archetype: str
    move_type: str
    template: str  # may contain {opponent}, {theme}, {callback}
    base_weight: float = 1.0


@dataclass
class FallbackSelection:
    """Result of selecting and substituting a fallback template."""

    text: str  # fully substituted, ready for broadcast
    template_id: str
    archetype: str
    move_type: str


# ---------------------------------------------------------------------------
# Relationship Memory types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InteractionRecord:
    """A single recorded interaction between two Elders."""

    timestamp: float
    elder_a: str
    elder_b: str
    move_used: str
    emotional_valence: Literal["positive", "negative", "neutral"]
    betrayal: bool = False
    alliance: bool = False
    concession: bool = False


@dataclass
class PairState:
    """Current relationship state between two Elders."""

    tension_level: int  # clamped [0, 10]
    last_interaction_ts: float
    reconciliation_arc: bool = False
    reconciliation_remaining: int = 0  # interactions left with context injection
    peak_tension_summary: str = ""


# ---------------------------------------------------------------------------
# Scene Context types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Beat:
    """A single unit of dialogue delivery — one agent's turn to speak."""

    speaker: str
    content: str
    move: str
    quality_score: int
    energy_label: Literal["hot", "warm", "flat", "dead"]
    timestamp: float


@dataclass
class SceneContextData:
    """Shared state for the current broadcast scene round."""

    recent_beats: deque[Beat] = field(default_factory=lambda: deque(maxlen=3))
    has_the_room: str | None = None  # elder with highest avg score (min 2 beats)
    landed_hit: Beat | None = None  # current landed hit (score > 12)
    landed_hit_remaining: int = 0  # speakers who still need to acknowledge it
    scene_energy: Literal["heated", "cooling", "neutral"] = "neutral"


# ---------------------------------------------------------------------------
# Model Router types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RouteDecision:
    """Routing decision for a generation request."""

    target: Literal["remote", "local"]
    quality_threshold: int  # 8 for remote, 10 for local fallback
    timeout_s: float


@dataclass
class CircuitBreakerState:
    """State for the model router circuit breaker."""

    window_start: float = 0.0
    request_count: int = 0
    error_count: int = 0
    tripped: bool = False
    tripped_at: float = 0.0
    cooldown_s: float = 60.0
    window_s: float = 300.0  # 5 minutes
    error_threshold: float = 0.20
    min_requests: int = 5


# ---------------------------------------------------------------------------
# Pacing Controller types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PacingDecision:
    """Computed pacing for a beat delivery."""

    inter_beat_delay_s: float  # [1.0, 10.0] always
    pre_delivery_pause_s: float  # 2.0 for CONCEDE, 0.0 otherwise
    rule_applied: str  # which rule won


# ---------------------------------------------------------------------------
# Anti-Repetition types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RepetitionVerdict:
    """Result of anti-repetition check on a candidate line."""

    accepted: bool
    rejection_reason: str | None = None  # "3gram_overlap" | "opener_reuse" | None
    overlap_ratio: float | None = None  # if 3-gram check was applied


# ---------------------------------------------------------------------------
# Pipeline / Engine types
# ---------------------------------------------------------------------------


@dataclass
class BeatResult:
    """Complete result of the banter generation pipeline for a single beat."""

    line: str  # final broadcast-ready text
    move: str  # move type used
    quality_score: int  # total quality score (0-15) or 0 if scored via fallback
    delay_s: float  # computed inter-beat pacing delay
    pre_pause_s: float  # CONCEDE pause (0.0 or 2.0)
    source: Literal["remote", "local", "fallback"]  # origin of the line
    template_id: str | None = None  # fallback template id if source == "fallback"
    metadata: dict = field(default_factory=dict)  # additional context for logging


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BanterConfig:
    """Global configuration for the banter engine."""

    quality_threshold: int = 8
    quality_threshold_local: int = 10
    max_refinement_rounds: int = 2
    max_rejection_rounds: int = 3
    remote_timeout_s: float = 4.0
    quality_judge_timeout_s: float = 2.0
    circuit_breaker_window_s: float = 300.0
    circuit_breaker_cooldown_s: float = 60.0
    circuit_breaker_error_threshold: float = 0.20
    circuit_breaker_min_requests: int = 5
    trigram_overlap_threshold: float = 0.60
    history_window: int = 20
    opener_window: int = 8
    min_fallback_per_archetype: int = 12
    min_fallback_per_move: int = 2
    session_timeout_s: float = 300.0  # 5 min gap = new session


# ---------------------------------------------------------------------------
# Session State
# ---------------------------------------------------------------------------


@dataclass
class SessionState:
    """In-memory session state, reset on new broadcast stream."""

    session_id: str = ""
    started_at: float = 0.0
    used_template_ids: set[str] = field(default_factory=set)  # 80% weight reduction
    recent_beat_template_ids: deque[str] = field(
        default_factory=lambda: deque(maxlen=10)
    )  # last 10 beats, 50% reduction
    per_elder_history: dict[str, deque[str]] = field(
        default_factory=dict
    )  # elder -> deque of last 20 lines
    per_elder_openers: dict[str, deque[str]] = field(
        default_factory=dict
    )  # elder -> deque of last 8 openers
    per_elder_registers: dict[str, deque[str]] = field(
        default_factory=dict
    )  # elder -> deque of last N registers
