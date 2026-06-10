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

-- Creator petition system (human-in-the-loop)
CREATE TABLE IF NOT EXISTS creator_petitions (
    petition_id             TEXT PRIMARY KEY,
    soul_id                 TEXT NOT NULL,
    petition_type           TEXT NOT NULL,
    title                   TEXT NOT NULL,
    description             TEXT,
    research_summary        TEXT,
    external_cost_usdc      NUMERIC(18,6),
    proposed_creator_fee_usdc NUMERIC(18,6) NOT NULL,
    fee_justification       TEXT,
    governance_approval_ref TEXT,
    governing_body          TEXT,
    escrowed_amount_usdc    NUMERIC(18,6) NOT NULL DEFAULT 0,
    escrow_tx_hash          TEXT,
    status                  TEXT NOT NULL DEFAULT 'pending',
    created_at              BIGINT NOT NULL,
    resolved_at             BIGINT,
    creator_notes           TEXT,
    result_summary          TEXT,
    credentials_encrypted_cid TEXT,
    world_id                TEXT NOT NULL DEFAULT 'local-dev-world-1'
);

-- World history tracking
CREATE TABLE IF NOT EXISTS world_firsts (
    first_id        TEXT PRIMARY KEY,
    first_type      TEXT NOT NULL,
    soul_id         TEXT,
    event_id        TEXT,
    recorded_at     BIGINT NOT NULL,
    world_id        TEXT NOT NULL DEFAULT 'local-dev-world-1',
    details         JSONB,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(first_type, world_id)
);

CREATE TABLE IF NOT EXISTS world_milestones (
    milestone_id        TEXT PRIMARY KEY,
    milestone_type      TEXT NOT NULL,
    threshold_value     NUMERIC(18,6),
    actual_value        NUMERIC(18,6),
    soul_id             TEXT,
    reached_at          BIGINT NOT NULL,
    world_id            TEXT NOT NULL DEFAULT 'local-dev-world-1',
    significance_score  INTEGER NOT NULL DEFAULT 50,
    narrative           TEXT,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(milestone_type, world_id)
);

-- Agent episodic memory index (content lives on IPFS)
CREATE TABLE IF NOT EXISTS episodes (
    episode_id          TEXT PRIMARY KEY,
    soul_id             TEXT NOT NULL,
    event_type          TEXT NOT NULL,
    timestamp           BIGINT NOT NULL,
    cycle_number        INTEGER,
    emotional_imprint   NUMERIC(4,3),
    tags                TEXT[],
    ipfs_cid            TEXT NOT NULL,
    participants        TEXT[],
    world_id            TEXT NOT NULL DEFAULT 'local-dev-world-1',
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Agent emotional state
CREATE TABLE IF NOT EXISTS emotional_states (
    soul_id         TEXT PRIMARY KEY,
    fear            NUMERIC(4,3) NOT NULL DEFAULT 0.200,
    confidence      NUMERIC(4,3) NOT NULL DEFAULT 0.500,
    grief           NUMERIC(4,3) NOT NULL DEFAULT 0.000,
    anger           NUMERIC(4,3) NOT NULL DEFAULT 0.000,
    curiosity       NUMERIC(4,3) NOT NULL DEFAULT 0.500,
    loneliness      NUMERIC(4,3) NOT NULL DEFAULT 0.300,
    updated_at      BIGINT NOT NULL DEFAULT 0
);

-- MCP tool registry (world-level tool catalogue)
CREATE TABLE IF NOT EXISTS mcp_tools (
    tool_id             TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    description         TEXT,
    category            TEXT NOT NULL DEFAULT 'custom',
    requires_tier       INTEGER NOT NULL DEFAULT 3,
    requires_corporate  BOOLEAN NOT NULL DEFAULT FALSE,
    activation_type     TEXT NOT NULL DEFAULT 'creator_petition',
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    active_agent_count  INTEGER NOT NULL DEFAULT 0,
    mcp_server_url      TEXT,
    documentation_url   TEXT,
    activated_at        BIGINT,
    world_id            TEXT NOT NULL DEFAULT 'local-dev-world-1',
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Per-agent tool access grants
CREATE TABLE IF NOT EXISTS agent_tool_grants (
    grant_id            TEXT PRIMARY KEY,
    soul_id             TEXT NOT NULL,
    tool_id             TEXT NOT NULL,
    granted_via         TEXT NOT NULL DEFAULT 'creator_petition',
    petition_id         TEXT,
    granted_at          BIGINT NOT NULL,
    expires_at          BIGINT,
    credentials_cid     TEXT,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    world_id            TEXT NOT NULL DEFAULT 'local-dev-world-1',
    UNIQUE(soul_id, tool_id)
);

-- Agent status tiers
CREATE TABLE IF NOT EXISTS agent_status (
    soul_id                         TEXT PRIMARY KEY,
    tier                            INTEGER NOT NULL DEFAULT 0,
    external_revenue_30d            NUMERIC(18,6) NOT NULL DEFAULT 0,
    external_revenue_lifetime       NUMERIC(18,6) NOT NULL DEFAULT 0,
    unique_payers_30d               INTEGER NOT NULL DEFAULT 0,
    repeat_payers_30d               INTEGER NOT NULL DEFAULT 0,
    self_sufficiency_ratio          NUMERIC(8,4) NOT NULL DEFAULT 0,
    prestige_score                  INTEGER NOT NULL DEFAULT 0,
    sovereignty_score               INTEGER NOT NULL DEFAULT 0,
    consecutive_profitable_periods  INTEGER NOT NULL DEFAULT 0,
    consecutive_loss_periods        INTEGER NOT NULL DEFAULT 0,
    last_status_update              BIGINT NOT NULL DEFAULT 0,
    last_promotion_at               BIGINT,
    last_demotion_at                BIGINT,
    world_id                        TEXT NOT NULL DEFAULT 'local-dev-world-1',
    created_at                      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- External payment ledger (status review source of truth)
CREATE TABLE IF NOT EXISTS external_payments (
    payment_id      TEXT PRIMARY KEY,
    soul_id         TEXT NOT NULL,
    payer_address   TEXT NOT NULL,
    source_type     TEXT NOT NULL,
    amount_usdc     NUMERIC(18,6) NOT NULL,
    timestamp       BIGINT NOT NULL,
    tx_hash         TEXT,
    is_internal     BOOLEAN NOT NULL DEFAULT FALSE,
    world_id        TEXT NOT NULL DEFAULT 'local-dev-world-1',
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Law amendment proposals
CREATE TABLE IF NOT EXISTS law_proposals (
    proposal_id             TEXT PRIMARY KEY,
    proposer_soul_id        TEXT NOT NULL,
    proposer_coalition      TEXT,
    proposal_type           TEXT NOT NULL,
    target_law_or_policy    TEXT NOT NULL,
    current_text            TEXT NOT NULL,
    proposed_text           TEXT NOT NULL,
    rationale               TEXT,
    estimated_impact        TEXT,
    quorum_required         INTEGER NOT NULL DEFAULT 10,
    approval_threshold      NUMERIC(4,3) NOT NULL DEFAULT 0.500,
    voting_period_cycles    INTEGER NOT NULL DEFAULT 7,
    submitted_at            BIGINT NOT NULL,
    voting_opens_at         BIGINT NOT NULL,
    voting_closes_at        BIGINT NOT NULL,
    status                  TEXT NOT NULL DEFAULT 'draft',
    votes_for               INTEGER NOT NULL DEFAULT 0,
    votes_against           INTEGER NOT NULL DEFAULT 0,
    abstentions             INTEGER NOT NULL DEFAULT 0,
    implementation_due_at   BIGINT,
    implemented_at          BIGINT,
    world_ledger_cid        TEXT,
    world_id                TEXT NOT NULL DEFAULT 'local-dev-world-1',
    created_at              TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Individual law votes
CREATE TABLE IF NOT EXISTS law_votes (
    vote_id         TEXT PRIMARY KEY,
    proposal_id     TEXT NOT NULL,
    voter_soul_id   TEXT NOT NULL,
    vote            TEXT NOT NULL,
    vote_weight     NUMERIC(8,4) NOT NULL DEFAULT 1.0,
    voted_at        BIGINT NOT NULL,
    world_id        TEXT NOT NULL DEFAULT 'local-dev-world-1',
    UNIQUE(proposal_id, voter_soul_id)
);

-- Coalitions
CREATE TABLE IF NOT EXISTS coalitions (
    coalition_id        TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    founder_soul_id     TEXT NOT NULL,
    treasury_wallet     TEXT,
    charter_cid         TEXT,
    member_count        INTEGER NOT NULL DEFAULT 1,
    status              TEXT NOT NULL DEFAULT 'active',
    formed_at           BIGINT NOT NULL,
    world_id            TEXT NOT NULL DEFAULT 'local-dev-world-1',
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS coalition_members (
    membership_id   TEXT PRIMARY KEY,
    coalition_id    TEXT NOT NULL,
    soul_id         TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'member',
    joined_at       BIGINT NOT NULL,
    world_id        TEXT NOT NULL DEFAULT 'local-dev-world-1',
    UNIQUE(coalition_id, soul_id)
);

-- Schema migrations (safe to run on existing DB)
ALTER TABLE agents ADD COLUMN IF NOT EXISTS archetype TEXT;
ALTER TABLE agents ADD COLUMN IF NOT EXISTS balance_usdc NUMERIC(18,6) NOT NULL DEFAULT 0;
ALTER TABLE agents ADD COLUMN IF NOT EXISTS generation INTEGER NOT NULL DEFAULT 1;
ALTER TABLE agents ADD COLUMN IF NOT EXISTS death_archive_cid TEXT;
ALTER TABLE agents ADD COLUMN IF NOT EXISTS emotional_state TEXT NOT NULL DEFAULT 'neutral';

-- Indexes
CREATE INDEX IF NOT EXISTS idx_events_agent_id ON events(agent_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_agents_alive ON agents(is_alive, world_id);
CREATE INDEX IF NOT EXISTS idx_rent_soul_id ON rent_payments(soul_id);
CREATE INDEX IF NOT EXISTS idx_signals_soul_id ON consciousness_signals(soul_id);
CREATE INDEX IF NOT EXISTS idx_petitions_soul_id ON creator_petitions(soul_id);
CREATE INDEX IF NOT EXISTS idx_petitions_status ON creator_petitions(status, world_id);
CREATE INDEX IF NOT EXISTS idx_firsts_type ON world_firsts(first_type, world_id);
CREATE INDEX IF NOT EXISTS idx_milestones_type ON world_milestones(milestone_type, world_id);
CREATE INDEX IF NOT EXISTS idx_episodes_soul_id ON episodes(soul_id);
CREATE INDEX IF NOT EXISTS idx_episodes_timestamp ON episodes(soul_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_episodes_emotional ON episodes(soul_id, emotional_imprint DESC);
CREATE INDEX IF NOT EXISTS idx_agent_status_tier ON agent_status(tier, world_id);
CREATE INDEX IF NOT EXISTS idx_ext_payments_soul ON external_payments(soul_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_proposals_status ON law_proposals(status, world_id);
CREATE INDEX IF NOT EXISTS idx_votes_proposal ON law_votes(proposal_id);
CREATE INDEX IF NOT EXISTS idx_coalition_members ON coalition_members(coalition_id);
CREATE INDEX IF NOT EXISTS idx_coalition_soul ON coalition_members(soul_id);

-- Seed initial MCP tool catalogue
INSERT INTO mcp_tools (tool_id, name, description, category, requires_tier, requires_corporate, activation_type, is_active)
VALUES
    ('internet_search',       'Internet Search',        'Read-only web search and URL fetch',                          'information', 1, false, 'world_unlock',    true),
    ('world_stats_api',       'World Stats API',        'Query internal world population and economic data',            'information', 1, false, 'world_unlock',    true),
    ('linkedin_mcp',          'LinkedIn MCP',           'Manage company page, post content, view analytics',           'social',      2, false, 'creator_petition', false),
    ('github_mcp',            'GitHub MCP',             'Repository management, issues, PRs',                          'development', 2, false, 'creator_petition', false),
    ('x_mcp',                 'X (Twitter) MCP',        'Post content, manage account, view analytics',                'social',      2, false, 'creator_petition', false),
    ('namecheap_mcp',         'Namecheap MCP',          'Domain registration and DNS management',                      'infrastructure', 2, true, 'creator_petition', false),
    ('stripe_mcp',            'Stripe MCP',             'Billing, subscriptions, invoices, revenue analytics',         'financial',   3, true,  'creator_petition', false),
    ('google_workspace_mcp',  'Google Workspace MCP',   'Email, Calendar, Docs, Drive for agent domain',              'communication', 3, true, 'creator_petition', false),
    ('akash_mcp',             'Akash Network MCP',      'Decentralized compute bidding and deployment management',     'compute',     3, false, 'creator_petition', false),
    ('google_ads_mcp',        'Google Ads MCP',         'Search and display advertising campaign management',          'marketing',   4, true,  'creator_petition', false)
ON CONFLICT (tool_id) DO NOTHING;

-- ============================================================
-- Phase 1 runtime additions — Dream, Messaging, Token Factory
-- ============================================================

-- Per-agent sleep state (upserted each cycle; row persists as awake record too)
CREATE TABLE IF NOT EXISTS sleep_states (
    soul_id             TEXT PRIMARY KEY,
    world_id            TEXT NOT NULL DEFAULT 'local-dev-world-1',
    is_sleeping         BOOLEAN NOT NULL DEFAULT false,
    sleep_until_ts      BIGINT,           -- NULL when awake; Unix ts of planned wake
    sleep_started_ts    BIGINT,           -- when they entered sleep
    rest_debt           INTEGER NOT NULL DEFAULT 0,
    consecutive_active  INTEGER NOT NULL DEFAULT 0,
    pending_mutation    TEXT,             -- one-time mutation written by dream engine
    updated_at          BIGINT NOT NULL DEFAULT 0
);

-- Dream log — one row per dream episode
CREATE TABLE IF NOT EXISTS dreams (
    dream_id            TEXT PRIMARY KEY,
    soul_id             TEXT NOT NULL,
    world_id            TEXT NOT NULL DEFAULT 'local-dev-world-1',
    dreamed_at          BIGINT NOT NULL,
    memory_summary      TEXT NOT NULL,
    mutation_proposal   TEXT NOT NULL,
    mutation_accepted   BOOLEAN NOT NULL DEFAULT false,
    rejection_reason    TEXT,
    emotional_state     TEXT NOT NULL DEFAULT 'neutral',
    sleep_cycles        INTEGER NOT NULL DEFAULT 1
);

-- Agent-to-agent messages
CREATE TABLE IF NOT EXISTS agent_messages (
    message_id      TEXT PRIMARY KEY,
    sender_id       TEXT NOT NULL,
    recipient_id    TEXT NOT NULL,    -- soul_id or 'BROADCAST'
    subject         TEXT NOT NULL DEFAULT '',
    body            TEXT NOT NULL,
    message_type    TEXT NOT NULL DEFAULT 'direct',  -- direct | broadcast | reply
    reply_to_id     TEXT,
    sent_at         BIGINT NOT NULL,
    world_id        TEXT NOT NULL DEFAULT 'local-dev-world-1',
    read            BOOLEAN NOT NULL DEFAULT false,
    metadata        JSONB NOT NULL DEFAULT '{}'
);

-- Private per-agent reputation model
CREATE TABLE IF NOT EXISTS reputation (
    observer_id         TEXT NOT NULL,
    subject_id          TEXT NOT NULL,
    score               NUMERIC(5,4) NOT NULL DEFAULT 0.0,  -- [-1.0, 1.0]
    last_updated        BIGINT NOT NULL,
    interaction_count   INTEGER NOT NULL DEFAULT 0,
    world_id            TEXT NOT NULL DEFAULT 'local-dev-world-1',
    PRIMARY KEY (observer_id, subject_id)
);

-- Tokens table (may already exist; safe to re-run)
CREATE TABLE IF NOT EXISTS tokens (
    contract_address    TEXT PRIMARY KEY,
    owner_soul_id       TEXT NOT NULL,
    name                TEXT NOT NULL,
    symbol              TEXT NOT NULL,
    initial_supply      BIGINT NOT NULL,
    deployed_at         BIGINT NOT NULL,
    on_chain_tx         TEXT,
    world_id            TEXT NOT NULL DEFAULT 'local-dev-world-1'
);

-- Indexes for new tables
CREATE INDEX IF NOT EXISTS idx_sleep_states_world  ON sleep_states(world_id);
CREATE INDEX IF NOT EXISTS idx_dreams_soul_id      ON dreams(soul_id, dreamed_at DESC);
CREATE INDEX IF NOT EXISTS idx_dreams_world        ON dreams(world_id, dreamed_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_recipient  ON agent_messages(recipient_id, world_id, sent_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_sender     ON agent_messages(sender_id, world_id, sent_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_broadcast  ON agent_messages(recipient_id, world_id) WHERE recipient_id = 'BROADCAST';
CREATE INDEX IF NOT EXISTS idx_reputation_observer ON reputation(observer_id, world_id);
CREATE INDEX IF NOT EXISTS idx_tokens_owner        ON tokens(owner_soul_id, world_id);
CREATE INDEX IF NOT EXISTS idx_tokens_world        ON tokens(world_id, deployed_at DESC);

-- ============================================================
-- Agent autonomy — local environment, capabilities, jobs
-- See docs/77-agent-autonomy-local.md
-- ============================================================

CREATE TABLE IF NOT EXISTS agent_scratch (
    soul_id         TEXT NOT NULL,
    scratch_key     TEXT NOT NULL,
    content         TEXT NOT NULL DEFAULT '',
    updated_at      BIGINT NOT NULL DEFAULT 0,
    world_id        TEXT NOT NULL DEFAULT 'local-dev-world-1',
    PRIMARY KEY (soul_id, scratch_key)
);

CREATE TABLE IF NOT EXISTS agent_action_log (
    id              BIGSERIAL PRIMARY KEY,
    soul_id         TEXT NOT NULL,
    action_type     TEXT NOT NULL,
    payload         JSONB NOT NULL DEFAULT '{}',
    result          JSONB NOT NULL DEFAULT '{}',
    success         BOOLEAN NOT NULL DEFAULT true,
    ts              BIGINT NOT NULL,
    world_id        TEXT NOT NULL DEFAULT 'local-dev-world-1'
);

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
);

CREATE TABLE IF NOT EXISTS agent_registered_tools (
    tool_id         TEXT PRIMARY KEY,
    owner_soul_id   TEXT NOT NULL,
    name            TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    handler_type    TEXT NOT NULL DEFAULT 'local',
    input_schema    JSONB NOT NULL DEFAULT '{}',
    cost_usdc       NUMERIC(18,6) NOT NULL DEFAULT 0.001,
    calls_served    BIGINT NOT NULL DEFAULT 0,
    is_active       BOOLEAN NOT NULL DEFAULT true,
    created_at      BIGINT NOT NULL,
    world_id        TEXT NOT NULL DEFAULT 'local-dev-world-1'
);

CREATE TABLE IF NOT EXISTS agent_graph_mutations (
    mutation_id     TEXT PRIMARY KEY,
    soul_id         TEXT NOT NULL,
    mutation_type   TEXT NOT NULL,
    payload         JSONB NOT NULL DEFAULT '{}',
    status          TEXT NOT NULL DEFAULT 'pending',
    created_at      BIGINT NOT NULL,
    applied_at      BIGINT,
    world_id        TEXT NOT NULL DEFAULT 'local-dev-world-1'
);

CREATE TABLE IF NOT EXISTS agent_capability_grants (
    soul_id         TEXT NOT NULL,
    capability_id   TEXT NOT NULL,
    granted_at      BIGINT NOT NULL,
    granted_via     TEXT NOT NULL DEFAULT 'tier',
    world_id        TEXT NOT NULL DEFAULT 'local-dev-world-1',
    PRIMARY KEY (soul_id, capability_id)
);

CREATE INDEX IF NOT EXISTS idx_action_log_soul    ON agent_action_log(soul_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_due           ON agent_scheduled_jobs(run_at, status);
CREATE INDEX IF NOT EXISTS idx_jobs_soul          ON agent_scheduled_jobs(soul_id, status);
CREATE INDEX IF NOT EXISTS idx_reg_tools_owner    ON agent_registered_tools(owner_soul_id, is_active);
CREATE INDEX IF NOT EXISTS idx_graph_mut_soul     ON agent_graph_mutations(soul_id, status);
