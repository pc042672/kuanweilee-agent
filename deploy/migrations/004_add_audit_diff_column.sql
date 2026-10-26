-- Migration 004: Add diff_json column to config_audit_log
-- Stores field-level diffs (added/removed/changed nodes) instead of just full snapshots

ALTER TABLE config_audit_log ADD COLUMN IF NOT EXISTS diff_json JSONB;
