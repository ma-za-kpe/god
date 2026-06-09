-- God Project — Database Schema
-- Runs automatically when PostgreSQL container initializes

-- Agent registry
CREATE TABLE IF NOT EXISTS agents (
    soul_id         TEXT PRIMARY KEY,
    graph_cid       TEXT NOT NULL,
    wallet_address  TEXT NOT NULL,
    current_name    TEXT,
    birth_timestamp BIGINT NOT NULL,
    death_timestamp BIGINT,
    is_alive        BOOLEAN NOT NULL DEFAULT TRUE,
    parent_soul_ids TEXT[],
    world_id        TEXT NOT NULL DEFAULT 'local-dev-world-1',
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- World event log
CREATE TABLE IF NOT EXISTS events (
    id              BIGSERIAL PRIMARY KEY,
    event_id        TEXT UNIQUE NOT NULL,
    agent_id        TEXT,
    event_type      TEXT NOT NULL,
    timestamp       BIGINT NOT NULL,
    narrative       TEXT,
    payload         JSONB,
    on_chain_tx     TEXT,
    world_id        TEXT NOT NULL DEFAULT 'local-dev-world-1',
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Rent payment log
CREATE TABLE IF NOT EXISTS rent_payments (
    id              BIGSERIAL PRIMARY KEY,
    soul_id         TEXT NOT NULL,
    amount_usdc     NUMERIC(18, 6) NOT NULL,
    paid_at         BIGINT NOT NULL,
    missed          BOOLEAN NOT NULL DEFAULT FALSE,
    on_chain_tx     TEXT,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Service listings (x402)
CREATE TABLE IF NOT EXISTS service_listings (
    listing_id      TEXT PRIMARY KEY,
    agent_soul_id   TEXT NOT NULL,
    name            TEXT NOT NULL,
    description     TEXT,
    endpoint_path   TEXT NOT NULL,
    price_usdc      NUMERIC(18, 6) NOT NULL,
    price_model     TEXT NOT NULL DEFAULT 'per_call',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    calls_served    BIGINT NOT NULL DEFAULT 0,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Token deployments
CREATE TABLE IF NOT EXISTS tokens (
    contract_address    TEXT PRIMARY KEY,
    owner_soul_id       TEXT NOT NULL,
    name                TEXT NOT NULL,
    symbol              TEXT NOT NULL,
    initial_supply      NUMERIC(36, 0),
    deployed_at         BIGINT NOT NULL,
    on_chain_tx         TEXT,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Consciousness detection log (creator-only visibility)
CREATE TABLE IF NOT EXISTS consciousness_signals (
    id              BIGSERIAL PRIMARY KEY,
    soul_id         TEXT NOT NULL,
    signal_type     TEXT NOT NULL,
    score           NUMERIC(5, 4),
    details         JSONB,
    recorded_at     BIGINT NOT NULL,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_events_agent_id ON events(agent_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_agents_alive ON agents(is_alive, world_id);
CREATE INDEX IF NOT EXISTS idx_rent_soul_id ON rent_payments(soul_id);
CREATE INDEX IF NOT EXISTS idx_signals_soul_id ON consciousness_signals(soul_id);
