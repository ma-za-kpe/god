"""Beat mode types and policy constants for the Banter Engine contract.

Defines the BeatMode enum, BeatModePolicy frozen dataclass, and PromptBlock
frozen dataclass. The policy table constants encode the hard contract from
Section 5 and Section 12 of the requirements.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


# ---------------------------------------------------------------------------
# BeatMode Enum
# ---------------------------------------------------------------------------


class BeatMode(Enum):
    """The six operational modes of the banter engine beat pipeline.

    Mode resolution follows strict precedence:
    SILENCE → BACKCHANNEL → SNAP_BACK → CRACK → CHAOS → NORMAL
    """

    NORMAL = "normal"
    CHAOS = "chaos"
    CRACK = "crack"
    SNAP_BACK = "snap_back"
    BACKCHANNEL = "backchannel"
    SILENCE = "silence"


# ---------------------------------------------------------------------------
# BeatModePolicy Dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BeatModePolicy:
    """Policy contract for a given beat mode.

    Each mode has a fixed policy that determines quality thresholds,
    feature toggles, word count limits, and pacing bounds. These are
    immutable constants — the runtime does not modify them.
    """

    mode: BeatMode
    quality_threshold: int | None  # None for BACKCHANNEL/SILENCE
    refinement_allowed: bool
    anti_repetition_enabled: bool
    hard_bans_enabled: bool
    word_count_min: int
    word_count_max: int
    move_override: str | None  # e.g. "ESCALATE" for CHAOS
    pacing_min_s: float = 1.0
    pacing_max_s: float = 10.0


# ---------------------------------------------------------------------------
# PromptBlock Dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PromptBlock:
    """A single block in the structured prompt assembly pipeline.

    Each block is identified by a marker (e.g. "[MODE]"), contains the
    block text content (without the marker prefix), and enforces a
    token budget ceiling.
    """

    marker: str  # e.g. "[MODE]", "[ARCHETYPE]"
    text: str  # block content (without marker prefix)
    max_tokens: int  # token budget ceiling


# ---------------------------------------------------------------------------
# Policy Table Constants
# ---------------------------------------------------------------------------

NORMAL_POLICY = BeatModePolicy(
    mode=BeatMode.NORMAL,
    quality_threshold=9,
    refinement_allowed=True,
    anti_repetition_enabled=True,
    hard_bans_enabled=True,
    word_count_min=4,
    word_count_max=30,
    move_override=None,
    pacing_min_s=1.0,
    pacing_max_s=10.0,
)

CHAOS_POLICY = BeatModePolicy(
    mode=BeatMode.CHAOS,
    quality_threshold=6,
    refinement_allowed=False,
    anti_repetition_enabled=False,
    hard_bans_enabled=True,
    word_count_min=4,
    word_count_max=30,
    move_override="ESCALATE",  # 75% ESCALATE / 25% TAUNT resolved at runtime
    pacing_min_s=1.0,
    pacing_max_s=10.0,
)

CRACK_POLICY = BeatModePolicy(
    mode=BeatMode.CRACK,
    quality_threshold=5,
    refinement_allowed=False,
    anti_repetition_enabled=True,
    hard_bans_enabled=True,
    word_count_min=4,
    word_count_max=20,
    move_override=None,
    pacing_min_s=1.0,
    pacing_max_s=10.0,
)

SNAP_BACK_POLICY = BeatModePolicy(
    mode=BeatMode.SNAP_BACK,
    quality_threshold=8,
    refinement_allowed=True,
    anti_repetition_enabled=True,
    hard_bans_enabled=True,
    word_count_min=4,
    word_count_max=30,
    move_override=None,
    pacing_min_s=1.0,
    pacing_max_s=10.0,
)

BACKCHANNEL_POLICY = BeatModePolicy(
    mode=BeatMode.BACKCHANNEL,
    quality_threshold=None,
    refinement_allowed=False,
    anti_repetition_enabled=False,
    hard_bans_enabled=True,
    word_count_min=2,
    word_count_max=6,
    move_override=None,
    pacing_min_s=1.0,
    pacing_max_s=10.0,
)

SILENCE_POLICY = BeatModePolicy(
    mode=BeatMode.SILENCE,
    quality_threshold=None,
    refinement_allowed=False,
    anti_repetition_enabled=False,
    hard_bans_enabled=False,
    word_count_min=0,
    word_count_max=0,
    move_override=None,
    pacing_min_s=3.0,
    pacing_max_s=5.0,
)


# ---------------------------------------------------------------------------
# Policy Lookup
# ---------------------------------------------------------------------------

POLICY_TABLE: dict[BeatMode, BeatModePolicy] = {
    BeatMode.NORMAL: NORMAL_POLICY,
    BeatMode.CHAOS: CHAOS_POLICY,
    BeatMode.CRACK: CRACK_POLICY,
    BeatMode.SNAP_BACK: SNAP_BACK_POLICY,
    BeatMode.BACKCHANNEL: BACKCHANNEL_POLICY,
    BeatMode.SILENCE: SILENCE_POLICY,
}
