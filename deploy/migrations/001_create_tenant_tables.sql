-- Migration 001: Create tenant tables (sites, data_sources, users, site_members)
-- Target: PostgreSQL 12+
-- Phase: 1 - Foundation

BEGIN;

-- Tenants
CREATE TABLE IF NOT EXISTS sites (
    id SERIAL PRIMARY KEY,
    name VARCHAR(256) NOT NULL,
    slug VARCHAR(64) UNIQUE NOT NULL,
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE sites IS 'Tenant registry. Each site is an isolated workspace with its own config and data sources.';
COMMENT ON COLUMN sites.settings IS 'Site-level settings JSONB: {"max_iterations": 3, "agent_timeout_seconds": 120}';

-- Data source connections (decoupled from sites, supports multiple DB types)
CREATE TABLE IF NOT EXISTS data_sources (
    id SERIAL PRIMARY KEY,
    site_id INTEGER NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    name VARCHAR(256) NOT NULL DEFAULT 'default',
    db_type VARCHAR(32) NOT NULL,
    connection_config JSONB NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE data_sources IS 'Per-site database connections. Supports greenplum, postgresql, mysql, mssql, oracle, bigquery, spanner.';
COMMENT ON COLUMN data_sources.connection_config IS 'Connection details JSONB. RDBMS: {host, port, dbname, user, password_secret_id, readonly_user, readonly_password_secret_id}. BigQuery: {project_id, dataset, credentials_secret_id}.';

CREATE INDEX IF NOT EXISTS idx_data_sources_site_id ON data_sources(site_id);

-- Google-authenticated users
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    google_id VARCHAR(128) UNIQUE NOT NULL,
    email VARCHAR(256) NOT NULL,
    name VARCHAR(256),
    avatar_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE users IS 'Users authenticated via Google OAuth. google_id is the sub claim from the ID token.';

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- Site membership (1 site : many users)
CREATE TABLE IF NOT EXISTS site_members (
    site_id INTEGER NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(32) NOT NULL DEFAULT 'member',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (site_id, user_id)
);

COMMENT ON TABLE site_members IS 'Maps users to sites with roles: owner, admin, member.';

-- Seed: default site for development / migration
INSERT INTO sites (name, slug, settings)
VALUES ('Default Site', 'default', '{"max_iterations": 3}')
ON CONFLICT (slug) DO NOTHING;

COMMIT;
