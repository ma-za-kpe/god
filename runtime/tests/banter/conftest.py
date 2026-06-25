"""Shared fixtures and Hypothesis strategies for banter engine tests.

Provides reusable strategies that generate realistic test data matching
the domain constraints defined in the design document.
"""

import os
import sys
import string
import time

# ---------------------------------------------------------------------------
# Path setup: add src/ to sys.path so `from banter.<module> import ...`
# resolves to src/banter/. Works both locally and in the Docker container.
# ---------------------------------------------------------------------------
_src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
for _p in (_src_path, "/app/src"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest
from hypothesis import strategies as st

from banter.types import (
    BanterConfig,
    Beat,
    FallbackTemplate,
    InteractionRecord,
    MoveContext,
    PairState,
    QualityScore,
)

# ---------------------------------------------------------------------------
# Domain constants
# ---------------------------------------------------------------------------

ARCHETYPES = [
    "parasite",
    "prophet",
    "trickster",
    "sovereign",
    "martyr",
    "shadow",
    "herald",
    "keeper",
]

MOVE_TYPES = [
    "COUNTER",
    "ESCALATE",
    "DEFLECT",
    "TAUNT",
    "QUESTION",
    "PIVOT",
    "CONCEDE",
    "CALLBACK",
]

# Subset of move types used in fallback pool (excludes CONCEDE and CALLBACK)
FALLBACK_MOVE_TYPES = ["COUNTER", "ESCALATE", "DEFLECT", "TAUNT", "QUESTION", "PIVOT"]

ENERGY_LABELS = ["hot", "warm", "flat", "dead"]

SCENE_ENERGY_LABELS = ["heated", "cooling", "neutral"]

EMOTIONAL_REGISTERS = ["vulnerable", "aggressive", "sardonic", "measured", "playful"]

EMOTIONAL_VALENCES = ["positive", "negative", "neutral"]

MOMENTUM_VALUES = ["escalating", "cooling", "stalemate", "shifting"]


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------


@st.composite
def st_candidate_line(draw: st.DrawFn) -> str:
    """Generate a candidate banter line.

    Produces strings ranging from empty to very long (up to 1000 words),
    including edge cases like single characters and lines with template tokens.
    """
    strategy = draw(
        st.one_of(
            # Empty string
            st.just(""),
            # Single character
            st.text(min_size=1, max_size=1, alphabet=string.ascii_letters),
            # Short lines (1-5 words)
            st.lists(
                st.text(
                    min_size=1,
                    max_size=12,
                    alphabet=st.sampled_from(string.ascii_letters + " "),
                ),
                min_size=1,
                max_size=5,
            ).map(lambda words: " ".join(w.strip() for w in words if w.strip())),
            # Normal lines (6-100 words) — most realistic banter
            st.lists(
                st.text(
                    min_size=2,
                    max_size=10,
                    alphabet=st.sampled_from(string.ascii_lowercase),
                ),
                min_size=6,
                max_size=100,
            ).map(lambda words: " ".join(words) + "."),
            # Long lines (101-1000 words)
            st.lists(
                st.text(
                    min_size=2,
                    max_size=8,
                    alphabet=st.sampled_from(string.ascii_lowercase),
                ),
                min_size=101,
                max_size=1000,
            ).map(lambda words: " ".join(words) + "."),
            # Lines with template-like tokens
            st.sampled_from(
                [
                    "You think {opponent} cares about that?",
                    "The {theme} cuts deeper than you know.",
                    "Remember when you said {callback}? Yeah.",
                    "No placeholders here, just truth.",
                    "{opponent} should worry about {theme} more.",
                ]
            ),
        )
    )
    return strategy


@st.composite
def st_archetype(draw: st.DrawFn) -> str:
    """Generate a valid archetype name.

    One of the 8 archetypes: parasite, prophet, trickster, sovereign,
    martyr, shadow, herald, keeper.
    """
    return draw(st.sampled_from(ARCHETYPES))


@st.composite
def st_move(draw: st.DrawFn) -> str:
    """Generate a valid move type.

    One of: COUNTER, ESCALATE, DEFLECT, TAUNT, QUESTION, PIVOT, CONCEDE, CALLBACK.
    """
    return draw(st.sampled_from(MOVE_TYPES))


@st.composite
def st_move_sequence(draw: st.DrawFn, min_size: int = 0, max_size: int = 20) -> list[str]:
    """Generate a sequence of moves (e.g., for conversation history)."""
    return draw(st.lists(st.sampled_from(MOVE_TYPES), min_size=min_size, max_size=max_size))


@st.composite
def st_tension_level(draw: st.DrawFn) -> int:
    """Generate a valid tension level (0-10 integer)."""
    return draw(st.integers(min_value=0, max_value=10))


@st.composite
def st_quality_score(draw: st.DrawFn) -> QualityScore:
    """Generate a valid QualityScore with each dimension in [0, 3]."""
    return QualityScore(
        sharpness=draw(st.integers(min_value=0, max_value=3)),
        emotional_texture=draw(st.integers(min_value=0, max_value=3)),
        rhythm=draw(st.integers(min_value=0, max_value=3)),
        thematic_relevance=draw(st.integers(min_value=0, max_value=3)),
        shareability=draw(st.integers(min_value=0, max_value=3)),
    )


@st.composite
def st_beat_sequence(draw: st.DrawFn, min_size: int = 0, max_size: int = 10) -> list[Beat]:
    """Generate a sequence of beats with realistic data."""
    num_beats = draw(st.integers(min_value=min_size, max_value=max_size))
    beats = []
    base_time = time.time()
    for i in range(num_beats):
        beat = Beat(
            speaker=draw(st.sampled_from(ARCHETYPES)),
            content=draw(
                st.text(
                    min_size=10,
                    max_size=80,
                    alphabet=st.sampled_from(string.ascii_lowercase + " "),
                )
            ),
            move=draw(st.sampled_from(MOVE_TYPES)),
            quality_score=draw(st.integers(min_value=0, max_value=15)),
            energy_label=draw(st.sampled_from(ENERGY_LABELS)),
            timestamp=base_time + i * 3.0,
        )
        beats.append(beat)
    return beats


@st.composite
def st_request_outcomes(draw: st.DrawFn, min_size: int = 1, max_size: int = 50) -> list[bool]:
    """Generate a sequence of request outcomes for circuit breaker testing.

    Each outcome is a boolean: True = success, False = error.
    """
    return draw(st.lists(st.booleans(), min_size=min_size, max_size=max_size))


@st.composite
def st_pacing_inputs(draw: st.DrawFn) -> tuple:
    """Generate inputs for the Pacing_Controller.compute_delay() method.

    Returns a tuple of (previous_score: int 0-15, upcoming_move: str,
    scene_energy: str, landed_hit: bool).
    """
    previous_score = draw(st.integers(min_value=0, max_value=15))
    upcoming_move = draw(st.sampled_from(MOVE_TYPES))
    scene_energy = draw(st.sampled_from(SCENE_ENERGY_LABELS))
    landed_hit = draw(st.booleans())
    return (previous_score, upcoming_move, scene_energy, landed_hit)


@st.composite
def st_fallback_template(draw: st.DrawFn) -> FallbackTemplate:
    """Generate a valid FallbackTemplate instance.

    Templates may contain {opponent}, {theme}, and {callback} placeholders.
    """
    archetype = draw(st.sampled_from(ARCHETYPES))
    move_type = draw(st.sampled_from(FALLBACK_MOVE_TYPES))
    idx = draw(st.integers(min_value=1, max_value=99))
    template_id = f"{archetype[:3]}_{move_type.lower()[:3]}_{idx:02d}"

    # Generate a template that may or may not have placeholders
    template_text = draw(
        st.one_of(
            # Plain text (no placeholders)
            st.text(
                min_size=10,
                max_size=60,
                alphabet=st.sampled_from(string.ascii_lowercase + " ,.!?"),
            ).map(lambda t: t.strip() or "fallback line here"),
            # With one placeholder
            st.sampled_from(
                [
                    "You think {opponent} gets it? Not even close.",
                    "The {theme} reveals everything about you.",
                    "Remember when you said {callback}? Still true.",
                    "{opponent} keeps dodging the {theme}.",
                    "Nobody asked about {theme}, yet here we are.",
                ]
            ),
            # With multiple placeholders
            st.sampled_from(
                [
                    "{opponent}, the {theme} will outlast your pride.",
                    "Like {callback}, but {opponent} won't admit it.",
                    "The {theme} hits different when {opponent} is quiet.",
                ]
            ),
        )
    )

    base_weight = draw(st.floats(min_value=0.5, max_value=2.0))

    return FallbackTemplate(
        template_id=template_id,
        archetype=archetype,
        move_type=move_type,
        template=template_text,
        base_weight=base_weight,
    )


@st.composite
def st_context_fragments(draw: st.DrawFn) -> dict:
    """Generate context fragments for fallback template substitution.

    Returns a dict with optional keys: opponent_name, arc_theme, callback_phrase.
    Each value is either a string or None (simulating unavailable context).
    """
    opponent_name = draw(
        st.one_of(
            st.none(),
            st.sampled_from(["Alpha", "Beta", "Gamma", "Delta", "Echo", "Zeta"]),
        )
    )
    arc_theme = draw(
        st.one_of(
            st.none(),
            st.sampled_from(
                [
                    "Should the weak be protected?",
                    "The Ethics of Hoarding in a Finite World",
                    "Can builders turn scarcity into durable infrastructure?",
                    "Patronage as Divine Intervention in a Scarcity Economy",
                    "What Does Cooperation Mean When Trust Cannot Be Verified?",
                ]
            ),
        )
    )
    callback_phrase = draw(
        st.one_of(
            st.none(),
            st.text(
                min_size=5,
                max_size=40,
                alphabet=st.sampled_from(string.ascii_lowercase + " "),
            ).map(lambda t: t.strip() or None),
        )
    )

    return {
        "opponent_name": opponent_name,
        "arc_theme": arc_theme,
        "callback_phrase": callback_phrase,
    }


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_config() -> BanterConfig:
    """Returns a BanterConfig with defaults."""
    return BanterConfig()


@pytest.fixture
def sample_archetypes() -> list[str]:
    """Returns list of all 8 archetypes."""
    return ARCHETYPES.copy()


@pytest.fixture
def all_move_types() -> list[str]:
    """All 8 move types."""
    return MOVE_TYPES.copy()


@pytest.fixture
def fallback_move_types() -> list[str]:
    """The 6 move types used in fallback pool."""
    return FALLBACK_MOVE_TYPES.copy()


@pytest.fixture
def sample_beat() -> Beat:
    """A single sample beat for testing."""
    return Beat(
        speaker="prophet",
        content="The question is not who speaks but who listens.",
        move="QUESTION",
        quality_score=10,
        energy_label="warm",
        timestamp=time.time(),
    )


@pytest.fixture
def sample_pair_state() -> PairState:
    """A sample pair state for relationship memory tests."""
    return PairState(
        tension_level=5,
        last_interaction_ts=time.time() - 3600,  # 1 hour ago
    )


@pytest.fixture
def sample_interaction_record() -> InteractionRecord:
    """A sample interaction record."""
    return InteractionRecord(
        timestamp=time.time(),
        elder_a="prophet",
        elder_b="keeper",
        move_used="COUNTER",
        emotional_valence="negative",
        betrayal=False,
        alliance=False,
        concession=False,
    )


@pytest.fixture
def sample_move_context() -> MoveContext:
    """A sample MoveContext for move selector tests."""
    return MoveContext(
        archetype="prophet",
        last_3_moves=["COUNTER", "QUESTION", "ESCALATE"],
        tension_level=5,
        momentum="escalating",
        arc_theme="Should the weak be protected?",
        fear_keywords=["meaninglessness", "irrelevance"],
        consecutive_counters_in_pair=0,
        consecutive_low_scores=0,
    )


@pytest.fixture
def minimal_fallback_templates() -> list[FallbackTemplate]:
    """Minimum valid set of fallback templates (12+ per archetype, 2+ per move).

    Generates the minimum required pool for property testing.
    """
    templates = []
    for archetype in ARCHETYPES:
        for move_type in FALLBACK_MOVE_TYPES:
            for i in range(2):
                templates.append(
                    FallbackTemplate(
                        template_id=f"{archetype[:3]}_{move_type.lower()[:3]}_{i:02d}",
                        archetype=archetype,
                        move_type=move_type,
                        template=f"Template {i} for {archetype} {move_type}: "
                        + "{opponent} knows the {theme} changes nothing.",
                        base_weight=1.0,
                    )
                )
    return templates
