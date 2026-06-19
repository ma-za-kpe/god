"""HardBanChecker — final delivery gate before any BeatResult is emitted.

Hard bans are absolute. A hard-ban violation is DISCARDED, never refined.
This is the last gate before delivery for all modes except SILENCE.

Implements all 7 mandatory bans from Section 10 of the contract.

Requirements: 10.1, 10.2, 10.3
"""

# ruff: noqa: I001
from __future__ import annotations

import re

from .contract_types import HardBanVerdict
from .mode_types import BeatMode, BeatModePolicy


# ---------------------------------------------------------------------------
# Banned phrase lists (Section 10.1)
# ---------------------------------------------------------------------------

DISCORD_REGISTER_PHRASES: list[str] = [
    "buckle up",
    "breaking news:",
    "coming in hot",
    "that's a no from me",
    "not gonna lie",
    "big yikes",
    "we are not doing this",
    "this is fine",
]

GENERIC_DEBATER_PHRASES: list[str] = [
    "that's fair",
    "good point",
    "interesting take",
    "you make a valid argument",
    "i see your point",
    "let's agree to disagree",
]

# Archetypes exempt from subjectless_opening ban
SUBJECTLESS_EXEMPT_ARCHETYPES: frozenset[str] = frozenset({"shadow", "trickster"})

# Regex for detecting lines starting with verb/gerund (subjectless opening)
_GERUND_START_RE = re.compile(
    r"^(being|having|getting|making|taking|going|coming|running|looking|"
    r"trying|keeping|feeling|thinking|saying|doing|asking|watching|waiting|"
    r"holding|pulling|pushing|breaking|building|burning|calling|carrying|"
    r"cutting|dealing|drawing|driving|eating|falling|fighting|finding|"
    r"flying|following|forgetting|giving|growing|hearing|hitting|hoping|"
    r"hurting|killing|knowing|leading|learning|leaving|letting|living|"
    r"losing|loving|meaning|meeting|moving|needing|opening|paying|"
    r"playing|putting|reading|remembering|rising|seeing|selling|"
    r"sending|setting|showing|sitting|speaking|spending|standing|"
    r"starting|staying|stopping|taking|talking|teaching|telling|"
    r"turning|understanding|using|walking|wanting|working|writing)\b",
    re.IGNORECASE,
)

# Common imperative verbs at start of sentence (subjectless)
_IMPERATIVE_START_RE = re.compile(
    r"^(look|listen|see|hear|watch|tell|give|take|let|make|come|go|"
    r"stop|start|keep|try|ask|think|consider|imagine|remember|forget|"
    r"notice|observe|admit|accept|realize|understand)\b",
    re.IGNORECASE,
)


class HardBanChecker:
    """Final delivery gate — checks all 7 hard bans before emission.

    Hard bans run after generation and before delivery for all modes
    except SILENCE. Violations are DISCARDED, never refined.

    The 7 bans:
    1. no_sentence_boundaries — two+ clauses without punctuation
    2. discord_register — internet slang / Discord voice
    3. generic_debater — generic debate phrases
    4. arc_theme_title_leak — literal arc theme title in output
    5. subjectless_opening — verb/gerund start without subject
    6. too_long — exceeds mode word limit
    7. too_short — below mode word limit

    Requirements: 10.1, 10.2, 10.3
    """

    def check(
        self,
        candidate: str,
        *,
        policy: BeatModePolicy,
        arc_theme_title: str,
        archetype: str,
    ) -> HardBanVerdict:
        """Run all hard bans on a candidate line.

        Args:
            candidate: The generated line to check.
            policy: The active BeatModePolicy (determines word limits).
            arc_theme_title: The raw arc theme title (must not appear).
            archetype: The speaker's archetype (for ban exceptions).

        Returns:
            HardBanVerdict — passed=True if all bans pass.
        """
        # Ban 1: no_sentence_boundaries
        verdict = self._check_sentence_boundaries(candidate)
        if not verdict.passed:
            return verdict

        # Ban 2: arc_theme_title_leak
        verdict = self._check_arc_title_leak(candidate, arc_theme_title)
        if not verdict.passed:
            return verdict

        # Ban 3: discord_register
        verdict = self._check_discord_register(candidate)
        if not verdict.passed:
            return verdict

        # Ban 4: generic_debater
        verdict = self._check_generic_debater(candidate)
        if not verdict.passed:
            return verdict

        # Ban 5: subjectless_opening (with archetype exceptions)
        verdict = self._check_subjectless_opening(candidate, archetype, policy)
        if not verdict.passed:
            return verdict

        # Ban 6: too_long
        verdict = self._check_too_long(candidate, policy)
        if not verdict.passed:
            return verdict

        # Ban 7: too_short (backchannel exempt)
        verdict = self._check_too_short(candidate, policy)
        if not verdict.passed:
            return verdict

        return HardBanVerdict(passed=True)

    def _check_sentence_boundaries(self, candidate: str) -> HardBanVerdict:
        """Ban 1: Two or more clauses without punctuation between them.

        Detects run-on sentences by checking for long stretches of words
        without any clause-ending punctuation.
        """
        # Split by sentence-ending punctuation
        sentences = re.split(r'[.!?]+', candidate)
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            # Count words in this sentence fragment
            words = sentence.split()
            # A fragment with 20+ words and no internal punctuation is a run-on
            if len(words) > 20:
                # Check for internal clause markers (comma, semicolon, dash, colon)
                if not re.search(r'[,;:\u2014—\-]', sentence):
                    return HardBanVerdict(
                        passed=False,
                        violated_ban="no_sentence_boundaries",
                        violation_detail=f"Run-on clause with {len(words)} words and no internal punctuation",
                    )
        return HardBanVerdict(passed=True)

    def _check_discord_register(self, candidate: str) -> HardBanVerdict:
        """Ban 2: Internet slang, sports commentary, Discord moderation voice."""
        lower = candidate.lower()
        for phrase in DISCORD_REGISTER_PHRASES:
            if phrase in lower:
                return HardBanVerdict(
                    passed=False,
                    violated_ban="discord_register",
                    violation_detail=f"Contains banned phrase: '{phrase}'",
                )
        return HardBanVerdict(passed=True)

    def _check_generic_debater(self, candidate: str) -> HardBanVerdict:
        """Ban 3: Line could have been said by any Elder."""
        lower = candidate.lower()
        for phrase in GENERIC_DEBATER_PHRASES:
            if phrase in lower:
                return HardBanVerdict(
                    passed=False,
                    violated_ban="generic_debater",
                    violation_detail=f"Contains generic debater phrase: '{phrase}'",
                )
        return HardBanVerdict(passed=True)

    def _check_arc_title_leak(self, candidate: str, arc_theme_title: str) -> HardBanVerdict:
        """Ban 4: Line contains the literal arc theme title string."""
        if not arc_theme_title:
            return HardBanVerdict(passed=True)

        # Normalize for comparison
        candidate_lower = candidate.lower()
        title_lower = arc_theme_title.lower().strip()

        if title_lower and title_lower in candidate_lower:
            return HardBanVerdict(
                passed=False,
                violated_ban="arc_theme_title_leak",
                violation_detail=f"Contains arc theme title: '{arc_theme_title}'",
            )
        return HardBanVerdict(passed=True)

    def _check_subjectless_opening(
        self, candidate: str, archetype: str, policy: BeatModePolicy
    ) -> HardBanVerdict:
        """Ban 5: Line starts with a verb or gerund without a subject.

        Exceptions: shadow and trickster archetypes are exempt.
        Backchannel mode is also exempt (short reactive utterances).
        """
        if archetype in SUBJECTLESS_EXEMPT_ARCHETYPES:
            return HardBanVerdict(passed=True)

        if policy.mode == BeatMode.BACKCHANNEL:
            return HardBanVerdict(passed=True)

        stripped = candidate.strip()
        if not stripped:
            return HardBanVerdict(passed=True)

        if _GERUND_START_RE.match(stripped) or _IMPERATIVE_START_RE.match(stripped):
            return HardBanVerdict(
                passed=False,
                violated_ban="subjectless_opening",
                violation_detail=f"Line starts with verb/gerund without subject: '{stripped[:30]}...'",
            )
        return HardBanVerdict(passed=True)

    def _check_too_long(self, candidate: str, policy: BeatModePolicy) -> HardBanVerdict:
        """Ban 6: Line exceeds mode word limit."""
        if policy.word_count_max == 0:
            return HardBanVerdict(passed=True)

        word_count = len(candidate.split())
        if word_count > policy.word_count_max:
            return HardBanVerdict(
                passed=False,
                violated_ban="too_long",
                violation_detail=f"Word count {word_count} exceeds max {policy.word_count_max}",
            )
        return HardBanVerdict(passed=True)

    def _check_too_short(self, candidate: str, policy: BeatModePolicy) -> HardBanVerdict:
        """Ban 7: Line is below mode word limit.

        Backchannel mode is exempt from this ban (Section 10.3).
        """
        if policy.mode == BeatMode.BACKCHANNEL:
            return HardBanVerdict(passed=True)

        if policy.word_count_min == 0:
            return HardBanVerdict(passed=True)

        word_count = len(candidate.split())
        if word_count < policy.word_count_min:
            return HardBanVerdict(
                passed=False,
                violated_ban="too_short",
                violation_detail=f"Word count {word_count} below min {policy.word_count_min}",
            )
        return HardBanVerdict(passed=True)
