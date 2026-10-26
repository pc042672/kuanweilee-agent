-- CDP Ontology System — Graph-Ready DDL
-- Designed for Greenplum (DISTRIBUTED BY), future migration to Google Spanner Graph.
-- All tables are site-aware (site_id) for multi-site support.
-- Edge tables include temporal columns (valid_from/valid_to) for bitemporal knowledge graph.

CREATE SCHEMA IF NOT EXISTS ontology;
CREATE SCHEMA IF NOT EXISTS cdp;
CREATE SCHEMA IF NOT EXISTS auth;

-- ==================== AUTH (Phase 2 enforcement, Phase 1 default site) ====================

CREATE TABLE IF NOT EXISTS auth.site (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(256) NOT NULL,
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
INSERT INTO auth.site (id, name) VALUES ('default', 'Default Site') ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS auth.user_account (
    id VARCHAR(64) PRIMARY KEY,
    site_id VARCHAR(64) NOT NULL DEFAULT 'default' REFERENCES auth.site(id),
    email VARCHAR(256) NOT NULL,
    name VARCHAR(256),
    role VARCHAR(32) NOT NULL DEFAULT 'viewer',
    password_hash VARCHAR(256),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(site_id, email)
);

CREATE TABLE IF NOT EXISTS auth.api_key (
    id VARCHAR(64) PRIMARY KEY,
    site_id VARCHAR(64) NOT NULL DEFAULT 'default' REFERENCES auth.site(id),
    key_hash VARCHAR(256) NOT NULL UNIQUE,
    name VARCHAR(128),
    scopes TEXT[] DEFAULT '{}',
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ==================== SCHEMA MIGRATION TRACKING ====================

CREATE TABLE IF NOT EXISTS schema_migrations (
    name VARCHAR(128) PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT NOW()
);

-- ==================== NODE TABLES (all site-aware) ====================

CREATE TABLE IF NOT EXISTS ontology.taxonomy_node (
    id SERIAL,
    site_id VARCHAR(64) NOT NULL DEFAULT 'default',
    business_key VARCHAR(128) NOT NULL,
    name VARCHAR(128) NOT NULL,
    description TEXT,
    node_type VARCHAR(16) DEFAULT 'STR',
    is_multiple BOOLEAN DEFAULT FALSE,
    is_scored BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(site_id, business_key)
) DISTRIBUTED BY (business_key);

CREATE TABLE IF NOT EXISTS ontology.taxonomy_option (
    id SERIAL,
    site_id VARCHAR(64) NOT NULL DEFAULT 'default',
    node_key VARCHAR(128) NOT NULL,
    name VARCHAR(128) NOT NULL,
    value VARCHAR(128) NOT NULL,
    semantic_definition TEXT,
    sort_order INT DEFAULT 0,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(site_id, node_key, value)
) DISTRIBUTED BY (node_key);

CREATE TABLE IF NOT EXISTS ontology.labeling_rule (
    id SERIAL,
    site_id VARCHAR(64) NOT NULL DEFAULT 'default',
    business_key VARCHAR(128) NOT NULL,
    name VARCHAR(128) NOT NULL,
    target_node VARCHAR(128) NOT NULL,
    rule_type VARCHAR(16) NOT NULL DEFAULT 'sql',
    sources TEXT[],
    sql_expression TEXT,
    quiz_config JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(site_id, business_key)
) DISTRIBUTED BY (business_key);

CREATE TABLE IF NOT EXISTS ontology.labeling_rule_value (
    id SERIAL,
    site_id VARCHAR(64) NOT NULL DEFAULT 'default',
    rule_key VARCHAR(128) NOT NULL,
    name VARCHAR(128) NOT NULL,
    value VARCHAR(128) NOT NULL,
    semantic_definition TEXT,
    sort_order INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(site_id, rule_key, value)
) DISTRIBUTED BY (rule_key);

CREATE TABLE IF NOT EXISTS ontology.segment (
    id SERIAL,
    site_id VARCHAR(64) NOT NULL DEFAULT 'default',
    business_key VARCHAR(128) NOT NULL,
    name VARCHAR(128) NOT NULL,
    description TEXT,
    logic VARCHAR(8) DEFAULT 'ALL',
    condition_expression TEXT,
    actions JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(site_id, business_key)
) DISTRIBUTED BY (business_key);

-- ==================== EDGE TABLES (site-aware + temporal) ====================

CREATE TABLE IF NOT EXISTS ontology.edge_rule_node (
    id SERIAL,
    site_id VARCHAR(64) NOT NULL DEFAULT 'default',
    rule_key VARCHAR(128) NOT NULL,
    node_key VARCHAR(128) NOT NULL,
    edge_type VARCHAR(32) DEFAULT 'TARGETS',
    valid_from TIMESTAMP DEFAULT NOW(),
    valid_to TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(site_id, rule_key, node_key)
) DISTRIBUTED BY (rule_key);

CREATE TABLE IF NOT EXISTS ontology.edge_segment_rule (
    id SERIAL,
    site_id VARCHAR(64) NOT NULL DEFAULT 'default',
    segment_key VARCHAR(128) NOT NULL,
    node_key VARCHAR(128) NOT NULL,
    operator VARCHAR(32) NOT NULL,
    value VARCHAR(256),
    second_value VARCHAR(256),
    min_score FLOAT,
    sort_order INT DEFAULT 0,
    valid_from TIMESTAMP DEFAULT NOW(),
    valid_to TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
) DISTRIBUTED BY (segment_key);

CREATE TABLE IF NOT EXISTS ontology.edge_segment_order (
    id SERIAL,
    site_id VARCHAR(64) NOT NULL DEFAULT 'default',
    segment_key VARCHAR(128) NOT NULL,
    code VARCHAR(128) NOT NULL,
    code_type VARCHAR(32) DEFAULT 'ITEM_CODE',
    counting VARCHAR(32) DEFAULT 'FREQUENCY',
    operator VARCHAR(16) NOT NULL,
    value VARCHAR(128) NOT NULL,
    start_date DATE,
    end_date DATE,
    sort_order INT DEFAULT 0,
    valid_from TIMESTAMP DEFAULT NOW(),
    valid_to TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
) DISTRIBUTED BY (segment_key);

-- ==================== QUIZ RESULTS (site-aware) ====================

CREATE TABLE IF NOT EXISTS cdp.quiz_results (
    id SERIAL,
    site_id VARCHAR(64) NOT NULL DEFAULT 'default',
    user_id VARCHAR(64) NOT NULL,
    quiz_id VARCHAR(64) NOT NULL,
    node_name VARCHAR(128) NOT NULL,
    option_value VARCHAR(128) NOT NULL,
    score FLOAT NOT NULL DEFAULT 1.0,
    is_primary BOOLEAN DEFAULT FALSE,
    raw_responses JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
) DISTRIBUTED BY (user_id);

CREATE INDEX IF NOT EXISTS idx_quiz_results_user ON cdp.quiz_results(site_id, user_id, quiz_id);
