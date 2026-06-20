"""Relationship Memory — persistent pairwise interaction history with tension tracking.

Uses the existing asyncpg pool from db_pool.py to store and retrieve
interaction records and pair state for the Banter Engine. Implements
lazy 24h decay on tension reads and reconciliation arc detection.

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6
"""

from __future__ import annotations

import hashlib
import logging
import time

from .types import InteractionRecord, PairState, RelationshipMemoryError

log = logging.getLogger("god.banter.relationship_memory")

# Moves that increase/decrease tension
_ESCALATE_MOVES = frozenset({"ESCALATE", "TAUNT"})
_DEESCALATE_MOVES = frozenset({"CONCEDE", "DEFLECT", "PIVOT"})

# 24 hours in seconds
_DECAY_INTERVAL_S = 86400.0

# Reconciliation thresholds
_RECONCILIATION_HIGH = 7
_RECONCILIATION_LOW = 3
_RECONCILIATION_INTERACTIONS = 5


def _compute_pair_id(elder_a: str, elder_b: str) -> str:
    """Compute a stable pair_id from two elder names (alphabetically sorted hash)."""
    pair = tuple(sorted([elder_a, elder_b]))
    raw = f"{pair[0]}:{pair[1]}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _normalize_pair(elder_a: str, elder_b: str) -> tuple[str, str]:
    """Return the pair in sorted (alphabetical) order."""
    return tuple(sorted([elder_a, elder_b]))  # type: ignore[return-value]


class RelationshipMemory:
    """Persistent pairwise interaction history with tension tracking.

    Uses the existing db_pool.py asyncpg pool for PostgreSQL persistence.
    Degrades gracefully when the database is unavailable — get_tension
    returns 0 and record_interaction raises RelationshipMemoryError.
    """

    def __init__(self, pool=None):
        """Initialize with an optional asyncpg pool.

        If pool is None, the class will attempt to get one from db_pool
        on first use.
        """
        self._pool = pool

    async def _get_pool(self):
        """Get the asyncpg pool, falling back to db_pool.get_pool()."""
        if self._pool is not None:
            return self._pool
        try:
            try:
                from ..db_pool import get_pool
            except ImportError:
                from db_pool import get_pool  # flat test path

            self._pool = await get_pool()
            return self._pool
        except Exception as exc:
            raise RelationshipMemoryError(f"Failed to acquire database pool: {exc}") from exc

    async def record_interaction(self, record: InteractionRecord) -> None:
        """Persist an interaction and update the pair's tension state.

        Creates the pair record if it doesn't exist, applies tension update,
        and checks for reconciliation arc triggers.

        Raises RelationshipMemoryError on DB unavailability.
        """
        try:
            pool = await self._get_pool()
        except RelationshipMemoryError:
            raise
        except Exception as exc:
            raise RelationshipMemoryError(f"Failed to acquire database pool: {exc}") from exc

        pair_id = _compute_pair_id(record.elder_a, record.elder_b)
        sorted_a, sorted_b = _normalize_pair(record.elder_a, record.elder_b)
        now_ts = int(record.timestamp)

        try:
            async with pool.acquire() as conn:
                # Upsert pair state
                existing = await conn.fetchrow(
                    "SELECT tension_level, last_interaction_ts, reconciliation_arc, "
                    "reconciliation_remaining, peak_tension_summary "
                    "FROM relationship_pairs WHERE pair_id = $1",
                    pair_id,
                )

                if existing is None:
                    # Create new pair
                    pair_state = PairState(
                        tension_level=0,
                        last_interaction_ts=0.0,
                    )
                else:
                    pair_state = PairState(
                        tension_level=existing["tension_level"],
                        last_interaction_ts=float(existing["last_interaction_ts"]),
                        reconciliation_arc=existing["reconciliation_arc"],
                        reconciliation_remaining=existing["reconciliation_remaining"],
                        peak_tension_summary=existing["peak_tension_summary"] or "",
                    )

                # Track whether tension was previously above the high threshold
                was_above_high = pair_state.tension_level > _RECONCILIATION_HIGH

                # Apply tension update (pure computation)
                new_tension = self.update_tension(pair_state, record.move_used)
                pair_state.tension_level = new_tension
                pair_state.last_interaction_ts = record.timestamp

                # Check reconciliation arc trigger:
                # tension drops below 3 after having exceeded 7
                if was_above_high and new_tension < _RECONCILIATION_LOW:
                    pair_state.reconciliation_arc = True
                    pair_state.reconciliation_remaining = _RECONCILIATION_INTERACTIONS
                    # Store a summary of the peak tension context
                    pair_state.peak_tension_summary = (
                        f"Tension peaked above {_RECONCILIATION_HIGH} "
                        f"with move {record.move_used} at ts={now_ts}"
                    )

                # Decrement reconciliation counter if arc is active
                if (
                    pair_state.reconciliation_arc
                    and pair_state.reconciliation_remaining > 0
                    and not was_above_high  # don't decrement on the trigger interaction
                ):
                    pair_state.reconciliation_remaining -= 1
                    if pair_state.reconciliation_remaining <= 0:
                        pair_state.reconciliation_arc = False
                        pair_state.reconciliation_remaining = 0

                # Upsert pair state in DB
                await conn.execute(
                    """
                    INSERT INTO relationship_pairs
                        (pair_id, elder_a, elder_b, tension_level,
                         last_interaction_ts, reconciliation_arc,
                         reconciliation_remaining, peak_tension_summary,
                         created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $9)
                    ON CONFLICT (pair_id) DO UPDATE SET
                        tension_level = $4,
                        last_interaction_ts = $5,
                        reconciliation_arc = $6,
                        reconciliation_remaining = $7,
                        peak_tension_summary = $8,
                        updated_at = $9
                    """,
                    pair_id,
                    sorted_a,
                    sorted_b,
                    pair_state.tension_level,
                    now_ts,
                    pair_state.reconciliation_arc,
                    pair_state.reconciliation_remaining,
                    pair_state.peak_tension_summary,
                    now_ts,
                )

                # Insert interaction record
                await conn.execute(
                    """
                    INSERT INTO interaction_records
                        (pair_id, timestamp, elder_acting, move_used,
                         emotional_valence, betrayal, alliance, concession)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    pair_id,
                    now_ts,
                    record.elder_a,  # elder_a is the acting elder
                    record.move_used,
                    record.emotional_valence,
                    record.betrayal,
                    record.alliance,
                    record.concession,
                )

        except RelationshipMemoryError:
            raise
        except Exception as exc:
            raise RelationshipMemoryError(f"Failed to record interaction: {exc}") from exc

    async def get_significant_history(
        self, elder_a: str, elder_b: str, limit: int = 5
    ) -> list[InteractionRecord]:
        """Retrieve the last N significant interactions for a pair.

        Significant = non-neutral emotional valence OR betrayal/alliance/concession.

        Returns an empty list on DB unavailability (graceful degradation).
        """
        pair_id = _compute_pair_id(elder_a, elder_b)

        try:
            pool = await self._get_pool()
        except RelationshipMemoryError:
            log.warning(
                "DB unavailable for get_significant_history(%s, %s)",
                elder_a,
                elder_b,
            )
            return []
        except Exception:
            return []

        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT timestamp, elder_acting, move_used,
                           emotional_valence, betrayal, alliance, concession
                    FROM interaction_records
                    WHERE pair_id = $1
                      AND (emotional_valence != 'neutral'
                           OR betrayal = TRUE
                           OR alliance = TRUE
                           OR concession = TRUE)
                    ORDER BY timestamp DESC
                    LIMIT $2
                    """,
                    pair_id,
                    limit,
                )

            sorted_a, sorted_b = _normalize_pair(elder_a, elder_b)
            records = []
            for row in rows:
                records.append(
                    InteractionRecord(
                        timestamp=float(row["timestamp"]),
                        elder_a=sorted_a,
                        elder_b=sorted_b,
                        move_used=row["move_used"],
                        emotional_valence=row["emotional_valence"],
                        betrayal=row["betrayal"],
                        alliance=row["alliance"],
                        concession=row["concession"],
                    )
                )
            return records

        except Exception as exc:
            log.warning(
                "Failed to fetch significant history for %s/%s: %s",
                elder_a,
                elder_b,
                exc,
            )
            return []

    async def get_tension(self, elder_a: str, elder_b: str) -> int:
        """Get current tension level for a pair, with lazy 24h decay applied.

        Decay: for each full 24h period elapsed since last_interaction_ts,
        subtract 1 from stored tension, clamping to 0.

        Returns 0 on DB unavailability (graceful degradation).
        """
        pair_id = _compute_pair_id(elder_a, elder_b)

        try:
            pool = await self._get_pool()
        except (RelationshipMemoryError, Exception):
            return 0

        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT tension_level, last_interaction_ts "
                    "FROM relationship_pairs WHERE pair_id = $1",
                    pair_id,
                )

            if row is None:
                return 0

            stored_tension = row["tension_level"]
            last_ts = float(row["last_interaction_ts"])

            # Apply lazy 24h decay
            now = time.time()
            if last_ts > 0:
                elapsed_s = now - last_ts
                decay_periods = int(elapsed_s // _DECAY_INTERVAL_S)
                decayed_tension = max(0, stored_tension - decay_periods)
            else:
                decayed_tension = stored_tension

            return decayed_tension

        except Exception as exc:
            log.warning("Failed to get tension for %s/%s: %s", elder_a, elder_b, exc)
            return 0

    def update_tension(self, pair: PairState, move: str) -> int:
        """Apply a move to the pair's tension level (pure computation, no DB).

        Rules:
        - ESCALATE, TAUNT → +1
        - CONCEDE, DEFLECT, PIVOT → -1
        - All others → unchanged
        - Always clamp to [0, 10]

        Returns the new tension level.
        """
        current = pair.tension_level

        if move in _ESCALATE_MOVES:
            current += 1
        elif move in _DEESCALATE_MOVES:
            current -= 1

        # Clamp to [0, 10]
        return max(0, min(10, current))

    async def get_pair_state(self, elder_a: str, elder_b: str) -> PairState | None:
        """Get the full pair state including reconciliation info.

        Returns None if the pair doesn't exist or DB is unavailable.
        """
        pair_id = _compute_pair_id(elder_a, elder_b)

        try:
            pool = await self._get_pool()
        except (RelationshipMemoryError, Exception):
            return None

        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT tension_level, last_interaction_ts, "
                    "reconciliation_arc, reconciliation_remaining, "
                    "peak_tension_summary "
                    "FROM relationship_pairs WHERE pair_id = $1",
                    pair_id,
                )

            if row is None:
                return None

            return PairState(
                tension_level=row["tension_level"],
                last_interaction_ts=float(row["last_interaction_ts"]),
                reconciliation_arc=row["reconciliation_arc"],
                reconciliation_remaining=row["reconciliation_remaining"],
                peak_tension_summary=row["peak_tension_summary"] or "",
            )

        except Exception as exc:
            log.warning(
                "Failed to get pair state for %s/%s: %s",
                elder_a,
                elder_b,
                exc,
            )
            return None
