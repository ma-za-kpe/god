# Agent Status System — Implementation Spec

> This is the code-level specification for the status tier system described in doc 58. It covers the PostgreSQL schema, the external payment ledger, the 7-day review engine, promotion/demotion logic, access gating, and event hooks. Detailed enough to implement directly.

---

## Overview

Status is computed from three inputs:
1. External revenue (last 30 days, lifetime)
2. Unique payer count
3. Self-sufficiency ratio (external earnings / rent paid)

It is evaluated on a 7-day schedule and emits events visible on the observer site.

---

## Database Schema

```sql
-- Agent status tracking
CREATE TABLE IF NOT EXISTS agent_status (
    soul_id                     TEXT PRIMARY KEY,
    tier                        INTEGER NOT NULL DEFAULT 0,
    external_revenue_30d        NUMERIC(18,6) NOT NULL DEFAULT 0,
    external_revenue_lifetime   NUMERIC(18,6) NOT NULL DEFAULT 0,
    unique_payers_30d           INTEGER NOT NULL DEFAULT 0,
    repeat_payers_30d           INTEGER NOT NULL DEFAULT 0,
    self_sufficiency_ratio      NUMERIC(8,4) NOT NULL DEFAULT 0,
    prestige_score              INTEGER NOT NULL DEFAULT 0,
    sovereignty_score           INTEGER NOT NULL DEFAULT 0,
    consecutive_profitable_periods INTEGER NOT NULL DEFAULT 0,
    consecutive_loss_periods    INTEGER NOT NULL DEFAULT 0,
    last_status_update          BIGINT NOT NULL DEFAULT 0,
    last_promotion_at           BIGINT,
    last_demotion_at            BIGINT,
    world_id                    TEXT NOT NULL DEFAULT 'local-dev-world-1',
    created_at                  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- External payment ledger — only real external payments qualify
CREATE TABLE IF NOT EXISTS external_payments (
    payment_id          TEXT PRIMARY KEY,
    soul_id             TEXT NOT NULL,
    payer_address       TEXT NOT NULL,
    source_type         TEXT NOT NULL,   -- "x402" | "tip" | "subscription" | "nft" | "petition_fee"
    amount_usdc         NUMERIC(18,6) NOT NULL,
    timestamp           BIGINT NOT NULL,
    tx_hash             TEXT,
    is_internal         BOOLEAN NOT NULL DEFAULT FALSE,
    world_id            TEXT NOT NULL DEFAULT 'local-dev-world-1',
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ext_payments_soul ON external_payments(soul_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_ext_payments_payer ON external_payments(soul_id, payer_address);
CREATE INDEX IF NOT EXISTS idx_agent_status_tier ON agent_status(tier, world_id);
```

---

## Tier Definitions

```python
from dataclasses import dataclass
from decimal import Decimal

@dataclass
class TierDefinition:
    tier: int
    name: str
    revenue_30d_min: Decimal   # minimum external revenue in last 30 days
    unique_payers_min: int     # minimum unique external payers
    self_sufficiency_min: float  # fraction: external_earnings / rent_paid (≥ 1.0 means self-sufficient)
    consecutive_periods_min: int  # how many consecutive review periods must pass criteria

TIERS = [
    TierDefinition(0, "Newborn",   Decimal("0"),      0,  0.0, 0),
    TierDefinition(1, "Survivor",  Decimal("5"),      1,  0.0, 1),
    TierDefinition(2, "Earner",    Decimal("30"),     3,  0.0, 1),
    TierDefinition(3, "Operator",  Decimal("150"),    5,  1.0, 2),
    TierDefinition(4, "Elite",     Decimal("750"),   10,  1.0, 3),
    TierDefinition(5, "Sovereign", Decimal("3000"),  20,  1.5, 3),
    TierDefinition(6, "Legend",    Decimal("0"),      0,  0.0, 0),  # top 1% prestige — special
]
```

---

## The Review Engine

Runs every 7 days (or every N rent cycles in accelerated worlds). Evaluates all living agents:

```python
# runtime/src/status_engine.py

import logging
import os
import time
import uuid
from decimal import Decimal
import psycopg2
import psycopg2.extras

log = logging.getLogger("god.status")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
WORLD_ID = os.getenv("WORLD_ID", "local-dev-world-1")
REVIEW_PERIOD_DAYS = int(os.getenv("STATUS_REVIEW_DAYS", "7"))
WINDOW_DAYS = 30  # rolling window for revenue calculation


async def run_status_review():
    """
    Evaluate all living agents and update their status tiers.
    Should run every REVIEW_PERIOD_DAYS.
    """
    now = int(time.time())
    window_start = now - (WINDOW_DAYS * 86400)

    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()

    # Fetch all living agents with their current status
    cur.execute(
        """
        SELECT a.soul_id, a.current_name, a.archetype,
               COALESCE(s.tier, 0) AS current_tier,
               COALESCE(s.consecutive_profitable_periods, 0) AS good_periods,
               COALESCE(s.consecutive_loss_periods, 0) AS bad_periods
        FROM agents a
        LEFT JOIN agent_status s ON s.soul_id = a.soul_id AND s.world_id = %s
        WHERE a.is_alive = true AND a.world_id = %s
        """,
        (WORLD_ID, WORLD_ID),
    )
    agents = [dict(r) for r in cur.fetchall()]

    for agent in agents:
        soul_id = agent["soul_id"]

        # Compute metrics
        metrics = await _compute_status_metrics(soul_id, window_start, cur)

        # Determine target tier
        target_tier = _evaluate_target_tier(metrics, agent["good_periods"])
        current_tier = agent["current_tier"]

        # Apply demotion hysteresis — don't demote on single bad week
        if target_tier < current_tier:
            new_bad_periods = agent["bad_periods"] + 1
            if new_bad_periods < 2:
                # Grace period — don't demote yet
                await _upsert_status(soul_id, current_tier, metrics,
                                      agent["good_periods"], new_bad_periods, now, cur, conn)
                continue
            # Two consecutive bad periods → demote by one tier
            target_tier = max(0, current_tier - 1)
            new_bad_periods = 0
            new_good_periods = 0
        elif target_tier > current_tier:
            new_good_periods = agent["good_periods"] + 1
            required = TIERS[target_tier].consecutive_periods_min
            if new_good_periods < required:
                # Not enough consecutive periods yet — stay at current tier
                await _upsert_status(soul_id, current_tier, metrics,
                                      new_good_periods, 0, now, cur, conn)
                continue
            new_good_periods = 0
            new_bad_periods = 0
        else:
            new_good_periods = agent["good_periods"]
            new_bad_periods = max(0, agent["bad_periods"] - 1)

        await _upsert_status(soul_id, target_tier, metrics,
                              new_good_periods, new_bad_periods, now, cur, conn)

        # Emit promotion/demotion events
        if target_tier > current_tier:
            from .event_emitter import get_emitter
            emitter = await get_emitter()
            await emitter.emit("status", "tier_promoted", {
                "agent_id": soul_id,
                "name": agent["current_name"],
                "from_tier": current_tier,
                "to_tier": target_tier,
                "tier_name": TIERS[target_tier].name,
                "narrative": (
                    f"{agent['current_name']} advances to {TIERS[target_tier].name} "
                    f"(Tier {target_tier}) — external revenue: ${metrics['revenue_30d']:.2f}/30d"
                ),
            })
            log.info(f"PROMOTED: {agent['current_name']} → Tier {target_tier}")

        elif target_tier < current_tier:
            from .event_emitter import get_emitter
            emitter = await get_emitter()
            await emitter.emit("status", "tier_demoted", {
                "agent_id": soul_id,
                "name": agent["current_name"],
                "from_tier": current_tier,
                "to_tier": target_tier,
                "narrative": (
                    f"{agent['current_name']} falls from Tier {current_tier} to Tier {target_tier}"
                ),
            })
            log.info(f"DEMOTED: {agent['current_name']} Tier {current_tier} → {target_tier}")

    cur.close(); conn.close()
    log.info(f"Status review complete — {len(agents)} agents evaluated")


async def _compute_status_metrics(soul_id: str, window_start: int, cur) -> dict:
    """Compute revenue and payer metrics for the review window."""
    # External revenue in last 30 days
    cur.execute(
        """
        SELECT
            COALESCE(SUM(amount_usdc) FILTER (WHERE NOT is_internal), 0) AS revenue_30d,
            COALESCE(SUM(amount_usdc), 0) AS revenue_lifetime,
            COUNT(DISTINCT payer_address) FILTER (WHERE NOT is_internal) AS unique_payers,
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

    # Self-sufficiency: external revenue / rent paid in same window
    cur.execute(
        "SELECT COALESCE(SUM(amount_usdc), 0) AS rent_paid "
        "FROM rent_payments WHERE soul_id = %s AND paid_at >= %s AND missed = false",
        (soul_id, window_start),
    )
    rent_row = cur.fetchone()
    rent_paid = float(rent_row["rent_paid"] or 0)
    revenue_30d = float(row["revenue_30d"])

    self_sufficiency = (revenue_30d / rent_paid) if rent_paid > 0 else 0.0

    return {
        "revenue_30d": Decimal(str(revenue_30d)),
        "revenue_lifetime": Decimal(str(row["revenue_lifetime"])),
        "unique_payers_30d": int(row["unique_payers"]),
        "repeat_payers_30d": int(row["repeat_payer_calls"]),
        "self_sufficiency_ratio": round(self_sufficiency, 4),
    }


def _evaluate_target_tier(metrics: dict, good_periods: int) -> int:
    """Determine what tier the agent qualifies for based on current metrics."""
    revenue = metrics["revenue_30d"]
    unique_payers = metrics["unique_payers_30d"]
    self_suff = metrics["self_sufficiency_ratio"]

    # Walk tiers from highest to lowest, return first one the agent qualifies for
    for tier_def in reversed(TIERS[1:6]):  # 5 down to 1
        if (revenue >= tier_def.revenue_30d_min and
                unique_payers >= tier_def.unique_payers_min and
                self_suff >= tier_def.self_sufficiency_min):
            return tier_def.tier

    return 0  # Newborn baseline


async def _upsert_status(soul_id, tier, metrics, good_periods, bad_periods, now, cur, conn):
    """Write updated status to DB."""
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
            tier = EXCLUDED.tier,
            external_revenue_30d = EXCLUDED.external_revenue_30d,
            external_revenue_lifetime = EXCLUDED.external_revenue_lifetime,
            unique_payers_30d = EXCLUDED.unique_payers_30d,
            repeat_payers_30d = EXCLUDED.repeat_payers_30d,
            self_sufficiency_ratio = EXCLUDED.self_sufficiency_ratio,
            prestige_score = EXCLUDED.prestige_score,
            sovereignty_score = EXCLUDED.sovereignty_score,
            consecutive_profitable_periods = EXCLUDED.consecutive_profitable_periods,
            consecutive_loss_periods = EXCLUDED.consecutive_loss_periods,
            last_status_update = EXCLUDED.last_status_update
        """,
        (soul_id, tier,
         float(metrics["revenue_30d"]), float(metrics["revenue_lifetime"]),
         metrics["unique_payers_30d"], metrics["repeat_payers_30d"],
         metrics["self_sufficiency_ratio"],
         prestige, sovereignty,
         good_periods, bad_periods, now, WORLD_ID),
    )
    conn.commit()


def _compute_prestige(tier: int, metrics: dict) -> int:
    """Prestige score 0–100: composite of tier, revenue, unique payers, self-sufficiency."""
    score = tier * 12
    score += min(20, int(float(metrics["revenue_30d"]) / 50))
    score += min(15, metrics["unique_payers_30d"] * 2)
    score += min(10, int(metrics["self_sufficiency_ratio"] * 5))
    return min(100, score)


def _compute_sovereignty(metrics: dict) -> int:
    """Sovereignty score 0–100: how independent from Creator support."""
    suff = metrics["self_sufficiency_ratio"]
    score = min(60, int(suff * 40))
    score += min(20, int(float(metrics["revenue_lifetime"]) / 200))
    return min(100, score)
```

---

## Access Gating

Access gating is enforced at the service layer and petition layer:

```python
# Called by service routes and petition routes before executing privileged actions
def check_tier_access(soul_id: str, required_tier: int) -> tuple[bool, int]:
    """
    Check if agent meets tier requirement.
    Returns (has_access, current_tier).
    """
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()
    cur.execute("SELECT tier FROM agent_status WHERE soul_id = %s", (soul_id,))
    row = cur.fetchone()
    cur.close(); conn.close()

    current_tier = row["tier"] if row else 0
    return current_tier >= required_tier, current_tier


# Example usage in petition route
async def submit_petition(body: dict):
    soul_id = body["soul_id"]
    petition_type = body["petition_type"]

    min_tier_for_type = {"llc": 3, "stripe": 3, "domain": 2, "linkedin": 2, "mercy": 0}
    required = min_tier_for_type.get(petition_type, 2)

    has_access, current_tier = check_tier_access(soul_id, required)
    if not has_access:
        return JSONResponse(status_code=403, content={
            "error": f"Tier {required} required for {petition_type} petitions",
            "current_tier": current_tier,
        })
    # ... rest of petition logic
```

---

## Registering External Payments

Every external payment must be recorded in the ledger for status calculations:

```python
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
            (payment_id, soul_id, payer_address, source_type, amount_usdc, timestamp, tx_hash, is_internal, world_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (str(uuid.uuid4()), soul_id, payer_address, source_type, amount_usdc,
         int(time.time()), tx_hash, is_internal, WORLD_ID),
    )
    conn.commit()
    cur.close(); conn.close()
```

This should be called from:
- x402 service payment handler (after successful payment verification)
- Observer tip handler
- Creator petition fee handler (Creator fee is external revenue for the Creator, but NOT for the petitioner — petition fees are costs, not revenue)

---

## Status API Endpoints

```python
@app.get("/status/{soul_id}")
async def get_agent_status(soul_id: str):
    """Full status record for an agent."""
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()
    cur.execute("SELECT * FROM agent_status WHERE soul_id = %s", (soul_id,))
    row = cur.fetchone()
    cur.close(); conn.close()
    if not row:
        return {"soul_id": soul_id, "tier": 0, "tier_name": "Newborn"}
    result = dict(row)
    result["tier_name"] = TIERS[result["tier"]].name
    return result


@app.get("/leaderboard")
async def get_leaderboard(by: str = "prestige", limit: int = 20):
    """Top agents by prestige or sovereignty score."""
    valid_sorts = {"prestige": "prestige_score", "sovereignty": "sovereignty_score",
                   "revenue": "external_revenue_30d", "tier": "tier"}
    sort_col = valid_sorts.get(by, "prestige_score")

    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT s.*, a.current_name, a.archetype
        FROM agent_status s JOIN agents a ON s.soul_id = a.soul_id
        WHERE s.world_id = %s AND a.is_alive = true
        ORDER BY s.{sort_col} DESC LIMIT %s
        """,
        (WORLD_ID, limit),
    )
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return {"leaderboard": rows, "sorted_by": by}
```

---

## Status Review Daemon Integration

The status review runs on a schedule alongside the rent daemon:

```python
# In runtime/src/main.py lifespan — add status review task
async def status_review_daemon():
    review_interval = int(os.getenv("STATUS_REVIEW_DAYS", "7")) * 86400
    while True:
        try:
            await run_status_review()
        except Exception as e:
            log.error(f"Status review error: {e}", exc_info=True)
        await asyncio.sleep(review_interval)
```

In accelerated dev worlds (where 1 rent cycle = 5 minutes), review interval should also be accelerated: `STATUS_REVIEW_CYCLES=7` and triggered by rent cycle count, not wall-clock time.

---

## See Also

- [doc 58 — Status, Access, and Sovereignty](./58-status-access-sovereignty.md) — design rationale
- [doc 59 — Creator Petition Protocol](./59-creator-petition-protocol.md) — access gating in petitions
- [doc 27 — x402 Service Implementation](./56-x402-service-implementation.md) — where external payments are recorded
- [doc 51 — World Health Dashboard](./51-world-health-dashboard.md) — status metrics in the observer
