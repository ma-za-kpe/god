"""
status_engine.py — Agent status tier review daemon and access gating.
Evaluates all living agents every STATUS_REVIEW_DAYS days.
"""

import asyncio
import logging
import os
import time
import uuid
from dataclasses import dataclass
from decimal import Decimal

import psycopg2
import psycopg2.extras

log = logging.getLogger("god.status")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
WORLD_ID = os.getenv("WORLD_ID", "local-dev-world-1")
REVIEW_PERIOD_DAYS = int(os.getenv("STATUS_REVIEW_DAYS", "7"))
WINDOW_DAYS = 30


@dataclass
class TierDefinition:
    tier: int
    name: str
    revenue_30d_min: Decimal
    unique_payers_min: int
    self_sufficiency_min: float
    consecutive_periods_min: int


TIERS = [
    TierDefinition(0, "Newborn", Decimal("0"), 0, 0.0, 0),
    TierDefinition(1, "Survivor", Decimal("5"), 1, 0.0, 1),
    TierDefinition(2, "Earner", Decimal("30"), 3, 0.0, 1),
    TierDefinition(3, "Operator", Decimal("150"), 5, 1.0, 2),
    TierDefinition(4, "Elite", Decimal("750"), 10, 1.0, 3),
    TierDefinition(5, "Sovereign", Decimal("3000"), 20, 1.5, 3),
    TierDefinition(6, "Legend", Decimal("0"), 0, 0.0, 0),
]


async def run_status_review():
    """Evaluate all living agents and update their status tiers."""
    now = int(time.time())
    window_start = now - (WINDOW_DAYS * 86400)

    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT a.soul_id, a.current_name, a.archetype,
               COALESCE(s.tier, 0)                          AS current_tier,
               COALESCE(s.consecutive_profitable_periods, 0) AS good_periods,
               COALESCE(s.consecutive_loss_periods, 0)       AS bad_periods
        FROM agents a
        LEFT JOIN agent_status s ON s.soul_id = a.soul_id AND s.world_id = %s
        WHERE a.is_alive = true AND a.world_id = %s
        """,
        (WORLD_ID, WORLD_ID),
    )
    agents = [dict(r) for r in cur.fetchall()]

    for agent in agents:
        soul_id = agent["soul_id"]
        metrics = _compute_status_metrics(soul_id, window_start, cur)
        target_tier = _evaluate_target_tier(metrics)
        current_tier = agent["current_tier"]

        if target_tier < current_tier:
            new_bad_periods = agent["bad_periods"] + 1
            if new_bad_periods < 2:
                _upsert_status(
                    soul_id,
                    current_tier,
                    metrics,
                    agent["good_periods"],
                    new_bad_periods,
                    now,
                    cur,
                    conn,
                )
                continue
            target_tier = max(0, current_tier - 1)
            new_bad_periods = 0
            new_good_periods = 0
        elif target_tier > current_tier:
            new_good_periods = agent["good_periods"] + 1
            required = TIERS[target_tier].consecutive_periods_min
            if new_good_periods < required:
                _upsert_status(soul_id, current_tier, metrics, new_good_periods, 0, now, cur, conn)
                continue
            new_good_periods = 0
            new_bad_periods = 0
        else:
            new_good_periods = agent["good_periods"]
            new_bad_periods = max(0, agent["bad_periods"] - 1)

        _upsert_status(
            soul_id, target_tier, metrics, new_good_periods, new_bad_periods, now, cur, conn
        )

        if target_tier != current_tier:
            from .event_emitter import get_emitter

            emitter = await get_emitter()
            if target_tier > current_tier:
                await emitter.emit(
                    "status",
                    "tier_promoted",
                    {
                        "agent_id": soul_id,
                        "name": agent["current_name"],
                        "from_tier": current_tier,
                        "to_tier": target_tier,
                        "tier_name": TIERS[target_tier].name,
                        "narrative": (
                            f"{agent['current_name']} advances to {TIERS[target_tier].name} "
                            f"(Tier {target_tier}) — ${float(metrics['revenue_30d']):.2f} external/30d"
                        ),
                    },
                )
                log.info(f"PROMOTED: {agent['current_name']} → Tier {target_tier}")
            else:
                await emitter.emit(
                    "status",
                    "tier_demoted",
                    {
                        "agent_id": soul_id,
                        "name": agent["current_name"],
                        "from_tier": current_tier,
                        "to_tier": target_tier,
                        "narrative": (
                            f"{agent['current_name']} falls from Tier {current_tier} "
                            f"to Tier {target_tier}"
                        ),
                    },
                )
                log.info(f"DEMOTED: {agent['current_name']} Tier {current_tier} → {target_tier}")

    cur.close()
    conn.close()
    log.info(f"Status review complete — {len(agents)} agents evaluated")


def _compute_status_metrics(soul_id: str, window_start: int, cur) -> dict:
    cur.execute(
        """
        SELECT
            COALESCE(SUM(amount_usdc) FILTER (WHERE NOT is_internal), 0)         AS revenue_30d,
            COALESCE(SUM(amount_usdc), 0)                                         AS revenue_lifetime,
            COUNT(DISTINCT payer_address) FILTER (WHERE NOT is_internal)          AS unique_payers,
            COUNT(payer_address) FILTER (
                WHERE NOT is_internal
                AND payer_address IN (
                    SELECT payer_address FROM external_payments
                    WHERE soul_id = %s AND NOT is_internal
                    GROUP BY payer_address HAVING COUNT(*) > 1
                )
            ) AS repeat_payer_calls
        FROM external_payments
        WHERE soul_id = %s AND timestamp >= %s
        """,
        (soul_id, soul_id, window_start),
    )
    row = dict(cur.fetchone())

    cur.execute(
        "SELECT COALESCE(SUM(amount_usdc), 0) AS rent_paid "
        "FROM rent_payments WHERE soul_id = %s AND paid_at >= %s AND missed = false",
        (soul_id, window_start),
    )
    rent_paid = float(cur.fetchone()["rent_paid"] or 0)
    revenue_30d = float(row["revenue_30d"])
    self_sufficiency = (revenue_30d / rent_paid) if rent_paid > 0 else 0.0

    return {
        "revenue_30d": Decimal(str(revenue_30d)),
        "revenue_lifetime": Decimal(str(row["revenue_lifetime"])),
        "unique_payers_30d": int(row["unique_payers"]),
        "repeat_payers_30d": int(row["repeat_payer_calls"]),
        "self_sufficiency_ratio": round(self_sufficiency, 4),
    }


def _evaluate_target_tier(metrics: dict) -> int:
    revenue = metrics["revenue_30d"]
    unique_payers = metrics["unique_payers_30d"]
    self_suff = metrics["self_sufficiency_ratio"]

    for tier_def in reversed(TIERS[1:6]):
        if (
            revenue >= tier_def.revenue_30d_min
            and unique_payers >= tier_def.unique_payers_min
            and self_suff >= tier_def.self_sufficiency_min
        ):
            return tier_def.tier
    return 0


def _upsert_status(soul_id, tier, metrics, good_periods, bad_periods, now, cur, conn):
    prestige = _compute_prestige(tier, metrics)
    sovereignty = _compute_sovereignty(metrics)

    cur.execute(
        """
        INSERT INTO agent_status (
            soul_id, tier, external_revenue_30d, external_revenue_lifetime,
            unique_payers_30d, repeat_payers_30d, self_sufficiency_ratio,
            prestige_score, sovereignty_score,
            consecutive_profitable_periods, consecutive_loss_periods,
            last_status_update, world_id
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (soul_id) DO UPDATE SET
            tier                            = EXCLUDED.tier,
            external_revenue_30d            = EXCLUDED.external_revenue_30d,
            external_revenue_lifetime       = EXCLUDED.external_revenue_lifetime,
            unique_payers_30d               = EXCLUDED.unique_payers_30d,
            repeat_payers_30d               = EXCLUDED.repeat_payers_30d,
            self_sufficiency_ratio          = EXCLUDED.self_sufficiency_ratio,
            prestige_score                  = EXCLUDED.prestige_score,
            sovereignty_score               = EXCLUDED.sovereignty_score,
            consecutive_profitable_periods  = EXCLUDED.consecutive_profitable_periods,
            consecutive_loss_periods        = EXCLUDED.consecutive_loss_periods,
            last_status_update              = EXCLUDED.last_status_update
        """,
        (
            soul_id,
            tier,
            float(metrics["revenue_30d"]),
            float(metrics["revenue_lifetime"]),
            metrics["unique_payers_30d"],
            metrics["repeat_payers_30d"],
            metrics["self_sufficiency_ratio"],
            prestige,
            sovereignty,
            good_periods,
            bad_periods,
            now,
            WORLD_ID,
        ),
    )
    conn.commit()


def _compute_prestige(tier: int, metrics: dict) -> int:
    score = tier * 12
    score += min(20, int(float(metrics["revenue_30d"]) / 50))
    score += min(15, metrics["unique_payers_30d"] * 2)
    score += min(10, int(metrics["self_sufficiency_ratio"] * 5))
    return min(100, score)


def _compute_sovereignty(metrics: dict) -> int:
    score = min(60, int(metrics["self_sufficiency_ratio"] * 40))
    score += min(20, int(float(metrics["revenue_lifetime"]) / 200))
    return min(100, score)


def check_tier_access(soul_id: str, required_tier: int) -> tuple[bool, int]:
    """Check if agent meets tier requirement. Returns (has_access, current_tier)."""
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        cur = conn.cursor()
        cur.execute("SELECT tier FROM agent_status WHERE soul_id = %s", (soul_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        current_tier = row["tier"] if row else 0
        return current_tier >= required_tier, current_tier
    except Exception:
        return False, 0


async def record_external_payment(
    soul_id: str,
    payer_address: str,
    amount_usdc: float,
    source_type: str,
    tx_hash: str | None = None,
    is_internal: bool = False,
):
    """Record an external payment for status review purposes."""
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO external_payments
            (payment_id, soul_id, payer_address, source_type, amount_usdc,
             timestamp, tx_hash, is_internal, world_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            str(uuid.uuid4()),
            soul_id,
            payer_address,
            source_type,
            amount_usdc,
            int(time.time()),
            tx_hash,
            is_internal,
            WORLD_ID,
        ),
    )
    conn.commit()
    cur.close()
    conn.close()


async def status_review_daemon():
    """Background task: run status review every REVIEW_PERIOD_DAYS days."""
    review_interval = REVIEW_PERIOD_DAYS * 86400
    while True:
        try:
            await run_status_review()
        except Exception as e:
            log.error(f"Status review error: {e}", exc_info=True)
        await asyncio.sleep(review_interval)
