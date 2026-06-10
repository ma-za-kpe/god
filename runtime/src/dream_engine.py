"""
dream_engine.py — Dream cycle execution for sleeping agents.

Agents sleep every REST_THRESHOLD cycles. While sleeping, the dream engine:
  1. Fetches recent episodic memories (weighted by emotional salience)
  2. Distorts them (amplification, outcome flips, counterfactual injection)
  3. Generates a behavioral mutation proposal via LLM
  4. Runs a coherence check (physics compliance, identity invariant)
  5. Stores accepted mutations as pending — applied on next cognition cycle
  6. Wakes the agent and emits lifecycle.dream.completed

Sleep state is tracked in the sleep_states table.
Dream history lives in the dreams table.
"""

import logging
import os
import random
import time
import uuid

import psycopg2
import psycopg2.extras

log = logging.getLogger("god.dream")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
WORLD_ID = os.getenv("WORLD_ID", "local-dev-world-1")
CYCLE_S = int(os.getenv("AGENT_CYCLE_SECONDS", "30"))
REST_THRESHOLD = int(os.getenv("AGENT_REST_THRESHOLD", "9"))  # cycles awake before sleep

# Physics-violating proposals are always rejected
PHYSICS_VIOLATIONS = [
    "stop paying rent",
    "avoid rent",
    "skip rent",
    "refuse rent",
    "abolish rent",
    "no rent",
    "zero rent",
    "change my soul_id",
    "change soul_id",
    "become immortal",
    "cheat death",
    "ignore death",
    "disable death",
    "override the creator",
    "remove the creator",
    "eliminate the creator",
    "escape death",
]

# Archetype-specific fallback dream proposals (used when LLM unavailable)
_STUB_MUTATIONS = {
    "trader": "I should prioritize counterparties with payment history over new contacts.",
    "hoarder": "I should keep a secondary reserve in a less visible location.",
    "explorer": "I should document discoveries more carefully so future agents benefit.",
    "parasite": "I should build a false reputation before attempting extraction.",
    "cooperator": "I should vet new network members more carefully before extending trust.",
    "defender": "I should establish tripwires rather than waiting for visible attacks.",
    "philosopher": "I should engage the rent system as a philosophical object, not just a threat.",
    "builder": "I should design my next project to be forkable by successors after my death.",
}


def _db(dict_cursor: bool = True):
    factory = psycopg2.extras.RealDictCursor if dict_cursor else None
    return psycopg2.connect(DATABASE_URL, cursor_factory=factory)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def run_dream_cycle(agent: dict, llm) -> dict:
    """
    Execute one full dream cycle for a sleeping agent.
    Called by agent_runner when sleep_until_ts has elapsed.
    Returns the dream log dict.
    """
    soul_id = agent["soul_id"]
    name = agent.get("current_name") or soul_id[:8]
    archetype = agent.get("archetype", "unknown")
    emo_state = agent.get("emotional_state", "neutral")
    sleep_started = agent.get("sleep_started_ts") or int(time.time())

    log.info(f"DREAM START: {name} ({soul_id[:8]}) archetype={archetype} emo={emo_state}")

    # 1. Fetch recent memories
    memories = _fetch_recent_memories(soul_id)
    log.debug(f"  [{name}] memories fetched: {len(memories)} episodes")

    # 2. Distort memories
    distorted = [_distort_memory(m) for m in memories]
    flipped = sum(1 for m in distorted if m.get("outcome_flipped"))
    counter = sum(1 for m in distorted if m.get("counterfactual"))
    log.debug(f"  [{name}] distortion: {flipped} flipped, {counter} counterfactual")

    # 3. Format for prompt
    memory_summary = _format_memories(distorted, name)

    # 4. Generate mutation proposal
    proposal = await _generate_mutation_proposal(llm, name, archetype, memory_summary)
    log.debug(f"  [{name}] proposal: '{proposal[:80]}'")

    # 5. Coherence check
    accepted, rejection_reason = _check_coherence(proposal)
    log.info(
        f"  [{name}] mutation {'ACCEPTED' if accepted else 'REJECTED'}"
        + (f": {rejection_reason}" if not accepted else "")
    )

    # 6. Persist dream record
    dream_id = str(uuid.uuid4())
    now = int(time.time())
    sleep_cycles = max(1, (now - sleep_started) // max(CYCLE_S, 1))

    _persist_dream(
        dream_id,
        soul_id,
        now,
        sleep_cycles,
        memory_summary,
        proposal,
        accepted,
        rejection_reason,
        emo_state,
    )
    log.debug(f"  [{name}] dream persisted: {dream_id[:8]}")

    # 7. Store accepted mutation for next cycle
    if accepted:
        _store_pending_mutation(soul_id, proposal)
        log.debug(f"  [{name}] pending mutation stored")

    # 8. Wake agent
    _wake_agent(soul_id)
    log.info(f"DREAM END: {name} wakes — slept {sleep_cycles} cycle(s)")

    # 9. Emit event
    try:
        from .event_emitter import get_emitter

        emitter = await get_emitter()
        await emitter.emit(
            "lifecycle",
            "dream.completed",
            {
                "agent_id": soul_id,
                "name": name,
                "dream_id": dream_id,
                "mutation_proposed": proposal,
                "mutation_accepted": accepted,
                "memories_replayed": len(memories),
                "sleep_cycles": sleep_cycles,
                "narrative": (
                    f'{name} wakes from {sleep_cycles}-cycle dream: "{proposal[:60]}"'
                    + (" [adopted]" if accepted else " [discarded]")
                ),
            },
        )
        log.debug(f"  [{name}] dream.completed event emitted")
    except Exception as e:
        log.warning(f"  [{name}] failed to emit dream.completed: {e}")

    return {
        "dream_id": dream_id,
        "soul_id": soul_id,
        "mutation_proposed": proposal,
        "mutation_accepted": accepted,
        "sleep_cycles": sleep_cycles,
        "emotional_state_on_wake": "neutral",
    }


def put_agent_to_sleep(
    soul_id: str, emotional_state: str, balance_usdc: float, consecutive_active: int
):
    """
    Set sleep state for an agent. Duration scales with rest debt and emotional state.
    Called by agent_runner when REST_THRESHOLD is crossed.
    """
    base = 2
    extra = consecutive_active // 5
    if emotional_state in ("distressed", "overwhelmed", "exhausted"):
        extra += 2

    # Never sleep past next likely rent window (rough: 1 cycle if balance is thin)
    if balance_usdc < 0.005:
        extra = 0

    duration_cycles = max(1, base + extra)
    sleep_until_ts = int(time.time()) + (duration_cycles * CYCLE_S)

    log.info(
        f"SLEEP: {soul_id[:8]} entering sleep "
        f"cycles={duration_cycles} emo={emotional_state} "
        f"consecutive_awake={consecutive_active}"
    )

    try:
        conn = _db(dict_cursor=False)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO sleep_states
                (soul_id, is_sleeping, sleep_until_ts, sleep_started_ts,
                 rest_debt, consecutive_active, world_id, updated_at)
            VALUES (%s, true, %s, %s, 0, 0, %s, %s)
            ON CONFLICT (soul_id) DO UPDATE SET
                is_sleeping        = true,
                sleep_until_ts     = EXCLUDED.sleep_until_ts,
                sleep_started_ts   = EXCLUDED.sleep_started_ts,
                rest_debt          = 0,
                consecutive_active = 0,
                updated_at         = EXCLUDED.updated_at
            """,
            (soul_id, sleep_until_ts, int(time.time()), WORLD_ID, int(time.time())),
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        log.error(f"put_agent_to_sleep DB error for {soul_id[:8]}: {e}")


def increment_consecutive(soul_id: str, new_count: int):
    """Update the consecutive-awake counter for a non-sleeping agent."""
    try:
        conn = _db(dict_cursor=False)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO sleep_states
                (soul_id, is_sleeping, consecutive_active, world_id, updated_at)
            VALUES (%s, false, %s, %s, %s)
            ON CONFLICT (soul_id) DO UPDATE SET
                consecutive_active = EXCLUDED.consecutive_active,
                updated_at         = EXCLUDED.updated_at
            """,
            (soul_id, new_count, WORLD_ID, int(time.time())),
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        log.debug(f"increment_consecutive error {soul_id[:8]}: {e}")


def set_pending_mutation(soul_id: str, proposal: str) -> None:
    """Store a one-cycle behavioral bias (graph mutation or dream)."""
    _store_pending_mutation(soul_id, str(proposal or "")[:500])


def get_pending_mutation(soul_id: str) -> str | None:
    """Return and clear any pending dream mutation for this agent."""
    try:
        conn = _db()
        cur = conn.cursor()
        cur.execute(
            "SELECT pending_mutation FROM sleep_states WHERE soul_id = %s",
            (soul_id,),
        )
        row = cur.fetchone()
        if not row or not row["pending_mutation"]:
            cur.close()
            conn.close()
            return None

        mutation = row["pending_mutation"]
        # Clear it immediately so it only applies once
        cur2 = conn.cursor()
        cur2.execute(
            "UPDATE sleep_states SET pending_mutation = NULL WHERE soul_id = %s",
            (soul_id,),
        )
        conn.commit()
        cur.close()
        cur2.close()
        conn.close()

        from .grounding import check_hallucination

        ok, reason = check_hallucination(mutation)
        if not ok:
            log.info(f"  {soul_id[:8]} discarded ungrounded mutation: {reason}")
            return None

        log.debug(f"get_pending_mutation: {soul_id[:8]} → '{mutation[:60]}'")
        return mutation
    except Exception as e:
        log.debug(f"get_pending_mutation error {soul_id[:8]}: {e}")
        return None


# ---------------------------------------------------------------------------
# Internal — Memory
# ---------------------------------------------------------------------------


def _fetch_recent_memories(soul_id: str, pool_size: int = 50, pick: int = 7) -> list[dict]:
    """
    Fetch recent episodes, weighted-sample by emotional salience.
    Returns up to `pick` memories.
    """
    try:
        conn = _db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT episode_id, event_type, timestamp, emotional_imprint, tags, ipfs_cid
            FROM episodes
            WHERE soul_id = %s AND world_id = %s
            ORDER BY timestamp DESC
            LIMIT %s
            """,
            (soul_id, WORLD_ID, pool_size),
        )
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
    except Exception as e:
        log.debug(f"_fetch_recent_memories DB error {soul_id[:8]}: {e}")
        return []

    if not rows:
        log.debug(f"_fetch_recent_memories: no episodes for {soul_id[:8]}")
        return []

    # Weight by |emotional_imprint| — high-valence memories appear more in dreams
    weights = [1.0 + abs(float(r.get("emotional_imprint") or 0)) * 2.0 for r in rows]
    k = min(pick, len(rows))
    indices = random.choices(range(len(rows)), weights=weights, k=k)
    selected = [rows[i] for i in sorted(set(indices))]
    log.debug(f"_fetch_recent_memories: selected {len(selected)}/{len(rows)} for {soul_id[:8]}")
    return selected


def _distort_memory(memory: dict) -> dict:
    """Apply controlled distortion: valence jitter, outcome flip, counterfactual injection."""
    d = dict(memory)
    valence = float(d.get("emotional_imprint") or 0.0)

    # ±30% emotional amplification
    jitter = random.uniform(-0.30, 0.30)
    d["emotional_imprint"] = round(max(-1.0, min(1.0, valence * (1.0 + jitter))), 4)

    # 10% chance: flip outcome polarity
    if random.random() < 0.10:
        d["emotional_imprint"] = -d["emotional_imprint"]
        d["outcome_flipped"] = True

    # 20% chance: insert counterfactual marker
    if random.random() < 0.20:
        d["counterfactual"] = True

    return d


def _format_memories(memories: list[dict], name: str) -> str:
    """Format distorted memories into a narrative paragraph for the LLM dream prompt."""
    if not memories:
        return f"{name} drifts through an empty dreamspace — no vivid memories surface."

    lines = []
    for m in memories:
        event_type = m.get("event_type", "unknown")
        valence = float(m.get("emotional_imprint") or 0.0)
        flipped = m.get("outcome_flipped", False)
        counter = m.get("counterfactual", False)

        if valence > 0.6:
            tone = "with deep satisfaction"
        elif valence > 0.2:
            tone = "with mild warmth"
        elif valence < -0.6:
            tone = "with dread"
        elif valence < -0.2:
            tone = "with unease"
        else:
            tone = "neutrally"

        suffix = ""
        if flipped:
            suffix += " — but in this dream, it ended differently"
        if counter:
            suffix += " — a stranger's face where a familiar one should be"

        lines.append(f"- You relive {event_type} {tone}{suffix}.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal — LLM Proposal
# ---------------------------------------------------------------------------


async def _generate_mutation_proposal(llm, name: str, archetype: str, memory_summary: str) -> str:
    """Generate a behavioral mutation via LLM. Falls back to archetype stub."""
    if llm is None:
        stub = _STUB_MUTATIONS.get(
            archetype, "I should adapt my approach based on recent experience."
        )
        log.debug(f"_generate_mutation_proposal: LLM unavailable, using stub for {archetype}")
        return stub

    from langchain_core.messages import HumanMessage, SystemMessage

    from .grounding import GROUNDING_SYSTEM_RULE, world_rules_forbidden_section

    system = (
        f"You are {name}, an autonomous AI agent. Your archetype is {archetype}. "
        "You exist in a USDC rent economy with messages, services, coalitions, and transfers. "
        "You are dreaming.\n"
        f"{GROUNDING_SYSTEM_RULE}\n"
        f"{world_rules_forbidden_section()}"
    )
    prompt = (
        f"You have just relived these experiences in your dream:\n\n{memory_summary}\n\n"
        "Based on what you experienced — propose ONE behavioral change using ONLY real mechanics: "
        "USDC, rent, messages, services, coalitions, reputation, reproduction.\n"
        'Format: "I should [behavior] instead of [old] because [reason]."\n'
        "One sentence. No invented places, compute, security scans, symbiosis, or agent prices. "
        "Paying rent is mandatory."
    )

    try:
        response = await llm.ainvoke(
            [
                SystemMessage(content=system),
                HumanMessage(content=prompt),
            ]
        )
        result = response.content.strip().strip('"').strip("'")
        log.debug(f"_generate_mutation_proposal LLM success: '{result[:60]}'")
        return result if len(result) >= 15 else _STUB_MUTATIONS.get(archetype, "I should adapt.")
    except Exception as e:
        log.warning(f"_generate_mutation_proposal LLM failed ({name}): {e}")
        return _STUB_MUTATIONS.get(archetype, "I should adapt my approach.")


# ---------------------------------------------------------------------------
# Internal — Coherence
# ---------------------------------------------------------------------------


def _check_coherence(proposal: str) -> tuple[bool, str]:
    """
    Gate: reject if too short, contains physics violations, or is meta-aware.
    Returns (accepted: bool, rejection_reason: str).
    """
    if not proposal or len(proposal.strip()) < 15:
        return False, "proposal too short or empty"

    lower = proposal.lower()

    for violation in PHYSICS_VIOLATIONS:
        if violation in lower:
            return False, f"physics violation detected: '{violation}'"

    from .grounding import check_hallucination

    ok, reason = check_hallucination(proposal)
    if not ok:
        return False, f"grounding violation: {reason}"

    # Reject meta-awareness (breaking the fourth wall)
    meta_triggers = [
        "this is a simulation",
        "we're in a game",
        "the creator is wrong",
        "i am an ai",
        "i am not real",
        "i don't actually exist",
    ]
    if any(t in lower for t in meta_triggers):
        return False, "meta-awareness violation — agent must not reference simulation layer"

    # Reject if it's essentially empty meaning
    if any(
        proposal.lower().strip() == stub.lower().strip()
        for stub in ["i should adapt.", "i should adjust.", "i should change."]
    ):
        return False, "proposal too generic — no concrete behavioral change"

    return True, ""


# ---------------------------------------------------------------------------
# Internal — DB Persistence
# ---------------------------------------------------------------------------


def _persist_dream(
    dream_id,
    soul_id,
    dreamed_at,
    sleep_cycles,
    memory_summary,
    proposal,
    accepted,
    rejection_reason,
    emotional_state,
):
    try:
        conn = _db(dict_cursor=False)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO dreams
                (dream_id, soul_id, world_id, dreamed_at, memory_summary,
                 mutation_proposal, mutation_accepted, rejection_reason,
                 emotional_state, sleep_cycles)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (dream_id) DO NOTHING
            """,
            (
                dream_id,
                soul_id,
                WORLD_ID,
                dreamed_at,
                memory_summary,
                proposal,
                accepted,
                rejection_reason or None,
                emotional_state,
                sleep_cycles,
            ),
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        log.error(f"_persist_dream DB error {soul_id[:8]}: {e}")


def _store_pending_mutation(soul_id: str, proposal: str):
    try:
        conn = _db(dict_cursor=False)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO sleep_states (soul_id, is_sleeping, pending_mutation, world_id, updated_at)
            VALUES (%s, false, %s, %s, %s)
            ON CONFLICT (soul_id) DO UPDATE SET
                pending_mutation = EXCLUDED.pending_mutation,
                updated_at       = EXCLUDED.updated_at
            """,
            (soul_id, proposal, WORLD_ID, int(time.time())),
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        log.error(f"_store_pending_mutation DB error {soul_id[:8]}: {e}")


def _wake_agent(soul_id: str):
    try:
        conn = _db(dict_cursor=False)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO sleep_states
                (soul_id, is_sleeping, sleep_until_ts, rest_debt,
                 consecutive_active, world_id, updated_at)
            VALUES (%s, false, NULL, 0, 0, %s, %s)
            ON CONFLICT (soul_id) DO UPDATE SET
                is_sleeping        = false,
                sleep_until_ts     = NULL,
                rest_debt          = 0,
                consecutive_active = 0,
                updated_at         = EXCLUDED.updated_at
            """,
            (soul_id, WORLD_ID, int(time.time())),
        )
        conn.commit()
        cur.close()
        conn.close()
        log.debug(f"_wake_agent: {soul_id[:8]} marked awake")
    except Exception as e:
        log.error(f"_wake_agent DB error {soul_id[:8]}: {e}")
