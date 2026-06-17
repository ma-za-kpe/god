"""Callback Registry — persistent store of memorable moments with dramaturgical surfacing.

Stores high-scoring lines, detects running gags and sore spots, and surfaces
callbacks at dramaturgically optimal moments. Uses the same asyncpg pool as
RelationshipMemory for PostgreSQL persistence with a WriteBuffer fallback
when the database is unavailable.

Requirements: 4.1, 4.2, 4.3, 4.5, 9.1, 9.2, 9.3, 9.4, 9.5, 9.6
"""

from __future__ import annotations

import hashlib
import logging
import time

from .soul_types import (
    CallbackSurface,
    CallbackUsageTracker,
    MemorableMoment,
    SoreSpot,
    SoulEngineConfig,
    WriteBuffer,
)

log = logging.getLogger("god.banter.callback_registry")

# Capacity limits
_MAX_MOMENTS_PER_PAIR = 50
_MAX_GAGS_PER_PAIR = 10
_RUNNING_GAG_THRESHOLD = 3  # interactions needed to flag a running gag
_SORE_SPOT_TENSION_THRESHOLD = 2  # minimum tension delta for sore spot

# Surfacing constraints
_MIN_BEAT_GAP = 15  # minimum beats between same callback uses
_MAX_CALLBACKS_PER_PAIR_PER_SESSION = 2  # max callbacks per pair per session
_TENSION_MATCH_THRESHOLD = 2  # tension within this range scores a point
_TENSION_MISMATCH_REJECT = 3  # tension diff > this means no match


class CallbackRegistry:
    """Persistent store of memorable moments with dramaturgical surfacing.

    Stores high-scoring banter lines as memorable moments, detects recurring
    argument patterns (running gags), and tracks sore spots (topics that
    produce high-tension responses). Persists to PostgreSQL using the same
    pool as RelationshipMemory.

    When the database is unavailable for writes, moments are buffered in
    memory (max 20 entries) and flushed when connectivity is restored.
    """

    def __init__(self, pool, config: SoulEngineConfig):
        """Initialize with an asyncpg pool and soul engine configuration.

        Parameters
        ----------
        pool : asyncpg.Pool or None
            The database connection pool. If None, the registry will
            attempt to get one from db_pool on first use.
        config : SoulEngineConfig
            Soul engine configuration controlling feature flags.
        """
        self._pool = pool
        self._config = config
        self._write_buffer = WriteBuffer()
        self._db_available = True
        self._usage_tracker = CallbackUsageTracker()

    # ------------------------------------------------------------------
    # Pool management
    # ------------------------------------------------------------------

    async def _get_pool(self):
        """Get the asyncpg pool, falling back to db_pool.get_pool()."""
        if self._pool is not None:
            return self._pool
        try:
            from db_pool import get_pool

            self._pool = await get_pool()
            return self._pool
        except Exception as exc:
            log.debug("Failed to acquire database pool: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Pair ID computation
    # ------------------------------------------------------------------

    def compute_pair_id(self, elder_a: str, elder_b: str) -> str:
        """Compute a stable pair_id from two elder names.

        Identical to RelationshipMemory._compute_pair_id: alphabetically
        sorted Elder names joined by ':', SHA-256 hash, first 16 hex chars.
        """
        pair = tuple(sorted([elder_a, elder_b]))
        raw = f"{pair[0]}:{pair[1]}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    # ------------------------------------------------------------------
    # Callback surfacing
    # ------------------------------------------------------------------

    async def surface_callback(
        self,
        speaker: str,
        target: str,
        current_tension: int,
        current_arc_theme: str,
        current_beat_number: int,
        session_callback_count: int,
    ) -> CallbackSurface | None:
        """Surface the best-matching callback for current conditions.

        Returns None if no suitable callback exists or limits exceeded.

        Surfacing rules:
        1. Return None if session_callback_count >= 2 (pair session limit)
        2. Query stored moments for this pair
        3. Score each moment:
           - Tension within 2 of original → +1 match point
           - Theme overlap (arc_theme matches or is contained) → +1 match point
           - Emotional register match (valence-based) → +1 match point
        4. Filter out moments used within last 15 beats
        5. Return highest-scoring match (score > 0) or None
        6. Record usage in CallbackUsageTracker

        Framing selection:
        - "direct_quote" for high tension (>=7)
        - "paraphrase" for medium tension (4-6)
        - "inversion" for opposing valence
        - "escalation" for increasing tension (current > original implied)
        """
        # 1. Session limit check
        if session_callback_count >= _MAX_CALLBACKS_PER_PAIR_PER_SESSION:
            log.debug(
                "Session callback limit reached (%d/%d) for %s→%s",
                session_callback_count,
                _MAX_CALLBACKS_PER_PAIR_PER_SESSION,
                speaker,
                target,
            )
            return None

        pair_id = self.compute_pair_id(speaker, target)

        # Also check pair session count from internal tracker
        tracked_count = self._usage_tracker.pair_session_count.get(pair_id, 0)
        if tracked_count >= _MAX_CALLBACKS_PER_PAIR_PER_SESSION:
            log.debug(
                "Internal pair session limit reached (%d/%d) for pair %s",
                tracked_count,
                _MAX_CALLBACKS_PER_PAIR_PER_SESSION,
                pair_id,
            )
            return None

        # 2. Query stored moments for this pair
        moments = await self._query_moments_for_pair(pair_id)
        if not moments:
            log.debug("No stored moments for pair %s", pair_id)
            return None

        # 3 & 4. Score moments and filter by beat gap
        best_moment = None
        best_score = 0

        for moment in moments:
            # Filter: skip moments used within last 15 beats
            callback_id = self._moment_callback_id(moment)
            last_used = self._usage_tracker.last_used_beat.get(callback_id)
            if last_used is not None:
                beats_since = current_beat_number - last_used
                if beats_since < _MIN_BEAT_GAP:
                    continue

            # Score match quality
            match_score = self._score_moment_match(
                moment, current_tension, current_arc_theme
            )

            if match_score > best_score:
                best_score = match_score
                best_moment = moment

        # 5. Return None if no match scores > 0
        if best_moment is None or best_score <= 0:
            log.debug(
                "No suitable callback found for pair %s (best_score=%d)",
                pair_id,
                best_score,
            )
            return None

        # 6. Record usage and select framing
        callback_id = self._moment_callback_id(best_moment)
        self._usage_tracker.last_used_beat[callback_id] = current_beat_number
        self._usage_tracker.pair_session_count[pair_id] = tracked_count + 1

        framing = self._select_framing(
            current_tension, best_moment
        )

        return CallbackSurface(
            original_line=best_moment.line,
            original_context=(
                f"{best_moment.speaker} to {best_moment.target} "
                f"[{best_moment.move}, theme: {best_moment.arc_theme}]"
            ),
            suggested_framing=framing,
            summary=best_moment.summary,
            beat_number_used=current_beat_number,
        )

    # ------------------------------------------------------------------
    # Surfacing helpers
    # ------------------------------------------------------------------

    def _moment_callback_id(self, moment: MemorableMoment) -> str:
        """Generate a unique ID for a moment to track usage."""
        # Use a combination of speaker, line content hash, and beat for uniqueness
        content_hash = hashlib.sha256(
            f"{moment.speaker}:{moment.target}:{moment.line}".encode()
        ).hexdigest()[:12]
        return content_hash

    def _score_moment_match(
        self,
        moment: MemorableMoment,
        current_tension: int,
        current_arc_theme: str,
    ) -> int:
        """Score how well a moment matches current dramatic conditions.

        Returns 0–3 match points:
        - +1 if tension within 2 of original (inferred from score)
        - +1 if theme overlap
        - +1 if emotional register match
        """
        score = 0

        # Tension matching: infer original tension from the moment's score.
        # High scores (>14) imply high tension (~7-10), medium (12-14) imply
        # medium tension (~4-6), lower imply lower tension.
        # We approximate original_tension from the score range.
        original_tension = self._infer_tension_from_moment(moment)
        tension_diff = abs(current_tension - original_tension)

        if tension_diff <= _TENSION_MATCH_THRESHOLD:
            score += 1
        elif tension_diff > _TENSION_MISMATCH_REJECT:
            # Hard reject: if tension mismatch is too large, score stays 0
            return 0

        # Theme overlap: arc_theme matches or is contained
        if self._themes_overlap(moment.arc_theme, current_arc_theme):
            score += 1

        # Emotional register match: valence alignment with current state
        # Positive valence matches low tension, negative matches high tension
        if self._valence_matches_tension(moment.valence, current_tension):
            score += 1

        return score

    def _infer_tension_from_moment(self, moment: MemorableMoment) -> int:
        """Infer approximate tension from a moment's characteristics.

        Uses the score and valence to estimate what the tension was
        when the moment was created.
        """
        # Higher scores with negative valence imply high tension
        # Higher scores with positive valence imply moderate tension
        if moment.valence == "negative":
            if moment.score >= 15:
                return 8
            elif moment.score >= 13:
                return 6
            else:
                return 5
        elif moment.valence == "positive":
            if moment.score >= 15:
                return 4
            elif moment.score >= 13:
                return 3
            else:
                return 2
        else:
            # neutral
            return 5

    def _themes_overlap(self, theme_a: str, theme_b: str) -> bool:
        """Check if two themes overlap (exact match or containment)."""
        if not theme_a or not theme_b:
            return False
        a_lower = theme_a.lower()
        b_lower = theme_b.lower()
        return a_lower == b_lower or a_lower in b_lower or b_lower in a_lower

    def _valence_matches_tension(self, valence: str, tension: int) -> bool:
        """Check if emotional register (valence) matches current tension state.

        - Negative valence matches high tension (>=6)
        - Positive valence matches low tension (<=4)
        - Neutral matches medium tension (3-7)
        """
        if valence == "negative":
            return tension >= 6
        elif valence == "positive":
            return tension <= 4
        else:
            # neutral matches medium range
            return 3 <= tension <= 7

    def _select_framing(
        self, current_tension: int, moment: MemorableMoment
    ) -> str:
        """Select the suggested framing based on current dramatic conditions.

        - "direct_quote" for high tension (>=7)
        - "paraphrase" for medium tension (4-6)
        - "inversion" for opposing valence (positive moment at high tension
          or negative moment at low tension)
        - "escalation" for increasing tension (current tension > inferred original)
        """
        original_tension = self._infer_tension_from_moment(moment)

        # Check for inversion: opposing valence vs current tension
        if (moment.valence == "positive" and current_tension >= 7) or (
            moment.valence == "negative" and current_tension <= 3
        ):
            return "inversion"

        # Check for escalation: current tension exceeds original
        if current_tension > original_tension + 1:
            return "escalation"

        # High tension → direct quote
        if current_tension >= 7:
            return "direct_quote"

        # Medium tension → paraphrase
        return "paraphrase"

    async def _query_moments_for_pair(
        self, pair_id: str
    ) -> list[MemorableMoment]:
        """Query the database for all stored moments for a pair.

        Returns an empty list if the database is unavailable.
        """
        pool = await self._get_pool()
        if pool is None:
            return []

        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT speaker, target, line, move, arc_theme,
                           valence, summary, score, beat_number, created_at
                    FROM callback_moments
                    WHERE pair_id = $1
                    ORDER BY score DESC, created_at DESC
                    """,
                    pair_id,
                )

                return [
                    MemorableMoment(
                        speaker=row["speaker"],
                        target=row["target"],
                        line=row["line"],
                        move=row["move"],
                        arc_theme=row["arc_theme"],
                        valence=row["valence"],
                        summary=row["summary"],
                        score=row["score"],
                        beat_number=row["beat_number"],
                        created_at=float(row["created_at"]),
                    )
                    for row in rows
                ]
        except Exception as exc:
            log.debug("Failed to query moments for pair %s: %s", pair_id, exc)
            return []

    # ------------------------------------------------------------------
    # Store memorable moment
    # ------------------------------------------------------------------

    async def store_memorable_moment(
        self,
        speaker: str,
        target: str,
        line: str,
        move: str,
        arc_theme: str,
        valence: str,
        summary: str,
        score: int,
    ) -> None:
        """Store a high-scoring line as a memorable moment.

        Only stores lines with score > 12. Enforces a 50-entry cap per
        Elder pair, evicting the oldest entries when the limit is reached.

        If the database is unavailable, the moment is buffered in memory
        (max 20 entries; oldest dropped on overflow).

        After storing, checks for running gag patterns and sore spots.
        """
        if score <= 12:
            log.debug(
                "Score %d not above threshold 12; skipping storage", score
            )
            return

        pair_id = self.compute_pair_id(speaker, target)
        now_ts = int(time.time())

        moment = MemorableMoment(
            speaker=speaker,
            target=target,
            line=line,
            move=move,
            arc_theme=arc_theme,
            valence=valence,
            summary=summary,
            score=score,
            beat_number=0,  # beat_number tracked externally if needed
            created_at=float(now_ts),
        )

        pool = await self._get_pool()
        if pool is None:
            self._db_available = False
            self._write_buffer.add(moment)
            log.debug(
                "DB unavailable; buffered moment (%d/%d)",
                len(self._write_buffer.entries),
                20,
            )
            return

        try:
            async with pool.acquire() as conn:
                # Insert the new moment
                await conn.execute(
                    """
                    INSERT INTO callback_moments
                        (pair_id, speaker, target, line, move, arc_theme,
                         valence, summary, score, beat_number, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    """,
                    pair_id,
                    speaker,
                    target,
                    line,
                    move,
                    arc_theme,
                    valence,
                    summary,
                    score,
                    0,
                    now_ts,
                )

                # Enforce 50-entry cap: evict oldest if over limit
                await self._enforce_moments_cap(conn, pair_id)

                # Check for running gag pattern
                await self._check_running_gag(conn, pair_id, arc_theme, speaker, target)

                # Check for sore spot
                await self._check_sore_spot(conn, target, arc_theme, valence)

            self._db_available = True

            # Flush write buffer if we just reconnected
            if len(self._write_buffer.entries) > 0:
                await self._flush_write_buffer()

        except Exception as exc:
            log.debug("DB write failed, buffering moment: %s", exc)
            self._db_available = False
            self._write_buffer.add(moment)

    # ------------------------------------------------------------------
    # Capacity enforcement
    # ------------------------------------------------------------------

    async def _enforce_moments_cap(self, conn, pair_id: str) -> None:
        """Ensure no more than 50 memorable moments exist for a pair.

        Evicts the oldest entries (by created_at) when the count exceeds
        the cap.
        """
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM callback_moments WHERE pair_id = $1",
            pair_id,
        )

        if count > _MAX_MOMENTS_PER_PAIR:
            excess = count - _MAX_MOMENTS_PER_PAIR
            await conn.execute(
                """
                DELETE FROM callback_moments
                WHERE id IN (
                    SELECT id FROM callback_moments
                    WHERE pair_id = $1
                    ORDER BY created_at ASC
                    LIMIT $2
                )
                """,
                pair_id,
                excess,
            )
            log.debug(
                "Evicted %d oldest moments for pair %s", excess, pair_id
            )

    async def _enforce_gags_cap(self, conn, pair_id: str) -> None:
        """Ensure no more than 10 running gags exist for a pair.

        Evicts the oldest entries (by created_at) when the count exceeds
        the cap.
        """
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM callback_running_gags WHERE pair_id = $1",
            pair_id,
        )

        if count > _MAX_GAGS_PER_PAIR:
            excess = count - _MAX_GAGS_PER_PAIR
            await conn.execute(
                """
                DELETE FROM callback_running_gags
                WHERE id IN (
                    SELECT id FROM callback_running_gags
                    WHERE pair_id = $1
                    ORDER BY created_at ASC
                    LIMIT $2
                )
                """,
                pair_id,
                excess,
            )
            log.debug(
                "Evicted %d oldest running gags for pair %s", excess, pair_id
            )

    # ------------------------------------------------------------------
    # Running gag detection
    # ------------------------------------------------------------------

    async def _check_running_gag(
        self, conn, pair_id: str, topic: str, speaker: str, target: str
    ) -> None:
        """Detect running gag patterns: 3+ high-scoring interactions on same topic.

        A running gag is flagged when there are 3 or more memorable moments
        (score > 10) for the same pair on the same topic/arc_theme.
        """
        # Count high-scoring interactions on this topic for the pair
        high_count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM callback_moments
            WHERE pair_id = $1 AND arc_theme = $2 AND score > 10
            """,
            pair_id,
            topic,
        )

        if high_count >= _RUNNING_GAG_THRESHOLD:
            # Check if a gag already exists for this pair+topic
            existing = await conn.fetchval(
                """
                SELECT id FROM callback_running_gags
                WHERE pair_id = $1 AND topic = $2
                """,
                pair_id,
                topic,
            )

            if existing is None:
                # Create new running gag
                await conn.execute(
                    """
                    INSERT INTO callback_running_gags
                        (pair_id, pattern_description, topic, interaction_count, created_at)
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    pair_id,
                    f"Recurring {topic} theme between {speaker} and {target}",
                    topic,
                    high_count,
                    int(time.time()),
                )
                log.debug(
                    "New running gag detected: pair=%s topic=%s count=%d",
                    pair_id,
                    topic,
                    high_count,
                )

                # Enforce 10-gag cap
                await self._enforce_gags_cap(conn, pair_id)
            else:
                # Update interaction count
                await conn.execute(
                    """
                    UPDATE callback_running_gags
                    SET interaction_count = $1
                    WHERE id = $2
                    """,
                    high_count,
                    existing,
                )

    # ------------------------------------------------------------------
    # Sore spot tracking
    # ------------------------------------------------------------------

    async def _check_sore_spot(
        self, conn, target: str, topic: str, valence: str
    ) -> None:
        """Track sore spots: topics with tension increase >= 2.

        A sore spot is recorded when a negative-valence interaction on
        a topic indicates a tension delta of at least 2. This is a
        simplified heuristic — negative valence on a high-scoring line
        implies significant tension increase.
        """
        if valence != "negative":
            return

        # Negative valence on a high-scoring line indicates tension spike.
        # The tension_delta is approximated as 2 (minimum threshold) for
        # high-scoring negative interactions.
        tension_delta = _SORE_SPOT_TENSION_THRESHOLD

        # Check if this sore spot already exists
        existing = await conn.fetchval(
            """
            SELECT id FROM callback_sore_spots
            WHERE elder_name = $1 AND topic = $2
            """,
            target,
            topic,
        )

        if existing is None:
            await conn.execute(
                """
                INSERT INTO callback_sore_spots
                    (elder_name, topic, trigger_phrase, tension_delta, created_at)
                VALUES ($1, $2, $3, $4, $5)
                """,
                target,
                topic,
                None,
                tension_delta,
                int(time.time()),
            )
            log.debug(
                "New sore spot tracked: elder=%s topic=%s delta=%d",
                target,
                topic,
                tension_delta,
            )
        else:
            # Update tension delta if higher
            await conn.execute(
                """
                UPDATE callback_sore_spots
                SET tension_delta = GREATEST(tension_delta, $1)
                WHERE id = $2
                """,
                tension_delta,
                existing,
            )

    # ------------------------------------------------------------------
    # Sore spot retrieval
    # ------------------------------------------------------------------

    async def get_sore_spots(self, target: str, arc_theme: str) -> list[SoreSpot]:
        """Get sore spots for a target Elder matching the current theme.

        Returns a list of SoreSpot objects for the given Elder whose topic
        matches (or is contained in) the current arc theme.

        Returns an empty list if the database is unavailable.
        """
        pool = await self._get_pool()
        if pool is None:
            return []

        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT elder_name, topic, trigger_phrase, tension_delta
                    FROM callback_sore_spots
                    WHERE elder_name = $1
                      AND (topic = $2 OR $2 LIKE '%%' || topic || '%%')
                    ORDER BY tension_delta DESC
                    """,
                    target,
                    arc_theme,
                )

                return [
                    SoreSpot(
                        elder_name=row["elder_name"],
                        topic=row["topic"],
                        trigger_phrase=row["trigger_phrase"],
                        tension_delta=row["tension_delta"],
                    )
                    for row in rows
                ]
        except Exception as exc:
            log.debug("Failed to retrieve sore spots: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Write buffer management
    # ------------------------------------------------------------------

    async def _flush_write_buffer(self) -> None:
        """Flush buffered writes to the database when connectivity is restored."""
        pool = await self._get_pool()
        if pool is None:
            return

        flushed = 0
        while self._write_buffer.entries:
            moment = self._write_buffer.entries.popleft()
            pair_id = self.compute_pair_id(moment.speaker, moment.target)

            try:
                async with pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO callback_moments
                            (pair_id, speaker, target, line, move, arc_theme,
                             valence, summary, score, beat_number, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                        """,
                        pair_id,
                        moment.speaker,
                        moment.target,
                        moment.line,
                        moment.move,
                        moment.arc_theme,
                        moment.valence,
                        moment.summary,
                        moment.score,
                        moment.beat_number,
                        int(moment.created_at),
                    )
                    await self._enforce_moments_cap(conn, pair_id)
                    flushed += 1
            except Exception as exc:
                # Re-buffer the moment and stop flushing
                self._write_buffer.entries.appendleft(moment)
                log.debug(
                    "Flush interrupted after %d writes: %s", flushed, exc
                )
                return

        if flushed > 0:
            log.debug("Flushed %d buffered moments to DB", flushed)
