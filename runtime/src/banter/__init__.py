"""Broadcast-Quality Banter Engine.

A modular, multi-layered dialogue system for producing sharp, character-driven
banter suitable for live Twitch broadcast.
"""

from .contract_types import ContractQualityScore, HardBan, HardBanVerdict
from .engine import BanterEngine
from .hard_bans import HardBanChecker
from .mode_resolver import ModeResolver
from .mode_types import BeatMode, BeatModePolicy, POLICY_TABLE
from .pacing_controller import PacingController
from .prompt_builder import PromptContractError, SacredPromptBuilder
from .quality_judge import QualityJudgeV2, evaluate_contract
from .silence_controller import SilenceController
from .theater_harness import TheaterHarness, ArchetypeRoster, SessionMetrics, HarnessResult
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
    # Prompt Builder (Section 1, 12)
    "SacredPromptBuilder",
    "PromptContractError",
    "QualityJudgeV2",
    "evaluate_contract",
    # Data models — contract-aligned (Section 7, 10)
    "ContractQualityScore",
    "HardBan",
    "HardBanVerdict",
    # Data models — legacy/shared
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
