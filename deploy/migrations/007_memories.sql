-- Long-term memory store for PostgresMemoryService (ADK BaseMemoryService impl).
-- Stores DISTILLED facts per session (campaign decisions, analysis/segment
-- definitions, user preferences) — never full conversation transcripts.
-- Search: PostgreSQL full-text (tsvector, generated column — PG12+).
-- Target: PostgreSQL 12+

CREATE TABLE IF NOT EXISTS memories (
    id          SERIAL PRIMARY KEY,
    app_name    TEXT NOT NULL,
    user_id     TEXT NOT NULL,
    session_id  TEXT NOT NULL,
    site_id     INTEGER REFERENCES sites(id) ON DELETE CASCADE,
    kind        TEXT NOT NULL,            -- campaign_summary | analysis | preference
    author      TEXT NOT NULL DEFAULT 'model',
    "timestamp" TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    content     JSONB NOT NULL,           -- serialized genai types.Content (lossless rebuild)
    text        TEXT NOT NULL,            -- searchable plain text
    tsv         TSVECTOR GENERATED ALWAYS AS (to_tsvector('simple', text)) STORED
);

CREATE INDEX IF NOT EXISTS idx_memories_tsv ON memories USING GIN (tsv);
CREATE INDEX IF NOT EXISTS idx_memories_user ON memories (app_name, user_id);
CREATE INDEX IF NOT EXISTS idx_memories_session ON memories (app_name, user_id, session_id);

COMMENT ON TABLE memories IS 'Long-term agent memory: distilled session facts, site-scoped, full-text searchable.';
