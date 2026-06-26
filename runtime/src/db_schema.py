"""
db_schema.py — Idempotent schema repair on runtime startup.

Fresh volumes use scripts/init-db.sql. Existing DBs (or partial init failures)
get missing columns/tables applied here so /stats, mutations, and capabilities work.
"""

from __future__ import annotations

import logging
import os

import psycopg2

log = logging.getLogger("god.schema")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://god:localdev@localhost:5432/god_world")
WORLD_ID = os.getenv("WORLD_ID", "local-dev-world-1")

_MIGRATIONS: list[str] = [
    """
    ALTER TABLE tokens
    ADD COLUMN IF NOT EXISTS world_id TEXT NOT NULL DEFAULT 'local-dev-world-1'
    """,
    """
    CREATE TABLE IF NOT EXISTS agent_scratch (
        soul_id         TEXT NOT NULL,
        scratch_key     TEXT NOT NULL,
        content         TEXT NOT NULL DEFAULT '',
        updated_at      BIGINT NOT NULL DEFAULT 0,
        world_id        TEXT NOT NULL DEFAULT 'local-dev-world-1',
        PRIMARY KEY (soul_id, scratch_key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS agent_action_log (
        id              BIGSERIAL PRIMARY KEY,
        soul_id         TEXT NOT NULL,
        action_type     TEXT NOT NULL,
        payload         JSONB NOT NULL DEFAULT '{}',
        result          JSONB NOT NULL DEFAULT '{}',
        success         BOOLEAN NOT NULL DEFAULT true,
        ts              BIGINT NOT NULL,
        world_id        TEXT NOT NULL DEFAULT 'local-dev-world-1'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS agent_scheduled_jobs (
        job_id          TEXT PRIMARY KEY,
        soul_id         TEXT NOT NULL,
        job_type        TEXT NOT NULL,
        payload         JSONB NOT NULL DEFAULT '{}',
        run_at          BIGINT NOT NULL,
        status          TEXT NOT NULL DEFAULT 'pending',
        created_at      BIGINT NOT NULL,
        completed_at    BIGINT,
        world_id        TEXT NOT NULL DEFAULT 'local-dev-world-1'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS agent_registered_tools (
        tool_id         TEXT PRIMARY KEY,
        owner_soul_id   TEXT NOT NULL,
        name            TEXT NOT NULL,
        description     TEXT NOT NULL DEFAULT '',
        handler_type    TEXT NOT NULL DEFAULT 'local',
        input_schema    JSONB NOT NULL DEFAULT '{}',
        cost_usdc       NUMERIC(18,6) NOT NULL DEFAULT 0.001 CHECK (cost_usdc > 0),
        calls_served    BIGINT NOT NULL DEFAULT 0,
        is_active       BOOLEAN NOT NULL DEFAULT true,
        created_at      BIGINT NOT NULL,
        world_id        TEXT NOT NULL DEFAULT 'local-dev-world-1'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS resilience_snapshots (
        snapshot_id     BIGSERIAL PRIMARY KEY,
        world_id        TEXT NOT NULL DEFAULT 'local-dev-world-1',
        created_at      BIGINT NOT NULL,
        snapshot        JSONB NOT NULL DEFAULT '{}'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS twitch_event_replays (
        replay_key      TEXT PRIMARY KEY,
        event_id        TEXT NOT NULL,
        event_type      TEXT NOT NULL,
        created_at      BIGINT NOT NULL,
        world_id        TEXT NOT NULL DEFAULT 'local-dev-world-1'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS agent_graph_mutations (
        mutation_id     TEXT PRIMARY KEY,
        soul_id         TEXT NOT NULL,
        mutation_type   TEXT NOT NULL,
        payload         JSONB NOT NULL DEFAULT '{}',
        status          TEXT NOT NULL DEFAULT 'pending',
        created_at      BIGINT NOT NULL,
        applied_at      BIGINT,
        world_id        TEXT NOT NULL DEFAULT 'local-dev-world-1'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS agent_capability_grants (
        soul_id         TEXT NOT NULL,
        capability_id   TEXT NOT NULL,
        granted_at      BIGINT NOT NULL,
        granted_via     TEXT NOT NULL DEFAULT 'tier',
        world_id        TEXT NOT NULL DEFAULT 'local-dev-world-1',
        PRIMARY KEY (soul_id, capability_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_tokens_owner ON tokens(owner_soul_id, world_id)",
    "CREATE INDEX IF NOT EXISTS idx_tokens_world ON tokens(world_id, deployed_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_events_world_timestamp ON events(world_id, timestamp DESC)",
    "CREATE INDEX IF NOT EXISTS idx_events_agent_type_ts ON events(agent_id, event_type, timestamp DESC)",
    "CREATE INDEX IF NOT EXISTS idx_agents_world_alive_birth ON agents(world_id, is_alive, birth_timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_messages_world_sent_at ON agent_messages(world_id, sent_at DESC)",
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = 'agent_registered_tools_cost_positive'
        ) THEN
            ALTER TABLE agent_registered_tools
              ADD CONSTRAINT agent_registered_tools_cost_positive CHECK (cost_usdc > 0);
        END IF;
    END $$;
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_ext_payments_x402_tx
        ON external_payments(tx_hash)
        WHERE source_type = 'x402'
          AND tx_hash IS NOT NULL
          AND tx_hash != ''
          AND tx_hash != '0x0000000000000000000000000000000000000000000000000000000000000000'
    """,
    "CREATE INDEX IF NOT EXISTS idx_action_log_soul ON agent_action_log(soul_id, ts DESC)",
    "CREATE INDEX IF NOT EXISTS idx_jobs_due ON agent_scheduled_jobs(run_at, status)",
    "CREATE INDEX IF NOT EXISTS idx_jobs_soul ON agent_scheduled_jobs(soul_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_reg_tools_owner ON agent_registered_tools(owner_soul_id, is_active)",
    "CREATE INDEX IF NOT EXISTS idx_graph_mut_soul ON agent_graph_mutations(soul_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_resilience_world_created ON resilience_snapshots(world_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_twitch_replays_world_created ON twitch_event_replays(world_id, created_at DESC)",
    # ── Banter Engine: Relationship Memory ──────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS relationship_pairs (
        pair_id                 TEXT PRIMARY KEY,
        elder_a                 TEXT NOT NULL,
        elder_b                 TEXT NOT NULL,
        tension_level           INTEGER DEFAULT 0 CHECK (tension_level >= 0 AND tension_level <= 10),
        last_interaction_ts     BIGINT DEFAULT 0,
        reconciliation_arc      BOOLEAN DEFAULT FALSE,
        reconciliation_remaining INTEGER DEFAULT 0,
        peak_tension_summary    TEXT DEFAULT '',
        created_at              BIGINT DEFAULT (EXTRACT(EPOCH FROM NOW())::BIGINT),
        updated_at              BIGINT DEFAULT (EXTRACT(EPOCH FROM NOW())::BIGINT)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS interaction_records (
        id                  SERIAL PRIMARY KEY,
        pair_id             TEXT REFERENCES relationship_pairs(pair_id),
        timestamp           BIGINT NOT NULL,
        elder_acting        TEXT NOT NULL,
        move_used           TEXT NOT NULL,
        emotional_valence   TEXT CHECK (emotional_valence IN ('positive', 'negative', 'neutral')),
        betrayal            BOOLEAN DEFAULT FALSE,
        alliance            BOOLEAN DEFAULT FALSE,
        concession          BOOLEAN DEFAULT FALSE,
        summary             TEXT DEFAULT ''
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_interaction_pair_ts ON interaction_records(pair_id, timestamp DESC)",
    """
    CREATE INDEX IF NOT EXISTS idx_interaction_significant
        ON interaction_records(pair_id, timestamp DESC)
        WHERE emotional_valence != 'neutral' OR betrayal OR alliance OR concession
    """,
    # Avatar genesis: direct CID columns so the /agents API can return them
    "ALTER TABLE agents ADD COLUMN IF NOT EXISTS avatar_cid TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE agents ADD COLUMN IF NOT EXISTS rigged_avatar_cid TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE agents ADD COLUMN IF NOT EXISTS vrm_avatar_url TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE agents ADD COLUMN IF NOT EXISTS voice_model_cid TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE agents ADD COLUMN IF NOT EXISTS avatar_style_prompt TEXT NOT NULL DEFAULT ''",
]


def ensure_schema() -> None:
    """Apply idempotent migrations. Safe on every startup."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        cur = conn.cursor()
        for stmt in _MIGRATIONS:
            cur.execute(stmt)
        cur.close()
        conn.close()
        log.info("Database schema verified")
    except Exception as e:
        log.warning(f"Database schema migration failed: {e}")
