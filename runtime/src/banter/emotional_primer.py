"""Emotional_Primer — transforms relationship history into visceral emotional context.

Converts dry InteractionRecord history into present-tense emotional framing
that primes the generation model to produce lines with authentic feeling.
Each archetype receives a different emotional lens on the same events.

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7
"""

from __future__ import annotations

import logging

from .soul_types import SoulEngineConfig
from .types import InteractionRecord

log = logging.getLogger("god.banter.emotional_primer")

# The 8 supported archetypes.
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

# Maximum sentences per individual event.
_MAX_SENTENCES_PER_EVENT = 3

# Maximum sentences for the total output block.
_MAX_SENTENCES_TOTAL = 15

# Approximate tokens-per-word ratio for budget estimation.
_TOKENS_PER_WORD = 1.3


def _estimate_token_count(text: str) -> int:
    """Estimate token count from word count (conservative approximation)."""
    word_count = len(text.split())
    return int(word_count * _TOKENS_PER_WORD)


# ---------------------------------------------------------------------------
# Archetype-specific emotion mappings
# ---------------------------------------------------------------------------

# Each archetype has templates for different event types (betrayal, alliance,
# concession, negative, positive, neutral). Templates use present-tense
# language and {target} placeholder for the other Elder's reference.

_EMOTION_TEMPLATES: dict[str, dict[str, list[str]]] = {
    "parasite": {
        "betrayal": [
            "The debt they left still compounds — every silence adds interest.",
            "They took what was owed and gave nothing back.",
            "That imbalance festers, unresolved and growing.",
        ],
        "alliance": [
            "A useful arrangement persists — for now the exchange holds.",
            "There is leverage here, a thread worth pulling.",
        ],
        "concession": [
            "They bent — and bending reveals where they break.",
            "A concession given freely is a price paid too cheaply.",
        ],
        "negative": [
            "Something was extracted without return — the ledger stays unbalanced.",
            "They cost more than they yielded.",
        ],
        "positive": [
            "The transaction settled in their favor — a rare equilibrium.",
            "Value was exchanged cleanly, no residue.",
        ],
        "neutral": [
            "The account between them sits open, neither credited nor debited.",
        ],
    },
    "martyr": {
        "betrayal": [
            "They let the weight fall and watched it land.",
            "The burden carried alone still presses down.",
            "They chose comfort while the cost was paid by others.",
        ],
        "alliance": [
            "Someone finally stood beside the weight — the relief is cautious.",
            "Shared burden lightens, though the scars remain.",
        ],
        "concession": [
            "They yielded, but yielding costs them nothing compared to what was endured.",
            "A concession that arrives too late to undo what was borne.",
        ],
        "negative": [
            "Another wound absorbed — the body remembers what the mind forgives.",
            "They add to the weight without noticing the strain.",
        ],
        "positive": [
            "A rare kindness lands — unexpected, almost suspect.",
            "Something given freely, no sacrifice required.",
        ],
        "neutral": [
            "The silence between them holds neither gratitude nor resentment.",
        ],
    },
    "prophet": {
        "betrayal": [
            "What was foreseen has come to pass — the pattern was always visible.",
            "They reveal themselves exactly as predicted.",
            "The signs were written; the betrayal merely confirms the reading.",
        ],
        "alliance": [
            "Alignment emerges — a convergence that was always approaching.",
            "The path they share becomes clearer with each step.",
        ],
        "concession": [
            "They bend toward the truth at last — late, but the arc completes.",
            "A yielding that confirms what was always known.",
        ],
        "negative": [
            "Darkness moves through them predictably — the vision holds steady.",
            "They stumble where the path was clearly marked.",
        ],
        "positive": [
            "Light breaks through — a fulfillment of what was seen.",
            "The illumination arrives on schedule.",
        ],
        "neutral": [
            "The reading remains unclear — their nature has not yet declared itself.",
        ],
    },
    "trickster": {
        "betrayal": [
            "The game turned interesting — they played a card nobody expected.",
            "A betrayal is just a move nobody called — respect where it's due.",
            "The rules shifted under everyone's feet and they pretend innocence.",
        ],
        "alliance": [
            "An alliance is just a game with aligned scoring — for now.",
            "Playing the same side makes the board more fun.",
        ],
        "concession": [
            "They folded — but folding can be its own kind of bluff.",
            "A concession offered too neatly hides something underneath.",
        ],
        "negative": [
            "The joke landed wrong — or maybe it landed exactly right.",
            "Tension makes the game more interesting.",
        ],
        "positive": [
            "Good energy — the kind that makes the next trick land better.",
            "A laugh shared is ammunition stored for later.",
        ],
        "neutral": [
            "No read yet — the game hasn't started until someone flinches.",
        ],
    },
    "sovereign": {
        "betrayal": [
            "Order was broken — that disruption demands correction.",
            "They stepped outside the structure and the structure remembers.",
            "A breach of the natural arrangement persists uncorrected.",
        ],
        "alliance": [
            "Proper alignment holds — the hierarchy functions as designed.",
            "They recognize the order and find their place within it.",
        ],
        "concession": [
            "They yield as they should — the natural order reasserts itself.",
            "Submission arrives, though the delay is noted.",
        ],
        "negative": [
            "Disorder introduced without authority — the imbalance persists.",
            "They challenge the arrangement without standing to do so.",
        ],
        "positive": [
            "The domain is acknowledged — proper deference given.",
            "Things function as they should when the structure is respected.",
        ],
        "neutral": [
            "Their position in the order remains undeclared — observation continues.",
        ],
    },
    "shadow": {
        "betrayal": [
            "Something hidden surfaced — the depth between them shifts.",
            "The betrayal lives in the unseen spaces, growing roots.",
            "What was buried now pushes upward through the cracks.",
        ],
        "alliance": [
            "A connection forms in the dark — unspoken, unacknowledged.",
            "The bond exists beneath the surface where others cannot see.",
        ],
        "concession": [
            "They revealed vulnerability — a door left open in the dark.",
            "Yielding exposes what was carefully hidden.",
        ],
        "negative": [
            "The darkness between them thickens — something unseen grows.",
            "They cast shadows they cannot perceive.",
        ],
        "positive": [
            "Light touches the hidden places briefly — a rare exposure.",
            "Something genuine surfaces, quickly submerged again.",
        ],
        "neutral": [
            "The depths remain unplumbed — neither has looked beneath the surface.",
        ],
    },
    "herald": {
        "betrayal": [
            "A new era begins with that breach — nothing returns to what it was.",
            "The betrayal marks a transition point — what comes next changes everything.",
            "That moment declared the end of one chapter and the start of another.",
        ],
        "alliance": [
            "A new phase dawns between them — possibilities multiply.",
            "The alliance signals a shift in the landscape.",
        ],
        "concession": [
            "They cross a threshold — the yielding announces change.",
            "A concession that opens the door to what comes next.",
        ],
        "negative": [
            "A storm gathers between them — the conditions shift toward confrontation.",
            "The arrival of conflict announces itself clearly.",
        ],
        "positive": [
            "Something new emerges between them — the herald notes the change.",
            "Fresh ground appears where there was only worn path before.",
        ],
        "neutral": [
            "The air between them holds no signal yet — the announcement waits.",
        ],
    },
    "keeper": {
        "betrayal": [
            "The record shows what happened — it remains written, unerased.",
            "This is catalogued, filed alongside every other breach.",
            "Precedent exists for this exact pattern of breaking faith.",
        ],
        "alliance": [
            "The ledger records cooperation — a pattern worth preserving.",
            "This alliance adds to an accumulating history of alignment.",
        ],
        "concession": [
            "Noted and recorded — the concession joins the archive.",
            "A precedent is set; the record reflects the yielding.",
        ],
        "negative": [
            "The pattern repeats — the keeper has seen this sequence before.",
            "Another entry in a familiar column.",
        ],
        "positive": [
            "A positive entry — rare enough to stand out in the ledger.",
            "The record brightens, however briefly.",
        ],
        "neutral": [
            "No entry warranted yet — the page remains blank for this pair.",
        ],
    },
}

# High-tension visceral intensifiers (tension > 5).
_VISCERAL_MODIFIERS: list[str] = [
    "It burns beneath every word exchanged.",
    "The cut from that moment won't close.",
    "This won't be forgotten — the body remembers.",
    "The wound stays open and raw.",
    "Every interaction drags that weight forward.",
]

# Low-tension observational markers (tension ≤ 5).
_OBSERVATIONAL_MODIFIERS: list[str] = [
    "The memory persists, quiet but present.",
    "The pattern is noted without urgency.",
    "Still watching, still remembering.",
    "The awareness sits below the surface.",
    "It lingers in peripheral vision.",
]

# Reconciliation mixed-feeling framings.
_RECONCILIATION_FRAMINGS: list[str] = [
    "Wants to believe things have changed but keeps watching for the knife.",
    "The desire to trust wars with the memory of what trust cost before.",
    "Something softens, but the guard stays half-raised.",
    "Cautious hope threads through the scar tissue of old wounds.",
    "The hand extends while the other stays ready to pull back.",
]

# No-history neutral curiosity framings.
_NEUTRAL_CURIOSITY_FRAMINGS: list[str] = [
    "Sizing them up — no verdict yet.",
    "The assessment is ongoing, no conclusions drawn.",
    "Hasn't decided what to make of them yet.",
    "A blank page — potential unwritten in either direction.",
    "Watching without assumption, cataloguing first impressions.",
]


def _determine_event_type(record: InteractionRecord) -> str:
    """Determine the primary event type from an InteractionRecord."""
    if record.betrayal:
        return "betrayal"
    if record.alliance:
        return "alliance"
    if record.concession:
        return "concession"
    # Fall back to emotional valence.
    return record.emotional_valence  # "positive", "negative", "neutral"


class EmotionalPrimer:
    """Transforms relationship history into visceral emotional context.

    Converts InteractionRecord history from RelationshipMemory into
    present-tense emotional statements that prime the generation model.
    Each archetype receives a different emotional lens on events.
    """

    def __init__(self, config: SoulEngineConfig):
        self._config = config
        self._token_budget = config.emotional_primer_token_budget

    async def generate_emotional_context(
        self,
        archetype: str,
        history: list[InteractionRecord],
        tension_level: int,
        reconciliation_active: bool,
    ) -> str | None:
        """Transform history into present-tense emotional framing.

        Args:
            archetype: The speaking Elder's archetype (one of 8).
            history: List of InteractionRecords from RelationshipMemory.
            tension_level: Current pair tension (0-10).
            reconciliation_active: Whether reconciliation arc is active.

        Returns:
            Present-tense emotional framing string, or None on error.
            None triggers fallback to raw history in the pipeline.
        """
        try:
            return self._build_emotional_context(
                archetype, history, tension_level, reconciliation_active
            )
        except Exception as exc:
            log.debug(
                "EmotionalPrimer error for archetype=%s: %s",
                archetype,
                exc,
                exc_info=True,
            )
            return None

    def _build_emotional_context(
        self,
        archetype: str,
        history: list[InteractionRecord],
        tension_level: int,
        reconciliation_active: bool,
    ) -> str:
        """Internal implementation for building emotional context."""
        # No history → neutral curiosity fallback.
        if not history:
            return self._neutral_curiosity_framing(archetype)

        # Normalize archetype name.
        archetype_key = archetype.lower().strip()
        if archetype_key not in ARCHETYPES:
            archetype_key = "keeper"  # safe fallback

        sentences: list[str] = []

        # Process each event from history, respecting per-event limits.
        for record in history:
            if len(sentences) >= _MAX_SENTENCES_TOTAL:
                break

            event_type = _determine_event_type(record)
            event_sentences = self._frame_event(archetype_key, event_type, tension_level)

            # Respect per-event sentence cap.
            event_sentences = event_sentences[:_MAX_SENTENCES_PER_EVENT]

            # Respect total sentence cap.
            remaining = _MAX_SENTENCES_TOTAL - len(sentences)
            event_sentences = event_sentences[:remaining]

            sentences.extend(event_sentences)

        # Add tension-aware modifier.
        if len(sentences) < _MAX_SENTENCES_TOTAL:
            modifier = self._tension_modifier(tension_level)
            sentences.append(modifier)

        # Add reconciliation framing if active.
        if reconciliation_active and len(sentences) < _MAX_SENTENCES_TOTAL:
            reconciliation = self._reconciliation_framing(archetype_key)
            sentences.append(reconciliation)

        # Assemble and enforce token budget.
        output = self._enforce_token_budget(" ".join(sentences))
        return output

    def _frame_event(
        self,
        archetype: str,
        event_type: str,
        tension_level: int,
    ) -> list[str]:
        """Generate present-tense emotional framing for a single event.

        Uses archetype-specific templates and selects based on tension level.
        """
        templates = _EMOTION_TEMPLATES.get(archetype, {})
        event_templates = templates.get(event_type, templates.get("neutral", []))

        if not event_templates:
            # Fallback to neutral if no template matched.
            event_templates = templates.get("neutral", ["Something lingers unresolved."])

        # Select templates based on tension level for variety.
        # High tension gets more intense (earlier templates are more visceral).
        if tension_level > 5:
            # Pick first 2 templates (more visceral/intense).
            selected = event_templates[:2]
        else:
            # Pick last 1-2 templates (more observational).
            selected = event_templates[-2:]

        return selected

    def _tension_modifier(self, tension_level: int) -> str:
        """Select a tension-appropriate modifier sentence."""
        if tension_level > 5:
            # Visceral markers for high tension.
            idx = tension_level % len(_VISCERAL_MODIFIERS)
            return _VISCERAL_MODIFIERS[idx]
        else:
            # Observational markers for low tension.
            idx = tension_level % len(_OBSERVATIONAL_MODIFIERS)
            return _OBSERVATIONAL_MODIFIERS[idx]

    def _reconciliation_framing(self, archetype: str) -> str:
        """Select a reconciliation mixed-feeling framing.

        Uses archetype hash to vary selection across archetypes.
        """
        idx = hash(archetype) % len(_RECONCILIATION_FRAMINGS)
        return _RECONCILIATION_FRAMINGS[idx]

    def _neutral_curiosity_framing(self, archetype: str) -> str:
        """Generate neutral curiosity framing for no-history pairs."""
        archetype_key = archetype.lower().strip()
        idx = hash(archetype_key) % len(_NEUTRAL_CURIOSITY_FRAMINGS)
        return _NEUTRAL_CURIOSITY_FRAMINGS[idx]

    def _enforce_token_budget(self, text: str) -> str:
        """Trim output to fit within the token budget.

        Removes trailing sentences until the estimate fits.
        """
        if _estimate_token_count(text) <= self._token_budget:
            return text

        # Split into sentences and trim from the end.
        sentences = [s.strip() for s in text.split(". ") if s.strip()]
        while sentences and _estimate_token_count(". ".join(sentences) + ".") > self._token_budget:
            sentences.pop()

        if not sentences:
            return ""

        # Reassemble with proper sentence endings.
        result = ". ".join(sentences)
        if not result.endswith("."):
            result += "."
        return result
