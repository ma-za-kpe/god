"""Anti-Repetition Gate for the Broadcast-Quality Banter Engine.

N-gram overlap detection, opener tracking, and emotional register variety
enforcement. Ensures no Elder repeats phrases, sentence openers, or emotional
registers too frequently within a broadcast session.
"""

from __future__ import annotations

from collections import deque

from .types import RepetitionVerdict


class AntiRepetitionGate:
    """Guards against repetitive banter output on a per-Elder basis.

    Tracks:
    - Last 20 delivered lines per Elder (history window)
    - Last 8 openers (first 3 words) per Elder
    - Last 20 emotional registers per Elder

    Rejects candidates that:
    - Share >60% 3-gram overlap with any line in the Elder's history (when >= 5 entries)
    - Reuse an opener seen in the Elder's last 8 deliveries
    """

    def __init__(self, history_window: int = 20, opener_window: int = 8) -> None:
        self._history_window = history_window
        self._opener_window = opener_window
        self._history: dict[str, deque[str]] = {}
        self._openers: dict[str, deque[str]] = {}
        self._registers: dict[str, deque[str]] = {}

    def _ensure_elder(self, elder: str) -> None:
        """Initialize tracking structures for an elder if not present."""
        if elder not in self._history:
            self._history[elder] = deque(maxlen=self._history_window)
        if elder not in self._openers:
            self._openers[elder] = deque(maxlen=self._opener_window)
        if elder not in self._registers:
            self._registers[elder] = deque(maxlen=self._history_window)

    @staticmethod
    def _get_opener(text: str) -> str:
        """Extract the opener (first 3 words, lowercased and stripped)."""
        words = text.strip().lower().split()
        return " ".join(words[:3])

    @staticmethod
    def _generate_trigrams(text: str) -> list[tuple[str, str, str]]:
        """Generate 3-grams (consecutive word triples) from lowercased text."""
        words = text.strip().lower().split()
        if len(words) < 3:
            return []
        return [(words[i], words[i + 1], words[i + 2]) for i in range(len(words) - 2)]

    def compute_trigram_overlap(self, a: str, b: str) -> float:
        """Compute the ratio of shared 3-grams to total 3-grams in the shorter string.

        Returns:
            Float ratio in [0.0, 1.0]. Returns 0.0 if either string has fewer
            than 3 words (no 3-grams can be generated).
        """
        trigrams_a = self._generate_trigrams(a)
        trigrams_b = self._generate_trigrams(b)

        if not trigrams_a or not trigrams_b:
            return 0.0

        # Use the shorter string's trigram count as the denominator
        shorter_count = min(len(trigrams_a), len(trigrams_b))

        # Count shared trigrams
        set_a = set(trigrams_a)
        set_b = set(trigrams_b)
        shared_count = len(set_a & set_b)

        return shared_count / shorter_count

    def check(self, elder: str, candidate: str) -> RepetitionVerdict:
        """Check a candidate line against the elder's history.

        Logic:
        1. Check opener against last 8 openers — reject if match.
        2. If history has >= 5 entries: compute trigram overlap vs each line.
           Reject if any overlap > 0.60.
        3. If history < 5: skip 3-gram check.
        4. Accept if all checks pass.

        Returns:
            RepetitionVerdict indicating acceptance or rejection with reason.
        """
        self._ensure_elder(elder)

        # Extract opener from candidate
        opener = self._get_opener(candidate)

        # Check opener reuse in last 8
        if opener and opener in self._openers[elder]:
            return RepetitionVerdict(
                accepted=False,
                rejection_reason="opener_reuse",
                overlap_ratio=None,
            )

        # 3-gram check: only if history has >= 5 entries
        history = self._history[elder]
        if len(history) >= 5:
            for past_line in history:
                overlap = self.compute_trigram_overlap(candidate, past_line)
                if overlap > 0.60:
                    return RepetitionVerdict(
                        accepted=False,
                        rejection_reason="3gram_overlap",
                        overlap_ratio=overlap,
                    )

        # All checks passed
        return RepetitionVerdict(accepted=True)

    def record_delivery(self, elder: str, line: str, register: str) -> None:
        """Record a delivered line for future anti-repetition checks.

        Updates:
        - History: appends line to elder's history deque
        - Openers: appends first 3 words of line to opener deque
        - Registers: appends the emotional register to register deque
        """
        self._ensure_elder(elder)
        self._history[elder].append(line)
        self._openers[elder].append(self._get_opener(line))
        self._registers[elder].append(register)

    def should_shift_register(self, elder: str) -> bool:
        """Check if the elder should shift emotional register.

        Returns True if the last 3 registers are all identical,
        indicating the elder is stuck in one emotional mode.
        """
        self._ensure_elder(elder)
        registers = self._registers[elder]
        if len(registers) < 3:
            return False
        last_three = list(registers)[-3:]
        return last_three[0] == last_three[1] == last_three[2]


# ---------------------------------------------------------------------------
# T1.4 — World-level cross-Elder repetition buffer (Section 9)
# ---------------------------------------------------------------------------

_WORLD_BUFFER_MAX_SIZE = 20
_WORLD_TRIGRAM_THRESHOLD = 0.60


def _trigrams(text: str) -> frozenset[str]:
    """Extract word trigrams from text."""
    words = text.lower().split()
    if len(words) < 3:
        return frozenset()
    return frozenset(f"{words[i]} {words[i + 1]} {words[i + 2]}" for i in range(len(words) - 2))


class WorldRepetitionBuffer:
    """Cross-Elder repetition guard — shared across all BanterEngine instances.

    Maintains a rolling buffer of the last 20 delivered lines from ANY Elder.
    Rejects lines that share > 60% trigram overlap with any prior line,
    preventing identical or near-identical lines from two different Elders.
    """

    def __init__(
        self,
        max_size: int = _WORLD_BUFFER_MAX_SIZE,
        threshold: float = _WORLD_TRIGRAM_THRESHOLD,
    ) -> None:
        self._buffer: list[str] = []
        self._max_size = max_size
        self._threshold = threshold

    def is_too_similar(self, candidate: str) -> bool:
        """Return True if candidate shares > threshold trigram overlap with any buffered line."""
        candidate_tris = _trigrams(candidate)
        if not candidate_tris:
            return False
        for prior in self._buffer:
            prior_tris = _trigrams(prior)
            if not prior_tris:
                continue
            overlap = len(candidate_tris & prior_tris) / max(len(candidate_tris), 1)
            if overlap > self._threshold:
                return True
        return False

    def record(self, line: str) -> None:
        """Add a delivered line to the buffer, evicting the oldest if at capacity."""
        self._buffer.append(line)
        if len(self._buffer) > self._max_size:
            self._buffer.pop(0)

    def clear(self) -> None:
        """Reset the buffer (call at session start if desired)."""
        self._buffer.clear()


# Module-level singleton — shared across all BanterEngine instances in this process
world_repetition_buffer = WorldRepetitionBuffer()
