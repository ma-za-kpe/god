-- Migration: Callback Registry tables for Soul Engine
-- Adds persistent storage for memorable moments, running gags, and sore spots.
-- Uses the same schema/pool as Relationship_Memory (003).
-- Safe to run multiple times (idempotent via IF NOT EXISTS).

-- ============================================================
-- Memorable moments (high-scoring lines stored for future callback)
-- ============================================================
CREATE TABLE IF NOT EXISTS callback_moments (
    id              SERIAL PRIMARY KEY,
    pair_id         VARCHAR(16) NOT NULL,
    speaker         VARCHAR(64) NOT NULL,
    target          VARCHAR(64) NOT NULL,
    line            TEXT NOT NULL,
    move            VARCHAR(32) NOT NULL,
    arc_theme       VARCHAR(128) NOT NULL,
    valence         VARCHAR(16) NOT NULL,
    summary         VARCHAR(256) NOT NULL,
    score           INTEGER NOT NULL,
    beat_number     INTEGER NOT NULL,
    created_at      BIGINT NOT NULL
);

-- ============================================================
-- Running gags (recurring patterns between Elder pairs)
-- ============================================================
CREATE TABLE IF NOT EXISTS callback_running_gags (
    id                  SERIAL PRIMARY KEY,
    pair_id             VARCHAR(16) NOT NULL,
    pattern_description TEXT NOT NULL,
    topic               VARCHAR(128) NOT NULL,
    interaction_count   INTEGER NOT NULL DEFAULT 0,
    created_at          BIGINT NOT NULL
);

-- ============================================================
-- Sore spots (known vulnerabilities for targeted provocation)
-- ============================================================
CREATE TABLE IF NOT EXISTS callback_sore_spots (
    id              SERIAL PRIMARY KEY,
    elder_name      VARCHAR(64) NOT NULL,
    topic           VARCHAR(128) NOT NULL,
    trigger_phrase  TEXT,
    tension_delta   INTEGER NOT NULL,
    created_at      BIGINT NOT NULL
);

-- ============================================================
-- Indexes for efficient lookups
-- ============================================================

-- Fast lookup of moments by pair (newest first for eviction)
CREATE INDEX IF NOT EXISTS idx_callback_moments_pair
    ON callback_moments(pair_id, created_at DESC);

-- Fast lookup of moments by speaker
CREATE INDEX IF NOT EXISTS idx_callback_moments_speaker
    ON callback_moments(speaker);

-- Fast lookup of running gags by pair
CREATE INDEX IF NOT EXISTS idx_callback_gags_pair
    ON callback_running_gags(pair_id);

-- Fast lookup of sore spots by elder name
CREATE INDEX IF NOT EXISTS idx_callback_sore_spots_elder
    ON callback_sore_spots(elder_name);

-- Fast lookup of sore spots by elder and topic (for theme matching)
CREATE INDEX IF NOT EXISTS idx_callback_sore_spots_elder_topic
    ON callback_sore_spots(elder_name, topic);
