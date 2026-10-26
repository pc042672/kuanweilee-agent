-- Migration 002: Create config storage tables (site_configs, config_audit_log)
-- Target: PostgreSQL 12+
-- Phase: 2 - Metadata & Governance

BEGIN;

CREATE TABLE IF NOT EXISTS site_configs (
    id SERIAL PRIMARY KEY,
    site_id INTEGER NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    config_type VARCHAR(32) NOT NULL
        CHECK (config_type IN ('ontology_v1', 'label_rules', 'taxonomy', 'plans', 'skills')),
    config_data JSONB NOT NULL,
    version VARCHAR(32) NOT NULL,
    updated_by INTEGER REFERENCES users(id),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(site_id, config_type)
);

COMMENT ON TABLE site_configs IS 'Per-site configuration storage. Replaces JSON files with DB-backed config.';

CREATE TABLE IF NOT EXISTS config_audit_log (
    id SERIAL PRIMARY KEY,
    site_id INTEGER NOT NULL,
    config_type VARCHAR(32) NOT NULL,
    action VARCHAR(16) NOT NULL CHECK (action IN ('create', 'update', 'delete')),
    changed_by INTEGER NOT NULL REFERENCES users(id),
    previous_data JSONB,
    new_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE config_audit_log IS 'Audit trail for all config changes with who/when/what.';

CREATE INDEX IF NOT EXISTS idx_audit_site_time ON config_audit_log (site_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_site_configs_site ON site_configs (site_id);

COMMIT;
