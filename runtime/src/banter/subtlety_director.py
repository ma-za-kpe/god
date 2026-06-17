"""Subtlety_Director — manages subtext injection and scoring for layered meaning.

Determines when a line should carry subtext based on dramatic conditions,
injects subtext instructions (surface meaning, implied meaning, technique)
into generation prompts, enforces technique variety, and provides
subtext_depth scoring for Quality_Judge integration.

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6
"""

from __future__ import annotations

import logging
import random
from collections import deque

from .soul_types import SoreSpot, SoulEngineConfig, SubtextInstruction

log = logging.getLogger("god.banter.subtlety_director")

# Approximate tokens-per-word ratio for budget estimation.
_TOKENS_PER_WORD = 1.3


def _estimate_token_count(text: str) -> int:
    """Estimate token count from word count (conservative approximation)."""
    word_count = len(text.split())
    return int(word_count * _TOKENS_PER_WORD)


# ---------------------------------------------------------------------------
# Subtext technique templates
# ---------------------------------------------------------------------------

# Each technique has templates for building surface/implied meaning pairs.
# Templates use {target}, {sore_spot}, and {arc_theme} placeholders.

_TECHNIQUE_TEMPLATES: dict[str, dict[str, list[str]]] = {
    "loaded_question": {
        "surface": [
            "Ask about {arc_theme} as if genuinely curious.",
            "Pose a question about {target}'s position on {arc_theme} that seems innocent.",
            "Frame a question that appears neutral but contains a premise {target} can't accept.",
        ],
        "implied": [
            "The question itself presumes {target}'s guilt or weakness.",
            "Asking forces {target} to either agree with a damaging premise or look evasive.",
            "The curiosity is performative — the answer is already known.",
        ],
    },
    "double_entendre": {
        "surface": [
            "Make a statement about {arc_theme} that reads as straightforward commentary.",
            "Offer praise or acknowledgment that can be taken at face value.",
            "Reference a shared situation in terms that seem neutral.",
        ],
        "implied": [
            "The same words carry a second meaning that references {target}'s vulnerability.",
            "The compliment contains its own negation for those paying attention.",
            "The neutral framing encodes a specific accusation about past behavior.",
        ],
    },
    "callback_inversion": {
        "surface": [
            "Echo something {target} previously said as if agreeing with it.",
            "Reference a past position of {target}'s approvingly.",
            "Restate {target}'s earlier argument in the current context.",
        ],
        "implied": [
            "The echo inverts the original meaning — their own words condemn them now.",
            "Agreement with the old position highlights how {target} has contradicted themselves.",
            "Restating reveals that {target}'s logic, applied consistently, undermines their current stance.",
        ],
    },
    "strategic_omission": {
        "surface": [
            "Discuss {arc_theme} comprehensively but leave one crucial element unmentioned.",
            "List relevant factors while conspicuously skipping {target}'s contribution.",
            "Acknowledge everyone's position except {target}'s, as if it doesn't exist.",
        ],
        "implied": [
            "What goes unsaid is louder than what's spoken — the gap is the message.",
            "The omission signals that {target}'s position isn't worth addressing.",
            "Silence where acknowledgment should be communicates deliberate erasure.",
        ],
    },
    "damning_praise": {
        "surface": [
            "Compliment {target}'s consistency or dedication sincerely.",
            "Praise {target}'s approach to {arc_theme} with apparent respect.",
            "Acknowledge {target}'s effort and commitment to their position.",
        ],
        "implied": [
            "The praise highlights exactly the quality that makes {target} wrong or dangerous.",
            "Dedication to a flawed position isn't a virtue — the compliment frames stubbornness.",
            "Respect for effort implicitly questions whether the effort achieves anything worthwhile.",
        ],
    },
}

# Context hint templates keyed by whether a sore spot is available.
_CONTEXT_HINTS_WITH_SORE_SPOT: list[str] = [
    "Reference their sensitivity to {sore_spot} without naming it directly.",
    "Let the subtext brush against {sore_spot} — they'll feel it without you spelling it out.",
    "The undertone should activate {target}'s known vulnerability around {sore_spot}.",
]

_CONTEXT_HINTS_WITHOUT_SORE_SPOT: list[str] = [
    "Let the subtext operate through implication alone — no specific wound to target.",
    "The layered meaning works through structural irony rather than personal attack.",
    "Subtext derives from the situation itself rather than personal history.",
]


class SubtletyDirector:
    """Manages subtext injection and scoring for layered meaning.

    Determines when a line should carry subtext based on dramatic conditions
    (tension, move type, sore spots), generates subtext instructions for
    the generation model, enforces technique variety per Elder, and scores
    subtext depth for the Quality_Judge.
    """

    TECHNIQUES = [
        "loaded_question",
        "double_entendre",
        "callback_inversion",
        "strategic_omission",
        "damning_praise",
    ]

    def __init__(self, config: SoulEngineConfig, seed: int | None = None):
        """Initialize the SubtletyDirector.

        Args:
            config: Soul engine configuration with feature flags and token budgets.
            seed: Optional random seed for deterministic behavior in tests.
        """
        self._config = config
        self._token_budget = config.subtlety_token_budget
        # Per-Elder technique history: elder_name -> deque of last 5 techniques used.
        self._technique_history: dict[str, deque[str]] = {}
        # Random instance for deterministic testing.
        self._rng = random.Random(seed)

    def should_inject_subtext(
        self,
        tension: int,
        move: str,
        has_sore_spot: bool,
        has_history: bool,
    ) -> bool:
        """Determine if subtext should be injected for this generation.

        Activation requires at least one condition to be true:
        - Pair tension between 4 and 8
        - Current move is DEFLECT or QUESTION
        - Target Elder has a stored sore spot matching current arc theme

        Deactivation overrides (always prevent activation):
        - Tension < 2
        - Move is CONCEDE
        - No relationship history

        Special case: tension > 8 reduces probability to 20%.

        Args:
            tension: Current pair tension level (0-10).
            move: The current move type (e.g., "DEFLECT", "COUNTER").
            has_sore_spot: Whether target has a sore spot matching arc theme.
            has_history: Whether relationship history exists for this pair.

        Returns:
            True if subtext should be injected, False otherwise.
        """
        # --- Deactivation overrides (hard blocks) ---
        if tension < 2:
            return False
        if move == "CONCEDE":
            return False
        if not has_history:
            return False

        # --- Check activation conditions ---
        tension_in_range = 4 <= tension <= 8
        move_triggers = move in ("DEFLECT", "QUESTION")
        sore_spot_available = has_sore_spot

        has_activation_condition = tension_in_range or move_triggers or sore_spot_available

        if not has_activation_condition:
            return False

        # --- High tension rate reduction ---
        if tension > 8:
            # 20% probability of activation at extreme tension.
            return self._rng.random() < 0.20

        return True

    def generate_subtext_instruction(
        self,
        elder: str,
        target: str,
        tension: int,
        sore_spot: SoreSpot | None,
        arc_theme: str,
    ) -> SubtextInstruction | None:
        """Build subtext instruction with surface/implied meaning and technique.

        Selects a technique that respects the variety constraint (same technique
        ≤ 2 in 5 consecutive uses per Elder), then builds surface meaning,
        implied meaning, and context hint from templates.

        Args:
            elder: The speaking Elder's name.
            target: The target Elder's name.
            tension: Current pair tension level.
            sore_spot: Optional sore spot for the target Elder.
            arc_theme: The current arc theme.

        Returns:
            A SubtextInstruction if generation succeeds within token budget,
            or None if no valid technique is available.
        """
        try:
            # Select technique respecting variety constraint.
            technique = self._select_technique(elder)
            if technique is None:
                log.debug(
                    "No valid technique available for elder=%s (all exceed variety limit)",
                    elder,
                )
                return None

            # Build the instruction from templates.
            instruction = self._build_instruction(
                technique, elder, target, tension, sore_spot, arc_theme
            )

            # Record the technique in history.
            self._record_technique(elder, technique)

            # Enforce token budget.
            if not self._within_token_budget(instruction):
                log.debug(
                    "Subtext instruction exceeds token budget (%d), trimming",
                    self._token_budget,
                )
                instruction = self._trim_to_budget(instruction)

            return instruction

        except Exception as exc:
            log.debug(
                "SubtletyDirector error generating instruction: %s",
                exc,
                exc_info=True,
            )
            return None

    def score_subtext_depth(self, candidate: str, instruction: SubtextInstruction) -> int:
        """Score subtext depth (0-3) for Quality_Judge integration.

        Scoring criteria:
        - 0: No subtext detected in candidate.
        - 1: Surface-level subtext present (candidate references the technique).
        - 2: Moderate depth (surface + implied meaning detectable).
        - 3: Full depth (all layers present, technique clearly employed).

        Args:
            candidate: The generated line to evaluate.
            instruction: The SubtextInstruction that was provided to generation.

        Returns:
            Integer score in [0, 3].
        """
        if not candidate or not candidate.strip():
            return 0

        score = 0
        candidate_lower = candidate.lower()

        # Check for surface meaning indicators.
        surface_words = self._extract_key_words(instruction.surface_meaning)
        surface_overlap = self._compute_word_overlap(candidate_lower, surface_words)

        # Check for implied meaning indicators.
        implied_words = self._extract_key_words(instruction.implied_meaning)
        implied_overlap = self._compute_word_overlap(candidate_lower, implied_words)

        # Check for technique markers.
        technique_present = self._detect_technique_markers(
            candidate_lower, instruction.technique
        )

        # Scoring logic:
        # 1 point: Surface meaning is referenced (overlap > 0.15)
        if surface_overlap > 0.15:
            score += 1

        # 1 point: Implied meaning is detectable (overlap > 0.10)
        if implied_overlap > 0.10:
            score += 1

        # 1 point: Technique is clearly employed
        if technique_present:
            score += 1

        # Clamp to [0, 3]
        return min(score, 3)

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _select_technique(self, elder: str) -> str | None:
        """Select a technique respecting the variety constraint.

        The same technique cannot appear more than 2 times in the last 5
        consecutive uses for this Elder.

        Returns:
            A valid technique name, or None if all are blocked.
        """
        history = self._get_technique_history(elder)

        # Find available techniques (those with count < 2 in last 5).
        available = []
        for technique in self.TECHNIQUES:
            count_in_window = sum(1 for t in history if t == technique)
            if count_in_window < 2:
                available.append(technique)

        if not available:
            return None

        # Random selection from available techniques.
        return self._rng.choice(available)

    def _get_technique_history(self, elder: str) -> deque[str]:
        """Get or create the technique history deque for an Elder."""
        if elder not in self._technique_history:
            self._technique_history[elder] = deque(maxlen=5)
        return self._technique_history[elder]

    def _record_technique(self, elder: str, technique: str) -> None:
        """Record a technique usage in the Elder's history."""
        history = self._get_technique_history(elder)
        history.append(technique)

    def _build_instruction(
        self,
        technique: str,
        elder: str,
        target: str,
        tension: int,
        sore_spot: SoreSpot | None,
        arc_theme: str,
    ) -> SubtextInstruction:
        """Build a SubtextInstruction from templates.

        Selects surface/implied meaning templates and fills placeholders.
        """
        templates = _TECHNIQUE_TEMPLATES[technique]

        # Select a surface meaning template.
        surface_template = self._rng.choice(templates["surface"])
        implied_template = self._rng.choice(templates["implied"])

        # Fill placeholders.
        sore_spot_topic = sore_spot.topic if sore_spot else "their position"
        replacements = {
            "{target}": target,
            "{arc_theme}": arc_theme,
            "{sore_spot}": sore_spot_topic,
        }

        surface_meaning = self._fill_template(surface_template, replacements)
        implied_meaning = self._fill_template(implied_template, replacements)

        # Build context hint.
        if sore_spot:
            hint_templates = _CONTEXT_HINTS_WITH_SORE_SPOT
            hint_replacements = {
                "{sore_spot}": sore_spot.topic,
                "{target}": target,
            }
        else:
            hint_templates = _CONTEXT_HINTS_WITHOUT_SORE_SPOT
            hint_replacements = {"{target}": target}

        context_hint = self._fill_template(
            self._rng.choice(hint_templates), hint_replacements
        )

        return SubtextInstruction(
            surface_meaning=surface_meaning,
            implied_meaning=implied_meaning,
            technique=technique,
            context_hint=context_hint,
        )

    def _fill_template(self, template: str, replacements: dict[str, str]) -> str:
        """Fill template placeholders with actual values."""
        result = template
        for placeholder, value in replacements.items():
            result = result.replace(placeholder, value)
        return result

    def _within_token_budget(self, instruction: SubtextInstruction) -> bool:
        """Check if a SubtextInstruction is within the token budget."""
        total_text = (
            f"{instruction.surface_meaning} "
            f"{instruction.implied_meaning} "
            f"{instruction.technique} "
            f"{instruction.context_hint}"
        )
        return _estimate_token_count(total_text) <= self._token_budget

    def _trim_to_budget(self, instruction: SubtextInstruction) -> SubtextInstruction:
        """Trim instruction fields to fit within token budget.

        Shortens context_hint first, then implied_meaning if needed.
        """
        # Start by trimming context_hint.
        trimmed_hint = self._trim_text(
            instruction.context_hint, max_words=15
        )
        candidate = SubtextInstruction(
            surface_meaning=instruction.surface_meaning,
            implied_meaning=instruction.implied_meaning,
            technique=instruction.technique,
            context_hint=trimmed_hint,
        )
        if self._within_token_budget(candidate):
            return candidate

        # Trim implied_meaning as well.
        trimmed_implied = self._trim_text(
            instruction.implied_meaning, max_words=15
        )
        candidate = SubtextInstruction(
            surface_meaning=instruction.surface_meaning,
            implied_meaning=trimmed_implied,
            technique=instruction.technique,
            context_hint=trimmed_hint,
        )
        if self._within_token_budget(candidate):
            return candidate

        # Trim surface_meaning as last resort.
        trimmed_surface = self._trim_text(
            instruction.surface_meaning, max_words=15
        )
        return SubtextInstruction(
            surface_meaning=trimmed_surface,
            implied_meaning=trimmed_implied,
            technique=instruction.technique,
            context_hint=trimmed_hint,
        )

    def _trim_text(self, text: str, max_words: int) -> str:
        """Trim text to a maximum word count."""
        words = text.split()
        if len(words) <= max_words:
            return text
        return " ".join(words[:max_words]) + "..."

    def _extract_key_words(self, text: str) -> set[str]:
        """Extract meaningful keywords from text (skip stop words)."""
        stop_words = frozenset(
            {
                "a", "an", "the", "is", "are", "was", "were", "be", "been",
                "being", "have", "has", "had", "do", "does", "did", "will",
                "would", "could", "should", "may", "might", "shall", "can",
                "to", "of", "in", "for", "on", "with", "at", "by", "from",
                "as", "into", "through", "during", "before", "after", "above",
                "below", "between", "and", "but", "or", "nor", "not", "so",
                "yet", "both", "either", "neither", "each", "every", "all",
                "any", "few", "more", "most", "other", "some", "such", "no",
                "only", "own", "same", "than", "too", "very", "just", "that",
                "this", "these", "those", "it", "its", "they", "them", "their",
                "we", "us", "our", "you", "your", "he", "him", "his", "she",
                "her", "if", "then", "else", "when", "where", "why", "how",
                "what", "which", "who", "whom", "whose",
            }
        )
        words = set()
        for word in text.lower().split():
            # Strip punctuation.
            cleaned = word.strip(".,!?;:\"'-()[]{}—")
            if cleaned and cleaned not in stop_words and len(cleaned) > 2:
                words.add(cleaned)
        return words

    def _compute_word_overlap(self, candidate: str, key_words: set[str]) -> float:
        """Compute overlap ratio between candidate text and key words."""
        if not key_words:
            return 0.0
        candidate_words = set(candidate.split())
        # Strip punctuation from candidate words for fair comparison.
        candidate_cleaned = {
            w.strip(".,!?;:\"'-()[]{}—") for w in candidate_words
        }
        matches = candidate_cleaned & key_words
        return len(matches) / len(key_words)

    def _detect_technique_markers(self, candidate: str, technique: str) -> bool:
        """Detect if the candidate employs markers of the specified technique.

        Uses heuristic detection based on structural markers characteristic
        of each technique.
        """
        if technique == "loaded_question":
            # Loaded questions contain question marks and presuppositions.
            return "?" in candidate

        elif technique == "double_entendre":
            # Double entendres often use ambiguous phrasing or dual-meaning words.
            # Heuristic: contains quotation marks, italics markers, or emphasis.
            ambiguity_markers = ['"', "'", "—", "..."]
            return any(marker in candidate for marker in ambiguity_markers)

        elif technique == "callback_inversion":
            # Callback inversions reference past statements — look for echoing patterns.
            echo_markers = [
                "you said", "remember", "your words", "you told",
                "as you put it", "you once", "back when",
            ]
            return any(marker in candidate for marker in echo_markers)

        elif technique == "strategic_omission":
            # Strategic omission is hard to detect directly — look for conspicuous gaps.
            # Heuristic: shorter-than-expected response or trailing off.
            omission_markers = ["...", "—", "but I digress", "anyway"]
            return any(marker in candidate for marker in omission_markers) or len(candidate.split()) < 10

        elif technique == "damning_praise":
            # Damning praise contains compliments with undermining qualifiers.
            praise_words = ["admire", "respect", "credit", "dedication", "consistent", "committed"]
            undermine_words = ["but", "however", "though", "still", "yet", "despite"]
            has_praise = any(w in candidate for w in praise_words)
            has_undermine = any(w in candidate for w in undermine_words)
            return has_praise or has_undermine

        return False
