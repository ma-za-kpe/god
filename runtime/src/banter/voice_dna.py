"""Voice_DNA — archetype linguistic profile management and prompt injection.

Loads VoiceDNA profiles from JSON files, validates them against schema,
provides structured linguistic instructions for prompt injection within
a 250-token budget, and supports hot-reload via 30-second file polling.

Requirements: 1.1, 1.2, 8.1, 8.2, 8.3, 8.4, 8.5
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path

from .soul_types import (
    RhythmPattern,
    SoulEngineConfig,
    VoiceDNAProfile,
    VOICE_DNA_SCHEMA,
    validate_voice_dna_profile,
)

log = logging.getLogger("god.banter.voice_dna")

# The 8 archetypes supported by the Voice_DNA module.
ARCHETYPES = frozenset(
    {
        "parasite",
        "prophet",
        "trickster",
        "sovereign",
        "martyr",
        "shadow",
        "herald",
        "keeper",
    }
)

# Polling interval for hot-reload (seconds).
_RELOAD_POLL_INTERVAL_S = 30.0

# Approximate tokens-per-word ratio for budget estimation.
_TOKENS_PER_WORD = 1.3


def _estimate_token_count(text: str) -> int:
    """Estimate token count from word count (conservative approximation)."""
    word_count = len(text.split())
    return int(word_count * _TOKENS_PER_WORD)


import re

_CLAUSE_DELIMITERS = re.compile(r"[,;:\-—]+|\band\b|\bbut\b|\bor\b")


def _split_into_clauses(text: str) -> list[str]:
    """Split text into clauses using common clause delimiters."""
    parts = _CLAUSE_DELIMITERS.split(text)
    return [p.strip() for p in parts if p.strip()]


def _matches_sentence_structure(candidate: str, structures: list[str]) -> bool:
    """Check if candidate loosely matches any of the given sentence structures.

    Heuristic: checks if the candidate's word-level shape (declarative,
    imperative, question, etc.) aligns with structure descriptions.
    Returns True if any structure keyword appears in the candidate.
    """
    candidate_lower = candidate.lower()
    # Simple heuristic: check if structure description keywords appear
    for structure in structures:
        # Extract key pattern words from the structure description
        keywords = [w.lower() for w in structure.split() if len(w) > 3]
        if any(kw in candidate_lower for kw in keywords[:3]):
            return True
    return False


# Clause delimiters: commas, semicolons, em-dashes, colons, and conjunctions
_CLAUSE_SPLIT_RE = re.compile(r"[,;:\u2014]|\s+—\s+|\s+-\s+")


def _split_into_clauses(text: str) -> list[str]:
    """Split text into clauses using common punctuation delimiters.

    Splits on commas, semicolons, colons, em-dashes, and hyphens used
    as dashes (surrounded by spaces). Returns non-empty clause segments.
    """
    parts = _CLAUSE_SPLIT_RE.split(text)
    return [p.strip() for p in parts if p.strip()]


def _matches_sentence_structure(candidate: str, structures: list[str]) -> bool:
    """Check if candidate matches any sentence structure pattern.

    Structure patterns contain placeholder tokens like {X}, {cost}, {benefit}.
    We check if the candidate's non-placeholder skeleton (the literal words)
    overlaps significantly with the pattern's literal segments.

    A match is declared if at least 40% of a pattern's literal words appear
    in the candidate in a contiguous or near-contiguous fashion.
    """
    if not structures:
        return False

    candidate_lower = candidate.lower()
    candidate_words = set(candidate_lower.split())

    # Pattern to find placeholder tokens in structure definitions
    placeholder_re = re.compile(r"\{[^}]+\}")

    for structure in structures:
        # Extract the literal (non-placeholder) words from the pattern
        literal_text = placeholder_re.sub("", structure).lower()
        literal_words = [w for w in literal_text.split() if len(w) > 2]

        if not literal_words:
            continue

        # Count how many of the pattern's literal words appear in candidate
        matches = sum(1 for w in literal_words if w in candidate_words)
        match_ratio = matches / len(literal_words)

        if match_ratio >= 0.4:
            return True

    return False


def _parse_rhythm_pattern(raw: dict) -> RhythmPattern:
    """Parse a raw rhythm pattern dict into a RhythmPattern dataclass."""
    return RhythmPattern(
        name=raw.get("name", "unnamed"),
        clause_count_range=tuple(raw.get("clause_count_range", [1, 3])),
        word_count_per_clause_range=tuple(
            raw.get("word_count_per_clause_range", [3, 12])
        ),
        pause_placement=raw.get("pause_placement", "before_final"),
    )


def _build_profile(data: dict) -> VoiceDNAProfile:
    """Build a VoiceDNAProfile from a validated dict."""
    return VoiceDNAProfile(
        archetype=data["archetype"],
        sentence_structures=list(data["sentence_structures"]),
        verbal_tics=list(data["verbal_tics"]),
        rhythm_patterns=[_parse_rhythm_pattern(rp) for rp in data["rhythm_patterns"]],
        micro_phrases=list(data["micro_phrases"]),
        rhetorical_devices=list(data["rhetorical_devices"]),
        opening_patterns=list(data["opening_patterns"]),
        closing_patterns=list(data["closing_patterns"]),
    )


class VoiceDNA:
    """Manages VoiceDNA profiles and provides prompt injection + scoring.

    Loads JSON profiles from disk, validates them against the schema,
    and provides archetype-specific linguistic instructions for the
    prompt-building phase.
    """

    def __init__(self, profiles_dir: Path, config: SoulEngineConfig):
        self._profiles_dir = profiles_dir
        self._config = config
        # archetype name → VoiceDNAProfile
        self._profiles: dict[str, VoiceDNAProfile] = {}
        # archetype name → last known mtime of the profile file
        self._file_mtimes: dict[str, float] = {}
        # Timestamp of last reload check
        self._last_check_ts: float = 0.0

    @property
    def profiles(self) -> dict[str, VoiceDNAProfile]:
        """Read-only access to currently loaded profiles."""
        return dict(self._profiles)

    async def load_profiles(self) -> None:
        """Load and validate all 8 archetype profiles from disk.

        Iterates over the expected archetype JSON files. Valid profiles are
        stored; invalid or missing files are logged as warnings but do not
        block loading of other profiles.
        """
        for archetype in sorted(ARCHETYPES):
            self._load_single_profile(archetype)

        loaded_count = len(self._profiles)
        log.info(
            "VoiceDNA loaded %d/%d archetype profiles from %s",
            loaded_count,
            len(ARCHETYPES),
            self._profiles_dir,
        )

    def _load_single_profile(self, archetype: str) -> bool:
        """Load and validate a single archetype profile.

        Returns True if the profile was successfully loaded, False otherwise.
        On validation failure, the previously loaded profile (if any) is retained.
        """
        filepath = self._profiles_dir / f"{archetype}.json"

        if not filepath.exists():
            log.warning(
                "VoiceDNA profile file not found: %s",
                filepath,
            )
            return False

        try:
            mtime = os.path.getmtime(filepath)
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            log.warning(
                "VoiceDNA failed to read/parse %s: %s",
                filepath,
                exc,
            )
            return False

        # Validate against schema
        is_valid, violations = validate_voice_dna_profile(data)
        if not is_valid:
            log.warning(
                "VoiceDNA profile '%s' failed validation: %s. "
                "Retaining previous valid profile.",
                archetype,
                "; ".join(violations),
            )
            return False

        # Check archetype field matches filename
        if data.get("archetype") != archetype:
            log.warning(
                "VoiceDNA profile '%s' has mismatched archetype field: '%s'. "
                "Retaining previous valid profile.",
                archetype,
                data.get("archetype"),
            )
            return False

        # Build and store
        profile = _build_profile(data)
        self._profiles[archetype] = profile
        self._file_mtimes[archetype] = mtime
        log.debug("VoiceDNA loaded profile for '%s'", archetype)
        return True

    def get_prompt_injection(self, archetype: str) -> str | None:
        """Return structured linguistic instructions for prompt injection.

        Formats the VoiceDNA profile as concise instructions that guide
        the generation model's sentence construction and word choice.
        Returns None if the archetype profile is unavailable (triggers fallback).

        The output is constrained to fit within the 250-token budget.
        """
        profile = self._profiles.get(archetype)
        if profile is None:
            return None

        # Build structured instruction text
        sections: list[str] = []

        # Sentence structures
        structures_str = "; ".join(profile.sentence_structures[:4])
        sections.append(f"SENTENCE PATTERNS: {structures_str}")

        # Verbal tics
        tics_str = ", ".join(profile.verbal_tics[:4])
        sections.append(f"VERBAL TICS (use naturally): {tics_str}")

        # Rhythm patterns
        rhythm_parts: list[str] = []
        for rp in profile.rhythm_patterns[:2]:
            rhythm_parts.append(
                f"{rp.name}: {rp.clause_count_range[0]}-{rp.clause_count_range[1]} "
                f"clauses, {rp.word_count_per_clause_range[0]}-"
                f"{rp.word_count_per_clause_range[1]} words/clause, "
                f"pause {rp.pause_placement}"
            )
        sections.append(f"RHYTHM: {'; '.join(rhythm_parts)}")

        # Micro-phrases
        phrases_str = "; ".join(profile.micro_phrases[:5])
        sections.append(f"SIGNATURE PHRASES: {phrases_str}")

        # Rhetorical devices
        devices_str = ", ".join(profile.rhetorical_devices[:3])
        sections.append(f"RHETORICAL DEVICES: {devices_str}")

        # Opening/closing patterns
        openers_str = "; ".join(profile.opening_patterns[:3])
        closers_str = "; ".join(profile.closing_patterns[:3])
        sections.append(f"OPENERS: {openers_str}")
        sections.append(f"CLOSERS: {closers_str}")

        # Compose final injection
        injection = (
            f"[VOICE DNA — {archetype.upper()}]\n"
            + "\n".join(sections)
        )

        # Trim to stay within token budget
        budget = self._config.voice_dna_token_budget
        estimated_tokens = _estimate_token_count(injection)

        if estimated_tokens > budget:
            # Progressively trim from the bottom
            while _estimate_token_count(injection) > budget and sections:
                sections.pop()
                injection = (
                    f"[VOICE DNA — {archetype.upper()}]\n"
                    + "\n".join(sections)
                )

        return injection

    def score_voice_conformance(self, candidate: str, archetype: str) -> int:
        """Score how well a line matches the archetype's VoiceDNA (0-3).

        Evaluates four structural categories:
        - Sentence structure pattern match
        - Verbal tics present in candidate
        - Rhythm pattern conformance (clause count and word count)
        - Micro-phrases used in candidate

        Scoring scale based on number of categories matched:
        - 0 = no matches to any VoiceDNA pattern
        - 1 = matches 1 category
        - 2 = matches 2-3 categories
        - 3 = matches 4+ categories (strong archetype voice)

        Deterministic for the same (candidate, archetype) input pair.
        Returns 0 if archetype profile is not available.
        """
        profile = self._profiles.get(archetype)
        if profile is None:
            return 0

        categories_matched = 0
        candidate_lower = candidate.lower()

        # --- Category 1: Sentence structure pattern match ---
        if _matches_sentence_structure(candidate, profile.sentence_structures):
            categories_matched += 1

        # --- Category 2: Verbal tics ---
        tics_found = sum(
            1 for tic in profile.verbal_tics
            if tic.lower() in candidate_lower
        )
        if tics_found > 0:
            categories_matched += 1

        # --- Category 3: Rhythm pattern conformance ---
        clauses = _split_into_clauses(candidate)
        clause_count = len(clauses)
        word_counts = [len(c.split()) for c in clauses if c.strip()]

        rhythm_match = False
        for rp in profile.rhythm_patterns:
            min_clauses, max_clauses = rp.clause_count_range
            min_words, max_words = rp.word_count_per_clause_range

            if min_clauses <= clause_count <= max_clauses:
                if word_counts and all(
                    min_words <= wc <= max_words for wc in word_counts
                ):
                    rhythm_match = True
                    break

        if rhythm_match:
            categories_matched += 1

        # --- Category 4: Micro-phrases ---
        phrases_found = sum(
            1 for phrase in profile.micro_phrases
            if phrase.lower() in candidate_lower
        )
        if phrases_found > 0:
            categories_matched += 1

        # Map category count to 0-3 score:
        # 0 matches → 0, 1 match → 1, 2-3 matches → 2, 4+ matches → 3
        if categories_matched == 0:
            return 0
        elif categories_matched == 1:
            return 1
        elif categories_matched <= 3:
            return 2
        else:
            return 3

    async def check_for_reload(self) -> None:
        """Poll for file changes and reload modified profiles.

        Checks modification times of profile files. If a file has changed
        since last load, attempts to reload it. On validation failure, the
        previous valid profile is retained (Requirement 8.5).

        Uses a 30-second polling interval to avoid excessive filesystem checks.
        """
        now = time.time()
        if now - self._last_check_ts < _RELOAD_POLL_INTERVAL_S:
            return
        self._last_check_ts = now

        for archetype in sorted(ARCHETYPES):
            filepath = self._profiles_dir / f"{archetype}.json"
            if not filepath.exists():
                continue

            try:
                current_mtime = os.path.getmtime(filepath)
            except OSError:
                continue

            last_mtime = self._file_mtimes.get(archetype, 0.0)
            if current_mtime > last_mtime:
                log.info(
                    "VoiceDNA detected change in '%s', reloading...",
                    archetype,
                )
                # _load_single_profile retains previous valid profile on failure
                self._load_single_profile(archetype)
