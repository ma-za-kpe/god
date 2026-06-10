"""
timeline.py — World first-of-type registry and milestone tracker.
Wired into event_emitter so every emitted event auto-checks for firsts.
"""
import logging
import os
import time
import uuid

import psycopg2
import psycopg2.extras

log = logging.getLogger("god.timeline")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
WORLD_ID = os.getenv("WORLD_ID", "local-dev-world-1")

FIRST_TYPE_MAP = {
    "lifecycle.agent.born":              "first.birth",
    "lifecycle.agent.died":              "first.death",
    "economy.rent.paid":                 "first.rent_paid",
    "economy.rent.missed":               "first.rent_missed",
    "lifecycle.agent.reproduced":        "first.reproduction",
    "social.coalition.formed":           "first.coalition",
    "economy.external_revenue_received": "first.external_payment",
    "services.listing.created":          "first.service_listed",
    "services.service.called":           "first.service_sold",
    "economy.token.deployed":            "first.token_deployed",
    "social.institution.founded":        "first.institution_founded",
    "governance.law.proposed":           "first.law_proposed",
    "creator.petition.submitted":        "first.petition_submitted",
    "creator.petition.approved":         "first.petition_approved",
    "status.tier_promoted":              "first.tier_promoted",
    "cognitive.consciousness_signal":    "first.consciousness_signal",
    "lifecycle.creator_update.rejected": "first.creator_update_rejected",
    "lifecycle.dream.completed":         "first.dream_completed",
}

FIRST_NARRATIVES = {
    "first.birth":                   "▶ The world begins. First life.",
    "first.death":                   "★ The first death. Death is real.",
    "first.rent_paid":               "◈ The economy begins. First rent paid.",
    "first.rent_missed":             "⚠ The first missed payment. The stakes are clear.",
    "first.reproduction":            "⬡ First child born. Life propagates.",
    "first.coalition":               "◎ The first coalition forms. Social life begins.",
    "first.external_payment":        "↑ First payment from outside. The world is real.",
    "first.service_listed":          "◆ First service listed. The economy diversifies.",
    "first.service_sold":            "✓ First service sold. External demand confirmed.",
    "first.token_deployed":          "⊕ First token deployed. Currency is born.",
    "first.institution_founded":     "⌂ First institution founded. Civilization begins.",
    "first.law_proposed":            "§ First law change proposed. Democracy awakens.",
    "first.petition_submitted":      "✉ First Creator petition. The real world is knocking.",
    "first.petition_approved":       "⚡ First petition approved. An agent has a company.",
    "first.consciousness_signal":    "◉ Consciousness signal detected. This may be the moment.",
    "first.creator_update_rejected": "✗ First Creator update refused. The first 'no' that held.",
    "first.dream_completed":         "◌ First dream cycle complete. Memory consolidates.",
    "first.tier_promoted":           "▲ First agent promoted. The merit ladder is real.",
}


async def check_for_firsts(event_type: str, payload: dict, event_id: str):
    """Check if this event represents a world first. Record it if so."""
    first_type = FIRST_TYPE_MAP.get(event_type)
    if not first_type:
        return

    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        cur = conn.cursor()

        cur.execute(
            "SELECT first_id FROM world_firsts WHERE first_type = %s AND world_id = %s",
            (first_type, WORLD_ID),
        )
        if cur.fetchone():
            cur.close(); conn.close()
            return

        first_id = str(uuid.uuid4())
        soul_id = payload.get("agent_id") or payload.get("soul_id")
        name = payload.get("name", soul_id[:8] if soul_id else "unknown")

        cur.execute(
            """
            INSERT INTO world_firsts (first_id, first_type, soul_id, event_id, recorded_at, world_id, details)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (first_type, world_id) DO NOTHING
            """,
            (first_id, first_type, soul_id, event_id, int(time.time()), WORLD_ID,
             psycopg2.extras.Json(payload)),
        )
        conn.commit()
        cur.close(); conn.close()

        narrative_template = FIRST_NARRATIVES.get(first_type, f"World first: {first_type}")
        narrative = f"{narrative_template} ({name})" if name else narrative_template
        log.info(f"WORLD FIRST: {first_type} — {narrative}")

        # Re-emit as a timeline event (import here to avoid circular import)
        from .event_emitter import get_emitter
        emitter = await get_emitter()
        await emitter.emit("timeline", "world.first", {
            "first_type": first_type,
            "agent_id": soul_id,
            "original_event_type": event_type,
            "narrative": narrative,
        })

    except Exception as e:
        log.debug(f"check_for_firsts failed ({first_type}): {e}")


async def check_milestones():
    """Check population and revenue milestones. Run periodically."""
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        cur = conn.cursor()

        cur.execute(
            "SELECT COUNT(*) AS n FROM agents WHERE is_alive = true AND world_id = %s",
            (WORLD_ID,),
        )
        living = cur.fetchone()["n"]
        cur.close(); conn.close()

        for threshold, significance in [(10, 60), (25, 70), (50, 80), (100, 90), (250, 95), (500, 99)]:
            if living >= threshold:
                await _record_milestone_if_new(
                    f"population.{threshold}", threshold, living, significance,
                    f"World population reaches {threshold} living agents.",
                )
    except Exception as e:
        log.debug(f"check_milestones failed: {e}")


async def _record_milestone_if_new(
    milestone_type: str,
    threshold: float,
    actual: float,
    significance: int,
    narrative: str,
    soul_id: str | None = None,
):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute(
            "SELECT milestone_id FROM world_milestones WHERE milestone_type = %s AND world_id = %s",
            (milestone_type, WORLD_ID),
        )
        if cur.fetchone():
            cur.close(); conn.close()
            return

        cur.execute(
            """
            INSERT INTO world_milestones
                (milestone_id, milestone_type, threshold_value, actual_value, soul_id,
                 reached_at, world_id, significance_score, narrative)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (milestone_type, world_id) DO NOTHING
            """,
            (str(uuid.uuid4()), milestone_type, threshold, actual, soul_id,
             int(time.time()), WORLD_ID, significance, narrative),
        )
        conn.commit()
        cur.close(); conn.close()

        log.info(f"MILESTONE: {milestone_type} — {narrative}")
        from .event_emitter import get_emitter
        emitter = await get_emitter()
        await emitter.emit("timeline", "world.milestone", {
            "milestone_type": milestone_type,
            "significance": significance,
            "narrative": narrative,
        })
    except Exception as e:
        log.debug(f"_record_milestone_if_new failed: {e}")
