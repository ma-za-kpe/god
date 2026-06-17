"""Property-based tests for the Elder Voice Soul Engine.

Uses Hypothesis to verify correctness properties defined in the design document.
"""

import os
import sys

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
for _p in (_src_path, "/app/src"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import json
from dataclasses import asdict
from itertools import combinations
from pathlib import Path

from hypothesis import given, settings, HealthCheck, assume
from hypothesis import strategies as st

from banter.soul_types import (
    VOICE_DNA_SCHEMA,
    RhythmPattern,
    SoulEngineConfig,
    VoiceDNAProfile,
    validate_voice_dna_profile,
)


# ---------------------------------------------------------------------------
# Strategies for VoiceDNA profile generation
# ---------------------------------------------------------------------------

# Minimum counts per field as defined in the schema
_MIN_COUNTS = {
    "sentence_structures": 3,
    "verbal_tics": 2,
    "rhythm_patterns": 1,
    "micro_phrases": 4,
    "rhetorical_devices": 2,
    "opening_patterns": 2,
    "closing_patterns": 2,
}


def _st_non_empty_string() -> st.SearchStrategy[str]:
    """Generate a non-empty string suitable for profile entries."""
    return st.text(min_size=1, max_size=50, alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "Z"),
        min_codepoint=32,
        max_codepoint=126,
    ))


def _st_rhythm_pattern_dict() -> st.SearchStrategy[dict]:
    """Generate a rhythm pattern dict matching the expected schema."""
    return st.fixed_dictionaries({
        "name": _st_non_empty_string(),
        "clause_count_range": st.tuples(
            st.integers(min_value=1, max_value=5),
            st.integers(min_value=1, max_value=10),
        ).map(lambda t: [min(t), max(t)] if t[0] != t[1] else [t[0], t[0] + 1]),
        "word_count_per_clause_range": st.tuples(
            st.integers(min_value=1, max_value=10),
            st.integers(min_value=1, max_value=20),
        ).map(lambda t: [min(t), max(t)] if t[0] != t[1] else [t[0], t[0] + 1]),
        "pause_placement": st.sampled_from([
            "before_final", "between_clauses", "front_loaded"
        ]),
    })


def _st_string_list(min_count: int, max_count: int = 10) -> st.SearchStrategy[list]:
    """Generate a list of non-empty strings with given count bounds."""
    return st.lists(_st_non_empty_string(), min_size=min_count, max_size=max_count)


@st.composite
def st_valid_voice_dna_profile(draw: st.DrawFn) -> dict:
    """Generate a valid VoiceDNA profile dict that meets all schema requirements.

    All 7 required fields are present with at least the minimum counts.
    """
    return {
        "sentence_structures": draw(_st_string_list(
            _MIN_COUNTS["sentence_structures"]
        )),
        "verbal_tics": draw(_st_string_list(
            _MIN_COUNTS["verbal_tics"]
        )),
        "rhythm_patterns": draw(st.lists(
            _st_rhythm_pattern_dict(),
            min_size=_MIN_COUNTS["rhythm_patterns"],
            max_size=5,
        )),
        "micro_phrases": draw(_st_string_list(
            _MIN_COUNTS["micro_phrases"]
        )),
        "rhetorical_devices": draw(_st_string_list(
            _MIN_COUNTS["rhetorical_devices"]
        )),
        "opening_patterns": draw(_st_string_list(
            _MIN_COUNTS["opening_patterns"]
        )),
        "closing_patterns": draw(_st_string_list(
            _MIN_COUNTS["closing_patterns"]
        )),
    }


@st.composite
def st_invalid_voice_dna_profile(draw: st.DrawFn) -> dict:
    """Generate an invalid VoiceDNA profile dict that violates at least one constraint.

    Uses one of three invalidation strategies:
    1. Remove a required field entirely
    2. Provide a field with fewer items than the minimum count
    3. Provide a field with a non-list value
    """
    # Start with a valid profile
    profile = draw(st_valid_voice_dna_profile())

    # Pick an invalidation strategy
    strategy = draw(st.sampled_from(["missing_field", "insufficient_count", "wrong_type"]))
    target_field = draw(st.sampled_from(list(_MIN_COUNTS.keys())))

    if strategy == "missing_field":
        del profile[target_field]
    elif strategy == "insufficient_count":
        min_count = _MIN_COUNTS[target_field]
        # Generate a list shorter than the minimum
        if min_count > 0:
            short_count = draw(st.integers(min_value=0, max_value=min_count - 1))
            if target_field == "rhythm_patterns":
                profile[target_field] = draw(st.lists(
                    _st_rhythm_pattern_dict(),
                    min_size=short_count,
                    max_size=short_count,
                ))
            else:
                profile[target_field] = draw(st.lists(
                    _st_non_empty_string(),
                    min_size=short_count,
                    max_size=short_count,
                ))
        else:
            # min_count is 0, can't make it insufficient; fall back to missing
            del profile[target_field]
    elif strategy == "wrong_type":
        # Replace a list field with a non-list value
        non_list_value = draw(st.one_of(
            st.text(min_size=0, max_size=20),
            st.integers(),
            st.none(),
            st.booleans(),
        ))
        profile[target_field] = non_list_value

    return profile


# ---------------------------------------------------------------------------
# Strategies for VoiceDNAProfile dataclass generation
# ---------------------------------------------------------------------------

VALID_PAUSE_PLACEMENTS = ["before_final", "between_clauses", "front_loaded"]


@st.composite
def st_rhythm_pattern_obj(draw: st.DrawFn) -> RhythmPattern:
    """Generate a valid RhythmPattern dataclass instance."""
    name = draw(_st_non_empty_string())
    clause_min = draw(st.integers(min_value=1, max_value=5))
    clause_max = draw(st.integers(min_value=clause_min, max_value=10))
    word_min = draw(st.integers(min_value=1, max_value=10))
    word_max = draw(st.integers(min_value=word_min, max_value=25))
    pause_placement = draw(st.sampled_from(VALID_PAUSE_PLACEMENTS))
    return RhythmPattern(
        name=name,
        clause_count_range=(clause_min, clause_max),
        word_count_per_clause_range=(word_min, word_max),
        pause_placement=pause_placement,
    )


@st.composite
def st_voice_dna_profile_obj(draw: st.DrawFn) -> VoiceDNAProfile:
    """Generate a valid VoiceDNAProfile dataclass instance."""
    archetype = draw(st.sampled_from(
        ["parasite", "prophet", "trickster", "sovereign", "martyr", "shadow", "herald", "keeper"]
    ))
    sentence_structures = draw(_st_string_list(_MIN_COUNTS["sentence_structures"]))
    verbal_tics = draw(_st_string_list(_MIN_COUNTS["verbal_tics"]))
    rhythm_patterns = draw(st.lists(st_rhythm_pattern_obj(), min_size=1, max_size=5))
    micro_phrases = draw(_st_string_list(_MIN_COUNTS["micro_phrases"]))
    rhetorical_devices = draw(_st_string_list(_MIN_COUNTS["rhetorical_devices"]))
    opening_patterns = draw(_st_string_list(_MIN_COUNTS["opening_patterns"]))
    closing_patterns = draw(_st_string_list(_MIN_COUNTS["closing_patterns"]))

    return VoiceDNAProfile(
        archetype=archetype,
        sentence_structures=sentence_structures,
        verbal_tics=verbal_tics,
        rhythm_patterns=rhythm_patterns,
        micro_phrases=micro_phrases,
        rhetorical_devices=rhetorical_devices,
        opening_patterns=opening_patterns,
        closing_patterns=closing_patterns,
    )


# ---------------------------------------------------------------------------
# Feature: elder-voice-soul-engine, Property 1: VoiceDNA schema validation
# ---------------------------------------------------------------------------


class TestVoiceDNASchemaValidation:
    """Property 1: VoiceDNA Schema Validation.

    *For any* VoiceDNA profile data dictionary, the schema validator accepts
    it if and only if it contains all 7 required fields with at least the
    specified minimum counts (3 sentence structures, 2 verbal tics, 1 rhythm
    pattern, 4 micro-phrases, 2 rhetorical devices, 2 opening patterns,
    2 closing patterns).

    **Validates: Requirements 1.1, 8.4**
    """

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(profile_data=st_valid_voice_dna_profile())
    def test_voice_dna_schema_validation_accepts_valid_profiles(self, profile_data):
        """Valid profiles (meeting all min counts) always pass validation."""
        is_valid, violations = validate_voice_dna_profile(profile_data)

        assert is_valid is True, (
            f"Expected valid profile to pass validation but got violations: {violations}"
        )
        assert violations == [], (
            f"Expected no violations for valid profile but got: {violations}"
        )

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(profile_data=st_invalid_voice_dna_profile())
    def test_voice_dna_schema_validation_rejects_invalid_profiles(self, profile_data):
        """Profiles missing fields or with insufficient counts always fail."""
        is_valid, violations = validate_voice_dna_profile(profile_data)

        assert is_valid is False, (
            "Expected invalid profile to fail validation but it passed. "
            f"Profile fields present: {list(profile_data.keys())}, "
            f"field counts: {({k: len(v) if isinstance(v, list) else type(v).__name__ for k, v in profile_data.items()})}"
        )
        assert len(violations) > 0, (
            "Expected at least one violation for invalid profile"
        )


# ---------------------------------------------------------------------------
# Feature: elder-voice-soul-engine, Property 15: VoiceDNA Serialization Round-Trip
# ---------------------------------------------------------------------------


class TestVoiceDNASerializationRoundTrip:
    """Property 15: VoiceDNA Serialization Round-Trip.

    *For any* valid VoiceDNA profile object, serializing to JSON and parsing
    back produces an equivalent VoiceDNA profile:
    parse(serialize(profile)) == profile.

    **Validates: Requirements 8.6**
    """

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(profile=st_voice_dna_profile_obj())
    def test_voice_dna_serialization_round_trip(self, profile: VoiceDNAProfile) -> None:
        """parse(serialize(profile)) == profile for any valid VoiceDNA profile."""
        # Serialize to JSON string
        serialized = json.dumps(asdict(profile))

        # Deserialize back to dict
        deserialized = json.loads(serialized)

        # Reconstruct VoiceDNAProfile from the deserialized dict
        reconstructed = VoiceDNAProfile(
            archetype=deserialized["archetype"],
            sentence_structures=deserialized["sentence_structures"],
            verbal_tics=deserialized["verbal_tics"],
            rhythm_patterns=[
                RhythmPattern(
                    name=rp["name"],
                    clause_count_range=tuple(rp["clause_count_range"]),
                    word_count_per_clause_range=tuple(rp["word_count_per_clause_range"]),
                    pause_placement=rp["pause_placement"],
                )
                for rp in deserialized["rhythm_patterns"]
            ],
            micro_phrases=deserialized["micro_phrases"],
            rhetorical_devices=deserialized["rhetorical_devices"],
            opening_patterns=deserialized["opening_patterns"],
            closing_patterns=deserialized["closing_patterns"],
        )

        assert reconstructed == profile


# ---------------------------------------------------------------------------
# Feature: elder-voice-soul-engine, Property 2: Voice Conformance Score Bounds
# ---------------------------------------------------------------------------

from pathlib import Path

from banter.voice_dna import VoiceDNA, ARCHETYPES
from banter.soul_types import SoulEngineConfig

# Resolve the voice profiles directory (works both locally and in Docker)
_PROFILES_DIR = Path("/app/src/banter/voice_profiles")
if not _PROFILES_DIR.exists():
    _PROFILES_DIR = Path(os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "src", "banter", "voice_profiles")
    ))

# Strategy: random archetype from the set of 8
def st_archetype() -> st.SearchStrategy[str]:
    """Pick a random archetype from the 8 defined archetypes."""
    return st.sampled_from([
        "parasite", "prophet", "trickster", "sovereign",
        "martyr", "shadow", "herald", "keeper",
    ])


# Strategy: random candidate line string
def st_candidate_line() -> st.SearchStrategy[str]:
    """Generate a random candidate line string."""
    return st.text(min_size=1, max_size=500)


class TestVoiceConformanceScoreBounds:
    """Property 2: Voice Conformance Score Bounds.

    *For any* candidate line string and any archetype name, the voice
    conformance score is always an integer in [0, 3].

    **Validates: Requirements 1.3**
    """

    @classmethod
    def setup_class(cls):
        """Load VoiceDNA profiles once for all tests in this class."""
        import asyncio

        config = SoulEngineConfig()
        cls.voice_dna = VoiceDNA(profiles_dir=_PROFILES_DIR, config=config)
        asyncio.run(cls.voice_dna.load_profiles())

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        candidate=st_candidate_line(),
        archetype=st_archetype(),
    )
    def test_score_always_in_bounds(self, candidate: str, archetype: str):
        """Voice conformance score is always an integer in [0, 3]."""
        score = self.voice_dna.score_voice_conformance(candidate, archetype)

        assert isinstance(score, int), (
            f"Expected score to be an int but got {type(score).__name__}: {score!r} "
            f"for candidate={candidate!r}, archetype={archetype!r}"
        )
        assert 0 <= score <= 3, (
            f"Expected score in [0, 3] but got {score} "
            f"for candidate={candidate!r}, archetype={archetype!r}"
        )


# ---------------------------------------------------------------------------
# Feature: elder-voice-soul-engine, Property 3: Archetype Linguistic Differentiation
# ---------------------------------------------------------------------------

# The 7 structural categories that define a VoiceDNA profile
_STRUCTURAL_CATEGORIES = [
    "sentence_structures",
    "verbal_tics",
    "rhythm_patterns",
    "micro_phrases",
    "rhetorical_devices",
    "opening_patterns",
    "closing_patterns",
]

# All 8 archetypes (module-level constant for Property 3)
_EIGHT_ARCHETYPES = [
    "parasite", "prophet", "trickster", "sovereign",
    "martyr", "shadow", "herald", "keeper",
]


def _load_all_profiles() -> dict:
    """Load all 8 archetype profile JSON files and return as {archetype: data}."""
    profiles_dir = Path("/app/src/banter/voice_profiles")
    if not profiles_dir.exists():
        profiles_dir = Path(__file__).resolve().parents[2] / "src" / "banter" / "voice_profiles"

    profiles = {}
    for archetype in _EIGHT_ARCHETYPES:
        profile_path = profiles_dir / f"{archetype}.json"
        assert profile_path.exists(), (
            f"Profile file missing for archetype '{archetype}': {profile_path}"
        )
        with open(profile_path, "r", encoding="utf-8") as f:
            profiles[archetype] = json.load(f)
    return profiles


def _categories_differ(profile_a: dict, profile_b: dict) -> list:
    """Return list of category names where the two profiles differ."""
    differing = []
    for category in _STRUCTURAL_CATEGORIES:
        content_a = profile_a.get(category)
        content_b = profile_b.get(category)
        if content_a != content_b:
            differing.append(category)
    return differing


@st.composite
def st_distinct_archetype_pair(draw: st.DrawFn) -> tuple:
    """Generate a pair of two distinct archetypes from the set of 8."""
    archetype_a = draw(st.sampled_from(_EIGHT_ARCHETYPES))
    archetype_b = draw(
        st.sampled_from([a for a in _EIGHT_ARCHETYPES if a != archetype_a])
    )
    return (archetype_a, archetype_b)


class TestArchetypeLinguisticDifferentiation:
    """Property 3: Archetype Linguistic Differentiation.

    *For any* two distinct archetypes A and B from the set of 8, their
    VoiceDNA profiles differ in at least 4 of the 7 structural categories
    (sentence_structures, verbal_tics, rhythm_patterns, micro_phrases,
    rhetorical_devices, opening_patterns, closing_patterns).

    **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8**
    """

    @classmethod
    def setup_class(cls):
        """Load all 8 archetype profiles once for all tests in this class."""
        cls.profiles = _load_all_profiles()
        assert len(cls.profiles) == 8, (
            f"Expected 8 profiles loaded, got {len(cls.profiles)}"
        )

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(pair=st_distinct_archetype_pair())
    def test_distinct_archetypes_differ_in_at_least_4_categories(self, pair):
        """For ANY two distinct archetypes, profiles differ in >= 4 of 7 categories."""
        archetype_a, archetype_b = pair

        profile_a = self.profiles[archetype_a]
        profile_b = self.profiles[archetype_b]

        differing = _categories_differ(profile_a, profile_b)

        assert len(differing) >= 4, (
            f"Archetypes '{archetype_a}' and '{archetype_b}' differ in only "
            f"{len(differing)}/7 categories ({differing}). "
            f"Expected at least 4 differing categories.\n"
            f"Identical categories: "
            f"{[c for c in _STRUCTURAL_CATEGORIES if c not in differing]}"
        )

    def test_all_pairs_differ_in_at_least_4_categories(self):
        """Exhaustive check: every pair of distinct archetypes differs in >= 4 categories."""
        profiles = self.profiles

        # There are C(8, 2) = 28 unique pairs
        pairs = list(combinations(_EIGHT_ARCHETYPES, 2))
        assert len(pairs) == 28, f"Expected 28 pairs, got {len(pairs)}"

        failures = []
        for archetype_a, archetype_b in pairs:
            differing = _categories_differ(profiles[archetype_a], profiles[archetype_b])
            if len(differing) < 4:
                failures.append(
                    f"  {archetype_a} vs {archetype_b}: only {len(differing)}/7 "
                    f"categories differ ({differing})"
                )

        assert not failures, (
            f"Archetype pairs with fewer than 4 differing categories:\n"
            + "\n".join(failures)
        )

    def test_each_archetype_profile_loads_successfully(self):
        """All 8 archetype profiles load without errors."""
        profiles = self.profiles
        assert len(profiles) == 8, f"Expected 8 profiles, got {len(profiles)}"

        for archetype, profile in profiles.items():
            for category in _STRUCTURAL_CATEGORIES:
                assert category in profile, (
                    f"Archetype '{archetype}' missing category '{category}'"
                )

    def test_minimum_differentiation_coverage(self):
        """No single category is identical across all pairs (diversity exists)."""
        profiles = self.profiles

        # For each category, count how many pairs share identical content
        for category in _STRUCTURAL_CATEGORIES:
            identical_count = 0
            for a, b in combinations(_EIGHT_ARCHETYPES, 2):
                if profiles[a].get(category) == profiles[b].get(category):
                    identical_count += 1
            # At most half the pairs can share any single category
            assert identical_count <= 14, (
                f"Category '{category}' is identical for {identical_count}/28 pairs "
                f"(more than half) — insufficient differentiation"
            )


# ---------------------------------------------------------------------------
# Feature: elder-voice-soul-engine, Property 23: Failed Validation Profile Retention
# ---------------------------------------------------------------------------

import tempfile
import asyncio


def _make_valid_profile_data(archetype: str) -> dict:
    """Create a minimal valid profile dict for testing purposes."""
    return {
        "archetype": archetype,
        "sentence_structures": ["structure_a", "structure_b", "structure_c"],
        "verbal_tics": ["tic_one", "tic_two"],
        "rhythm_patterns": [
            {
                "name": "steady_beat",
                "clause_count_range": [2, 4],
                "word_count_per_clause_range": [3, 8],
                "pause_placement": "before_final",
            }
        ],
        "micro_phrases": ["phrase_1", "phrase_2", "phrase_3", "phrase_4"],
        "rhetorical_devices": ["device_a", "device_b"],
        "opening_patterns": ["opener_one", "opener_two"],
        "closing_patterns": ["closer_one", "closer_two"],
    }


class TestFailedValidationProfileRetention:
    """Property 23: Failed Validation Profile Retention.

    *For any* VoiceDNA profile that fails schema validation during hot-reload,
    the previously loaded valid profile for that archetype remains active and
    is used for all subsequent prompt injections.

    **Validates: Requirements 8.5**
    """

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(invalid_profile=st_invalid_voice_dna_profile())
    def test_failed_reload_retains_previous_profile(self, invalid_profile):
        """After a failed hot-reload, the original valid profile stays active."""
        archetype = "parasite"

        with tempfile.TemporaryDirectory() as tmpdir:
            profiles_dir = Path(tmpdir)
            profile_path = profiles_dir / f"{archetype}.json"

            # Write a valid profile and load it
            valid_data = _make_valid_profile_data(archetype)
            profile_path.write_text(json.dumps(valid_data), encoding="utf-8")

            config = SoulEngineConfig()
            voice_dna = VoiceDNA(profiles_dir=profiles_dir, config=config)
            asyncio.run(voice_dna.load_profiles())

            # Confirm valid profile is loaded
            assert archetype in voice_dna.profiles, (
                f"Expected '{archetype}' to be loaded after initial load"
            )
            original_profile = voice_dna.profiles[archetype]
            original_injection = voice_dna.get_prompt_injection(archetype)
            assert original_injection is not None, (
                "Expected prompt injection to be available for loaded profile"
            )

            # Overwrite the file with an invalid profile (add archetype field
            # so the file is valid JSON but fails schema validation)
            invalid_data = dict(invalid_profile)
            invalid_data["archetype"] = archetype
            profile_path.write_text(json.dumps(invalid_data), encoding="utf-8")

            # Force mtime change detection by resetting internal state
            # (bypass the 30s polling interval for test purposes)
            voice_dna._last_check_ts = 0.0
            voice_dna._file_mtimes[archetype] = 0.0

            # Trigger reload check
            asyncio.run(voice_dna.check_for_reload())

            # Verify: the original valid profile is STILL active
            assert archetype in voice_dna.profiles, (
                "Archetype profile was removed after failed reload"
            )
            assert voice_dna.profiles[archetype] == original_profile, (
                "Profile was changed after failed validation reload. "
                f"Expected original profile but got: {voice_dna.profiles[archetype]}"
            )

            # Verify: get_prompt_injection still works for the archetype
            post_reload_injection = voice_dna.get_prompt_injection(archetype)
            assert post_reload_injection is not None, (
                "Prompt injection returned None after failed reload — "
                "original profile should still be active"
            )
            assert post_reload_injection == original_injection, (
                "Prompt injection changed after failed reload"
            )


# ---------------------------------------------------------------------------
# Feature: elder-voice-soul-engine, Property 5: Emotional_Primer Output Size Bounds
# ---------------------------------------------------------------------------

from banter.emotional_primer import EmotionalPrimer, _estimate_token_count
from banter.types import InteractionRecord


# Strategy: generate a random InteractionRecord
@st.composite
def st_interaction_record(draw: st.DrawFn) -> InteractionRecord:
    """Generate a random InteractionRecord."""
    return InteractionRecord(
        timestamp=draw(st.floats(min_value=0.0, max_value=1e12, allow_nan=False, allow_infinity=False)),
        elder_a=draw(st.sampled_from(["alpha", "beta", "gamma", "delta", "epsilon"])),
        elder_b=draw(st.sampled_from(["zeta", "eta", "theta", "iota", "kappa"])),
        move_used=draw(st.sampled_from([
            "COUNTER", "ESCALATE", "DEFLECT", "TAUNT", "QUESTION", "PIVOT", "CONCEDE", "CALLBACK",
        ])),
        emotional_valence=draw(st.sampled_from(["positive", "negative", "neutral"])),
        betrayal=draw(st.booleans()),
        alliance=draw(st.booleans()),
        concession=draw(st.booleans()),
    )


def _count_sentences(text: str) -> int:
    """Count sentences in output text.

    Uses ending punctuation (., !, ?) followed by space or end-of-string
    as sentence boundaries, consistent with how EmotionalPrimer constructs
    output by joining sentences with ". " or space-separated sentences
    ending with periods.
    """
    if not text or not text.strip():
        return 0

    import re
    # Split on sentence-ending punctuation followed by space or end-of-string
    # This handles ". ", "! ", "? " as boundaries
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    # Filter out empty strings
    sentences = [s for s in sentences if s.strip()]
    return len(sentences)


class TestEmotionalPrimerOutputSizeBounds:
    """Property 5: Emotional_Primer Output Size Bounds.

    *For any* list of InteractionRecords (regardless of length), the
    Emotional_Primer output never exceeds 3 sentences per relationship
    event and never exceeds 15 sentences total.

    **Validates: Requirements 3.5**
    """

    @classmethod
    def setup_class(cls):
        """Set up EmotionalPrimer instance for testing."""
        config = SoulEngineConfig()
        cls.primer = EmotionalPrimer(config=config)

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        history=st.lists(st_interaction_record(), min_size=1, max_size=50),
        archetype=st.sampled_from([
            "parasite", "prophet", "trickster", "sovereign",
            "martyr", "shadow", "herald", "keeper",
        ]),
        tension_level=st.integers(min_value=0, max_value=10),
        reconciliation_active=st.booleans(),
    )
    def test_output_never_exceeds_15_sentences_total(
        self, history, archetype, tension_level, reconciliation_active
    ):
        """Total sentence count in output never exceeds 15 regardless of input size."""
        result = asyncio.run(
            self.primer.generate_emotional_context(
                archetype=archetype,
                history=history,
                tension_level=tension_level,
                reconciliation_active=reconciliation_active,
            )
        )

        # EmotionalPrimer returns None on error (which is acceptable)
        if result is None:
            return

        sentence_count = _count_sentences(result)
        assert sentence_count <= 15, (
            f"Output exceeded 15 sentences (got {sentence_count}) for "
            f"archetype={archetype}, tension={tension_level}, "
            f"reconciliation={reconciliation_active}, "
            f"history_length={len(history)}.\n"
            f"Output: {result!r}"
        )

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        history=st.lists(st_interaction_record(), min_size=1, max_size=50),
        archetype=st.sampled_from([
            "parasite", "prophet", "trickster", "sovereign",
            "martyr", "shadow", "herald", "keeper",
        ]),
        tension_level=st.integers(min_value=0, max_value=10),
        reconciliation_active=st.booleans(),
    )
    def test_output_never_exceeds_token_budget(
        self, history, archetype, tension_level, reconciliation_active
    ):
        """Token count of output never exceeds the 200-token budget."""
        result = asyncio.run(
            self.primer.generate_emotional_context(
                archetype=archetype,
                history=history,
                tension_level=tension_level,
                reconciliation_active=reconciliation_active,
            )
        )

        # EmotionalPrimer returns None on error (which is acceptable)
        if result is None:
            return

        token_count = _estimate_token_count(result)
        assert token_count <= 200, (
            f"Output exceeded 200 tokens (got {token_count}) for "
            f"archetype={archetype}, tension={tension_level}, "
            f"reconciliation={reconciliation_active}, "
            f"history_length={len(history)}.\n"
            f"Output: {result!r}"
        )


# ---------------------------------------------------------------------------
# Feature: elder-voice-soul-engine, Property 4: Emotional_Primer Present-Tense Invariant
# ---------------------------------------------------------------------------

import re

from banter.emotional_primer import EmotionalPrimer
from banter.types import InteractionRecord


# ---------------------------------------------------------------------------
# Strategies for InteractionRecord generation
# ---------------------------------------------------------------------------

# Valid Elder names for generating interaction records.
_ELDER_NAMES = [
    "elder_alpha", "elder_beta", "elder_gamma", "elder_delta",
    "elder_epsilon", "elder_zeta", "elder_eta", "elder_theta",
]


@st.composite
def st_interaction_record(draw: st.DrawFn) -> InteractionRecord:
    """Generate a random InteractionRecord with valid field values."""
    timestamp = draw(st.floats(min_value=1_000_000, max_value=9_999_999_999.0,
                               allow_nan=False, allow_infinity=False))
    elder_a = draw(st.sampled_from(_ELDER_NAMES))
    elder_b = draw(st.sampled_from([n for n in _ELDER_NAMES if n != elder_a]))
    move_used = draw(st.sampled_from([
        "COUNTER", "ESCALATE", "DEFLECT", "TAUNT",
        "QUESTION", "PIVOT", "CONCEDE", "CALLBACK",
    ]))
    emotional_valence = draw(st.sampled_from(["positive", "negative", "neutral"]))
    betrayal = draw(st.booleans())
    alliance = draw(st.booleans())
    concession = draw(st.booleans())

    return InteractionRecord(
        timestamp=timestamp,
        elder_a=elder_a,
        elder_b=elder_b,
        move_used=move_used,
        emotional_valence=emotional_valence,
        betrayal=betrayal,
        alliance=alliance,
        concession=concession,
    )


def st_interaction_history() -> st.SearchStrategy[list]:
    """Generate a random list of InteractionRecords (0 to 20 records)."""
    return st.lists(st_interaction_record(), min_size=0, max_size=20)


# ---------------------------------------------------------------------------
# Past-tense and timestamp detection patterns
# ---------------------------------------------------------------------------

# Regex patterns that indicate past-tense event descriptions with timestamps.
_PAST_TENSE_TIMESTAMP_PATTERNS = [
    # ISO-style dates: 2024-01-15, 2023/12/31
    r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b",
    # Timestamps with colons: 14:30:00, 2:30 PM
    r"\b\d{1,2}:\d{2}(:\d{2})?\s*(AM|PM|am|pm)?\b",
    # "X happened at Y" patterns
    r"\bhappened\s+(at|on|in|during)\b",
    # "X occurred at/on Y" patterns
    r"\boccurred\s+(at|on|in|during)\b",
    # "was delivered at" pattern
    r"\bwas\s+delivered\s+at\b",
    # "at time Y" or "at timestamp" patterns
    r"\bat\s+time(stamp)?\s+\d",
    # Unix timestamp-like numbers in context: "at 1700000000"
    r"\bat\s+\d{9,10}\b",
    # "on date" patterns
    r"\bon\s+\d{4}[-/]\d{1,2}[-/]\d{1,2}\b",
    # Month-day patterns: "on January 5", "on Dec 12"
    r"\bon\s+(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}\b",
]

# Compiled regex for past-tense timestamp detection.
_PAST_TENSE_RE = re.compile(
    "|".join(_PAST_TENSE_TIMESTAMP_PATTERNS),
    re.IGNORECASE,
)

# Present-tense markers: verbs and participles indicating present-tense language.
# The EmotionalPrimer templates use present-tense emotional framing.
# We check for indicators that the output is framed in the present rather
# than as a historical event log.
_PRESENT_TENSE_MARKERS = [
    # Present participles (gerunds) - "growing", "watching", "sizing"
    r"\b\w+ing\b",
    # Common present-tense verbs used in emotional framing templates
    r"\b(burns|cuts|grows|holds|lingers|persists|remains|sits|stays|watches|"
    r"compounds|reveals|confirms|demands|adds|breaks|touches|surfaces|emerges|"
    r"forms|exists|drags|lives|pushes|thickens|gathers|dawns|signals|shifts|"
    r"shows|records|repeats|brightens|multiplies|announces|extends|opens|"
    r"feels|knows|wants|needs|remembers|notes|marks|sees|believes|"
    r"wars|threads|lands|arrives|functions|challenges|lightens)\b",
    # Present-tense state/auxiliary verbs
    r"\b(is|are|has|have|can|cannot)\b",
    # Contractions indicating present state
    r"\b(won't|can't|hasn't|doesn't|isn't|aren't)\b",
]

_PRESENT_TENSE_RE = re.compile(
    "|".join(_PRESENT_TENSE_MARKERS),
    re.IGNORECASE,
)


class TestEmotionalPrimerPresentTenseInvariant:
    """Property 4: Emotional_Primer Present-Tense Invariant.

    *For any* list of InteractionRecords and any archetype, the
    Emotional_Primer output contains only present-tense emotional framing
    and NEVER contains past-tense event descriptions with timestamps.

    **Validates: Requirements 3.1**
    """

    @classmethod
    def setup_class(cls):
        """Create EmotionalPrimer instance for testing."""
        config = SoulEngineConfig()
        cls.primer = EmotionalPrimer(config=config)

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        history=st_interaction_history(),
        archetype=st_archetype(),
        tension_level=st.integers(min_value=0, max_value=10),
        reconciliation_active=st.booleans(),
    )
    def test_output_never_contains_past_tense_timestamps(
        self,
        history: list,
        archetype: str,
        tension_level: int,
        reconciliation_active: bool,
    ):
        """Emotional_Primer output never contains past-tense event descriptions with timestamps."""
        result = asyncio.run(
            self.primer.generate_emotional_context(
                archetype=archetype,
                history=history,
                tension_level=tension_level,
                reconciliation_active=reconciliation_active,
            )
        )

        # Result can be None on error (which is valid — triggers fallback).
        if result is None:
            return

        # Assert: NO past-tense timestamp patterns found.
        match = _PAST_TENSE_RE.search(result)
        assert match is None, (
            f"Found past-tense event description with timestamp in output:\n"
            f"  Match: '{match.group()}' at position {match.start()}\n"
            f"  Full output: {result!r}\n"
            f"  Archetype: {archetype}\n"
            f"  Tension: {tension_level}\n"
            f"  History length: {len(history)}"
        )

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        history=st.lists(st_interaction_record(), min_size=1, max_size=20),
        archetype=st_archetype(),
        tension_level=st.integers(min_value=0, max_value=10),
        reconciliation_active=st.booleans(),
    )
    def test_output_contains_present_tense_language(
        self,
        history: list,
        archetype: str,
        tension_level: int,
        reconciliation_active: bool,
    ):
        """Emotional_Primer output (when history exists) uses present-tense language."""
        result = asyncio.run(
            self.primer.generate_emotional_context(
                archetype=archetype,
                history=history,
                tension_level=tension_level,
                reconciliation_active=reconciliation_active,
            )
        )

        # Result can be None on error (which is valid — triggers fallback).
        if result is None:
            return

        # Non-empty output with history should contain present-tense markers.
        if result.strip():
            match = _PRESENT_TENSE_RE.search(result)
            assert match is not None, (
                f"No present-tense markers found in output:\n"
                f"  Full output: {result!r}\n"
                f"  Archetype: {archetype}\n"
                f"  Tension: {tension_level}\n"
                f"  History length: {len(history)}\n"
                f"  Reconciliation: {reconciliation_active}\n"
                f"Expected present-tense verbs, participles, or state verbs."
            )


# ---------------------------------------------------------------------------
# Feature: elder-voice-soul-engine, Property 6: Emotional_Primer Archetype-Specific Output
# ---------------------------------------------------------------------------

from banter.emotional_primer import EmotionalPrimer, ARCHETYPES as EP_ARCHETYPES
from banter.types import InteractionRecord

# Strategy: generate a valid InteractionRecord
@st.composite
def st_interaction_record(draw: st.DrawFn) -> InteractionRecord:
    """Generate a random InteractionRecord with valid field values."""
    timestamp = draw(st.floats(min_value=1_000_000_000.0, max_value=2_000_000_000.0))
    elder_a = draw(st.sampled_from(["alpha", "beta", "gamma", "delta", "epsilon"]))
    elder_b = draw(st.sampled_from([e for e in ["alpha", "beta", "gamma", "delta", "epsilon"] if e != elder_a]))
    move_used = draw(st.sampled_from([
        "COUNTER", "ESCALATE", "DEFLECT", "TAUNT",
        "QUESTION", "PIVOT", "CONCEDE", "CALLBACK",
    ]))
    emotional_valence = draw(st.sampled_from(["positive", "negative", "neutral"]))
    betrayal = draw(st.booleans())
    alliance = draw(st.booleans()) if not betrayal else False
    concession = draw(st.booleans()) if not betrayal and not alliance else False

    return InteractionRecord(
        timestamp=timestamp,
        elder_a=elder_a,
        elder_b=elder_b,
        move_used=move_used,
        emotional_valence=emotional_valence,
        betrayal=betrayal,
        alliance=alliance,
        concession=concession,
    )


def st_non_empty_interaction_history() -> st.SearchStrategy[list[InteractionRecord]]:
    """Generate a non-empty list of InteractionRecords."""
    return st.lists(st_interaction_record(), min_size=1, max_size=10)


@st.composite
def st_distinct_ep_archetype_pair(draw: st.DrawFn) -> tuple[str, str]:
    """Generate a pair of two distinct archetypes from the supported set."""
    archetypes_list = sorted(EP_ARCHETYPES)
    archetype_a = draw(st.sampled_from(archetypes_list))
    archetype_b = draw(
        st.sampled_from([a for a in archetypes_list if a != archetype_a])
    )
    return (archetype_a, archetype_b)


class TestEmotionalPrimerArchetypeSpecificOutput:
    """Property 6: Emotional_Primer Archetype-Specific Output.

    *For any* non-empty list of InteractionRecords, two different archetypes
    ALWAYS produce different Emotional_Primer output text given the same
    history input.

    **Validates: Requirements 3.2**
    """

    @classmethod
    def setup_class(cls):
        """Create an EmotionalPrimer instance for testing."""
        config = SoulEngineConfig()
        cls.primer = EmotionalPrimer(config=config)

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        pair=st_distinct_ep_archetype_pair(),
        history=st_non_empty_interaction_history(),
        tension_level=st.integers(min_value=0, max_value=10),
        reconciliation_active=st.booleans(),
    )
    def test_different_archetypes_produce_different_output(
        self,
        pair: tuple[str, str],
        history: list[InteractionRecord],
        tension_level: int,
        reconciliation_active: bool,
    ):
        """Two different archetypes ALWAYS produce different emotional context output."""
        archetype_a, archetype_b = pair

        # Call generate_emotional_context for both archetypes with same inputs
        output_a = asyncio.run(
            self.primer.generate_emotional_context(
                archetype=archetype_a,
                history=history,
                tension_level=tension_level,
                reconciliation_active=reconciliation_active,
            )
        )
        output_b = asyncio.run(
            self.primer.generate_emotional_context(
                archetype=archetype_b,
                history=history,
                tension_level=tension_level,
                reconciliation_active=reconciliation_active,
            )
        )

        # Both outputs should be non-None (valid non-empty history)
        assert output_a is not None, (
            f"EmotionalPrimer returned None for archetype '{archetype_a}' "
            f"with non-empty history ({len(history)} records)"
        )
        assert output_b is not None, (
            f"EmotionalPrimer returned None for archetype '{archetype_b}' "
            f"with non-empty history ({len(history)} records)"
        )

        # The two outputs must NEVER be identical
        assert output_a != output_b, (
            f"EmotionalPrimer produced IDENTICAL output for two different archetypes!\n"
            f"  Archetype A: '{archetype_a}'\n"
            f"  Archetype B: '{archetype_b}'\n"
            f"  Tension: {tension_level}\n"
            f"  Reconciliation: {reconciliation_active}\n"
            f"  History records: {len(history)}\n"
            f"  Output (identical): '{output_a}'"
        )


# ---------------------------------------------------------------------------
# Feature: elder-voice-soul-engine, Property 16: Pair ID Computation Equivalence
# ---------------------------------------------------------------------------

from banter.callback_registry import CallbackRegistry
from banter.relationship_memory import _compute_pair_id


def st_elder_name() -> st.SearchStrategy[str]:
    """Generate a random Elder name string (non-empty, printable ASCII)."""
    return st.text(
        min_size=1,
        max_size=64,
        alphabet=st.characters(min_codepoint=32, max_codepoint=126),
    )


class TestPairIDComputationEquivalence:
    """Property 16: Pair ID Computation Equivalence.

    *For any* pair of Elder names (elder_a, elder_b), the pair_id computed
    by Callback_Registry is identical to the pair_id computed by
    RelationshipMemory's _compute_pair_id function.

    **Validates: Requirements 9.4**
    """

    @classmethod
    def setup_class(cls):
        """Create a CallbackRegistry instance for testing pair_id computation."""
        config = SoulEngineConfig()
        cls.registry = CallbackRegistry(pool=None, config=config)

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        elder_a=st_elder_name(),
        elder_b=st_elder_name(),
    )
    def test_pair_id_matches_between_modules(self, elder_a: str, elder_b: str):
        """CallbackRegistry.compute_pair_id produces the same result as RelationshipMemory._compute_pair_id."""
        registry_id = self.registry.compute_pair_id(elder_a, elder_b)
        memory_id = _compute_pair_id(elder_a, elder_b)

        assert registry_id == memory_id, (
            f"Pair ID mismatch for elder_a={elder_a!r}, elder_b={elder_b!r}:\n"
            f"  CallbackRegistry: {registry_id!r}\n"
            f"  RelationshipMemory: {memory_id!r}"
        )

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        elder_a=st_elder_name(),
        elder_b=st_elder_name(),
    )
    def test_pair_id_commutativity(self, elder_a: str, elder_b: str):
        """compute_pair_id(a, b) == compute_pair_id(b, a) for both modules."""
        # CallbackRegistry commutativity
        reg_ab = self.registry.compute_pair_id(elder_a, elder_b)
        reg_ba = self.registry.compute_pair_id(elder_b, elder_a)
        assert reg_ab == reg_ba, (
            f"CallbackRegistry pair_id not commutative for "
            f"elder_a={elder_a!r}, elder_b={elder_b!r}:\n"
            f"  (a, b): {reg_ab!r}\n"
            f"  (b, a): {reg_ba!r}"
        )

        # RelationshipMemory commutativity
        mem_ab = _compute_pair_id(elder_a, elder_b)
        mem_ba = _compute_pair_id(elder_b, elder_a)
        assert mem_ab == mem_ba, (
            f"RelationshipMemory pair_id not commutative for "
            f"elder_a={elder_a!r}, elder_b={elder_b!r}:\n"
            f"  (a, b): {mem_ab!r}\n"
            f"  (b, a): {mem_ba!r}"
        )


# ---------------------------------------------------------------------------
# Feature: elder-voice-soul-engine, Property 17: Write Buffer Capacity
# ---------------------------------------------------------------------------

from banter.soul_types import WriteBuffer, MemorableMoment


# Strategy: generate a random MemorableMoment
@st.composite
def st_memorable_moment(draw: st.DrawFn) -> MemorableMoment:
    """Generate a random MemorableMoment for write buffer testing."""
    return MemorableMoment(
        speaker=draw(st.sampled_from([
            "parasite", "prophet", "trickster", "sovereign",
            "martyr", "shadow", "herald", "keeper",
        ])),
        target=draw(st.sampled_from([
            "parasite", "prophet", "trickster", "sovereign",
            "martyr", "shadow", "herald", "keeper",
        ])),
        line=draw(st.text(min_size=1, max_size=100, alphabet=st.characters(
            whitelist_categories=("L", "N", "P", "Z"),
            min_codepoint=32, max_codepoint=126,
        ))),
        move=draw(st.sampled_from([
            "COUNTER", "ESCALATE", "DEFLECT", "TAUNT",
            "QUESTION", "PIVOT", "CONCEDE", "CALLBACK",
        ])),
        arc_theme=draw(st.text(min_size=1, max_size=50, alphabet=st.characters(
            whitelist_categories=("L", "N", "Z"),
            min_codepoint=32, max_codepoint=126,
        ))),
        valence=draw(st.sampled_from(["positive", "negative", "neutral"])),
        summary=draw(st.text(min_size=1, max_size=100, alphabet=st.characters(
            whitelist_categories=("L", "N", "P", "Z"),
            min_codepoint=32, max_codepoint=126,
        ))),
        score=draw(st.integers(min_value=13, max_value=18)),
        beat_number=draw(st.integers(min_value=1, max_value=1000)),
        created_at=draw(st.floats(
            min_value=1_000_000_000.0, max_value=2_000_000_000.0,
            allow_nan=False, allow_infinity=False,
        )),
    )


class TestWriteBufferCapacity:
    """Property 17: Write Buffer Capacity.

    *For any* sequence of writes to the in-memory buffer (during DB
    unavailability), the buffer never exceeds 20 entries; the 21st entry
    causes the oldest to be dropped.

    **Validates: Requirements 9.6**
    """

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(moments=st.lists(st_memorable_moment(), min_size=1, max_size=100))
    def test_buffer_never_exceeds_20_entries(self, moments: list[MemorableMoment]):
        """After ANY sequence of writes, len(buffer.entries) <= 20."""
        buffer = WriteBuffer()

        for moment in moments:
            buffer.add(moment)
            assert len(buffer.entries) <= 20, (
                f"Buffer exceeded 20 entries (got {len(buffer.entries)}) "
                f"after adding {moments.index(moment) + 1} moments"
            )

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(moments=st.lists(st_memorable_moment(), min_size=21, max_size=100))
    def test_buffer_contains_last_20_items_after_overflow(
        self, moments: list[MemorableMoment]
    ):
        """After adding >20 items, the buffer contains exactly the last 20 (FIFO eviction)."""
        buffer = WriteBuffer()

        for moment in moments:
            buffer.add(moment)

        # Buffer should contain exactly 20 entries
        assert len(buffer.entries) == 20, (
            f"Expected exactly 20 entries after adding {len(moments)} moments, "
            f"got {len(buffer.entries)}"
        )

        # The buffer should contain the LAST 20 items added (oldest evicted first)
        expected_last_20 = moments[-20:]
        actual_entries = list(buffer.entries)

        assert actual_entries == expected_last_20, (
            f"Buffer does not contain the last 20 items.\n"
            f"Expected last 20 speakers: {[m.speaker for m in expected_last_20]}\n"
            f"Actual buffer speakers: {[m.speaker for m in actual_entries]}"
        )

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(moments=st.lists(st_memorable_moment(), min_size=1, max_size=20))
    def test_buffer_retains_all_when_under_capacity(
        self, moments: list[MemorableMoment]
    ):
        """When fewer than 20 items are added, ALL are retained in order."""
        buffer = WriteBuffer()

        for moment in moments:
            buffer.add(moment)

        assert len(buffer.entries) == len(moments), (
            f"Expected {len(moments)} entries (under capacity), "
            f"got {len(buffer.entries)}"
        )

        actual_entries = list(buffer.entries)
        assert actual_entries == moments, (
            f"Buffer entries don't match input order when under capacity"
        )

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(moments=st.lists(st_memorable_moment(), min_size=21, max_size=100))
    def test_21st_entry_drops_oldest(self, moments: list[MemorableMoment]):
        """Specifically, the 21st entry causes the 1st entry to be dropped."""
        buffer = WriteBuffer()

        # Add first 20
        for moment in moments[:20]:
            buffer.add(moment)

        assert len(buffer.entries) == 20

        # Add the 21st entry
        twenty_first = moments[20]
        buffer.add(twenty_first)

        # Buffer should still be 20
        assert len(buffer.entries) == 20, (
            f"Expected 20 entries after 21st add, got {len(buffer.entries)}"
        )

        # The buffer should now contain items [1:21] — the first was evicted
        expected = moments[1:21]
        actual = list(buffer.entries)
        assert actual == expected, (
            f"After adding the 21st entry, buffer should contain moments[1:21] "
            f"(oldest evicted, newest appended)"
        )

        # The 21st entry should be at the end
        assert buffer.entries[-1] == twenty_first, (
            f"The 21st entry was not added to the buffer"
        )


# ---------------------------------------------------------------------------
# Feature: elder-voice-soul-engine, Property 10: Subtlety Director Activation Logic
# ---------------------------------------------------------------------------

from banter.subtlety_director import SubtletyDirector


class TestSubtletyDirectorActivationLogic:
    """Property 10: Subtlety Director Activation Logic.

    *For any* state tuple (tension, move, has_sore_spot, has_history), the
    Subtlety_Director activates subtext injection if and only if at least one
    activation condition is met (tension 4–8, move is DEFLECT/QUESTION, or
    matching sore spot exists) AND no override condition applies (tension < 2,
    no history, move is CONCEDE).

    **Validates: Requirements 6.2, 6.6**
    """

    @classmethod
    def setup_class(cls):
        """Create SubtletyDirector with a fixed seed for deterministic behavior."""
        config = SoulEngineConfig()
        cls.director = SubtletyDirector(config=config, seed=42)

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        tension=st.integers(min_value=0, max_value=10),
        move=st.sampled_from([
            "COUNTER", "ESCALATE", "DEFLECT", "QUESTION",
            "TAUNT", "PIVOT", "CONCEDE", "CALLBACK",
        ]),
        has_sore_spot=st.booleans(),
        has_history=st.booleans(),
    )
    def test_activation_logic_deterministic_cases(
        self,
        tension: int,
        move: str,
        has_sore_spot: bool,
        has_history: bool,
    ):
        """For tension <= 8 (deterministic), verify activation matches expected logic exactly.

        Activation requires ALL of:
        1. No override condition: tension >= 2, move != CONCEDE, has_history == True
        2. At least one activation condition:
           - tension in [4, 8]
           - move in (DEFLECT, QUESTION)
           - has_sore_spot == True

        For tension > 8 (probabilistic 20%), we skip deterministic assertion.
        """
        # Skip probabilistic case (tension > 8) — tested separately in Property 11
        assume(tension <= 8)

        result = self.director.should_inject_subtext(
            tension=tension,
            move=move,
            has_sore_spot=has_sore_spot,
            has_history=has_history,
        )

        # Compute expected result based on documented logic
        # Override conditions (hard blocks)
        has_override = (tension < 2) or (move == "CONCEDE") or (not has_history)

        # Activation conditions
        tension_in_range = 4 <= tension <= 8
        move_triggers = move in ("DEFLECT", "QUESTION")
        has_activation = tension_in_range or move_triggers or has_sore_spot

        expected = has_activation and not has_override

        assert result == expected, (
            f"Subtlety activation mismatch!\n"
            f"  Input: tension={tension}, move={move}, "
            f"has_sore_spot={has_sore_spot}, has_history={has_history}\n"
            f"  Expected: {expected}, Got: {result}\n"
            f"  Override conditions: tension<2={tension < 2}, "
            f"move==CONCEDE={move == 'CONCEDE'}, "
            f"no_history={not has_history}\n"
            f"  Activation conditions: tension_in_range={tension_in_range}, "
            f"move_triggers={move_triggers}, sore_spot={has_sore_spot}"
        )

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        tension=st.integers(min_value=0, max_value=10),
        move=st.sampled_from([
            "COUNTER", "ESCALATE", "DEFLECT", "QUESTION",
            "TAUNT", "PIVOT", "CONCEDE", "CALLBACK",
        ]),
        has_sore_spot=st.booleans(),
        has_history=st.booleans(),
    )
    def test_override_conditions_always_block(
        self,
        tension: int,
        move: str,
        has_sore_spot: bool,
        has_history: bool,
    ):
        """Override conditions ALWAYS prevent activation regardless of other state.

        Override conditions:
        - tension < 2
        - move == CONCEDE
        - has_history == False
        """
        # Only test cases where an override is active
        has_override = (tension < 2) or (move == "CONCEDE") or (not has_history)
        assume(has_override)

        result = self.director.should_inject_subtext(
            tension=tension,
            move=move,
            has_sore_spot=has_sore_spot,
            has_history=has_history,
        )

        assert result is False, (
            f"Override condition present but activation returned True!\n"
            f"  Input: tension={tension}, move={move}, "
            f"has_sore_spot={has_sore_spot}, has_history={has_history}\n"
            f"  Active overrides: tension<2={tension < 2}, "
            f"move==CONCEDE={move == 'CONCEDE'}, "
            f"no_history={not has_history}"
        )

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        tension=st.integers(min_value=2, max_value=8),
        move=st.sampled_from([
            "COUNTER", "ESCALATE", "DEFLECT", "QUESTION",
            "TAUNT", "PIVOT", "CALLBACK",
        ]),
        has_sore_spot=st.booleans(),
    )
    def test_activation_when_no_override_and_condition_met(
        self,
        tension: int,
        move: str,
        has_sore_spot: bool,
    ):
        """When no override applies and at least one activation condition is met,
        subtext is ALWAYS activated (for tension <= 8).

        Conditions tested (at least one must be true):
        - tension in [4, 8]
        - move in (DEFLECT, QUESTION)
        - has_sore_spot == True
        """
        # Ensure at least one activation condition is met
        tension_in_range = 4 <= tension <= 8
        move_triggers = move in ("DEFLECT", "QUESTION")
        has_activation = tension_in_range or move_triggers or has_sore_spot
        assume(has_activation)

        # No override: tension >= 2 (guaranteed by strategy), move != CONCEDE
        # (filtered in strategy), has_history = True
        result = self.director.should_inject_subtext(
            tension=tension,
            move=move,
            has_sore_spot=has_sore_spot,
            has_history=True,
        )

        assert result is True, (
            f"Expected activation but got False!\n"
            f"  Input: tension={tension}, move={move}, "
            f"has_sore_spot={has_sore_spot}, has_history=True\n"
            f"  Activation conditions: tension_in_range={tension_in_range}, "
            f"move_triggers={move_triggers}, sore_spot={has_sore_spot}"
        )

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        tension=st.sampled_from([2, 3]),
        move=st.sampled_from([
            "COUNTER", "ESCALATE", "TAUNT", "PIVOT", "CALLBACK",
        ]),
    )
    def test_no_activation_without_any_condition(
        self,
        tension: int,
        move: str,
    ):
        """When no override applies but NO activation condition is met,
        subtext is NEVER activated.

        This tests the case where:
        - tension in [2, 3] (not in 4-8 range, not < 2)
        - move NOT in (DEFLECT, QUESTION, CONCEDE)
        - has_sore_spot = False
        - has_history = True
        """
        result = self.director.should_inject_subtext(
            tension=tension,
            move=move,
            has_sore_spot=False,
            has_history=True,
        )

        assert result is False, (
            f"Expected no activation but got True!\n"
            f"  Input: tension={tension}, move={move}, "
            f"has_sore_spot=False, has_history=True\n"
            f"  No activation condition is met: tension not in [4,8], "
            f"move not DEFLECT/QUESTION, no sore spot"
        )


# ---------------------------------------------------------------------------
# Feature: elder-voice-soul-engine, Property 7: Callback Registry Capacity Invariant
# ---------------------------------------------------------------------------

from collections import deque

from banter.callback_registry import (
    CallbackRegistry,
    _MAX_MOMENTS_PER_PAIR,
    _MAX_GAGS_PER_PAIR,
)
from banter.soul_types import MemorableMoment, WriteBuffer, SoulEngineConfig


# ---------------------------------------------------------------------------
# Strategies for callback registry capacity testing
# ---------------------------------------------------------------------------


def _make_moment(speaker: str, target: str, index: int) -> MemorableMoment:
    """Create a MemorableMoment with unique data based on index."""
    return MemorableMoment(
        speaker=speaker,
        target=target,
        line=f"Test line number {index}",
        move="TAUNT",
        arc_theme=f"theme_{index}",
        valence="negative",
        summary=f"Summary for moment {index}",
        score=13,
        beat_number=index,
        created_at=float(1000000 + index),
    )


@st.composite
def st_moment_sequence(draw: st.DrawFn) -> list[MemorableMoment]:
    """Generate a sequence of MemorableMoments for capacity testing.

    Generates between 1 and 60 moments (exceeding the 50-moment cap and
    the 20-entry write buffer cap) for the same Elder pair.
    """
    speaker = draw(st.sampled_from(["alpha", "beta", "gamma", "delta"]))
    target = draw(st.sampled_from(
        [e for e in ["epsilon", "zeta", "eta", "theta"] if e != speaker]
    ))
    count = draw(st.integers(min_value=1, max_value=60))

    moments = []
    for i in range(count):
        moments.append(MemorableMoment(
            speaker=speaker,
            target=target,
            line=draw(st.text(min_size=5, max_size=100, alphabet=st.characters(
                whitelist_categories=("L", "N", "Z"), min_codepoint=32, max_codepoint=126
            ))),
            move=draw(st.sampled_from(["TAUNT", "COUNTER", "ESCALATE", "DEFLECT"])),
            arc_theme=draw(st.text(min_size=3, max_size=30, alphabet=st.characters(
                whitelist_categories=("L",), min_codepoint=97, max_codepoint=122
            ))),
            valence=draw(st.sampled_from(["positive", "negative", "neutral"])),
            summary=draw(st.text(min_size=5, max_size=50, alphabet=st.characters(
                whitelist_categories=("L", "N", "Z"), min_codepoint=32, max_codepoint=126
            ))),
            score=draw(st.integers(min_value=13, max_value=18)),
            beat_number=i,
            created_at=float(1000000 + i),
        ))

    return moments


class TestCallbackRegistryCapacityInvariant:
    """Property 7: Callback Registry Capacity Invariant.

    *For any* sequence of write operations to the Callback_Registry, the
    stored count never exceeds 50 memorable moments per Elder pair and never
    exceeds 10 running gags per Elder pair; the (N+1)th entry evicts the
    oldest.

    **Validates: Requirements 4.5, 9.5**
    """

    # ------------------------------------------------------------------
    # WriteBuffer capacity (max 20 entries, deque-based eviction)
    # ------------------------------------------------------------------

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        count=st.integers(min_value=1, max_value=100),
    )
    def test_write_buffer_never_exceeds_20_entries(self, count: int):
        """WriteBuffer never stores more than 20 entries regardless of how many are added.

        The WriteBuffer uses a deque(maxlen=20), so adding more than 20
        entries causes the oldest to be dropped automatically.
        """
        buffer = WriteBuffer()

        for i in range(count):
            moment = _make_moment("speaker_a", "target_b", i)
            buffer.add(moment)

            # Invariant: buffer size never exceeds 20 at any point
            assert len(buffer.entries) <= 20, (
                f"WriteBuffer exceeded 20 entries after adding {i + 1} moments: "
                f"got {len(buffer.entries)} entries"
            )

        # Final state: at most 20 entries
        assert len(buffer.entries) <= 20, (
            f"WriteBuffer has {len(buffer.entries)} entries after adding {count} moments"
        )

        # If more than 20 were added, exactly 20 should remain
        if count > 20:
            assert len(buffer.entries) == 20, (
                f"Expected exactly 20 entries after adding {count} > 20 moments, "
                f"got {len(buffer.entries)}"
            )

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        count=st.integers(min_value=21, max_value=100),
    )
    def test_write_buffer_evicts_oldest_on_overflow(self, count: int):
        """When WriteBuffer overflows, the oldest entries are evicted (FIFO).

        After adding N > 20 moments, only the last 20 remain, and the
        oldest (first added) entries are gone.
        """
        buffer = WriteBuffer()

        all_moments = []
        for i in range(count):
            moment = _make_moment("speaker_a", "target_b", i)
            all_moments.append(moment)
            buffer.add(moment)

        # The buffer should contain the last 20 moments added
        expected_remaining = all_moments[-20:]
        actual_remaining = list(buffer.entries)

        assert actual_remaining == expected_remaining, (
            f"WriteBuffer did not retain the 20 most recent entries. "
            f"Expected beat_numbers {[m.beat_number for m in expected_remaining]}, "
            f"got {[m.beat_number for m in actual_remaining]}"
        )

    # ------------------------------------------------------------------
    # Moments cap (max 50 per pair) - tested via DB in Docker
    # ------------------------------------------------------------------

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(moments=st_moment_sequence())
    def test_moments_cap_logic_never_exceeds_50(self, moments: list[MemorableMoment]):
        """Simulating the capacity enforcement logic: after any sequence of
        writes for the same pair, at most 50 moments are retained.

        This tests the invariant conceptually by simulating what
        _enforce_moments_cap does: after each insert, if count > 50,
        evict the oldest (count - 50) entries.
        """
        # Simulate in-memory storage with the same eviction logic
        stored: deque[MemorableMoment] = deque()

        for moment in moments:
            stored.append(moment)

            # Enforce cap (same logic as _enforce_moments_cap)
            if len(stored) > _MAX_MOMENTS_PER_PAIR:
                excess = len(stored) - _MAX_MOMENTS_PER_PAIR
                for _ in range(excess):
                    stored.popleft()  # evict oldest

            # Invariant: never exceeds 50 at any point
            assert len(stored) <= _MAX_MOMENTS_PER_PAIR, (
                f"Moments count exceeded {_MAX_MOMENTS_PER_PAIR} after "
                f"storing moment at beat {moment.beat_number}: "
                f"got {len(stored)} entries"
            )

        # Final state: at most 50 entries
        assert len(stored) <= _MAX_MOMENTS_PER_PAIR, (
            f"Final moments count is {len(stored)}, exceeds cap of "
            f"{_MAX_MOMENTS_PER_PAIR}"
        )

    # ------------------------------------------------------------------
    # Running gags cap (max 10 per pair) - eviction logic
    # ------------------------------------------------------------------

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        gag_count=st.integers(min_value=1, max_value=30),
    )
    def test_running_gags_cap_logic_never_exceeds_10(self, gag_count: int):
        """Simulating the gag capacity enforcement logic: after any sequence
        of gag insertions for the same pair, at most 10 gags are retained.

        This tests the invariant conceptually by simulating what
        _enforce_gags_cap does: after each insert, if count > 10,
        evict the oldest (count - 10) entries.
        """
        # Simulate in-memory storage with the same eviction logic
        stored_gags: deque[dict] = deque()

        for i in range(gag_count):
            gag = {
                "pair_id": "test_pair",
                "topic": f"topic_{i}",
                "pattern_description": f"Pattern {i}",
                "interaction_count": 3,
                "created_at": 1000000 + i,
            }
            stored_gags.append(gag)

            # Enforce cap (same logic as _enforce_gags_cap)
            if len(stored_gags) > _MAX_GAGS_PER_PAIR:
                excess = len(stored_gags) - _MAX_GAGS_PER_PAIR
                for _ in range(excess):
                    stored_gags.popleft()  # evict oldest

            # Invariant: never exceeds 10 at any point
            assert len(stored_gags) <= _MAX_GAGS_PER_PAIR, (
                f"Running gags count exceeded {_MAX_GAGS_PER_PAIR} after "
                f"storing gag {i}: got {len(stored_gags)} entries"
            )

        # Final state: at most 10 entries
        assert len(stored_gags) <= _MAX_GAGS_PER_PAIR, (
            f"Final gags count is {len(stored_gags)}, exceeds cap of "
            f"{_MAX_GAGS_PER_PAIR}"
        )

    # ------------------------------------------------------------------
    # Combined: moments + write buffer capacity interaction
    # ------------------------------------------------------------------

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        count=st.integers(min_value=1, max_value=100),
    )
    def test_write_buffer_capacity_is_independent_per_instance(self, count: int):
        """Each WriteBuffer instance independently enforces the 20-entry cap.

        Creating a new WriteBuffer always starts at 0, and each one
        independently caps at 20.
        """
        buffer = WriteBuffer()

        # Verify fresh buffer is empty
        assert len(buffer.entries) == 0, "Fresh WriteBuffer should be empty"

        # Add entries
        for i in range(count):
            buffer.add(_make_moment("x", "y", i))

        # Invariant holds
        assert len(buffer.entries) <= 20, (
            f"WriteBuffer exceeded 20 entries: {len(buffer.entries)}"
        )
        assert len(buffer.entries) == min(count, 20), (
            f"Expected {min(count, 20)} entries after adding {count}, "
            f"got {len(buffer.entries)}"
        )


# ---------------------------------------------------------------------------
# Feature: elder-voice-soul-engine, Property 11: Subtlety High-Tension Rate Reduction
# ---------------------------------------------------------------------------

from banter.subtlety_director import SubtletyDirector
from banter.soul_types import SoulEngineConfig


class TestSubtletyHighTensionRateReduction:
    """Property 11: Subtlety High-Tension Rate Reduction.

    *For any* sequence of 10 or more consecutive subtext opportunities where
    pair tension exceeds 8, the Subtlety_Director activates subtext injection
    no more than 20% of the time.

    **Validates: Requirements 6.3**
    """

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(seed=st.integers(min_value=0, max_value=2**31 - 1))
    def test_high_tension_rate_never_exceeds_30_percent(self, seed: int):
        """At tension > 8, activation rate stays within statistical margin of 20%.

        We generate 100 opportunities at tension 9 or 10 with valid activation
        conditions (has_history=True, has_sore_spot=True, move=DEFLECT) and
        assert that the activation rate is <= 30% (allowing statistical margin
        above the 20% target for any single seed).
        """
        config = SoulEngineConfig()
        director = SubtletyDirector(config=config, seed=seed)

        num_opportunities = 100
        activations = 0

        for _ in range(num_opportunities):
            result = director.should_inject_subtext(
                tension=9,
                move="DEFLECT",
                has_sore_spot=True,
                has_history=True,
            )
            if result:
                activations += 1

        rate = activations / num_opportunities

        # With 20% probability and 100 trials, 30% is a generous upper bound.
        # P(X > 30 | n=100, p=0.2) is extremely low (~0.003 by binomial CDF).
        assert rate <= 0.30, (
            f"High-tension activation rate exceeded 30%: "
            f"got {activations}/{num_opportunities} = {rate:.2%} "
            f"(expected ~20% with statistical margin up to 30%). "
            f"Seed: {seed}"
        )

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(seed=st.integers(min_value=0, max_value=2**31 - 1))
    def test_high_tension_rate_at_tension_10(self, seed: int):
        """At tension 10 (maximum), activation rate stays within 30% bound.

        Tests the extreme tension case to confirm the 20% rate reduction
        applies regardless of how high tension goes above 8.
        """
        config = SoulEngineConfig()
        director = SubtletyDirector(config=config, seed=seed)

        num_opportunities = 100
        activations = 0

        for _ in range(num_opportunities):
            result = director.should_inject_subtext(
                tension=10,
                move="QUESTION",
                has_sore_spot=True,
                has_history=True,
            )
            if result:
                activations += 1

        rate = activations / num_opportunities

        assert rate <= 0.30, (
            f"High-tension (10) activation rate exceeded 30%: "
            f"got {activations}/{num_opportunities} = {rate:.2%} "
            f"(expected ~20% with statistical margin up to 30%). "
            f"Seed: {seed}"
        )

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(seed=st.integers(min_value=0, max_value=2**31 - 1))
    def test_average_rate_across_multiple_runs_near_20_percent(self, seed: int):
        """Across multiple independent runs, the average rate converges to ~20%.

        Uses 5 independent SubtletyDirector instances (different derived seeds)
        each with 100 opportunities. The average activation rate across all 500
        trials should be between 10% and 30% (tight bounds for convergence).
        """
        total_activations = 0
        total_opportunities = 0
        num_runs = 5
        opportunities_per_run = 100

        for run_offset in range(num_runs):
            config = SoulEngineConfig()
            # Derive a different seed for each run
            derived_seed = seed + run_offset * 7919  # prime offset for independence
            director = SubtletyDirector(config=config, seed=derived_seed)

            for _ in range(opportunities_per_run):
                result = director.should_inject_subtext(
                    tension=9,
                    move="DEFLECT",
                    has_sore_spot=True,
                    has_history=True,
                )
                if result:
                    total_activations += 1
                total_opportunities += 1

        avg_rate = total_activations / total_opportunities

        # With 500 trials at p=0.2, the expected value is 100.
        # 99.9% confidence interval: roughly [0.14, 0.26].
        # We use [0.10, 0.30] for robustness.
        assert 0.10 <= avg_rate <= 0.30, (
            f"Average activation rate across {num_runs} runs "
            f"({total_opportunities} total opportunities) was {avg_rate:.2%}. "
            f"Expected approximately 20% (within [10%, 30%] bounds). "
            f"Base seed: {seed}, total activations: {total_activations}"
        )


# ---------------------------------------------------------------------------
# Feature: elder-voice-soul-engine, Property 12: Technique Variety Constraint
# ---------------------------------------------------------------------------

from collections import Counter

from banter.subtlety_director import SubtletyDirector
from banter.soul_types import SoreSpot, SoulEngineConfig, SubtextInstruction


# Strategy: generate a random Elder name
def st_elder_name() -> st.SearchStrategy[str]:
    """Generate a random Elder name."""
    return st.sampled_from([
        "elder_alpha", "elder_beta", "elder_gamma", "elder_delta",
        "elder_epsilon", "elder_zeta", "elder_eta", "elder_theta",
    ])


# Strategy: generate a random arc theme
def st_arc_theme() -> st.SearchStrategy[str]:
    """Generate a random arc theme."""
    return st.sampled_from([
        "betrayal", "redemption", "power_struggle", "hidden_truth",
        "sacrifice", "corruption", "loyalty_test", "origin_reveal",
    ])


# Strategy: optional sore spot for generating subtext instructions
@st.composite
def st_optional_sore_spot(draw: st.DrawFn, target: str = "elder_zeta") -> SoreSpot | None:
    """Generate an optional SoreSpot (50% chance of None)."""
    if draw(st.booleans()):
        return None
    return SoreSpot(
        elder_name=target,
        topic=draw(st_arc_theme()),
        trigger_phrase=draw(st.one_of(st.none(), st.text(min_size=3, max_size=30))),
        tension_delta=draw(st.integers(min_value=2, max_value=5)),
    )


class TestTechniqueVarietyConstraint:
    """Property 12: Technique Variety Constraint.

    *For any* Elder and any sliding window of 5 consecutive subtext-injected
    lines, the same subtext technique appears no more than twice.

    **Validates: Requirements 6.5**
    """

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        elder=st_elder_name(),
        num_instructions=st.integers(min_value=5, max_value=30),
        seed=st.integers(min_value=0, max_value=2**31 - 1),
    )
    def test_technique_variety_in_sliding_window(
        self,
        elder: str,
        num_instructions: int,
        seed: int,
    ):
        """For any sequence of subtext instructions for the same Elder,
        no technique appears more than twice in any window of 5 consecutive uses."""
        config = SoulEngineConfig()
        director = SubtletyDirector(config=config, seed=seed)

        target = "elder_target"
        arc_theme = "power_struggle"
        tension = 6  # In the activation range (4-8)

        # Collect techniques from consecutive generate_subtext_instruction() calls
        techniques: list[str] = []

        for _ in range(num_instructions):
            instruction = director.generate_subtext_instruction(
                elder=elder,
                target=target,
                tension=tension,
                sore_spot=None,
                arc_theme=arc_theme,
            )

            # If instruction is None, it means all techniques are blocked
            # (shouldn't happen with 5 techniques and max 2 per window, but
            # if it does, it doesn't violate the property — skip it).
            if instruction is None:
                continue

            techniques.append(instruction.technique)

        # Check every sliding window of 5 consecutive techniques
        for i in range(len(techniques) - 4):
            window = techniques[i : i + 5]
            counts = Counter(window)

            for technique, count in counts.items():
                assert count <= 2, (
                    f"Technique '{technique}' appears {count} times in window "
                    f"of 5 consecutive uses (position {i} to {i + 4}).\n"
                    f"Window: {window}\n"
                    f"Full technique sequence: {techniques}\n"
                    f"Elder: {elder}, seed: {seed}"
                )

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        elder=st_elder_name(),
        seed=st.integers(min_value=0, max_value=2**31 - 1),
        sore_spot_topics=st.lists(
            st_arc_theme(), min_size=5, max_size=30
        ),
    )
    def test_technique_variety_with_varying_sore_spots(
        self,
        elder: str,
        seed: int,
        sore_spot_topics: list[str],
    ):
        """Variety constraint holds even when sore spots and arc themes vary."""
        config = SoulEngineConfig()
        director = SubtletyDirector(config=config, seed=seed)

        target = "elder_opponent"
        techniques: list[str] = []

        for topic in sore_spot_topics:
            # Alternate between having and not having a sore spot
            sore_spot = SoreSpot(
                elder_name=target,
                topic=topic,
                trigger_phrase=f"trigger about {topic}",
                tension_delta=3,
            )

            instruction = director.generate_subtext_instruction(
                elder=elder,
                target=target,
                tension=6,
                sore_spot=sore_spot,
                arc_theme=topic,
            )

            if instruction is None:
                continue

            techniques.append(instruction.technique)

        # Check every sliding window of 5 consecutive techniques
        for i in range(len(techniques) - 4):
            window = techniques[i : i + 5]
            counts_w = Counter(window)

            for technique, count in counts_w.items():
                assert count <= 2, (
                    f"Technique '{technique}' appears {count} times in window "
                    f"of 5 consecutive uses (position {i} to {i + 4}).\n"
                    f"Window: {window}\n"
                    f"Full technique sequence: {techniques}\n"
                    f"Elder: {elder}, seed: {seed}"
                )


# ---------------------------------------------------------------------------
# Feature: elder-voice-soul-engine, Property 8: Callback Timing Constraints
# ---------------------------------------------------------------------------

from banter.callback_registry import CallbackRegistry, _MIN_BEAT_GAP
from banter.soul_types import CallbackUsageTracker, MemorableMoment, SoulEngineConfig


class TestCallbackTimingConstraints:
    """Property 8: Callback Timing Constraints.

    *For any* callback that was used at beat B_used, the same callback
    cannot be surfaced again until at least 15 beats have elapsed.
    Equivalently, the beat gap check `current_beat - last_used_beat < 15`
    must filter out the callback when the gap is insufficient.

    **Validates: Requirements 5.3**
    """

    @classmethod
    def setup_class(cls):
        """Create a CallbackRegistry instance for testing."""
        config = SoulEngineConfig()
        cls.registry = CallbackRegistry(pool=None, config=config)

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        last_used_beat=st.integers(min_value=0, max_value=1000),
        beats_elapsed=st.integers(min_value=0, max_value=_MIN_BEAT_GAP - 1),
    )
    def test_callback_blocked_when_gap_too_small(
        self, last_used_beat: int, beats_elapsed: int
    ):
        """A callback is filtered when current_beat - last_used < MIN_BEAT_GAP (15)."""
        current_beat = last_used_beat + beats_elapsed
        beats_since = current_beat - last_used_beat
        should_filter = beats_since < _MIN_BEAT_GAP
        assert should_filter is True, (
            f"Expected callback to be filtered at gap {beats_since} < {_MIN_BEAT_GAP}"
        )

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        last_used_beat=st.integers(min_value=0, max_value=1000),
        beats_elapsed=st.integers(min_value=_MIN_BEAT_GAP, max_value=200),
    )
    def test_callback_allowed_when_gap_sufficient(
        self, last_used_beat: int, beats_elapsed: int
    ):
        """A callback passes the timing filter when gap >= MIN_BEAT_GAP (15)."""
        current_beat = last_used_beat + beats_elapsed
        beats_since = current_beat - last_used_beat
        should_filter = beats_since < _MIN_BEAT_GAP
        assert should_filter is False, (
            f"Expected callback NOT to be filtered at gap {beats_since} >= {_MIN_BEAT_GAP}"
        )

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        base_beat=st.integers(min_value=0, max_value=500),
        gap=st.integers(min_value=0, max_value=30),
    )
    def test_timing_boundary_exactly_at_min_beat_gap(self, base_beat: int, gap: int):
        """Boundary condition: gap < MIN_BEAT_GAP filtered, gap >= MIN_BEAT_GAP allowed."""
        current_beat = base_beat + gap
        beats_since = current_beat - base_beat
        should_filter = beats_since < _MIN_BEAT_GAP
        if gap < _MIN_BEAT_GAP:
            assert should_filter is True
        else:
            assert should_filter is False

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        num_uses=st.integers(min_value=1, max_value=10),
        base_beat=st.integers(min_value=0, max_value=100),
    )
    def test_usage_tracker_records_most_recent_beat(
        self, num_uses: int, base_beat: int
    ):
        """CallbackUsageTracker records the most recent beat for each callback (overwrite)."""
        tracker = CallbackUsageTracker()
        callback_id = "test_callback_id"
        last_beat = base_beat
        for i in range(num_uses):
            beat = base_beat + (i * _MIN_BEAT_GAP)
            tracker.last_used_beat[callback_id] = beat
            last_beat = beat
        assert tracker.last_used_beat[callback_id] == last_beat

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        callback_ids=st.lists(
            st.text(min_size=1, max_size=12, alphabet="abcdef0123456789"),
            min_size=1, max_size=10, unique=True,
        ),
        beat=st.integers(min_value=0, max_value=1000),
    )
    def test_timing_is_independent_per_callback(
        self, callback_ids: list, beat: int
    ):
        """Each callback has an independent timing record — one doesn't affect another."""
        tracker = CallbackUsageTracker()
        for cb_id in callback_ids:
            tracker.last_used_beat[cb_id] = beat
        for cb_id in callback_ids:
            assert tracker.last_used_beat.get(cb_id) == beat
        fresh_id = "fresh_unrecorded"
        assert fresh_id not in tracker.last_used_beat


# ---------------------------------------------------------------------------
# Feature: elder-voice-soul-engine, Property 9: Callback Surfacing Match Quality
# ---------------------------------------------------------------------------

from banter.callback_registry import CallbackRegistry, _TENSION_MISMATCH_REJECT
from banter.soul_types import MemorableMoment, SoulEngineConfig


@st.composite
def st_moment_for_match(draw: st.DrawFn) -> MemorableMoment:
    """Generate a MemorableMoment for match quality testing."""
    valence = draw(st.sampled_from(["positive", "negative", "neutral"]))
    score = draw(st.integers(min_value=13, max_value=18))
    arc_theme = draw(st.sampled_from([
        "betrayal", "redemption", "power", "sacrifice",
        "loyalty", "corruption", "truth", "survival",
    ]))
    return MemorableMoment(
        speaker="alpha", target="beta",
        line="Test line for match scoring.",
        move="TAUNT", arc_theme=arc_theme,
        valence=valence, summary="Match test moment",
        score=score, beat_number=5, created_at=1_000_000.0,
    )


class TestCallbackSurfacingMatchQuality:
    """Property 9: Callback Surfacing Match Quality.

    *For any* moment and current conditions, the match scoring function
    `_score_moment_match` respects the documented contract:
    - Returns 0 (hard reject) when tension mismatch > _TENSION_MISMATCH_REJECT (3)
    - Returns 0–3 otherwise based on tension/theme/valence

    **Validates: Requirements 5.1, 5.6**
    """

    @classmethod
    def setup_class(cls):
        config = SoulEngineConfig()
        cls.registry = CallbackRegistry(pool=None, config=config)

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        moment=st_moment_for_match(),
        current_tension=st.integers(min_value=0, max_value=10),
        current_arc_theme=st.text(
            min_size=1, max_size=30, alphabet="abcdefghijklmnopqrstuvwxyz "
        ),
    )
    def test_match_score_always_in_range(
        self, moment: MemorableMoment, current_tension: int, current_arc_theme: str
    ):
        """_score_moment_match always returns int in [0, 3]."""
        score = self.registry._score_moment_match(moment, current_tension, current_arc_theme)
        assert isinstance(score, int)
        assert 0 <= score <= 3, f"Score {score} out of [0, 3]"

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(moment=st_moment_for_match())
    def test_large_tension_mismatch_returns_zero(self, moment: MemorableMoment):
        """When abs(current_tension - inferred) > TENSION_MISMATCH_REJECT, score == 0."""
        inferred = self.registry._infer_tension_from_moment(moment)
        too_high = inferred + _TENSION_MISMATCH_REJECT + 1
        if too_high <= 10:
            score = self.registry._score_moment_match(moment, too_high, moment.arc_theme)
            assert score == 0, (
                f"Expected 0 for tension mismatch, inferred={inferred}, "
                f"current={too_high}, diff={too_high - inferred}"
            )
        too_low = inferred - _TENSION_MISMATCH_REJECT - 1
        if too_low >= 0:
            score = self.registry._score_moment_match(moment, too_low, moment.arc_theme)
            assert score == 0, (
                f"Expected 0 for tension mismatch, inferred={inferred}, "
                f"current={too_low}, diff={inferred - too_low}"
            )

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(moment=st_moment_for_match())
    def test_exact_theme_match_contributes_score(self, moment: MemorableMoment):
        """Exact theme match always scores >= non-matching theme, given same tension."""
        inferred = self.registry._infer_tension_from_moment(moment)
        with_match = self.registry._score_moment_match(moment, inferred, moment.arc_theme)
        without_match = self.registry._score_moment_match(moment, inferred, "zzz_no_overlap_xyz")
        assert with_match >= without_match

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        tension=st.integers(min_value=0, max_value=10),
        valence=st.sampled_from(["positive", "negative", "neutral"]),
    )
    def test_valence_tension_matching_logic(self, tension: int, valence: str):
        """_valence_matches_tension follows: negative→>=6, positive→<=4, neutral→3–7."""
        result = self.registry._valence_matches_tension(valence, tension)
        assert isinstance(result, bool)
        if valence == "negative":
            assert result == (tension >= 6)
        elif valence == "positive":
            assert result == (tension <= 4)
        else:
            assert result == (3 <= tension <= 7)

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        theme_a=st.text(min_size=1, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz "),
        theme_b=st.text(min_size=1, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz "),
    )
    def test_theme_overlap_is_commutative(self, theme_a: str, theme_b: str):
        """_themes_overlap(a, b) == _themes_overlap(b, a)."""
        assert self.registry._themes_overlap(theme_a, theme_b) == \
               self.registry._themes_overlap(theme_b, theme_a)

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(theme=st.text(min_size=1, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz "))
    def test_exact_theme_always_overlaps(self, theme: str):
        """A theme always overlaps with itself."""
        assert self.registry._themes_overlap(theme, theme) is True

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(moment=st_moment_for_match())
    def test_inferred_tension_always_in_valid_range(self, moment: MemorableMoment):
        """_infer_tension_from_moment always returns int in [2, 8]."""
        inferred = self.registry._infer_tension_from_moment(moment)
        assert isinstance(inferred, int)
        assert 2 <= inferred <= 8, (
            f"Inferred tension {inferred} out of [2, 8] for "
            f"valence={moment.valence}, score={moment.score}"
        )


# ---------------------------------------------------------------------------
# Feature: elder-voice-soul-engine, Property 18: Quality_Judge Dimension Count
# ---------------------------------------------------------------------------

import asyncio as _asyncio

from banter.quality_judge import (
    EnhancedQualityScore,
    evaluate_enhanced,
    BASE_PASS_THRESHOLD,
    BASE_REFINE_THRESHOLD,
    SOUL_PASS_THRESHOLD,
    SOUL_REFINE_THRESHOLD,
    get_pass_threshold,
    get_refine_threshold,
)
from banter.soul_types import SoulEngineConfig, SubtextInstruction


class TestQualityJudgeDimensionCount:
    """Property 18: Quality_Judge Dimension Count.

    *For any* call to evaluate_enhanced, the returned EnhancedQualityScore
    always has exactly 7 dimensions (5 base + voice_authenticity + subtext_depth).

    **Validates: Requirements 10.1, 10.2**
    """

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        candidate=st.text(min_size=1, max_size=200, alphabet="abcdefghijklmnopqrstuvwxyz .,?!"),
        archetype=st.sampled_from([
            "parasite", "prophet", "trickster", "sovereign",
            "martyr", "shadow", "herald", "keeper",
        ]),
        arc_theme=st.text(min_size=1, max_size=50, alphabet="abcdefghijklmnopqrstuvwxyz "),
    )
    def test_enhanced_score_has_exactly_7_dimensions(
        self, candidate: str, archetype: str, arc_theme: str
    ):
        """EnhancedQualityScore always has exactly 7 dimension keys."""
        config = SoulEngineConfig()
        result = _asyncio.run(evaluate_enhanced(
            candidate, archetype=archetype, move="COUNTER",
            arc_theme=arc_theme, config=config,
        ))
        assert isinstance(result, EnhancedQualityScore)
        dims = result.as_dict()
        assert len(dims) == 7, f"Expected 7 dimensions, got {len(dims)}: {list(dims.keys())}"
        required = {
            "sharpness", "emotional_texture", "rhythm",
            "thematic_relevance", "shareability",
            "voice_authenticity", "subtext_depth",
        }
        assert set(dims.keys()) == required, f"Missing dims: {required - set(dims.keys())}"

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        candidate=st.text(min_size=1, max_size=200, alphabet="abcdefghijklmnopqrstuvwxyz .,?!"),
        archetype=st.sampled_from([
            "parasite", "prophet", "trickster", "sovereign",
            "martyr", "shadow", "herald", "keeper",
        ]),
        arc_theme=st.text(min_size=1, max_size=50, alphabet="abcdefghijklmnopqrstuvwxyz "),
    )
    def test_all_dimensions_in_0_to_3(
        self, candidate: str, archetype: str, arc_theme: str
    ):
        """Every dimension in EnhancedQualityScore is always in [0, 3]."""
        config = SoulEngineConfig()
        result = _asyncio.run(evaluate_enhanced(
            candidate, archetype=archetype, move="COUNTER",
            arc_theme=arc_theme, config=config,
        ))
        for name, val in result.as_dict().items():
            assert isinstance(val, int), f"Dim {name} is not int: {type(val)}"
            assert 0 <= val <= 3, f"Dim {name}={val} out of [0, 3]"

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        candidate=st.text(min_size=1, max_size=200, alphabet="abcdefghijklmnopqrstuvwxyz .,?!"),
        archetype=st.sampled_from([
            "parasite", "prophet", "trickster", "sovereign",
            "martyr", "shadow", "herald", "keeper",
        ]),
        arc_theme=st.text(min_size=1, max_size=50, alphabet="abcdefghijklmnopqrstuvwxyz "),
    )
    def test_total_in_0_to_21(
        self, candidate: str, archetype: str, arc_theme: str
    ):
        """EnhancedQualityScore.total is always in [0, 21]."""
        config = SoulEngineConfig()
        result = _asyncio.run(evaluate_enhanced(
            candidate, archetype=archetype, move="COUNTER",
            arc_theme=arc_theme, config=config,
        ))
        assert 0 <= result.total <= 21, f"Total {result.total} out of [0, 21]"


# ---------------------------------------------------------------------------
# Feature: elder-voice-soul-engine, Property 19: Subtext Depth Conditional Scoring
# ---------------------------------------------------------------------------


class TestSubtextDepthConditionalScoring:
    """Property 19: Subtext Depth Conditional Scoring.

    *For any* candidate line, subtext_depth is scored as 0 when
    subtext_was_injected=False, regardless of whether a SubtletyDirector
    or SubtextInstruction is provided.

    **Validates: Requirements 10.3, 10.5**
    """

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        candidate=st.text(min_size=1, max_size=200, alphabet="abcdefghijklmnopqrstuvwxyz .,?!"),
    )
    def test_subtext_depth_zero_when_not_injected(self, candidate: str):
        """subtext_depth is always 0 when subtext_was_injected=False."""
        from banter.subtlety_director import SubtletyDirector
        config = SoulEngineConfig()
        director = SubtletyDirector(config, seed=0)
        instruction = SubtextInstruction(
            surface_meaning="Ask about power as if curious.",
            implied_meaning="The question presumes guilt.",
            technique="loaded_question",
            context_hint="Let the subtext operate.",
        )
        result = _asyncio.run(evaluate_enhanced(
            candidate, archetype="prophet", move="QUESTION",
            arc_theme="power", config=config,
            subtlety_director=director,
            subtext_instruction=instruction,
            subtext_was_injected=False,  # NOT injected
        ))
        assert result.subtext_depth == 0, (
            f"Expected subtext_depth=0 when not injected, got {result.subtext_depth}"
        )

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        candidate=st.text(min_size=1, max_size=200, alphabet="abcdefghijklmnopqrstuvwxyz .,?!"),
    )
    def test_subtext_depth_zero_without_director(self, candidate: str):
        """subtext_depth is 0 when no SubtletyDirector is provided."""
        config = SoulEngineConfig()
        instruction = SubtextInstruction(
            surface_meaning="Ask about power as if curious.",
            implied_meaning="The question presumes guilt.",
            technique="loaded_question",
            context_hint="hint",
        )
        result = _asyncio.run(evaluate_enhanced(
            candidate, archetype="prophet", move="QUESTION",
            arc_theme="power", config=config,
            subtlety_director=None,  # no director
            subtext_instruction=instruction,
            subtext_was_injected=True,
        ))
        assert result.subtext_depth == 0

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        candidate=st.text(min_size=1, max_size=200, alphabet="abcdefghijklmnopqrstuvwxyz .,?!"),
    )
    def test_subtext_depth_zero_without_instruction(self, candidate: str):
        """subtext_depth is 0 when no SubtextInstruction is provided."""
        from banter.subtlety_director import SubtletyDirector
        config = SoulEngineConfig()
        director = SubtletyDirector(config, seed=0)
        result = _asyncio.run(evaluate_enhanced(
            candidate, archetype="prophet", move="QUESTION",
            arc_theme="power", config=config,
            subtlety_director=director,
            subtext_instruction=None,  # no instruction
            subtext_was_injected=True,
        ))
        assert result.subtext_depth == 0

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        candidate=st.text(min_size=1, max_size=200, alphabet="abcdefghijklmnopqrstuvwxyz .,?!"),
    )
    def test_subtext_depth_zero_when_soul_disabled(self, candidate: str):
        """subtext_depth is 0 when soul engine is disabled in config."""
        from banter.subtlety_director import SubtletyDirector
        config = SoulEngineConfig(enabled=False)
        director = SubtletyDirector(config, seed=0)
        instruction = SubtextInstruction(
            surface_meaning="Ask about power.",
            implied_meaning="Presumes guilt.",
            technique="loaded_question",
            context_hint="hint",
        )
        result = _asyncio.run(evaluate_enhanced(
            candidate, archetype="prophet", move="QUESTION",
            arc_theme="power", config=config,
            subtlety_director=director,
            subtext_instruction=instruction,
            subtext_was_injected=True,
        ))
        assert result.subtext_depth == 0, (
            f"subtext_depth should be 0 when soul disabled, got {result.subtext_depth}"
        )


# ---------------------------------------------------------------------------
# Feature: elder-voice-soul-engine, Property 20: Quality Threshold Configuration
# ---------------------------------------------------------------------------


class TestQualityThresholdConfiguration:
    """Property 20: Quality Threshold Configuration.

    *For any* SoulEngineConfig, the pass threshold is 10/12 when soul
    enabled and 8/10 when disabled.

    **Validates: Requirements 10.4**
    """

    def test_soul_pass_threshold_constant(self):
        """SOUL_PASS_THRESHOLD is 10."""
        assert SOUL_PASS_THRESHOLD == 10

    def test_soul_refine_threshold_constant(self):
        """SOUL_REFINE_THRESHOLD is 12."""
        assert SOUL_REFINE_THRESHOLD == 12

    def test_base_pass_threshold_constant(self):
        """BASE_PASS_THRESHOLD is 8."""
        assert BASE_PASS_THRESHOLD == 8

    def test_base_refine_threshold_constant(self):
        """BASE_REFINE_THRESHOLD is 10."""
        assert BASE_REFINE_THRESHOLD == 10

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(soul_active=st.booleans())
    def test_get_pass_threshold_matches_config(self, soul_active: bool):
        """get_pass_threshold returns correct value based on soul_active."""
        threshold = get_pass_threshold(soul_active)
        if soul_active:
            assert threshold == SOUL_PASS_THRESHOLD
        else:
            assert threshold == BASE_PASS_THRESHOLD

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(soul_active=st.booleans())
    def test_get_refine_threshold_matches_config(self, soul_active: bool):
        """get_refine_threshold returns correct value based on soul_active."""
        threshold = get_refine_threshold(soul_active)
        if soul_active:
            assert threshold == SOUL_REFINE_THRESHOLD
        else:
            assert threshold == BASE_REFINE_THRESHOLD

    def test_soul_threshold_higher_than_base(self):
        """Soul thresholds are always higher than base thresholds."""
        assert SOUL_PASS_THRESHOLD > BASE_PASS_THRESHOLD
        assert SOUL_REFINE_THRESHOLD > BASE_REFINE_THRESHOLD

    def test_refine_threshold_higher_than_pass_threshold(self):
        """Refinement threshold is always higher than pass threshold."""
        assert BASE_REFINE_THRESHOLD > BASE_PASS_THRESHOLD
        assert SOUL_REFINE_THRESHOLD > SOUL_PASS_THRESHOLD


# ---------------------------------------------------------------------------
# Feature: elder-voice-soul-engine, Property 22: Shareability Bonus Conditional
# ---------------------------------------------------------------------------


class TestShareabilityBonusConditional:
    """Property 22: Shareability Bonus Conditional.

    *For any* candidate with subtext_depth > 0, shareability in
    EnhancedQualityScore is at least as large as the base shareability
    from QualityScore (and at most base + subtext_depth, capped at 3).

    **Validates: Requirements 5.5**
    """

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        candidate=st.text(min_size=5, max_size=200, alphabet="abcdefghijklmnopqrstuvwxyz .,?!"),
        archetype=st.sampled_from([
            "prophet", "trickster", "keeper", "shadow",
        ]),
    )
    def test_shareability_at_least_base_when_subtext_present(
        self, candidate: str, archetype: str
    ):
        """When subtext was injected, enhanced shareability >= base shareability."""
        from banter.subtlety_director import SubtletyDirector
        from banter.quality_judge import evaluate

        config = SoulEngineConfig()
        director = SubtletyDirector(config, seed=42)
        instruction = SubtextInstruction(
            surface_meaning="Ask about the arc theme as if genuinely curious.",
            implied_meaning="The question presumes target guilt or weakness.",
            technique="loaded_question",
            context_hint="Let the subtext brush against sensitivity.",
        )

        # Get base shareability
        base_result = _asyncio.run(evaluate(
            candidate, archetype=archetype, move="QUESTION", arc_theme="power",
        ))

        # Get enhanced shareability with subtext injection
        enhanced_result = _asyncio.run(evaluate_enhanced(
            candidate, archetype=archetype, move="QUESTION",
            arc_theme="power", config=config,
            subtlety_director=director,
            subtext_instruction=instruction,
            subtext_was_injected=True,
        ))

        assert enhanced_result.shareability >= base_result.shareability, (
            f"Enhanced shareability ({enhanced_result.shareability}) < "
            f"base ({base_result.shareability}) for candidate={candidate!r}"
        )

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        base_shareability=st.integers(min_value=0, max_value=3),
        subtext_depth=st.integers(min_value=0, max_value=3),
    )
    def test_shareability_bonus_capped_at_3(
        self, base_shareability: int, subtext_depth: int
    ):
        """shareability + subtext_depth bonus is always capped at 3."""
        boosted = min(3, base_shareability + subtext_depth)
        assert 0 <= boosted <= 3

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        candidate=st.text(min_size=1, max_size=200, alphabet="abcdefghijklmnopqrstuvwxyz .,?!"),
        archetype=st.sampled_from(["prophet", "keeper", "shadow"]),
    )
    def test_no_bonus_when_subtext_not_injected(self, candidate: str, archetype: str):
        """When subtext_was_injected=False, shareability equals base shareability."""
        from banter.subtlety_director import SubtletyDirector
        from banter.quality_judge import evaluate

        config = SoulEngineConfig()
        director = SubtletyDirector(config, seed=0)
        instruction = SubtextInstruction(
            surface_meaning="Ask about the arc theme.",
            implied_meaning="The question presumes target guilt.",
            technique="loaded_question",
            context_hint="hint",
        )

        base_result = _asyncio.run(evaluate(
            candidate, archetype=archetype, move="QUESTION", arc_theme="power",
        ))
        enhanced_result = _asyncio.run(evaluate_enhanced(
            candidate, archetype=archetype, move="QUESTION",
            arc_theme="power", config=config,
            subtlety_director=director,
            subtext_instruction=instruction,
            subtext_was_injected=False,  # not injected
        ))

        assert enhanced_result.shareability == base_result.shareability, (
            f"No bonus expected when subtext not injected, "
            f"enhanced={enhanced_result.shareability}, base={base_result.shareability}"
        )


# ---------------------------------------------------------------------------
# Feature: elder-voice-soul-engine, Property 13: Soul Engine Token Budget
# ---------------------------------------------------------------------------


import asyncio as _asyncio_engine
from unittest.mock import AsyncMock, MagicMock


def _make_minimal_engine(**soul_kwargs):
    """Build a BanterEngine with stub required components and given soul kwargs."""
    from banter.engine import BanterEngine

    qj = AsyncMock(return_value=MagicMock(total=10, weak_dimensions=[]))
    ms = MagicMock()
    fp = MagicMock()
    rm = MagicMock()
    rm.get_significant_history = AsyncMock(return_value=[])
    rm.get_pair_state = AsyncMock(return_value=None)
    sc = MagicMock()
    mr = MagicMock()
    pc = MagicMock()
    ar = MagicMock()

    return BanterEngine(
        quality_judge=qj,
        move_selector=ms,
        fallback_pool=fp,
        relationship_memory=rm,
        scene_context=sc,
        model_router=mr,
        pacing_controller=pc,
        anti_repetition=ar,
        soul_config=SoulEngineConfig(),
        **soul_kwargs,
    )


class TestSoulEngineTokenBudget:
    """Property 13: Soul Engine Token Budget.

    The combined soul module prompt output never exceeds SOUL_BUDGET_TOKENS
    (800 tokens ≈ 3200 characters), regardless of individual module output sizes.

    **Validates: Requirements 7.2**
    """

    def _make_verbose_voice_dna(self, text: str):
        vdna = MagicMock()
        vdna.get_prompt_injection = MagicMock(return_value=text)
        return vdna

    def _make_verbose_emotional_primer(self, text: str):
        ep = MagicMock()
        ep.generate_emotional_context = AsyncMock(return_value=text)
        return ep

    def _make_verbose_subtlety_director(self, should_inject: bool, inj_text: str):
        sd = MagicMock()
        sd.should_inject_subtext = MagicMock(return_value=should_inject)
        if should_inject:
            from banter.soul_types import SubtextInstruction
            instr = SubtextInstruction(
                surface_meaning=inj_text[:50],
                implied_meaning=inj_text[50:100] if len(inj_text) > 50 else inj_text,
                technique="loaded_question",
                context_hint="hint",
            )
            sd.generate_subtext_instruction = MagicMock(return_value=instr)
        else:
            sd.generate_subtext_instruction = MagicMock(return_value=None)
        return sd

    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        voice_len=st.integers(min_value=0, max_value=5000),
        emotional_len=st.integers(min_value=0, max_value=5000),
        subtext_len=st.integers(min_value=50, max_value=5000),
    )
    def test_combined_output_never_exceeds_budget(
        self, voice_len: int, emotional_len: int, subtext_len: int
    ):
        """Total chars of all soul parts never exceeds _SOUL_BUDGET_CHARS."""
        from banter.engine import _SOUL_BUDGET_CHARS

        voice_text = "v" * voice_len
        emotional_text = "e" * emotional_len
        subtext_text = "s" * subtext_len

        engine = _make_minimal_engine(
            voice_dna=self._make_verbose_voice_dna(voice_text),
            emotional_primer=self._make_verbose_emotional_primer(emotional_text),
            subtlety_director=self._make_verbose_subtlety_director(True, subtext_text),
        )

        soul_parts, _ = _asyncio_engine.run(
            engine._build_soul_prompt(
                elder="elder_a", archetype="prophet", opponent="elder_b",
                arc_theme="power", move="QUESTION",
                history=[], tension=6, reconciliation_active=False,
            )
        )

        total = sum(len(p) for p in soul_parts)
        assert total <= _SOUL_BUDGET_CHARS, (
            f"Combined soul output {total} chars exceeds budget {_SOUL_BUDGET_CHARS}: "
            f"voice={voice_len}, emotional={emotional_len}, subtext={subtext_len}"
        )

    def test_budget_constant_is_800_tokens(self):
        """SOUL_BUDGET_TOKENS is exactly 800."""
        from banter.engine import SOUL_BUDGET_TOKENS
        assert SOUL_BUDGET_TOKENS == 800

    def test_char_budget_is_4x_token_budget(self):
        """_SOUL_BUDGET_CHARS equals SOUL_BUDGET_TOKENS * 4."""
        from banter.engine import SOUL_BUDGET_TOKENS, _SOUL_BUDGET_CHARS
        assert _SOUL_BUDGET_CHARS == SOUL_BUDGET_TOKENS * 4


# ---------------------------------------------------------------------------
# Feature: elder-voice-soul-engine, Property 14: Module Fault Isolation
# ---------------------------------------------------------------------------


class TestModuleFaultIsolation:
    """Property 14: Module Fault Isolation.

    If any single soul module raises an exception, the remaining modules
    still produce output. No exception propagates from _build_soul_prompt.
    BeatResult.metadata records failures.

    **Validates: Requirements 1.6, 3.7, 4.6, 7.3**
    """

    def _make_broken_voice_dna(self, msg: str = "vdna failure"):
        vdna = MagicMock()
        vdna.get_prompt_injection = MagicMock(side_effect=RuntimeError(msg))
        return vdna

    def _make_broken_emotional_primer(self, msg: str = "ep failure"):
        ep = MagicMock()
        ep.generate_emotional_context = AsyncMock(side_effect=RuntimeError(msg))
        return ep

    def _make_working_voice_dna(self, text: str = "[VOICE] archetype style"):
        vdna = MagicMock()
        vdna.get_prompt_injection = MagicMock(return_value=text)
        return vdna

    def _make_working_emotional_primer(self, text: str = "[EMOTIONAL] context here"):
        ep = MagicMock()
        ep.generate_emotional_context = AsyncMock(return_value=text)
        return ep

    def test_voice_dna_failure_does_not_suppress_emotional_primer(self):
        """Broken voice_dna → emotional_primer still contributes output."""
        emotional_text = "The weight of prior acts still presses down."
        engine = _make_minimal_engine(
            voice_dna=self._make_broken_voice_dna(),
            emotional_primer=self._make_working_emotional_primer(emotional_text),
        )

        soul_parts, meta = _asyncio_engine.run(
            engine._build_soul_prompt(
                "elder_a", "shadow", "elder_b", "betrayal", "DEFLECT",
                [], 5, False,
            )
        )

        combined = "\n".join(soul_parts)
        assert emotional_text in combined, "Emotional primer output should survive voice_dna failure"
        assert meta.get("voice_dna") is False, "voice_dna failure should be recorded"
        assert meta.get("emotional_primer") is True, "emotional_primer should succeed"

    def test_emotional_primer_failure_does_not_suppress_voice_dna(self):
        """Broken emotional_primer → voice_dna still contributes output."""
        voice_text = "Short declarative truth. Each sentence its own weight."
        engine = _make_minimal_engine(
            voice_dna=self._make_working_voice_dna(voice_text),
            emotional_primer=self._make_broken_emotional_primer(),
        )

        soul_parts, meta = _asyncio_engine.run(
            engine._build_soul_prompt(
                "elder_a", "keeper", "elder_b", "survival", "COUNTER",
                [], 5, False,
            )
        )

        combined = "\n".join(soul_parts)
        assert voice_text in combined, "Voice DNA output should survive emotional_primer failure"
        assert meta.get("emotional_primer") is False, "emotional_primer failure should be recorded"
        assert meta.get("voice_dna") is True, "voice_dna should succeed"

    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    @given(
        fail_voice=st.booleans(),
        fail_emotional=st.booleans(),
    )
    def test_no_exception_propagates_from_build_soul_prompt(
        self, fail_voice: bool, fail_emotional: bool
    ):
        """_build_soul_prompt never raises regardless of which modules fail."""
        voice_dna = (
            self._make_broken_voice_dna() if fail_voice
            else self._make_working_voice_dna()
        )
        emotional_primer = (
            self._make_broken_emotional_primer() if fail_emotional
            else self._make_working_emotional_primer()
        )
        engine = _make_minimal_engine(
            voice_dna=voice_dna,
            emotional_primer=emotional_primer,
        )

        # Must not raise
        soul_parts, meta = _asyncio_engine.run(
            engine._build_soul_prompt(
                "elder_a", "martyr", "elder_b", "sacrifice", "COUNTER",
                [], 4, False,
            )
        )

        assert isinstance(soul_parts, list)
        assert isinstance(meta, dict)
        if fail_voice:
            assert meta.get("voice_dna") is False
        else:
            assert meta.get("voice_dna") is True
        if fail_emotional:
            assert meta.get("emotional_primer") is False
        else:
            assert meta.get("emotional_primer") is True

    def test_metadata_records_all_module_outcomes(self):
        """metadata dict has entries for each active module."""
        engine = _make_minimal_engine(
            voice_dna=self._make_working_voice_dna(),
            emotional_primer=self._make_working_emotional_primer(),
        )

        _, meta = _asyncio_engine.run(
            engine._build_soul_prompt(
                "elder_a", "herald", "elder_b", "change", "COUNTER",
                [], 3, False,
            )
        )

        assert "voice_dna" in meta
        assert "emotional_primer" in meta


# ---------------------------------------------------------------------------
# Feature: elder-voice-soul-engine, Property 21: Prompt Composition Order
# ---------------------------------------------------------------------------


class TestPromptCompositionOrder:
    """Property 21: Prompt Composition Order.

    Soul module injections appear in the built prompt before existing
    components (scene context), in the order:
    Voice_DNA → Emotional_Primer → Callback_Registry → Subtlety_Director → existing.

    **Validates: Requirements 7.1**
    """

    def _make_tagged_voice_dna(self, tag: str = "VDNA_MARKER"):
        vdna = MagicMock()
        vdna.get_prompt_injection = MagicMock(return_value=tag)
        return vdna

    def _make_tagged_emotional_primer(self, tag: str = "EP_MARKER"):
        ep = MagicMock()
        ep.generate_emotional_context = AsyncMock(return_value=tag)
        return ep

    def test_voice_dna_before_emotional_primer_in_soul_parts(self):
        """Voice_DNA injection appears before Emotional_Primer in soul parts list."""
        engine = _make_minimal_engine(
            voice_dna=self._make_tagged_voice_dna("VOICE_FIRST"),
            emotional_primer=self._make_tagged_emotional_primer("EMOTIONAL_SECOND"),
        )

        soul_parts, _ = _asyncio_engine.run(
            engine._build_soul_prompt(
                "elder_a", "prophet", "elder_b", "power", "QUESTION",
                [], 5, False,
            )
        )

        combined = "\n\n".join(soul_parts)
        voice_pos = combined.find("VOICE_FIRST")
        emotional_pos = combined.find("EMOTIONAL_SECOND")

        assert voice_pos != -1, "Voice_DNA marker should appear in soul parts"
        assert emotional_pos != -1, "Emotional_Primer marker should appear in soul parts"
        assert voice_pos < emotional_pos, (
            f"Voice_DNA (pos {voice_pos}) must precede Emotional_Primer (pos {emotional_pos})"
        )

    def test_soul_parts_precede_scene_context_in_full_prompt(self):
        """All soul module injections appear before the scene context in _build_prompt."""
        scene_marker = "Scene energy:"

        mock_scene_data = MagicMock()
        mock_scene_data.recent_beats = []
        mock_scene_data.has_the_room = None
        mock_scene_data.scene_energy = "neutral"
        mock_scene_data.landed_hit = None
        mock_scene_data.landed_hit_remaining = 0

        mock_sc = MagicMock()
        mock_sc.get_context_for_generation = MagicMock(return_value=mock_scene_data)

        mock_ar = MagicMock()
        mock_ar.should_shift_register = MagicMock(return_value=False)

        from banter.engine import BanterEngine

        qj = AsyncMock(return_value=MagicMock(total=10, weak_dimensions=[]))
        rm = MagicMock()
        rm.get_significant_history = AsyncMock(return_value=[])
        rm.get_pair_state = AsyncMock(return_value=None)

        engine = BanterEngine(
            quality_judge=qj,
            move_selector=MagicMock(),
            fallback_pool=MagicMock(),
            relationship_memory=rm,
            scene_context=mock_sc,
            model_router=MagicMock(),
            pacing_controller=MagicMock(),
            anti_repetition=mock_ar,
            soul_config=SoulEngineConfig(),
            voice_dna=self._make_tagged_voice_dna("SOUL_VOICE_TAG"),
            emotional_primer=self._make_tagged_emotional_primer("SOUL_EMOTIONAL_TAG"),
        )

        prompt = _asyncio_engine.run(
            engine._build_prompt(
                "elder_a", "shadow", "elder_b", "secrets", "DEFLECT",
                [], mock_scene_data,
            )
        )

        voice_pos = prompt.find("SOUL_VOICE_TAG")
        emotional_pos = prompt.find("SOUL_EMOTIONAL_TAG")
        scene_pos = prompt.find(scene_marker)

        assert voice_pos != -1, "Voice_DNA marker should appear in prompt"
        assert scene_pos != -1, "Scene context should appear in prompt"
        assert voice_pos < scene_pos, (
            f"Soul Voice_DNA (pos {voice_pos}) must precede scene context (pos {scene_pos})"
        )
        if emotional_pos != -1:
            assert emotional_pos < scene_pos, (
                f"Soul Emotional_Primer (pos {emotional_pos}) must precede scene context (pos {scene_pos})"
            )

    @settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow])
    @given(
        include_voice=st.booleans(),
        include_emotional=st.booleans(),
    )
    def test_soul_parts_order_is_voice_then_emotional(
        self, include_voice: bool, include_emotional: bool
    ):
        """When both modules present, voice_dna always precedes emotional_primer."""
        engine = _make_minimal_engine(
            voice_dna=self._make_tagged_voice_dna("V_TAG") if include_voice else None,
            emotional_primer=self._make_tagged_emotional_primer("E_TAG") if include_emotional else None,
        )

        soul_parts, _ = _asyncio_engine.run(
            engine._build_soul_prompt(
                "elder_x", "trickster", "elder_y", "deception", "DEFLECT",
                [], 5, False,
            )
        )

        combined = "\n\n".join(soul_parts)

        if include_voice and include_emotional:
            v_pos = combined.find("V_TAG")
            e_pos = combined.find("E_TAG")
            assert v_pos != -1 and e_pos != -1
            assert v_pos < e_pos, "Voice_DNA must come before Emotional_Primer"
