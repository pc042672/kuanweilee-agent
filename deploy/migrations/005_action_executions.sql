-- Migration 005: Action execution log
-- Tracks every scoring, segment evaluation, and NBA/NBO action for observability

CREATE TABLE IF NOT EXISTS action_executions (
    id SERIAL PRIMARY KEY,
    site_id INTEGER NOT NULL REFERENCES sites(id),
    action_type TEXT NOT NULL,
    target_node_key TEXT,
    request_json JSONB,
    response_json JSONB,
    execution_status TEXT NOT NULL DEFAULT 'succeeded',
    error_message TEXT,
    executed_by INTEGER REFERENCES users(id),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    correlation_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_action_executions_site ON action_executions(site_id);
CREATE INDEX IF NOT EXISTS idx_action_executions_type ON action_executions(action_type);
CREATE INDEX IF NOT EXISTS idx_action_executions_target ON action_executions(target_node_key);
