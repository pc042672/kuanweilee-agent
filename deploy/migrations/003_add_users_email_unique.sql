-- Migration 003: Add unique index on users.email
-- Needed for admin upsert in init_db.py

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_unique ON users(email);
