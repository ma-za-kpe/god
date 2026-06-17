"""Soul engine data models for the Elder Voice Soul Engine.

All typed dataclasses, schema validation constants, and validation functions
used across the soul engine modules (Voice_DNA, Emotional_Primer,
Callback_Registry, Subtlety_Director) are defined here.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SoulEngineConfig:
    """Configuration for the Elder Voice Soul Engine.

    Controls feature flags and token budgets for all soul engine modules.
    When ``enabled`` is False, all soul modules are skipped and the pipeline
    behaves identically to the pre-soul-engine version.
    """

    enabled: bool = True
    voice_dna_enabled: bool = True
    emotional_primer_enabled: bool = True
    callback_registry_enabled: bool = True
    subtlety_director_enabled: bool = True
    max_total_tokens: int = 800
    voice_dna_token_budget: int = 250
    emotional_primer_token_budget: int = 200
    callback_token_budget: int = 200
    subtlety_token_budget: int = 150


# ---------------------------------------------------------------------------
# Schema validation constants
# ---------------------------------------------------------------------------

VOICE_DNA_SCHEMA: dict[str, dict[str, int]] = {
    "sentence_structures": {"min_count": 3},
    "verbal_tics": {"min_count": 2},
    "rhythm_patterns": {"min_count": 1},
    "micro_phrases": {"min_count": 4},
    "rhetorical_devices": {"min_count": 2},
    "opening_patterns": {"min_count": 2},
    "closing_patterns": {"min_count": 2},
}


# ---------------------------------------------------------------------------
# Voice DNA types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RhythmPattern:
    """Quantified rhythm constraint for an archetype's speech cadence."""

    name: str
    clause_count_range: tuple[int, int]
    word_count_per_clause_range: tuple[int, int]
    pause_placement: str  # "before_final" | "between_clauses" | "front_loaded"


@dataclass(frozen=True)
class VoiceDNAProfile:
    """Complete linguistic fingerprint for an archetype."""

    archetype: str
    sentence_structures: list[str]  # min 3
    verbal_tics: list[str]  # min 2
    rhythm_patterns: list[RhythmPattern]  # min 1
    micro_phrases: list[str]  # min 4
    rhetorical_devices: list[str]  # min 2
    opening_patterns: list[str]  # min 2
    closing_patterns: list[str]  # min 2
    system_prompt: str = ""  # Nuclear worldview prompt (T2.1) — overrides checklist injection


# ---------------------------------------------------------------------------
# Callback Registry types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CallbackSurface:
    """A surfaced callback ready for prompt injection."""

    original_line: str
    original_context: str
    suggested_framing: str  # "direct_quote" | "paraphrase" | "inversion" | "escalation"
    summary: str
    beat_number_used: int


@dataclass(frozen=True)
class SoreSpot:
    """A known vulnerability for targeted provocation."""

    elder_name: str
    topic: str
    trigger_phrase: str | None
    tension_delta: int


@dataclass(frozen=True)
class MemorableMoment:
    """A stored high-scoring line for future callback."""

    speaker: str
    target: str
    line: str
    move: str
    arc_theme: str
    valence: str
    summary: str
    score: int
    beat_number: int
    created_at: float


@dataclass
class CallbackUsageTracker:
    """Tracks callback usage for rate limiting within a session."""

    last_used_beat: dict[str, int] = field(default_factory=dict)  # callback_id → beat
    pair_session_count: dict[str, int] = field(
        default_factory=dict
    )  # pair_id → count


@dataclass
class WriteBuffer:
    """In-memory buffer for DB writes when database is unavailable."""

    entries: deque[MemorableMoment] = field(
        default_factory=lambda: deque(maxlen=20)
    )

    def add(self, moment: MemorableMoment) -> None:
        """Add to buffer. If full (20), oldest entry is dropped."""
        self.entries.append(moment)  # deque(maxlen=20) handles eviction


# ---------------------------------------------------------------------------
# Subtlety Director types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SubtextInstruction:
    """Instruction for layered meaning generation."""

    surface_meaning: str
    implied_meaning: str
    technique: str  # one of SubtletyDirector.TECHNIQUES
    context_hint: str


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_voice_dna_profile(data: dict) -> tuple[bool, list[str]]:
    """Validate a VoiceDNA profile dict against schema.

    Returns (is_valid, list_of_violations). An empty violations list
    indicates a valid profile.
    """
    violations: list[str] = []

    for field_name, constraints in VOICE_DNA_SCHEMA.items():
        min_count = constraints["min_count"]

        if field_name not in data:
            violations.append(
                f"Missing required field '{field_name}'"
            )
        elif not isinstance(data[field_name], list):
            violations.append(
                f"Field '{field_name}' must be a list, got {type(data[field_name]).__name__}"
            )
        elif len(data[field_name]) < min_count:
            violations.append(
                f"Field '{field_name}' requires at least {min_count} entries, "
                f"got {len(data[field_name])}"
            )

    return (len(violations) == 0, violations)
