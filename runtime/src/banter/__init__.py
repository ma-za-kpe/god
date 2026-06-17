"""Broadcast-Quality Banter Engine.

A modular, multi-layered dialogue system for producing sharp, character-driven
banter suitable for live Twitch broadcast.
"""

from .engine import BanterEngine
from .pacing_controller import PacingController
from .types import (
    MOVE_TYPES,
    BanterConfig,
    Beat,
    BeatResult,
    CircuitBreakerState,
    FallbackSelection,
    FallbackTemplate,
    InteractionRecord,
    ModelRouterError,
    MoveContext,
    MoveDistribution,
    PacingDecision,
    PairState,
    QualityJudgeError,
    QualityScore,
    RelationshipMemoryError,
    RepetitionVerdict,
    RouteDecision,
    SceneContextData,
    SessionState,
)

__all__ = [
    # Type literal
    "MOVE_TYPES",
    # Components
    "BanterEngine",
    "PacingController",
    # Data models
    "BanterConfig",
    "Beat",
    "BeatResult",
    "CircuitBreakerState",
    "FallbackSelection",
    "FallbackTemplate",
    "InteractionRecord",
    "MoveContext",
    "MoveDistribution",
    "PacingDecision",
    "PairState",
    "QualityScore",
    "RepetitionVerdict",
    "RouteDecision",
    "SceneContextData",
    "SessionState",
    # Exceptions
    "ModelRouterError",
    "QualityJudgeError",
    "RelationshipMemoryError",
]
