"""Fallback_Pool — Curated, weighted template pool with context substitution.

Provides broadcast-safe fallback lines when generation fails or quality is
below threshold. Supports session-aware de-duplication and context injection.
"""

from __future__ import annotations

import json
import logging
import random
import re
from collections import deque
from pathlib import Path
from typing import Optional

from .types import FallbackSelection, FallbackTemplate

log = logging.getLogger("god.banter.fallback_pool")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_DEFAULT_TEMPLATES_FILE = _TEMPLATE_DIR / "fallback_templates.json"

# Regex for placeholder tokens: {word}
_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")

# Valid placeholder names that we substitute
_VALID_PLACEHOLDERS = {"opponent", "theme", "callback"}

# The 6 move types supported in fallback templates
FALLBACK_MOVE_TYPES = ("COUNTER", "ESCALATE", "DEFLECT", "TAUNT", "QUESTION", "PIVOT")

# Minimum template requirements
MIN_TEMPLATES_PER_ARCHETYPE = 12
MIN_TEMPLATES_PER_MOVE = 2


# ---------------------------------------------------------------------------
# FallbackPool class
# ---------------------------------------------------------------------------


class FallbackPool:
    """Curated fallback template pool with weighted selection and substitution.

    Invariants:
    - At least 12 templates per archetype.
    - At least 2 templates per archetype × move_type combination.
    - No raw {token} placeholders in output.
    - 50% weight reduction for templates used in last 10 beats.
    - 80% weight reduction for templates used this session.
    - When both reductions apply, the minimum (most aggressive) is used.
    """

    def __init__(
        self,
        templates: list[FallbackTemplate],
        *,
        min_per_archetype: int = MIN_TEMPLATES_PER_ARCHETYPE,
        min_per_move: int = MIN_TEMPLATES_PER_MOVE,
    ):
        """Initialize pool with templates. Validates completeness.

        Args:
            templates: List of FallbackTemplate instances.
            min_per_archetype: Minimum templates per archetype (default 12).
            min_per_move: Minimum templates per archetype×move (default 2).

        Raises:
            ValueError: If minimum template counts are not met.
        """
        self._templates = templates
        self._by_archetype: dict[str, list[FallbackTemplate]] = {}
        self._by_archetype_move: dict[str, dict[str, list[FallbackTemplate]]] = {}

        # Index templates
        for t in templates:
            self._by_archetype.setdefault(t.archetype, []).append(t)
            self._by_archetype_move.setdefault(t.archetype, {})
            self._by_archetype_move[t.archetype].setdefault(t.move_type, []).append(t)

        # Validate on construction
        self._validate(min_per_archetype, min_per_move)

        # Session state
        self._session_used_ids: set[str] = set()
        self._recent_beat_ids: deque[str] = deque(maxlen=10)

    def _validate(self, min_per_archetype: int, min_per_move: int) -> None:
        """Validate that pool meets minimum template requirements.

        Raises:
            ValueError: If any archetype has < min_per_archetype templates
                       or any archetype×move has < min_per_move templates.
        """
        for archetype, templates in self._by_archetype.items():
            if len(templates) < min_per_archetype:
                raise ValueError(
                    f"Archetype '{archetype}' has {len(templates)} templates, "
                    f"need at least {min_per_archetype}"
                )

            # Check each of the 6 fallback move types
            move_dict = self._by_archetype_move.get(archetype, {})
            for move_type in FALLBACK_MOVE_TYPES:
                move_templates = move_dict.get(move_type, [])
                if len(move_templates) < min_per_move:
                    raise ValueError(
                        f"Archetype '{archetype}' move '{move_type}' has "
                        f"{len(move_templates)} templates, need at least {min_per_move}"
                    )

    def select(
        self,
        archetype: str,
        move_type: str,
        *,
        opponent_name: str | None = None,
        arc_theme: str | None = None,
        callback_phrase: str | None = None,
        recent_beat_ids: list[str] | None = None,
        session_used_ids: set[str] | None = None,
        excluded_ids: set[str] | None = None,
    ) -> FallbackSelection:
        """Select a weighted-random fallback template and substitute context.

        Weight modifiers:
        - 50% reduction for templates used in last 10 beats (multiply by 0.50)
        - 80% reduction for templates used this session (multiply by 0.20)
        - If both apply, take the minimum multiplier (0.20) rather than
          compounding (i.e., the most aggressive reduction wins)
        - Excluded IDs get weight 0 (completely skipped)

        Placeholders are substituted: {opponent}, {theme}, {callback}.
        Unavailable placeholders are gracefully removed from the output.

        Args:
            archetype: Speaker archetype.
            move_type: Desired move type.
            opponent_name: Optional opponent name for {opponent}.
            arc_theme: Optional theme for {theme}.
            callback_phrase: Optional callback for {callback}.
            recent_beat_ids: Override for recent beat template IDs.
            session_used_ids: Override for session-used template IDs.
            excluded_ids: Template IDs to completely exclude.

        Returns:
            FallbackSelection with fully substituted text.
        """
        # Use instance state if no overrides
        used_recent = (
            set(recent_beat_ids) if recent_beat_ids is not None else set(self._recent_beat_ids)
        )
        used_session = session_used_ids if session_used_ids is not None else self._session_used_ids
        excluded = excluded_ids or set()

        # Get candidates for this archetype + move
        candidates = self._by_archetype_move.get(archetype, {}).get(move_type, [])

        if not candidates:
            # Fall back to any template for this archetype
            candidates = self._by_archetype.get(archetype, [])

        if not candidates:
            # Emergency: pick any template at all
            candidates = self._templates

        # Compute weights
        weighted: list[tuple[FallbackTemplate, float]] = []
        for t in candidates:
            if t.template_id in excluded:
                continue

            weight = t.base_weight

            # Determine applicable multipliers
            in_recent = t.template_id in used_recent
            in_session = t.template_id in used_session

            if in_recent and in_session:
                # Apply minimum of the two reductions (most aggressive one wins)
                # 50% reduction = multiply by 0.50
                # 80% reduction = multiply by 0.20
                # Minimum multiplier = 0.20
                weight *= min(0.50, 0.20)
            elif in_recent:
                # 50% reduction for last-10-beats usage
                weight *= 0.50
            elif in_session:
                # 80% reduction for session usage
                weight *= 0.20

            if weight > 0:
                weighted.append((t, weight))

        if not weighted:
            # If all excluded/zeroed, use candidates without exclusion
            weighted = [(t, t.base_weight) for t in candidates if t.template_id not in excluded]
            if not weighted:
                weighted = [(t, t.base_weight) for t in candidates]

        # Weighted random selection
        templates_list = [t for t, _ in weighted]
        weights_list = [w for _, w in weighted]
        selected = random.choices(templates_list, weights=weights_list, k=1)[0]

        # Context substitution
        text = self._substitute(
            selected.template,
            opponent_name=opponent_name,
            arc_theme=arc_theme,
            callback_phrase=callback_phrase,
        )

        # Record usage in instance state
        self._session_used_ids.add(selected.template_id)
        self._recent_beat_ids.append(selected.template_id)

        return FallbackSelection(
            text=text,
            template_id=selected.template_id,
            archetype=selected.archetype,
            move_type=selected.move_type,
        )

    def _substitute(
        self,
        template: str,
        *,
        opponent_name: str | None = None,
        arc_theme: str | None = None,
        callback_phrase: str | None = None,
    ) -> str:
        """Substitute placeholders, gracefully removing unavailable ones.

        Never leaves raw {token} in output. When a placeholder value is None,
        the placeholder AND surrounding whitespace are cleaned up to avoid
        double spaces or dangling punctuation.
        """
        context = {
            "opponent": opponent_name,
            "theme": arc_theme,
            "callback": callback_phrase,
        }

        def replacer(match: re.Match) -> str:
            key = match.group(1)
            if key in context and context[key] is not None:
                return context[key]
            # Remove placeholder — return empty string
            return ""

        text = _PLACEHOLDER_RE.sub(replacer, template)

        # Clean up double/multiple spaces
        text = re.sub(r"  +", " ", text)

        # Remove space before punctuation caused by removed placeholders
        text = re.sub(r"\s+([,.\?!;:])", r"\1", text)

        # Remove leading/trailing comma/period artifacts (e.g., ", rest" → "rest")
        text = re.sub(r"^[,.\s]+", "", text)
        text = re.sub(r"[,\s]+$", "", text)

        # Final strip
        text = text.strip()

        # Final safety net: ensure no raw {word} tokens remain
        # (handles any unknown placeholders not in our context dict)
        text = _PLACEHOLDER_RE.sub("", text)
        text = re.sub(r"  +", " ", text).strip()

        return text

    def reset_session(self) -> None:
        """Reset session weights for a new broadcast stream.

        Clears both session-used IDs and recent beat IDs, restoring
        all templates to their base weights.
        """
        self._session_used_ids.clear()
        self._recent_beat_ids.clear()

    @classmethod
    def from_json_file(
        cls,
        path: Optional[Path] = None,
        *,
        min_per_archetype: int = MIN_TEMPLATES_PER_ARCHETYPE,
        min_per_move: int = MIN_TEMPLATES_PER_MOVE,
    ) -> "FallbackPool":
        """Load templates from a JSON file.

        Args:
            path: Path to JSON file. Defaults to templates/fallback_templates.json.
            min_per_archetype: Minimum templates per archetype for validation.
            min_per_move: Minimum templates per archetype×move for validation.

        Returns:
            Initialized and validated FallbackPool.
        """
        file_path = path or _DEFAULT_TEMPLATES_FILE
        with open(file_path, "r") as f:
            data = json.load(f)

        templates: list[FallbackTemplate] = []
        for archetype, moves in data.items():
            for move_type, entries in moves.items():
                for entry in entries:
                    templates.append(
                        FallbackTemplate(
                            template_id=entry["id"],
                            archetype=archetype,
                            move_type=move_type,
                            template=entry["template"],
                            base_weight=entry.get("weight", 1.0),
                        )
                    )

        return cls(templates, min_per_archetype=min_per_archetype, min_per_move=min_per_move)
