"""Pipeline Orchestrator — wires all banter components into a single generate_beat() call.

Replaces `_compose_reactive_banter` and `_banter_loop` from archetype_graphs.py
with a modular pipeline: move selection → prompt building → model routing →
quality scoring → refinement loop → anti-repetition → fallback → pacing.

Requirements: 1.3, 1.4, 1.5, 1.6, 3.2, 3.6, 5.2, 5.3, 8.4, 8.5, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
import uuid
from typing import TYPE_CHECKING, Callable, Protocol

from .anti_repetition import AntiRepetitionGate, WorldRepetitionBuffer
from .arc_context import arc_context_builder
from .fallback_pool import FallbackPool
from .veil_layer import VeilLayer
from .model_router import ModelRouter
from .move_selector import compute_distribution as _compute_distribution
from .pacing_controller import PacingController
from .quality_judge import evaluate_enhanced, get_pass_threshold, get_refine_threshold
from .relationship_memory import RelationshipMemory
from .scene_context import SceneContext
from .types import (
    BanterConfig,
    BeatResult,
    MoveContext,
    QualityJudgeError,
    QualityScore,
    RelationshipMemoryError,
    SessionState,
)

if TYPE_CHECKING:
    from .callback_registry import CallbackRegistry
    from .emotional_primer import EmotionalPrimer
    from .soul_types import SoulEngineConfig, SubtextInstruction
    from .subtlety_director import SubtletyDirector
    from .voice_dna import VoiceDNA

log = logging.getLogger("god.banter.engine")

# ~800 tokens at 4 chars/token; combined cap for all soul module prompt outputs
SOUL_BUDGET_TOKENS: int = 800
_SOUL_BUDGET_CHARS: int = SOUL_BUDGET_TOKENS * 4
_SOUL_TIMEOUT_S: float = 0.2


# ---------------------------------------------------------------------------
# Protocols for injectable callables
# ---------------------------------------------------------------------------


class QualityEvaluator(Protocol):
    """Protocol for the quality judge evaluate function."""

    async def __call__(
        self,
        candidate: str,
        *,
        archetype: str,
        move: str,
        arc_theme: str,
        scene_context=None,
        timeout_s: float = 2.0,
    ) -> QualityScore: ...


class MoveDistributionComputer(Protocol):
    """Protocol for move_selector.compute_distribution."""

    def __call__(self, ctx: MoveContext): ...


# ---------------------------------------------------------------------------
# BanterEngine
# ---------------------------------------------------------------------------


class BanterEngine:
    """Top-level pipeline orchestrator for broadcast banter generation.

    Accepts all 8 banter components via dependency injection and orchestrates
    the full generation pipeline in `generate_beat()`.

    Parameters
    ----------
    quality_judge : QualityEvaluator
        Async callable that scores candidate lines (typically quality_judge.evaluate).
    move_selector : MoveDistributionComputer
        Callable that computes a MoveDistribution from MoveContext.
    fallback_pool : FallbackPool
        Curated fallback template pool.
    relationship_memory : RelationshipMemory
        Persistent pairwise interaction history.
    scene_context : SceneContext
        Scene-level state (beats, energy, landed hits).
    model_router : ModelRouter
        Dual-model routing with circuit breaking.
    pacing_controller : PacingController
        Energy-aware pacing calculations.
    anti_repetition : AntiRepetitionGate
        N-gram and opener repetition guard.
    config : BanterConfig
        Global configuration parameters.
    """

    def __init__(
        self,
        quality_judge: QualityEvaluator,
        move_selector: MoveDistributionComputer,
        fallback_pool: FallbackPool,
        relationship_memory: RelationshipMemory,
        scene_context: SceneContext,
        model_router: ModelRouter,
        pacing_controller: PacingController,
        anti_repetition: AntiRepetitionGate,
        config: BanterConfig | None = None,
        voice_dna: VoiceDNA | None = None,
        emotional_primer: EmotionalPrimer | None = None,
        callback_registry: CallbackRegistry | None = None,
        subtlety_director: SubtletyDirector | None = None,
        soul_config: SoulEngineConfig | None = None,
        veil_layer: VeilLayer | None = None,
        world_buffer: WorldRepetitionBuffer | None = None,
    ) -> None:
        self._quality_judge = quality_judge
        self._move_selector = move_selector
        self._fallback_pool = fallback_pool
        self._relationship_memory = relationship_memory
        self._scene_context = scene_context
        self._model_router = model_router
        self._pacing_controller = pacing_controller
        self._anti_repetition = anti_repetition
        self._config = config or BanterConfig()

        # Soul engine modules (all optional)
        self._voice_dna = voice_dna
        self._emotional_primer = emotional_primer
        self._callback_registry = callback_registry
        self._subtlety_director = subtlety_director
        self._soul_config = soul_config
        self._veil_layer = veil_layer or VeilLayer()
        self._world_buffer = world_buffer or WorldRepetitionBuffer()

        # Session state
        self._session = SessionState(
            session_id=str(uuid.uuid4()),
            started_at=time.time(),
        )
        self._last_beat_ts: float = 0.0

        # Per-beat soul context (reset each generate_beat call)
        self._pending_subtext_instruction: SubtextInstruction | None = None
        self._pending_subtext_was_injected: bool = False
        self._last_soul_metadata: dict = {}
        self._last_quality_detail = None  # EnhancedQualityScore | None; set per beat

        # Session-level soul tracking
        self._session_callback_count: int = 0
        self._beat_number: int = 0

        # CRACK move state (T4.1)
        self._crack_active: bool = False  # True during a CRACK beat
        self._next_move_override: str | None = None  # snap-back override
        self._consecutive_counters: int = 0  # tracks consecutive COUNTER moves per elder

        # Chaos window state (T3.1)
        self._consecutive_escalating: int = 0  # tracks consecutive ESCALATE/TAUNT moves
        self._last_tension: int = 5  # last known tension level

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate_beat(
        self,
        elder: str,
        archetype: str,
        opponent: str | None,
        arc_theme: str,
        conv_thread: list[dict],
    ) -> BeatResult:
        """Full pipeline: generate a single broadcast-quality banter beat.

        Steps:
        1. Session boundary detection (5-min gap → reset)
        2. Move selection via Move_Selector
        3. Prompt building with Scene_Context + Relationship_Memory
        4. Model routing via Model_Router
        5. Quality scoring via Quality_Judge (word-count rule on error)
        6. Refinement loop (up to max_refinement_rounds)
        7. Anti-repetition check (fallback after max_rejection_rounds)
        8. Pacing computation
        9. Return BeatResult

        Args:
            elder: Name of the speaking Elder.
            archetype: The Elder's archetype.
            opponent: Name of the opponent Elder (None if none).
            arc_theme: Current narrative arc theme.
            conv_thread: Recent conversation thread (list of dicts with
                         'speaker' and 'content' keys).

        Returns:
            BeatResult with line, move, quality_score, delay_s, pre_pause_s,
            source, template_id, and metadata.
        """
        now = time.time()
        self._beat_number += 1

        # --- Step 1: Session boundary detection ---
        if self._last_beat_ts > 0:
            gap = now - self._last_beat_ts
            if gap > self._config.session_timeout_s:
                self._reset_session()
        self._last_beat_ts = now

        # --- Step 2: Move selection ---
        scene_data = self._scene_context.get_context_for_generation(elder)

        # Apply snap-back override if previous beat was CRACK (T4.1)
        if self._next_move_override is not None:
            move = self._next_move_override
            self._next_move_override = None
        else:
            move = self._select_move(elder, archetype, arc_theme, conv_thread, scene_data)

        # CRACK move override — check trigger conditions (T4.1)
        if move != "CRACK":
            # Build a minimal pair_state preview for CRACK evaluation
            _pair_state_preview = None
            if opponent:
                _pair_state_preview = await self._get_pair_state(elder, opponent)
            _tension_preview = (
                _pair_state_preview.tension_level if _pair_state_preview is not None else 5
            )
            if self._should_crack(_tension_preview, _pair_state_preview, self._consecutive_counters):
                move = "CRACK"

        # Track consecutive COUNTER for CRACK trigger
        if move == "COUNTER":
            self._consecutive_counters += 1
        else:
            self._consecutive_counters = 0

        # Track consecutive ESCALATE/TAUNT for chaos window (T3.1)
        if move in ("ESCALATE", "TAUNT"):
            self._consecutive_escalating += 1
        else:
            self._consecutive_escalating = 0

        # If CRACK, set snap-back for next beat
        self._crack_active = move == "CRACK"
        if self._crack_active:
            self._next_move_override = "COUNTER" if random.random() < 0.5 else "ESCALATE"

        # --- Step 3: Prompt building ---
        prompt = await self._build_prompt(
            elder, archetype, opponent, arc_theme, move, conv_thread, scene_data
        )

        # --- Step 4 + 5 + 6: Generate, score, refine ---
        line, score, source, route_decision = await self._generate_and_refine(
            prompt, elder, archetype, move, arc_theme, scene_data
        )

        # --- Step 7: Anti-repetition check ---
        line, score, source, template_id = await self._anti_repetition_loop(
            line, score, source, prompt, elder, archetype, move, arc_theme,
            opponent, scene_data
        )

        # --- Step 8: Pacing computation ---
        landed_hit = scene_data.landed_hit is not None and scene_data.landed_hit_remaining > 0
        pacing = self._pacing_controller.compute_delay(
            previous_score=score,
            upcoming_move=move,
            scene_energy=scene_data.scene_energy,
            landed_hit=landed_hit,
        )

        # Record delivery for anti-repetition tracking (per-Elder + world buffer)
        register = self._infer_register(move, score)
        self._anti_repetition.record_delivery(elder, line, register)
        self._world_buffer.record(line)

        # Record for cross-pair eavesdropping (T3.2)
        self._scene_context.record_pair_line(elder, opponent or "", line)

        # Store memorable moments when soul is active and quality is high
        soul_active = self._soul_config is not None and self._soul_config.enabled
        if soul_active and self._callback_registry is not None and opponent is not None:
            refine_thresh = get_refine_threshold(True)
            if score >= refine_thresh:
                asyncio.ensure_future(
                    self._callback_registry.store_memorable_moment(
                        elder, opponent, line, move, arc_theme,
                        valence="positive",
                        summary=f"{move} on {arc_theme}",
                        score=score,
                    )
                )

        # --- Step 9: Return BeatResult ---
        clip_candidate = (
            self._last_quality_detail.is_clip_candidate
            if self._last_quality_detail is not None
            else False
        )
        return BeatResult(
            line=line,
            move=move,
            quality_score=score,
            delay_s=pacing.inter_beat_delay_s,
            pre_pause_s=pacing.pre_delivery_pause_s,
            source=source,
            template_id=template_id,
            metadata={
                "pacing_rule": pacing.rule_applied,
                "session_id": self._session.session_id,
                "soul": self._last_soul_metadata,
                "clip_candidate": clip_candidate,
            },
        )

    # ------------------------------------------------------------------
    # Internal: Move selection
    # ------------------------------------------------------------------

    def _select_move(
        self,
        elder: str,
        archetype: str,
        arc_theme: str,
        conv_thread: list[dict],
        scene_data,
    ) -> str:
        """Build MoveContext and sample a move from the distribution."""
        # Extract last 3 moves from conversation thread
        last_3_moves = self._extract_last_moves(elder, conv_thread)

        # Get tension from scene or default
        tension = self._get_tension_from_scene(scene_data)

        # Compute momentum from conversation thread
        momentum = self._compute_momentum(conv_thread)

        # Get fear keywords for this archetype
        from .move_selector import ARCHETYPE_FEARS
        fear_keywords = ARCHETYPE_FEARS.get(archetype, [])

        # Count consecutive counters in pair
        consecutive_counters = self._count_consecutive_counters(conv_thread)

        # Detect "losing the room" signal from Scene_Context
        consecutive_low_scores = self._count_consecutive_low_scores(elder, scene_data)

        ctx = MoveContext(
            archetype=archetype,
            last_3_moves=last_3_moves,
            tension_level=tension,
            momentum=momentum,
            arc_theme=arc_theme,
            fear_keywords=fear_keywords,
            consecutive_counters_in_pair=consecutive_counters,
            consecutive_low_scores=consecutive_low_scores,
        )

        distribution = self._move_selector(ctx)
        return distribution.sample()

    # ------------------------------------------------------------------
    # Internal: Prompt building
    # ------------------------------------------------------------------

    async def _build_prompt(
        self,
        elder: str,
        archetype: str,
        opponent: str | None,
        arc_theme: str,
        move: str,
        conv_thread: list[dict],
        scene_data,
    ) -> str:
        """Build generation prompt with soul modules, scene context and relationship memory."""
        parts: list[str] = []

        # Fetch relationship data once (used by both soul modules and existing components)
        history: list = []
        pair_state = None
        if opponent:
            history = await self._get_relationship_history(elder, opponent)
            pair_state = await self._get_pair_state(elder, opponent)

        tension: int = pair_state.tension_level if pair_state is not None else 5
        self._last_tension = tension  # cache for chaos window check
        reconciliation_active: bool = (
            pair_state is not None
            and pair_state.reconciliation_arc
            and pair_state.reconciliation_remaining > 0
        )

        # Soul engine prompt phase (200ms total budget, Req 7.1, 7.2)
        soul_active = self._soul_config is not None and self._soul_config.enabled
        self._last_soul_metadata = {}
        if soul_active:
            try:
                soul_parts, soul_meta = await asyncio.wait_for(
                    self._build_soul_prompt(
                        elder, archetype, opponent, arc_theme, move,
                        history, tension, reconciliation_active,
                    ),
                    timeout=_SOUL_TIMEOUT_S,
                )
                parts.extend(soul_parts)
                self._last_soul_metadata = soul_meta
            except asyncio.TimeoutError:
                log.debug("Soul prompt building timed out after %.0fms", _SOUL_TIMEOUT_S * 1000)
                self._last_soul_metadata = {"timeout": True}
            except Exception as e:
                log.debug("Soul prompt building failed: %s", e)
                self._last_soul_metadata = {"error": str(e)}

        # Scene context injection (Req 5.2)
        parts.append(self._format_scene_context(scene_data, elder))

        # Relationship memory injection (Req 3.2 — last 5 significant interactions)
        if opponent:
            if history:
                parts.append(self._format_relationship_history(history))

            # Reconciliation context if active (Req 3.5)
            if reconciliation_active and pair_state is not None:
                parts.append(self._format_reconciliation_context(pair_state, opponent))

        # Landed hit instruction (Req 5.3)
        if scene_data.landed_hit is not None and scene_data.landed_hit_remaining > 0:
            hit_line = scene_data.landed_hit.content
            hit_speaker = scene_data.landed_hit.speaker
            parts.append(
                f"[LANDED HIT] {hit_speaker} just delivered a devastating line: "
                f'"{hit_line}". Acknowledge or respond to it.'
            )

        # Register shift instruction (Req 8.4)
        if self._anti_repetition.should_shift_register(elder):
            parts.append(
                "[REGISTER SHIFT] Your last 3 lines used the same emotional register. "
                "Shift to a different tone."
            )

        # Arc pressure — never injects raw theme title (T1.1 fix)
        parts.append(arc_context_builder.format_injection(arc_theme))

        # VeilLayer — meta-awareness injection (T5.2, Section 6)
        if self._veil_layer.should_inject(
            beat_number=self._beat_number,
            move=move,
            pair_state=pair_state,
            twitch_event_fired=False,
        ):
            parts.append(self._veil_layer.get_injection())

        # CRACK override — replaces archetype prompt for this beat (T4.1)
        if move == "CRACK":
            parts.append(self._CRACK_PROMPT)
        # Snap-back — fires when previous beat was CRACK
        elif self._next_move_override is not None:
            parts.append(self._SNAP_BACK_PROMPT)

        # Interruption mechanic (T6.2) — em-dash interrupt at tension > 8, 20% chance
        interrupt_mode = (
            tension > 8
            and opponent is not None
            and random.random() < 0.2
        )

        # Trailing-off mechanic (T6.3) — hesitation at low tension CONCEDE/DEFLECT
        trailing_mode = (
            move in ("CONCEDE", "DEFLECT")
            and tension <= 3
        )

        # Core generation instruction (T1.3: grammar enforcement in prompt)
        if interrupt_mode:
            # Extract opponent's last line from conv_thread for reference
            opponent_last = ""
            if conv_thread and opponent:
                for turn in reversed(conv_thread):
                    if turn.get("speaker") == opponent:
                        opponent_last = turn.get("content", "")
                        break
            ref = f' Reference what {opponent} just said: "{opponent_last}".' if opponent_last else ""
            parts.append(
                f"You are {elder} ({archetype}). Move: {move}. Opponent: {opponent}. "
                f"Start your line with an em-dash (—) and cut into the middle of their argument.{ref} "
                f"No run-on sentences."
            )
        elif trailing_mode:
            parts.append(
                f"You are {elder} ({archetype}). Move: {move}. "
                f"{'Opponent: ' + opponent + '. ' if opponent else ''}"
                f"Generate a line that trails off or hesitates — incomplete thoughts, ellipses, "
                f"or a retraction mid-sentence are appropriate here. Show reluctance or exhaustion."
            )
        else:
            parts.append(
                f"You are {elder} ({archetype}). Move: {move}. "
                f"{'Opponent: ' + opponent + '. ' if opponent else ''}"
                f"Generate a single broadcast-quality banter line. "
                f"Each sentence must end with punctuation (. ! ?). "
                f"No run-on sentences. Maximum 2 sentences."
            )

        # Cross-pair eavesdropping injection (T3.2) — 1-in-10 beats
        if opponent and random.random() < 0.1:
            overheard = self._scene_context.get_other_pair_line(elder, opponent)
            if isinstance(overheard, tuple) and len(overheard) == 3:
                ox, oy, oline = overheard
                parts.append(f'[OVERHEARD] {ox} to {oy}: "{oline}"')

        # Recent conversation for context (pair-filtered)
        if conv_thread and opponent:
            pair_thread = [
                t for t in conv_thread
                if t.get("speaker") in (elder, opponent)
                or t.get("target") in (elder, opponent)
            ][-4:]
            if pair_thread:
                thread_text = "\n".join(
                    f"{t.get('speaker', '???')}: {t.get('content', '')}"
                    for t in pair_thread
                )
                parts.append(f"Recent exchange:\n{thread_text}")
        elif conv_thread:
            recent = conv_thread[-4:]
            thread_text = "\n".join(
                f"{t.get('speaker', '???')}: {t.get('content', '')}"
                for t in recent
            )
            parts.append(f"Recent conversation:\n{thread_text}")

        return "\n\n".join(parts)

    async def _build_soul_prompt(
        self,
        elder: str,
        archetype: str,
        opponent: str | None,
        arc_theme: str,
        move: str,
        history: list,
        tension: int,
        reconciliation_active: bool,
    ) -> tuple[list[str], dict]:
        """Compose soul module prompt injections with 800-token combined cap.

        Order: Voice_DNA → Emotional_Primer → Callback_Registry → Subtlety_Director
        Each module is wrapped in try/except; exceptions → skip module, log DEBUG.
        Returns (soul_parts, metadata_dict) where metadata records module success/failure.
        """
        soul_parts: list[str] = []
        metadata: dict = {}
        total_chars = 0
        sore_spots: list = []

        # 1. Voice_DNA — linguistic style guidance (Req 1.6)
        if self._voice_dna is not None:
            try:
                injection = self._voice_dna.get_prompt_injection(archetype)
                if injection:
                    chunk = f"[VOICE DNA]\n{injection}"
                    if total_chars + len(chunk) <= _SOUL_BUDGET_CHARS:
                        soul_parts.append(chunk)
                        total_chars += len(chunk)
                metadata["voice_dna"] = True
            except Exception as e:
                log.debug("Voice_DNA.get_prompt_injection failed: %s", e)
                metadata["voice_dna"] = False

        # 2. Emotional_Primer — present-tense emotional framing (Req 3.7)
        if self._emotional_primer is not None:
            try:
                emotional_ctx = await self._emotional_primer.generate_emotional_context(
                    archetype, history, tension, reconciliation_active
                )
                if emotional_ctx:
                    chunk = f"[EMOTIONAL CONTEXT]\n{emotional_ctx}"
                    if total_chars + len(chunk) <= _SOUL_BUDGET_CHARS:
                        soul_parts.append(chunk)
                        total_chars += len(chunk)
                metadata["emotional_primer"] = True
            except Exception as e:
                log.debug("Emotional_Primer.generate_emotional_context failed: %s", e)
                metadata["emotional_primer"] = False

        # 3. Callback_Registry — memorable moments and sore spots (Req 4.6)
        if self._callback_registry is not None and opponent is not None:
            try:
                sore_spots = await self._callback_registry.get_sore_spots(opponent, arc_theme)
                callback = await self._callback_registry.surface_callback(
                    elder, opponent, tension, arc_theme,
                    self._beat_number, self._session_callback_count,
                )
                if callback is not None:
                    chunk = (
                        f"[CALLBACK] Reference this earlier moment: "
                        f'"{callback.original_line}" ({callback.suggested_framing})'
                    )
                    if total_chars + len(chunk) <= _SOUL_BUDGET_CHARS:
                        soul_parts.append(chunk)
                        total_chars += len(chunk)
                        self._session_callback_count += 1
                metadata["callback_registry"] = True
            except Exception as e:
                log.debug("Callback_Registry failed: %s", e)
                metadata["callback_registry"] = False

        # 4. Subtlety_Director — subtext instruction (Req 7.4)
        self._pending_subtext_instruction = None
        self._pending_subtext_was_injected = False
        if self._subtlety_director is not None:
            try:
                has_history = len(history) > 0
                has_sore_spot = len(sore_spots) > 0
                should_inject = self._subtlety_director.should_inject_subtext(
                    tension, move, has_sore_spot, has_history
                )
                if should_inject:
                    sore_spot = sore_spots[0] if sore_spots else None
                    instruction = self._subtlety_director.generate_subtext_instruction(
                        elder, opponent or "opponent", tension, sore_spot, arc_theme
                    )
                    if instruction is not None:
                        chunk = (
                            f"[SUBTEXT] Surface meaning: {instruction.surface_meaning}. "
                            f"Implied: {instruction.implied_meaning}. "
                            f"Technique: {instruction.technique}."
                        )
                        if total_chars + len(chunk) <= _SOUL_BUDGET_CHARS:
                            soul_parts.append(chunk)
                            total_chars += len(chunk)
                            self._pending_subtext_instruction = instruction
                            self._pending_subtext_was_injected = True
                metadata["subtlety_director"] = True
            except Exception as e:
                log.debug("Subtlety_Director failed: %s", e)
                metadata["subtlety_director"] = False

        return soul_parts, metadata

    # ------------------------------------------------------------------
    # Internal: Generation and refinement
    # ------------------------------------------------------------------

    async def _generate_and_refine(
        self,
        prompt: str,
        elder: str,
        archetype: str,
        move: str,
        arc_theme: str,
        scene_data,
    ) -> tuple[str, int, str, object]:
        """Generate a line via model router, score it, and refine if needed.

        Returns (line, score, source, route_decision).
        """
        route_decision = self._model_router.route("broadcast")
        soul_active = self._soul_config is not None and self._soul_config.enabled

        # Chaos window check (T3.1) — must read tension from last known pair_state
        chaos = self._is_chaos_window()
        if chaos:
            threshold = 6  # Hard floor — raw is the point
        elif move == "CRACK":
            threshold = 5  # CRACK: rawness over polish (T4.1, T7.3)
        elif move == "CONCEDE":
            threshold = 5  # graceful collapse is fine at lower scores (T7.3)
        elif move == "CALLBACK":
            threshold = 10  # must earn the reference (T7.3)
        elif move == "ESCALATE" and self._last_tension > 8:
            threshold = 8  # still needs to land at high tension (T7.3)
        else:
            threshold = get_pass_threshold(soul_active) if soul_active else route_decision.quality_threshold

        # Attempt probe if circuit is broken and cooldown expired
        if self._model_router.should_probe():
            probed = await self._model_router.probe_remote()
            if probed:
                route_decision = self._model_router.route("broadcast")
                if not chaos and move not in ("CRACK", "CONCEDE", "CALLBACK") and not (move == "ESCALATE" and self._last_tension > 8):
                    threshold = route_decision.quality_threshold

        # Initial generation
        line = await self._call_model(prompt, route_decision)
        if line is None:
            # Model failed entirely — use fallback immediately
            return self._select_fallback(archetype, move, elder, arc_theme)

        source = route_decision.target
        score = 0

        # Chaos window and CRACK: no refinement loop (raw is the point)
        if chaos or move == "CRACK":
            score, scoring_failed = await self._score_candidate(
                line, archetype, move, arc_theme, scene_data
            )
            word_count = len(line.split())
            if 4 <= word_count <= 30:
                return line, score if not scoring_failed else 0, source, route_decision
            return self._select_fallback(archetype, move, elder, arc_theme)

        # Normal score and refine loop
        refinement_round = 0

        while refinement_round <= self._config.max_refinement_rounds:
            # Score the candidate
            score, scoring_failed = await self._score_candidate(
                line, archetype, move, arc_theme, scene_data
            )

            if scoring_failed:
                # Word-count acceptance rule (Req 1.5, 1.6)
                word_count = len(line.split())
                if 4 <= word_count <= 30:
                    return line, 0, source, route_decision
                else:
                    return self._select_fallback(archetype, move, elder, arc_theme)

            if score >= threshold:
                return line, score, source, route_decision

            # Below threshold — refine if attempts remain
            refinement_round += 1
            if refinement_round > self._config.max_refinement_rounds:
                break

            # Build refinement prompt with weak dimensions feedback
            line = await self._refine(
                prompt, line, archetype, move, arc_theme, route_decision, score
            )
            if line is None:
                break

        # Exhausted refinement — fallback (Req 1.4)
        return self._select_fallback(archetype, move, elder, arc_theme)

    async def _refine(
        self,
        original_prompt: str,
        current_line: str,
        archetype: str,
        move: str,
        arc_theme: str,
        route_decision,
        current_score: int,
    ) -> str | None:
        """Request a refined version with weak dimension feedback."""
        # Get weak dimensions from last scoring (use enhanced judge when soul active)
        soul_active = self._soul_config is not None and self._soul_config.enabled
        try:
            if soul_active:
                quality = await evaluate_enhanced(
                    current_line,
                    archetype=archetype,
                    move=move,
                    arc_theme=arc_theme,
                    voice_dna=self._voice_dna,
                    subtlety_director=self._subtlety_director,
                    subtext_instruction=self._pending_subtext_instruction,
                    subtext_was_injected=self._pending_subtext_was_injected,
                    config=self._soul_config,
                    timeout_s=self._config.quality_judge_timeout_s,
                )
            else:
                quality = await self._quality_judge(
                    current_line,
                    archetype=archetype,
                    move=move,
                    arc_theme=arc_theme,
                    timeout_s=self._config.quality_judge_timeout_s,
                )
            weak = quality.weak_dimensions
        except QualityJudgeError:
            weak = []

        feedback_parts = []
        if weak:
            dims_str = ", ".join(f"{name}={val}" for name, val in weak)
            feedback_parts.append(f"Weak dimensions: {dims_str}. Improve these.")

        feedback_parts.append(
            f"Previous line scored {current_score}/15. Generate a sharper version."
        )

        refinement_prompt = (
            original_prompt
            + "\n\n[REFINEMENT FEEDBACK]\n"
            + "\n".join(feedback_parts)
            + f"\nPrevious attempt: \"{current_line}\""
        )

        return await self._call_model(refinement_prompt, route_decision)

    # ------------------------------------------------------------------
    # Internal: Anti-repetition loop
    # ------------------------------------------------------------------

    async def _anti_repetition_loop(
        self,
        line: str,
        score: int,
        source: str,
        prompt: str,
        elder: str,
        archetype: str,
        move: str,
        arc_theme: str,
        opponent: str | None,
        scene_data,
    ) -> tuple[str, int, str, str | None]:
        """Check line against anti-repetition gate, re-generate if rejected.

        After max_rejection_rounds (3) rejections, falls back to fallback pool.

        Returns (line, score, source, template_id).
        """
        rejection_count = 0

        while rejection_count < self._config.max_rejection_rounds:
            # Per-Elder gate
            verdict = self._anti_repetition.check(elder, line)
            # World-level cross-Elder gate (T1.4)
            world_rejected = verdict.accepted and self._world_buffer.is_too_similar(line)
            if verdict.accepted and not world_rejected:
                return line, score, source, None

            # Rejected — re-generate
            rejection_count += 1
            log.debug(
                "Anti-repetition rejected for %s (reason=%s, attempt=%d)",
                elder, verdict.rejection_reason, rejection_count,
            )

            if rejection_count >= self._config.max_rejection_rounds:
                break

            # Try to generate a fresh line
            route_decision = self._model_router.route("broadcast")
            new_line = await self._call_model(prompt, route_decision)
            if new_line is None:
                break

            # Score the new line
            new_score, scoring_failed = await self._score_candidate(
                new_line, archetype, move, arc_theme, scene_data
            )
            if scoring_failed:
                word_count = len(new_line.split())
                if 4 <= word_count <= 30:
                    line, score, source = new_line, 0, route_decision.target
                else:
                    break
            else:
                line, score, source = new_line, new_score, route_decision.target

        # Max rejections reached — fallback (Req 8.5)
        fb_line, fb_score, fb_source, fb_result = self._select_fallback(
            archetype, move, elder, arc_theme
        )
        return fb_line, fb_score, fb_source, fb_result[1] if isinstance(fb_result, tuple) else None

    # ------------------------------------------------------------------
    # Internal: Scoring
    # ------------------------------------------------------------------

    async def _score_candidate(
        self,
        line: str,
        archetype: str,
        move: str,
        arc_theme: str,
        scene_data,
    ) -> tuple[int, bool]:
        """Score a candidate line. Returns (score, scoring_failed).

        Uses EnhancedQualityScore when soul engine is active (Req 7.5).
        On QualityJudgeError, returns (0, True) for word-count rule handling.
        """
        soul_active = self._soul_config is not None and self._soul_config.enabled
        try:
            if soul_active:
                quality = await evaluate_enhanced(
                    line,
                    archetype=archetype,
                    move=move,
                    arc_theme=arc_theme,
                    scene_context=scene_data,
                    voice_dna=self._voice_dna,
                    subtlety_director=self._subtlety_director,
                    subtext_instruction=self._pending_subtext_instruction,
                    subtext_was_injected=self._pending_subtext_was_injected,
                    config=self._soul_config,
                    timeout_s=self._config.quality_judge_timeout_s,
                )
                self._last_quality_detail = quality
            else:
                quality = await self._quality_judge(
                    line,
                    archetype=archetype,
                    move=move,
                    arc_theme=arc_theme,
                    scene_context=scene_data,
                    timeout_s=self._config.quality_judge_timeout_s,
                )
                self._last_quality_detail = None
            return quality.total, False
        except QualityJudgeError as e:
            log.debug("Quality judge error: %s", e)
            return 0, True

    # ------------------------------------------------------------------
    # Internal: Model calling
    # ------------------------------------------------------------------

    async def _call_model(self, prompt: str, route_decision) -> str | None:
        """Call the appropriate model based on route decision.

        Falls back to local if remote fails, and to None if both fail.
        """
        if route_decision.target == "remote":
            result = await self._model_router.call_remote(
                prompt, timeout_s=route_decision.timeout_s
            )
            if result is not None:
                return result.strip()

            # Remote failed — try local if available
            if self._model_router._local_model is not None:
                try:
                    local_result = await self._model_router._local_model(prompt)
                    if local_result and self._model_router.validate_response(local_result):
                        return local_result.strip()
                except Exception as e:
                    log.debug("Local model also failed: %s", e)
            return None
        else:
            # Local routing
            if self._model_router._local_model is not None:
                try:
                    result = await self._model_router._local_model(prompt)
                    if result and self._model_router.validate_response(result):
                        return result.strip()
                except Exception as e:
                    log.debug("Local model failed: %s", e)
            return None

    # ------------------------------------------------------------------
    # Internal: Fallback selection
    # ------------------------------------------------------------------

    def _select_fallback(
        self,
        archetype: str,
        move: str,
        elder: str,
        arc_theme: str,
    ) -> tuple[str, int, str, object]:
        """Select from fallback pool with exclusions.

        Returns (line, score=0, source="fallback", route_decision_placeholder).
        """
        # Exclude last 5 used templates (Req 8.5)
        recent_ids = list(self._session.recent_beat_template_ids)[-5:]
        excluded = set(recent_ids)

        selection = self._fallback_pool.select(
            archetype,
            move,
            arc_theme=arc_theme,
            excluded_ids=excluded,
            session_used_ids=self._session.used_template_ids,
        )

        # Track template usage in session
        self._session.used_template_ids.add(selection.template_id)
        self._session.recent_beat_template_ids.append(selection.template_id)

        return selection.text, 0, "fallback", selection.template_id

    # ------------------------------------------------------------------
    # Internal: Relationship memory
    # ------------------------------------------------------------------

    async def _get_relationship_history(self, elder: str, opponent: str) -> list:
        """Get last 5 significant interactions, with graceful degradation."""
        try:
            return await self._relationship_memory.get_significant_history(
                elder, opponent, limit=5
            )
        except (RelationshipMemoryError, Exception) as e:
            log.debug("Relationship memory unavailable: %s", e)
            return []

    async def _get_pair_state(self, elder: str, opponent: str):
        """Get pair state (tension, reconciliation) with graceful degradation."""
        try:
            return await self._relationship_memory.get_pair_state(elder, opponent)
        except (RelationshipMemoryError, Exception) as e:
            log.debug("Pair state unavailable: %s", e)
        return None

    def _format_reconciliation_context(self, pair_state, opponent: str) -> str:
        """Format reconciliation arc context for prompt injection."""
        return (
            f"[RECONCILIATION ARC] You and {opponent} are in a reconciliation phase. "
            f"Peak tension context: {pair_state.peak_tension_summary}. "
            f"Remaining interactions with this context: {pair_state.reconciliation_remaining}."
        )

    # ------------------------------------------------------------------
    # Internal: Helper methods
    # ------------------------------------------------------------------

    def _reset_session(self) -> None:
        """Reset session state for a new broadcast stream."""
        log.info("Session boundary detected — resetting session state")
        self._session = SessionState(
            session_id=str(uuid.uuid4()),
            started_at=time.time(),
        )
        self._fallback_pool.reset_session()
        self._session_callback_count = 0
        self._beat_number = 0
        self._crack_active = False
        self._next_move_override = None
        self._consecutive_counters = 0
        self._consecutive_escalating = 0
        self._last_tension = 5

    def _extract_last_moves(self, elder: str, conv_thread: list[dict]) -> list[str]:
        """Extract the last 3 moves made by this elder from the conversation thread."""
        moves: list[str] = []
        for entry in reversed(conv_thread):
            if entry.get("speaker") == elder and "move" in entry:
                moves.append(entry["move"])
                if len(moves) >= 3:
                    break
        moves.reverse()
        return moves

    def _get_tension_from_scene(self, scene_data) -> int | None:
        """Extract tension level from scene data or return None."""
        # Tension is tracked per-pair in relationship memory; scene_data
        # doesn't directly hold it. Return None to let move_selector
        # use its base distribution without tension adjustments.
        return None

    def _compute_momentum(self, conv_thread: list[dict]) -> str | None:
        """Derive conversation momentum from recent thread."""
        if len(conv_thread) < 3:
            return None

        recent = conv_thread[-4:]
        moves = [e.get("move", "") for e in recent if "move" in e]

        if not moves:
            return None

        escalating_moves = {"ESCALATE", "TAUNT", "COUNTER"}
        cooling_moves = {"CONCEDE", "DEFLECT", "PIVOT"}

        escalating_count = sum(1 for m in moves if m in escalating_moves)
        cooling_count = sum(1 for m in moves if m in cooling_moves)

        if escalating_count >= 3:
            return "escalating"
        elif cooling_count >= 3:
            return "cooling"
        elif escalating_count == cooling_count and len(moves) >= 3:
            return "stalemate"
        else:
            return "shifting"

    def _count_consecutive_counters(self, conv_thread: list[dict]) -> int:
        """Count consecutive COUNTER moves at the end of the conversation."""
        count = 0
        for entry in reversed(conv_thread):
            if entry.get("move") == "COUNTER":
                count += 1
            else:
                break
        return count

    def _count_consecutive_low_scores(self, elder: str, scene_data) -> int:
        """Count consecutive low scores for an elder from scene context.

        "Losing the room" = 2+ consecutive beats below 6 from this elder.
        """
        beats = list(scene_data.recent_beats)
        count = 0
        for beat in reversed(beats):
            if beat.speaker == elder and beat.quality_score < 6:
                count += 1
            elif beat.speaker == elder:
                break
        return count

    def _format_scene_context(self, scene_data, elder: str) -> str:
        """Format scene context for prompt injection."""
        parts = []

        if scene_data.recent_beats:
            beats_text = []
            for b in scene_data.recent_beats:
                beats_text.append(
                    f"  {b.speaker} [{b.move}] (energy: {b.energy_label}): {b.content}"
                )
            parts.append("Recent scene:\n" + "\n".join(beats_text))

        if scene_data.has_the_room:
            parts.append(f"Has the room: {scene_data.has_the_room}")

        parts.append(f"Scene energy: {scene_data.scene_energy}")

        return "\n".join(parts) if parts else "Scene: neutral, no prior beats."

    def _format_relationship_history(self, history: list) -> str:
        """Format relationship history for prompt injection."""
        if not history:
            return ""

        lines = ["[RELATIONSHIP HISTORY - Last significant interactions]"]
        for record in history[:5]:
            valence = record.emotional_valence
            flags = []
            if record.betrayal:
                flags.append("betrayal")
            if record.alliance:
                flags.append("alliance")
            if record.concession:
                flags.append("concession")
            flag_str = f" [{', '.join(flags)}]" if flags else ""
            lines.append(
                f"  {record.move_used} ({valence}){flag_str}"
            )
        return "\n".join(lines)

    def _infer_register(self, move: str, score: int) -> str:
        """Infer the emotional register from the move and score."""
        register_map = {
            "ESCALATE": "aggressive",
            "TAUNT": "aggressive",
            "CONCEDE": "vulnerable",
            "DEFLECT": "sardonic",
            "PIVOT": "measured",
            "QUESTION": "measured",
            "COUNTER": "sardonic",
            "CALLBACK": "playful",
            "CRACK": "vulnerable",
        }
        return register_map.get(move, "measured")

    # ------------------------------------------------------------------
    # Internal: CRACK vulnerability trigger (T4.1)
    # ------------------------------------------------------------------

    _CRACK_PROMPT = (
        "[CRACK — OVERRIDE]\n"
        "You are exhausted. Not physically. The kind of exhaustion that comes from holding\n"
        "your position for too long against someone who has earned the right to see through it.\n\n"
        "For this one line: do not defend your archetype. Do not perform your role.\n"
        "Say something true about what this exchange is actually costing you right now.\n"
        "You don't have to be broken — just honest for exactly one sentence before\n"
        "you recover.\n\n"
        "After this line, you will never speak this way again in this session."
    )

    _SNAP_BACK_PROMPT = (
        "[SNAP-BACK]\n"
        "You showed something last turn. That was a mistake. The being across from you\n"
        "witnessed it. Make them regret it. Recover completely. Be worse to them than\n"
        "before you slipped."
    )

    def _should_crack(
        self,
        tension: int,
        pair_state,
        consecutive_counters: int,
        rng: random.Random | None = None,
    ) -> bool:
        """Return True if this beat should be a CRACK (vulnerability) moment."""
        if pair_state is None:
            return False
        if not getattr(pair_state, "betrayal", False):
            return False
        if tension <= 8:
            return False
        if consecutive_counters < 3:
            return False
        _rng = rng or random
        return _rng.random() < 0.20

    def _is_chaos_window(self) -> bool:
        """Return True if this beat qualifies as a chaos window (T3.1).

        Chaos window: tension >= 8 OR 4+ consecutive escalating moves.
        Lasts exactly 1 beat; callers reset _consecutive_escalating after the beat.
        """
        return self._last_tension >= 8 or self._consecutive_escalating >= 4
