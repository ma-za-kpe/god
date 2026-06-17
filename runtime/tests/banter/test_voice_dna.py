"""Unit tests for the Voice_DNA module.

Tests profile loading, validation, prompt injection, and hot-reload behavior.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

import pytest

# Path setup
_src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
for _p in (_src_path, "/app/src"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from banter.soul_types import SoulEngineConfig, validate_voice_dna_profile
from banter.voice_dna import VoiceDNA, ARCHETYPES, _estimate_token_count


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_valid_profile(archetype: str) -> dict:
    """Create a minimal valid profile dict for the given archetype."""
    return {
        "archetype": archetype,
        "sentence_structures": [
            f"Structure {i} for {archetype}" for i in range(3)
        ],
        "verbal_tics": [f"tic-{i}" for i in range(2)],
        "rhythm_patterns": [
            {
                "name": "default_rhythm",
                "clause_count_range": [1, 3],
                "word_count_per_clause_range": [3, 10],
                "pause_placement": "before_final",
            }
        ],
        "micro_phrases": [f"phrase-{i}" for i in range(4)],
        "rhetorical_devices": [f"device-{i}" for i in range(2)],
        "opening_patterns": [f"opener-{i}" for i in range(2)],
        "closing_patterns": [f"closer-{i}" for i in range(2)],
    }


@pytest.fixture
def config():
    """Default SoulEngineConfig."""
    return SoulEngineConfig()


@pytest.fixture
def profiles_dir(tmp_path):
    """Temporary directory with all 8 valid profiles."""
    for archetype in ARCHETYPES:
        profile = _make_valid_profile(archetype)
        filepath = tmp_path / f"{archetype}.json"
        filepath.write_text(json.dumps(profile), encoding="utf-8")
    return tmp_path


@pytest.fixture
def partial_profiles_dir(tmp_path):
    """Temporary directory with only 3 valid profiles."""
    for archetype in ["parasite", "prophet", "trickster"]:
        profile = _make_valid_profile(archetype)
        filepath = tmp_path / f"{archetype}.json"
        filepath.write_text(json.dumps(profile), encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# Tests: load_profiles
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_profiles_all_valid(profiles_dir, config):
    """All 8 valid profiles are loaded successfully."""
    vdna = VoiceDNA(profiles_dir, config)
    await vdna.load_profiles()

    assert len(vdna.profiles) == 8
    for archetype in ARCHETYPES:
        assert archetype in vdna.profiles
        assert vdna.profiles[archetype].archetype == archetype


@pytest.mark.asyncio
async def test_load_profiles_partial(partial_profiles_dir, config):
    """Only available profiles are loaded; missing ones are skipped."""
    vdna = VoiceDNA(partial_profiles_dir, config)
    await vdna.load_profiles()

    assert len(vdna.profiles) == 3
    assert "parasite" in vdna.profiles
    assert "prophet" in vdna.profiles
    assert "trickster" in vdna.profiles
    assert "sovereign" not in vdna.profiles


@pytest.mark.asyncio
async def test_load_profiles_invalid_json(tmp_path, config):
    """Malformed JSON file is skipped without crashing."""
    filepath = tmp_path / "parasite.json"
    filepath.write_text("not valid json {{{", encoding="utf-8")

    vdna = VoiceDNA(tmp_path, config)
    await vdna.load_profiles()

    assert "parasite" not in vdna.profiles


@pytest.mark.asyncio
async def test_load_profiles_fails_validation(tmp_path, config):
    """Profile that fails schema validation is not loaded."""
    # Missing micro_phrases (needs 4)
    profile = {
        "archetype": "parasite",
        "sentence_structures": ["s1", "s2", "s3"],
        "verbal_tics": ["t1", "t2"],
        "rhythm_patterns": [{"name": "r1", "clause_count_range": [1, 2],
                             "word_count_per_clause_range": [3, 8],
                             "pause_placement": "before_final"}],
        "micro_phrases": ["p1"],  # Too few — needs 4
        "rhetorical_devices": ["d1", "d2"],
        "opening_patterns": ["o1", "o2"],
        "closing_patterns": ["c1", "c2"],
    }
    filepath = tmp_path / "parasite.json"
    filepath.write_text(json.dumps(profile), encoding="utf-8")

    vdna = VoiceDNA(tmp_path, config)
    await vdna.load_profiles()

    assert "parasite" not in vdna.profiles


@pytest.mark.asyncio
async def test_load_profiles_archetype_mismatch(tmp_path, config):
    """Profile with wrong archetype field is rejected."""
    profile = _make_valid_profile("prophet")  # archetype = "prophet"
    filepath = tmp_path / "parasite.json"  # but filename says parasite
    filepath.write_text(json.dumps(profile), encoding="utf-8")

    vdna = VoiceDNA(tmp_path, config)
    await vdna.load_profiles()

    assert "parasite" not in vdna.profiles


# ---------------------------------------------------------------------------
# Tests: get_prompt_injection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_prompt_injection_returns_string(profiles_dir, config):
    """Each archetype returns a non-empty string within 250 token budget.

    Validates Requirements 1.2 (injection output) and token budget adherence.
    """
    vdna = VoiceDNA(profiles_dir, config)
    await vdna.load_profiles()

    for archetype in ARCHETYPES:
        injection = vdna.get_prompt_injection(archetype)
        assert injection is not None, f"{archetype}: expected non-None injection"
        assert isinstance(injection, str), f"{archetype}: expected str"
        assert len(injection) > 0, f"{archetype}: expected non-empty string"
        tokens = _estimate_token_count(injection)
        assert tokens <= config.voice_dna_token_budget, (
            f"{archetype}: {tokens} tokens exceeds {config.voice_dna_token_budget} budget"
        )


@pytest.mark.asyncio
async def test_get_prompt_injection_contains_archetype(profiles_dir, config):
    """Injection contains the archetype name."""
    vdna = VoiceDNA(profiles_dir, config)
    await vdna.load_profiles()

    injection = vdna.get_prompt_injection("prophet")
    assert "PROPHET" in injection


@pytest.mark.asyncio
async def test_get_prompt_injection_within_token_budget(profiles_dir, config):
    """Injection stays within the 250-token budget."""
    vdna = VoiceDNA(profiles_dir, config)
    await vdna.load_profiles()

    for archetype in ARCHETYPES:
        injection = vdna.get_prompt_injection(archetype)
        assert injection is not None
        tokens = _estimate_token_count(injection)
        assert tokens <= config.voice_dna_token_budget, (
            f"{archetype}: {tokens} tokens > {config.voice_dna_token_budget} budget"
        )


@pytest.mark.asyncio
async def test_get_prompt_injection_unavailable_archetype(profiles_dir, config):
    """Returns None for an archetype that isn't loaded."""
    vdna = VoiceDNA(profiles_dir, config)
    await vdna.load_profiles()

    result = vdna.get_prompt_injection("nonexistent_archetype")
    assert result is None


@pytest.mark.asyncio
async def test_get_prompt_injection_empty_profiles(tmp_path, config):
    """Returns None when no profiles are loaded."""
    vdna = VoiceDNA(tmp_path, config)
    await vdna.load_profiles()

    result = vdna.get_prompt_injection("parasite")
    assert result is None


# ---------------------------------------------------------------------------
# Tests: score_voice_conformance (stub)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_score_voice_conformance_unavailable_archetype(profiles_dir, config):
    """Returns 0 for unavailable archetype."""
    vdna = VoiceDNA(profiles_dir, config)
    await vdna.load_profiles()

    score = vdna.score_voice_conformance("Any line of text", "nonexistent")
    assert score == 0


@pytest.mark.asyncio
async def test_score_voice_conformance_returns_valid_range(profiles_dir, config):
    """Score is always 0-3 for any archetype and any input text.

    Validates Requirement 1.3: the voice conformance score is always an
    integer in [0, 3].
    """
    vdna = VoiceDNA(profiles_dir, config)
    await vdna.load_profiles()

    test_lines = [
        "Any line of text",
        "",
        "A short one.",
        "This is a much longer line that contains many words and clauses, "
        "spanning different rhythm patterns and including various verbal tics.",
        "Single",
        "One, two, three — a fragmented line with multiple clauses.",
    ]

    for archetype in ARCHETYPES:
        for line in test_lines:
            score = vdna.score_voice_conformance(line, archetype)
            assert isinstance(score, int), (
                f"{archetype}/{line[:20]}: expected int, got {type(score)}"
            )
            assert 0 <= score <= 3, (
                f"{archetype}/{line[:20]}: score {score} not in [0, 3]"
            )


@pytest.mark.asyncio
async def test_score_voice_conformance_returns_int(profiles_dir, config):
    """Returns an integer in [0, 3] range."""
    vdna = VoiceDNA(profiles_dir, config)
    await vdna.load_profiles()

    score = vdna.score_voice_conformance("Any line of text", "parasite")
    assert isinstance(score, int)
    assert 0 <= score <= 3


# ---------------------------------------------------------------------------
# Tests: check_for_reload
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_for_reload_detects_change(profiles_dir, config):
    """Modified file is reloaded on next check."""
    vdna = VoiceDNA(profiles_dir, config)
    await vdna.load_profiles()

    original_profile = vdna.profiles["parasite"]

    # Modify the parasite profile
    updated = _make_valid_profile("parasite")
    updated["verbal_tics"] = ["new-tic-1", "new-tic-2"]
    filepath = profiles_dir / "parasite.json"

    # Ensure mtime changes (some filesystems have 1s resolution)
    time.sleep(0.01)
    filepath.write_text(json.dumps(updated), encoding="utf-8")

    # Force the next check by resetting the timer
    vdna._last_check_ts = 0.0
    await vdna.check_for_reload()

    reloaded_profile = vdna.profiles["parasite"]
    assert reloaded_profile.verbal_tics == ["new-tic-1", "new-tic-2"]


@pytest.mark.asyncio
async def test_check_for_reload_retains_on_validation_failure(profiles_dir, config):
    """Invalid update retains the previous valid profile (Req 8.5)."""
    vdna = VoiceDNA(profiles_dir, config)
    await vdna.load_profiles()

    original_tics = vdna.profiles["parasite"].verbal_tics

    # Write an invalid profile (too few micro_phrases)
    invalid = _make_valid_profile("parasite")
    invalid["micro_phrases"] = ["only-one"]  # needs 4
    filepath = profiles_dir / "parasite.json"
    time.sleep(0.01)
    filepath.write_text(json.dumps(invalid), encoding="utf-8")

    # Force reload
    vdna._last_check_ts = 0.0
    await vdna.check_for_reload()

    # Previous valid profile should be retained
    assert vdna.profiles["parasite"].verbal_tics == original_tics


@pytest.mark.asyncio
async def test_check_for_reload_respects_interval(profiles_dir, config):
    """Reload is skipped when called within the 30s interval."""
    vdna = VoiceDNA(profiles_dir, config)
    await vdna.load_profiles()

    # Update file
    updated = _make_valid_profile("parasite")
    updated["verbal_tics"] = ["changed-tic-1", "changed-tic-2"]
    filepath = profiles_dir / "parasite.json"
    time.sleep(0.01)
    filepath.write_text(json.dumps(updated), encoding="utf-8")

    # Set last check to very recent (should skip)
    vdna._last_check_ts = time.time()
    await vdna.check_for_reload()

    # Should NOT have reloaded
    assert vdna.profiles["parasite"].verbal_tics != ["changed-tic-1", "changed-tic-2"]


@pytest.mark.asyncio
async def test_check_for_reload_other_profiles_unaffected(profiles_dir, config):
    """Reloading one profile does not affect others (Req 8.4)."""
    vdna = VoiceDNA(profiles_dir, config)
    await vdna.load_profiles()

    original_prophet = vdna.profiles["prophet"]

    # Modify only parasite
    updated = _make_valid_profile("parasite")
    updated["verbal_tics"] = ["changed-1", "changed-2"]
    filepath = profiles_dir / "parasite.json"
    time.sleep(0.01)
    filepath.write_text(json.dumps(updated), encoding="utf-8")

    vdna._last_check_ts = 0.0
    await vdna.check_for_reload()

    # Prophet should be unchanged
    assert vdna.profiles["prophet"] == original_prophet


# ---------------------------------------------------------------------------
# Tests: profile unavailability does not block (Req 1.6)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_profile_unavailable_does_not_block(tmp_path, config):
    """Missing profile file gracefully returns None without blocking.

    Validates Requirement 1.6: if the VoiceDNA profile for a requested
    archetype is unavailable or fails to load, the Banter_Engine falls back
    without delaying generation.
    """
    # Create profiles dir with NO files at all
    vdna = VoiceDNA(tmp_path, config)
    await vdna.load_profiles()

    # Requesting any archetype should return None gracefully
    for archetype in ARCHETYPES:
        result = vdna.get_prompt_injection(archetype)
        assert result is None, (
            f"Expected None for missing archetype '{archetype}', got: {result}"
        )

    # score_voice_conformance should also return 0 (not raise)
    for archetype in ARCHETYPES:
        score = vdna.score_voice_conformance("test line", archetype)
        assert score == 0


@pytest.mark.asyncio
async def test_profile_unavailable_partial_load_does_not_block(tmp_path, config):
    """A profile directory with some missing files still loads available ones.

    Ensures that missing files for some archetypes don't prevent loading
    the valid profiles for other archetypes.
    """
    # Only write parasite and prophet profiles
    for archetype in ["parasite", "prophet"]:
        profile = _make_valid_profile(archetype)
        filepath = tmp_path / f"{archetype}.json"
        filepath.write_text(json.dumps(profile), encoding="utf-8")

    vdna = VoiceDNA(tmp_path, config)
    await vdna.load_profiles()

    # Available ones work
    assert vdna.get_prompt_injection("parasite") is not None
    assert vdna.get_prompt_injection("prophet") is not None

    # Missing ones return None (don't block or crash)
    assert vdna.get_prompt_injection("keeper") is None
    assert vdna.get_prompt_injection("shadow") is None


# ---------------------------------------------------------------------------
# Tests: all actual JSON profiles pass schema validation (Req 8.3)
# ---------------------------------------------------------------------------


# Path to the actual voice_profiles directory shipped with the project
_ACTUAL_PROFILES_DIR = Path(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "src", "banter", "voice_profiles")
    )
)


@pytest.mark.asyncio
async def test_all_profiles_pass_schema_validation():
    """All 8 shipped JSON profile files pass validate_voice_dna_profile().

    Validates Requirement 8.3: when the Banter_Engine starts, all 8 archetype
    profiles load from disk and validate. This test verifies the actual profile
    files in the source tree.
    """
    if not _ACTUAL_PROFILES_DIR.exists():
        pytest.skip("Voice profiles directory not found at expected path")

    for archetype in sorted(ARCHETYPES):
        filepath = _ACTUAL_PROFILES_DIR / f"{archetype}.json"
        assert filepath.exists(), f"Profile file missing for '{archetype}': {filepath}"

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        is_valid, violations = validate_voice_dna_profile(data)
        assert is_valid, (
            f"Profile '{archetype}' failed schema validation: {violations}"
        )

        # Also verify archetype field matches filename
        assert data.get("archetype") == archetype, (
            f"Profile file '{archetype}.json' has archetype='{data.get('archetype')}'"
        )


@pytest.mark.asyncio
async def test_all_profiles_load_in_voice_dna():
    """All 8 profiles load successfully through the VoiceDNA class.

    Integration-level validation that the actual profile files work with
    the full load_profiles() flow including parsing into VoiceDNAProfile.
    """
    if not _ACTUAL_PROFILES_DIR.exists():
        pytest.skip("Voice profiles directory not found at expected path")

    config = SoulEngineConfig()
    vdna = VoiceDNA(_ACTUAL_PROFILES_DIR, config)
    await vdna.load_profiles()

    assert len(vdna.profiles) == 8, (
        f"Expected 8 profiles loaded, got {len(vdna.profiles)}. "
        f"Missing: {ARCHETYPES - set(vdna.profiles.keys())}"
    )
