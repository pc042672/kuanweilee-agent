-- Migration 008: Per-site external service credentials + data_sources secrets
-- Target: PostgreSQL 12+
-- Phase: Integrations — settings page for data sources + external AI services
--
-- KEY CUSTODY: credentials_encrypted / secrets_encrypted are Fernet tokens
-- encrypted with APP_ENCRYPTION_KEY (env var or Secret Manager). Losing that
-- key makes the stored secrets unrecoverable — non-secret metadata survives,
-- so credentials can be re-entered on the settings page.

BEGIN;

CREATE TABLE IF NOT EXISTS external_credentials (
    id SERIAL PRIMARY KEY,
    site_id INTEGER NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    service VARCHAR(64) NOT NULL,
    credentials_encrypted BYTEA NOT NULL,
    metadata JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT true,
    created_by INTEGER REFERENCES users(id),
    updated_by INTEGER REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (site_id, service)
);

COMMENT ON TABLE external_credentials IS
    'Per-site external service credentials (gemini, vertex_ai, ...), Fernet-encrypted with APP_ENCRYPTION_KEY.';
COMMENT ON COLUMN external_credentials.metadata IS
    'NON-SECRET display fields only: {project_id, location, key_hint}. Secrets live in credentials_encrypted.';

CREATE INDEX IF NOT EXISTS idx_external_credentials_site ON external_credentials (site_id);

-- Encrypted secret blob for data source connections; connection_config keeps
-- only non-secret keys (host, port, dbname, readonly_user). Plaintext
-- password keys in connection_config remain readable as a legacy fallback.
ALTER TABLE data_sources ADD COLUMN IF NOT EXISTS secrets_encrypted BYTEA;
ALTER TABLE data_sources ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

COMMENT ON COLUMN data_sources.secrets_encrypted IS
    'Fernet-encrypted JSON: {password, readonly_password}. Encrypted with APP_ENCRYPTION_KEY.';

COMMIT;
