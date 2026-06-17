-- Migration: Relationship Memory tables for Banter Engine
-- Extends the existing episodes schema with pairwise relationship tracking.
-- Safe to run multiple times (idempotent via IF NOT EXISTS).

-- ============================================================
-- Relationship pair state (one row per unique elder pair)
-- ============================================================
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
);

-- ============================================================
-- Interaction records (append-only log per pair)
-- ============================================================
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
);

-- ============================================================
-- Indexes for efficient lookups
-- ============================================================

-- Fast lookup of recent interactions for a pair (newest first)
CREATE INDEX IF NOT EXISTS idx_interaction_pair_ts
    ON interaction_records(pair_id, timestamp DESC);

-- Fast lookup of significant interactions (non-neutral or high-stakes events)
CREATE INDEX IF NOT EXISTS idx_interaction_significant
    ON interaction_records(pair_id, timestamp DESC)
    WHERE emotional_valence != 'neutral' OR betrayal OR alliance OR concession;
