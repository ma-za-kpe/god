"""Deterministic sliding-window rate controllers for the Banter Engine.

Replaces scattered `random.random() < X` patterns with deterministic,
auditable rate limiting. The SlidingWindowController uses a deque-based
sliding window per key to track activations within a configurable window
of eligible beats.

Requirement: 12.4 — Randomness may choose among allowed options after the
controller grants permission. Randomness must not decide whether the
contract is respected.
"""

from __future__ import annotations

from collections import deque


class SlidingWindowController:
    """Deque-based sliding window rate controller.

    Each key maps to a deque of beat numbers where the feature was activated.
    ``allow()`` checks if the count within the current window is below
    ``max_count``. ``record()`` appends the current beat number.

    The controller tracks a monotonic beat counter internally. Callers
    advance the beat via ``tick()`` or supply beat numbers externally
    via ``record(key, beat)``.

    Edge cases (per design doc):
    - Window overflow: oldest entry evicted, new entry allowed.
    - Key not found: auto-initialize empty window, allow first request.
    - Beat number wraparound: not expected in 100-beat sessions; for
      long-running processes the monotonic counter prevents issues.
    """

    def __init__(self, max_count: int, window_size: int) -> None:
        """Initialize the controller.

        Args:
            max_count: Maximum allowed activations within the window.
            window_size: Size of the sliding window in eligible beats.
        """
        if max_count < 0:
            raise ValueError(f"max_count must be >= 0, got {max_count}")
        if window_size < 1:
            raise ValueError(f"window_size must be >= 1, got {window_size}")

        self.max_count: int = max_count
        self.window_size: int = window_size
        self._counters: dict[str, deque[int]] = {}
        self._beat: int = 0

    @property
    def beat(self) -> int:
        """Current beat number (monotonic counter)."""
        return self._beat

    def tick(self) -> int:
        """Advance the internal beat counter by one and return the new value."""
        self._beat += 1
        return self._beat

    def allow(self, key: str) -> bool:
        """Check whether an activation is allowed for the given key.

        Evicts stale entries outside the current window, then checks
        if the remaining count is below ``max_count``.

        Args:
            key: Identifier for the rate-limited entity (e.g. pair ID).

        Returns:
            True if activation is permitted, False otherwise.
        """
        window = self._get_or_create(key)
        self._evict_stale(window)
        return len(window) < self.max_count

    def record(self, key: str, beat: int | None = None) -> None:
        """Record an activation for the given key.

        Args:
            key: Identifier for the rate-limited entity.
            beat: Beat number to record. Defaults to the internal counter.
        """
        if beat is None:
            beat = self._beat
        window = self._get_or_create(key)
        window.append(beat)

    def reset(self, key: str) -> None:
        """Clear all recorded activations for a key.

        Args:
            key: Identifier to reset.
        """
        if key in self._counters:
            self._counters[key].clear()

    def count(self, key: str) -> int:
        """Return the number of activations within the current window.

        Args:
            key: Identifier to query.

        Returns:
            Number of activations in the current window.
        """
        window = self._get_or_create(key)
        self._evict_stale(window)
        return len(window)

    def _get_or_create(self, key: str) -> deque[int]:
        """Get or auto-initialize the deque for a key."""
        if key not in self._counters:
            self._counters[key] = deque()
        return self._counters[key]

    def _evict_stale(self, window: deque[int]) -> None:
        """Remove entries outside the current sliding window."""
        cutoff = self._beat - self.window_size
        while window and window[0] <= cutoff:
            window.popleft()
