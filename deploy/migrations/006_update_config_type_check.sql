-- Drop the config_type allowlist. The original check only covered pre-v3
-- types, so saving the current configs (ontology / rules / strategies)
-- violated the constraint on any database created from migration 002.
-- Config types are application-defined and keep growing (guardrails,
-- channel configs, ...) — an enum CHECK would need a DDL migration per new
-- type for no real invariant; validation lives in the repositories.
-- Target: PostgreSQL 12+

ALTER TABLE site_configs DROP CONSTRAINT IF EXISTS site_configs_config_type_check;
