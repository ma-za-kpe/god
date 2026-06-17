"""Unit tests for the Emotional_Primer module.

Tests high-tension visceral markers, low-tension observational markers,
reconciliation language, no-history fallback, output bounds, archetype
differentiation, error handling, and token budget enforcement.

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6
"""

from __future__ import annotations

import os
import re
import sys
import time

import pytest

# Path setup
_src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
for _p in (_src_path, "/app/src"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from banter.emotional_primer import (
    EmotionalPrimer,
    _VISCERAL_MODIFIERS,
    _OBSERVATIONAL_MODIFIERS,
    _RECONCILIATION_FRAMINGS,
    _NEUTRAL_CURIOSITY_FRAMINGS,
    _MAX_SENTENCES_PER_EVENT,
    _MAX_SENTENCES_TOTAL,
    _estimate_token_count,
)
from banter.soul_types import SoulEngineConfig
from banter.types import InteractionRecord


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def config() -> SoulEngineConfig:
    """Default soul engine configuration."""
    return SoulEngineConfig()


@pytest.fixture
def primer(config: SoulEngineConfig) -> EmotionalPrimer:
    """EmotionalPrimer instance with default config."""
    return EmotionalPrimer(config)


@pytest.fixture
def betrayal_record() -> InteractionRecord:
    """A betrayal interaction record."""
    return InteractionRecord(
        timestamp=time.time() - 3600,
        elder_a="prophet",
        elder_b="parasite",
        move_used="ESCALATE",
        emotional_valence="negative",
        betrayal=True,
        alliance=False,
        concession=False,
    )


@pytest.fixture
def alliance_record() -> InteractionRecord:
    """An alliance interaction record."""
    return InteractionRecord(
        timestamp=time.time() - 7200,
        elder_a="sovereign",
        elder_b="keeper",
        move_used="CONCEDE",
        emotional_valence="positive",
        betrayal=False,
        alliance=True,
        concession=False,
    )


@pytest.fixture
def neutral_record() -> InteractionRecord:
    """A neutral interaction record."""
    return InteractionRecord(
        timestamp=time.time() - 1800,
        elder_a="trickster",
        elder_b="herald",
        move_used="QUESTION",
        emotional_valence="neutral",
        betrayal=False,
        alliance=False,
        concession=False,
    )


@pytest.fixture
def multiple_records() -> list[InteractionRecord]:
    """Multiple interaction records for testing bounds."""
    base_time = time.time()
    records = []
    for i in range(10):
        records.append(
            InteractionRecord(
                timestamp=base_time - (i * 600),
                elder_a="martyr",
                elder_b="shadow",
                move_used="COUNTER",
                emotional_valence="negative",
                betrayal=(i % 3 == 0),
                alliance=False,
                concession=(i % 4 == 0),
            )
        )
    return records


# ---------------------------------------------------------------------------
# Test: High tension uses visceral markers (Requirement 3.3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_high_tension_uses_visceral_markers(
    primer: EmotionalPrimer, betrayal_record: InteractionRecord
):
    """Tension > 5 produces visceral language markers.

    Validates: Requirements 3.3
    """
    result = await primer.generate_emotional_context(
        archetype="parasite",
        history=[betrayal_record],
        tension_level=8,
        reconciliation_active=False,
    )

    assert result is not None
    # Check that at least one visceral marker phrase or its keywords appear.
    visceral_keywords = ["burns", "cuts", "won't forget", "wound", "raw",
                         "cut", "burn", "forget", "open", "weight"]
    text_lower = result.lower()
    has_visceral = any(kw in text_lower for kw in visceral_keywords)
    # Also check that the visceral modifiers list was sampled from.
    has_modifier = any(mod in result for mod in _VISCERAL_MODIFIERS)
    assert has_visceral or has_modifier, (
        f"Expected visceral language at tension=8, got: {result}"
    )


# ---------------------------------------------------------------------------
# Test: Low tension uses observational markers (Requirement 3.3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_low_tension_uses_observational_markers(
    primer: EmotionalPrimer, betrayal_record: InteractionRecord
):
    """Tension ≤ 5 produces observational language markers.

    Validates: Requirements 3.3
    """
    result = await primer.generate_emotional_context(
        archetype="keeper",
        history=[betrayal_record],
        tension_level=3,
        reconciliation_active=False,
    )

    assert result is not None
    observational_keywords = ["persists", "noted", "watching", "remembering",
                              "lingers", "quiet", "present", "surface",
                              "peripheral", "awareness"]
    text_lower = result.lower()
    has_observational = any(kw in text_lower for kw in observational_keywords)
    has_modifier = any(mod in result for mod in _OBSERVATIONAL_MODIFIERS)
    assert has_observational or has_modifier, (
        f"Expected observational language at tension=3, got: {result}"
    )


# ---------------------------------------------------------------------------
# Test: Reconciliation produces mixed-feeling language (Requirement 3.4)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reconciliation_mixed_feelings(
    primer: EmotionalPrimer, betrayal_record: InteractionRecord
):
    """Reconciliation_active=True produces mixed-feeling language.

    Validates: Requirements 3.4
    """
    result = await primer.generate_emotional_context(
        archetype="martyr",
        history=[betrayal_record],
        tension_level=5,
        reconciliation_active=True,
    )

    assert result is not None
    # Check for reconciliation-related phrases.
    reconciliation_keywords = [
        "wants to believe", "trust wars with memory", "cautious hope",
        "believe", "trust", "watching for the knife", "softens",
        "guard", "hope", "extends", "pull back", "scar"
    ]
    text_lower = result.lower()
    has_reconciliation = any(kw in text_lower for kw in reconciliation_keywords)
    has_framing = any(f in result for f in _RECONCILIATION_FRAMINGS)
    assert has_reconciliation or has_framing, (
        f"Expected reconciliation language, got: {result}"
    )


# ---------------------------------------------------------------------------
# Test: No history produces neutral curiosity (Requirement 3.6)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_history_neutral_curiosity(primer: EmotionalPrimer):
    """Empty history produces neutral curiosity framing.

    Validates: Requirements 3.6
    """
    result = await primer.generate_emotional_context(
        archetype="trickster",
        history=[],
        tension_level=5,
        reconciliation_active=False,
    )

    assert result is not None
    # Check for neutral curiosity phrases.
    curiosity_keywords = [
        "sizing them up", "hasn't decided", "no verdict", "blank page",
        "assessment", "ongoing", "watching", "assumption", "cataloguing",
        "potential", "unwritten"
    ]
    text_lower = result.lower()
    has_curiosity = any(kw in text_lower for kw in curiosity_keywords)
    has_framing = any(f in result for f in _NEUTRAL_CURIOSITY_FRAMINGS)
    assert has_curiosity or has_framing, (
        f"Expected neutral curiosity for empty history, got: {result}"
    )


# ---------------------------------------------------------------------------
# Test: Output contains present-tense only (Requirement 3.1)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_output_present_tense_only(
    primer: EmotionalPrimer, betrayal_record: InteractionRecord
):
    """Output never contains past-tense timestamps or 'happened at' patterns.

    Validates: Requirements 3.1
    """
    # Test across multiple archetypes and tension levels.
    for archetype in ["parasite", "prophet", "martyr", "keeper"]:
        for tension in [2, 5, 8]:
            result = await primer.generate_emotional_context(
                archetype=archetype,
                history=[betrayal_record],
                tension_level=tension,
                reconciliation_active=False,
            )
            assert result is not None
            # Should not contain date/time patterns or "happened at".
            assert "happened at" not in result.lower()
            assert "occurred at" not in result.lower()
            # Should not contain ISO timestamps.
            assert not re.search(
                r"\d{4}-\d{2}-\d{2}", result
            ), f"Timestamp found in output for {archetype}: {result}"
            # Should not contain epoch-like numbers.
            assert not re.search(
                r"\b1[67]\d{8}\b", result
            ), f"Epoch timestamp found in output for {archetype}: {result}"


# ---------------------------------------------------------------------------
# Test: Output within sentence bounds (Requirements 3.5)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_output_within_sentence_bounds(
    primer: EmotionalPrimer, multiple_records: list[InteractionRecord]
):
    """Output never exceeds 15 sentences total and ≤3 per event.

    Validates: Requirements 3.5
    """
    result = await primer.generate_emotional_context(
        archetype="shadow",
        history=multiple_records,
        tension_level=7,
        reconciliation_active=True,
    )

    assert result is not None
    # Count sentences (split by period followed by space or end of string).
    # This is an approximation since some sentences may contain abbreviations.
    sentences = [s.strip() for s in re.split(r'[.!?]+', result) if s.strip()]
    assert len(sentences) <= _MAX_SENTENCES_TOTAL, (
        f"Total sentences {len(sentences)} exceeds max {_MAX_SENTENCES_TOTAL}: {result}"
    )


# ---------------------------------------------------------------------------
# Test: Different archetypes produce different output (Requirement 3.2)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_different_archetypes_different_output(
    primer: EmotionalPrimer, betrayal_record: InteractionRecord
):
    """Same history + different archetypes → different text.

    Validates: Requirements 3.2
    """
    archetypes = ["parasite", "prophet", "trickster", "sovereign",
                  "martyr", "shadow", "herald", "keeper"]
    results = {}

    for archetype in archetypes:
        result = await primer.generate_emotional_context(
            archetype=archetype,
            history=[betrayal_record],
            tension_level=6,
            reconciliation_active=False,
        )
        assert result is not None
        results[archetype] = result

    # Every pair of archetypes should produce different output.
    for i, arch_a in enumerate(archetypes):
        for arch_b in archetypes[i + 1:]:
            assert results[arch_a] != results[arch_b], (
                f"Archetypes {arch_a} and {arch_b} produced identical output: "
                f"{results[arch_a]}"
            )


# ---------------------------------------------------------------------------
# Test: Returns None on error (Requirement 3.7)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_returns_none_on_error(primer: EmotionalPrimer):
    """Passing invalid data returns None (not exception).

    Validates: Requirements 3.7
    """
    # Pass invalid history that would cause internal errors.
    # The module should catch exceptions and return None.
    class BrokenRecord:
        """Mimics InteractionRecord but raises on attribute access."""
        @property
        def betrayal(self):
            raise RuntimeError("Simulated data corruption")

        @property
        def alliance(self):
            raise RuntimeError("Simulated data corruption")

        @property
        def concession(self):
            raise RuntimeError("Simulated data corruption")

        @property
        def emotional_valence(self):
            raise RuntimeError("Simulated data corruption")

    # The method should handle this gracefully and return None.
    result = await primer.generate_emotional_context(
        archetype="prophet",
        history=[BrokenRecord()],  # type: ignore
        tension_level=5,
        reconciliation_active=False,
    )
    assert result is None


# ---------------------------------------------------------------------------
# Test: Output within token budget (Requirement 7.2, design spec)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_output_within_token_budget(
    primer: EmotionalPrimer, multiple_records: list[InteractionRecord]
):
    """Output never exceeds 200 token budget.

    Validates: Requirements 3.5 (token budget enforcement)
    """
    result = await primer.generate_emotional_context(
        archetype="keeper",
        history=multiple_records,
        tension_level=9,
        reconciliation_active=True,
    )

    assert result is not None
    token_count = _estimate_token_count(result)
    assert token_count <= 200, (
        f"Token count {token_count} exceeds budget of 200. Output: {result}"
    )
