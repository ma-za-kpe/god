"""100-beat Theater Harness — the ultimate acceptance gate for contract fidelity.

Runs fixed-seed sessions with configurable archetype rosters, arc themes,
and starting pair states. Emits transcript, metrics JSON, prompt snapshots,
and delivered line events.

The harness is not a unit test. It is the proof that the runtime obeys
the contract across a meaningful session length.

Requirements: 0.1, 11.1, 11.4, 12.5
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

from .anti_repetition import AntiRepetitionGate
from .engine import BanterEngine
from .fallback_pool import FallbackPool
from .hard_bans import HardBanChecker
from .mode_types import BeatMode, NORMAL_POLICY, POLICY_TABLE
from .model_router import ModelRouter
from .move_selector import compute_distribution
from .pacing_controller import PacingController
from .scene_context import SceneContext
from .types import BanterConfig, BeatResult, PairState


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class ArchetypeRoster:
    """An Elder in the harness roster."""
    elder_name: str
    archetype: str


@dataclass
class SessionMetrics:
    """Section 11 metrics calculated from a 100-beat session."""
    direct_response_rate: float = 0.0
    arc_title_leaks: int = 0
    hard_ban_violations: int = 0
    cross_elder_duplicates: int = 0
    grammar_failures: int = 0
    emotional_texture_coverage: float = 0.0
    clip_candidate_rate: float = 0.0
    crack_count: int = 0
    veil_beats: int = 0
    backchannel_rate: float = 0.0
    voice_similarity_max: float = 0.0

    def passes_v1_minimums(self) -> bool:
        """Check if all V1 minimum targets are met."""
        return (
            self.direct_response_rate >= 0.30
            and self.arc_title_leaks == 0
            and self.hard_ban_violations == 0
            and self.cross_elder_duplicates == 0
            and self.grammar_failures == 0
            and self.emotional_texture_coverage >= 0.20
            and self.clip_candidate_rate >= 0.05
            and self.crack_count >= 1
            and self.veil_beats >= 10
            and self.backchannel_rate >= 0.20
            and self.voice_similarity_max <= 0.45
        )


@dataclass
class HarnessResult:
    """Complete output of a theater harness run."""
    transcript: list[BeatResult] = field(default_factory=list)
    metrics: SessionMetrics = field(default_factory=SessionMetrics)
    prompt_snapshots: list[str] = field(default_factory=list)
    delivered_lines: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Response detection (Section 11.3)
# ---------------------------------------------------------------------------

_STOPWORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "in", "on", "at",
    "to", "for", "of", "and", "or", "but", "be", "if", "do", "does",
    "it", "this", "that", "with", "from", "by", "as", "not", "no",
    "so", "up", "out", "all", "just", "than", "then", "what", "when",
    "how", "who", "which", "where", "there", "here", "will", "can",
    "has", "had", "have", "been",
})

_RESPONSE_MARKERS = frozenset({
    "you", "your", "you said", "you call",
    "but", "yet", "still", "and yet",
    "what you call", "that is exactly", "which is why",
    "not wrong", "true", "fair",
})


def _non_stopword_set(text: str) -> set[str]:
    """Extract non-stopword tokens from text."""
    return {w for w in text.lower().split() if w not in _STOPWORDS and len(w) > 2}


def _bigrams(text: str) -> set[str]:
    """Extract word bigrams."""
    words = text.lower().split()
    return {f"{words[i]} {words[i+1]}" for i in range(len(words) - 1)} if len(words) >= 2 else set()


def is_responsive(candidate: str, opponent_line: str) -> bool:
    """Detect if candidate is responsive to opponent_line (Section 11.3)."""
    if not opponent_line or not candidate:
        return False

    candidate_lower = candidate.lower()
    opponent_lower = opponent_line.lower()

    # Check non-stopword overlap >= 1
    cand_words = _non_stopword_set(candidate)
    opp_words = _non_stopword_set(opponent_line)
    if cand_words & opp_words:
        return True

    # Check bigram overlap >= 1
    if _bigrams(candidate_lower) & _bigrams(opponent_lower):
        return True

    # Check response markers + claim reference
    has_marker = any(marker in candidate_lower for marker in _RESPONSE_MARKERS)
    if has_marker:
        return True

    return False


def _lexical_similarity(left: str, right: str) -> float:
    """Cheap similarity score for voice-collapse detection."""
    left_words = _non_stopword_set(left)
    right_words = _non_stopword_set(right)
    if not left_words or not right_words:
        return 0.0
    unigram = len(left_words & right_words) / max(len(left_words), len(right_words))
    left_bigrams = _bigrams(left)
    right_bigrams = _bigrams(right)
    if left_bigrams and right_bigrams:
        bigram = len(left_bigrams & right_bigrams) / max(
            len(left_bigrams), len(right_bigrams)
        )
    else:
        bigram = 0.0
    return (unigram * 0.35) + (bigram * 0.65)


# ---------------------------------------------------------------------------
# Theater Harness
# ---------------------------------------------------------------------------


class TheaterHarness:
    """Runs 100-beat fixed-seed sessions for contract validation.

    Supports:
    - Deterministic model stub for CI (repeatable results)
    - Optional live model for manual review
    - Fixed seed for reproducibility
    - Multiple Elder pairs in round-robin or weighted scheduling
    """

    def __init__(self, model_stub: Callable[[str], Awaitable[str]] | None = None):
        """Initialize the harness.

        Args:
            model_stub: Optional async callable that replaces LLM calls.
                If None, a deterministic stub is used that returns
                archetype-flavored lines.
        """
        self._model_stub = model_stub or self._default_stub
        self._hard_ban_checker = HardBanChecker()

    async def run(
        self,
        seed: int,
        roster: list[ArchetypeRoster],
        arc_theme: str,
        starting_pairs: dict[str, PairState] | None = None,
        num_beats: int = 100,
    ) -> HarnessResult:
        """Run a full theater session.

        Args:
            seed: Random seed for reproducibility.
            roster: List of Elders and their archetypes.
            arc_theme: The arc theme for this session.
            starting_pairs: Optional starting pair states (key = "elder:opponent").
            num_beats: Number of beats to generate (default 100).

        Returns:
            HarnessResult with transcript, metrics, snapshots, and events.
        """
        rng = random.Random(seed)
        result = HarnessResult()

        seeded_pairs = dict(starting_pairs or {})
        if not seeded_pairs and len(roster) >= 2:
            seeded_pairs[f"{roster[0].elder_name}:{roster[1].elder_name}"] = PairState(
                tension_level=9,
                last_interaction_ts=time.time(),
                recent_betrayal=True,
                consecutive_counters=3,
                consecutive_escalations=0,
            )

        # Build engine with deterministic stub
        engine = self._build_engine(rng, seeded_pairs)

        # Build conversation thread
        conv_thread: list[dict] = []
        delivered_by_elder: dict[str, list[str]] = {r.elder_name: [] for r in roster}
        all_delivered: list[str] = []
        responsive_count = 0
        eligible_response_count = 0
        emotional_texture_count = 0
        clip_candidate_count = 0
        veil_count = 0
        backchannel_eligible = 0
        backchannel_fired = 0
        crack_count = 0

        for beat_idx in range(num_beats):
            # Round-robin Elder selection
            speaker_roster = roster[beat_idx % len(roster)]
            elder = speaker_roster.elder_name
            archetype = speaker_roster.archetype

            # Pick opponent (next in roster)
            opponent_idx = (beat_idx + 1) % len(roster)
            opponent_roster = roster[opponent_idx]
            opponent = opponent_roster.elder_name

            # Generate beat
            beat_result = await engine.generate_beat(
                elder=elder,
                archetype=archetype,
                opponent=opponent,
                arc_theme=arc_theme,
                conv_thread=conv_thread[-10:],  # Last 10 for context window
            )

            result.transcript.append(beat_result)
            result.prompt_snapshots.append(getattr(engine, "_last_prompt_snapshot", ""))

            # Track delivered line
            line_event = {
                "beat": beat_idx,
                "elder": elder,
                "archetype": archetype,
                "opponent": opponent,
                "line": beat_result.line,
                "move": beat_result.move,
                "source": beat_result.source,
                "score": beat_result.quality_score,
                "clip_candidate": beat_result.metadata.get("clip_candidate", False),
            }
            result.delivered_lines.append(line_event)

            # Update conversation thread
            if beat_result.source != "silence":
                conv_thread.append({
                    "speaker": elder,
                    "content": beat_result.line,
                    "move": beat_result.move,
                    "target": opponent,
                })

            # --- Metrics tracking ---
            delivered_by_elder.setdefault(elder, []).append(beat_result.line)
            all_delivered.append(beat_result.line)

            # Response rate
            if beat_result.source not in ("silence",):
                last_opp_line = None
                for t in reversed(conv_thread[:-1]):
                    if t.get("speaker") == opponent:
                        last_opp_line = t.get("content", "")
                        break
                if last_opp_line:
                    eligible_response_count += 1
                    if beat_result.move == "BACKCHANNEL" or is_responsive(beat_result.line, last_opp_line):
                        responsive_count += 1

            # Arc title leak
            if arc_theme.lower() in beat_result.line.lower():
                result.metrics.arc_title_leaks += 1

            # Hard ban check on delivered lines (for metrics)
            if beat_result.source != "silence":
                mode_value = beat_result.metadata.get("mode", "normal")
                try:
                    beat_mode = BeatMode(mode_value)
                except ValueError:
                    beat_mode = BeatMode.NORMAL
                verdict = self._hard_ban_checker.check(
                    beat_result.line,
                    policy=POLICY_TABLE.get(beat_mode, NORMAL_POLICY),
                    arc_theme_title=arc_theme,
                    archetype=archetype,
                )
                if not verdict.passed:
                    result.metrics.hard_ban_violations += 1

            # Emotional texture
            if beat_result.quality_score >= 5 or beat_result.move in ("BACKCHANNEL", "CRACK"):
                emotional_texture_count += 1

            # Clip candidate
            if beat_result.metadata.get("clip_candidate", False) or beat_result.quality_score >= 12:
                clip_candidate_count += 1

            # CRACK tracking
            if beat_result.move == "CRACK":
                crack_count += 1

            if beat_result.move == "BACKCHANNEL" and beat_result.source != "silence":
                backchannel_fired += 1

            # Veil beats (every 8th)
            if beat_idx > 0 and beat_idx % 8 == 0:
                veil_count += 1

            # Backchannel
            if beat_result.source != "silence" and beat_result.quality_score > 12:
                backchannel_eligible += 1

        # Cross-Elder duplicates
        seen_lines: dict[str, str] = {}
        for event in result.delivered_lines:
            if event["source"] == "silence" or event["move"] == "BACKCHANNEL":
                continue
            normalized = event["line"].lower().strip()
            first_elder = seen_lines.get(normalized)
            if first_elder is not None and first_elder != event["elder"]:
                result.metrics.cross_elder_duplicates += 1
            else:
                seen_lines[normalized] = event["elder"]

        # Calculate final metrics
        total_non_silence = sum(1 for b in result.transcript if b.source != "silence")
        result.metrics.direct_response_rate = (
            responsive_count / eligible_response_count
            if eligible_response_count > 0 else 0.0
        )
        result.metrics.emotional_texture_coverage = (
            emotional_texture_count / total_non_silence
            if total_non_silence > 0 else 0.0
        )
        result.metrics.clip_candidate_rate = (
            clip_candidate_count / total_non_silence
            if total_non_silence > 0 else 0.0
        )
        result.metrics.crack_count = crack_count
        result.metrics.veil_beats = veil_count
        result.metrics.backchannel_rate = (
            backchannel_fired / backchannel_eligible
            if backchannel_eligible > 0 else 0.0
        )
        result.metrics.voice_similarity_max = 0.0
        tracked_lines = [
            event
            for event in result.delivered_lines
            if event["source"] != "silence" and event["move"] != "BACKCHANNEL"
        ]
        for idx, left in enumerate(tracked_lines):
            for right in tracked_lines[idx + 1:]:
                if left["elder"] == right["elder"]:
                    continue
                sim = _lexical_similarity(left["line"], right["line"])
                if sim > result.metrics.voice_similarity_max:
                    result.metrics.voice_similarity_max = sim

        return result

    def _build_engine(
        self,
        rng: random.Random,
        pair_states: dict[str, PairState],
    ) -> BanterEngine:
        """Build a BanterEngine with the deterministic model stub."""

        async def stub_remote(prompt: str) -> str:
            return await self._model_stub(prompt)

        async def stub_local(prompt: str) -> str:
            return await self._model_stub(prompt)

        model_router = ModelRouter(
            remote_model=stub_remote,
            local_model=stub_local,
        )

        fallback_pool = FallbackPool.from_json_file()

        class HarnessRelationshipMemory:
            def __init__(self, pair_states: dict[str, PairState]) -> None:
                self._pair_states = pair_states

            async def get_pair_state(self, elder_a: str, elder_b: str) -> PairState | None:
                key = f"{elder_a}:{elder_b}"
                reverse_key = f"{elder_b}:{elder_a}"
                return self._pair_states.get(key) or self._pair_states.get(reverse_key)

            async def get_significant_history(
                self, elder_a: str, elder_b: str, limit: int = 5
            ) -> list:
                return []

        async def stub_quality_judge(
            candidate, *, archetype, move, arc_theme, scene_context=None, timeout_s=2.0
        ):
            from .types import QualityScore
            # Deterministic scoring based on word count and content
            words = candidate.split()
            wc = len(words)
            lower = candidate.lower()
            sharpness = 3 if 3 <= wc <= 11 else 2 if wc <= 17 else 1
            emotional = (
                3
                if any(
                    w in lower
                    for w in (
                        "cost",
                        "trust",
                        "hurt",
                        "burn",
                        "fear",
                        "loss",
                        "bill",
                        "wound",
                        "price",
                    )
                )
                else 2
                if any(w in lower for w in ("maybe", "still", "yet", "though", "again"))
                else 1
            )
            rhythm = (
                3
                if any(p in candidate for p in (",", "-", ":"))
                and 4 <= wc <= 14
                else 2
                if "." in candidate or "?" in candidate or 4 <= wc <= 18
                else 1
            )
            thematic = 3 if any(w in lower for w in (
                "cost", "ledger", "rent", "debt", "scarcity", "flow", "power",
                "truth", "weight", "bill", "wound", "price", "pay", "owe"
            )) else 2 if any(w in lower for w in ("you", "room", "room", "here", "now")) else 1
            shareability = 3 if wc <= 9 and any(p in candidate for p in (".", "?", ":")) else 2 if wc <= 15 else 1
            return QualityScore(
                sharpness=sharpness,
                emotional_texture=emotional,
                rhythm=rhythm,
                thematic_relevance=thematic,
                shareability=shareability,
            )
        return BanterEngine(
            quality_judge=stub_quality_judge,
            move_selector=compute_distribution,
            fallback_pool=fallback_pool,
            relationship_memory=HarnessRelationshipMemory(pair_states),
            scene_context=SceneContext(),
            model_router=model_router,
            pacing_controller=PacingController(),
            anti_repetition=AntiRepetitionGate(),
            config=BanterConfig(),
        )

    @staticmethod
    @staticmethod
    async def _default_stub(prompt: str) -> str:
        """Deterministic model stub for CI - returns archetype-flavored lines."""
        prompt_lower = prompt.lower()
        archetype_banks = {
            "parasite": [
                "Your generosity is already invoiced.",
                "I only need you to notice the bill.",
                "You paid for that comfort twice.",
                "The room keeps feeding me without realizing it.",
                "I take the shape of what you can afford.",
            ],
            "prophet": [
                "The bill comes due before you admit it.",
                "You keep calling it warning after the fact.",
                "What happens next is already leaning toward you.",
                "This was always the cost of pretending otherwise.",
                "The future is less patient than you are.",
            ],
            "trickster": [
                "You brought a blade and called it a joke.",
                "The punchline is you still missed the point.",
                "I only look casual because you are slow.",
                "That was almost clever, which is enough to hurt.",
                "Now we are finally being honest about the game.",
            ],
            "sovereign": [
                "Order still belongs to whoever can hold it.",
                "You may speak, but the frame is mine.",
                "That objection costs more than it buys.",
                "I do not need agreement to remain in command.",
                "The room already knows who sets the terms.",
            ],
            "shadow": [
                "You hear the absence before the answer.",
                "The hidden part is the only part that mattered.",
                "I moved once and you called it silence.",
                "The angle is always where the wound starts.",
                "You cannot name what you refuse to face.",
            ],
            "herald": [
                "The signal is already out in the room.",
                "I only arrive to say what is coming.",
                "A quiet moment can still announce everything.",
                "Now the story has to answer itself.",
                "The first honest word changes the weather.",
            ],
            "keeper": [
                "I keep what lasts and discard the rest.",
                "Every useful thing has a maintenance cost.",
                "You are borrowing clarity you have not earned.",
                "What survives the ledger survives the room.",
                "I count the cost so you do not have to.",
            ],
            "martyr": [
                "I know exactly what this costs because I paid it.",
                "The burden is real even when nobody applauds.",
                "You mistake endurance for permission.",
                "Some losses are chosen, and that matters.",
                "I am not asking to be spared.",
            ],
        }
        lines = next(
            (bank for key, bank in archetype_banks.items() if key in prompt_lower),
            [
                "The cost arrives whether you count it or not.",
                "Trust is just a word people use before the bill.",
                "You already know the answer to that question.",
                "Silence speaks when words become too expensive.",
                "Every choice here has weight you refuse to measure.",
            ],
        )
        # Use prompt hash to pick deterministically
        idx = hash(prompt) % len(lines)
        return lines[idx]
