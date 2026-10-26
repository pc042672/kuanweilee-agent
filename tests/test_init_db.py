"""Integration test for deploy/init_db.py against a real PostgreSQL 12.

Skipped unless DATABASE_URL_TEST is set, e.g.:
    DATABASE_URL_TEST=postgresql+psycopg2://postgres:aicdp-dev@localhost:5432/aicdp \
        python -m pytest tests/test_init_db.py -v

Also asserts the ADK 2.x session-event schema (created lazily by
DatabaseSessionService) carries the columns the 2.x service reads
unconditionally — missing columns mean a silent 500 on every chat.
"""

import os
import types
from pathlib import Path

import pytest

DATABASE_URL_TEST = os.environ.get("DATABASE_URL_TEST")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL_TEST, reason="DATABASE_URL_TEST not set (needs a real PostgreSQL 12)"
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

CORE_TABLES = [
    "sites",
    "data_sources",
    "users",
    "site_members",
    "site_configs",
    "config_audit_log",
    "action_executions",
]

# ADK 2.2.0 session schema: events carry a consolidated event_data JSON column,
# and adk_internal_metadata tracks the schema version. A DB created by ADK 1.x
# (per-field event columns, no metadata table) must NOT be reused with 2.x.
ADK_TABLES = {"sessions", "events", "app_states", "user_states", "adk_internal_metadata"}


@pytest.fixture(scope="module")
def engine():
    from sqlalchemy import create_engine

    eng = create_engine(DATABASE_URL_TEST)
    yield eng
    eng.dispose()


@pytest.fixture(scope="module", autouse=True)
def run_init_db(engine):
    import init_db

    args = types.SimpleNamespace(
        database_url=DATABASE_URL_TEST,
        admin_email="dev@test.com",
        admin_name="Dev",
        site_name="Dev Site",
        seed_configs=True,
    )
    init_db.run(args)


def test_all_migrations_applied(engine):
    from sqlalchemy import text

    migration_files = sorted(
        p.name for p in (PROJECT_ROOT / "deploy" / "migrations").glob("*.sql")
    )
    with engine.connect() as conn:
        applied = {
            r[0]
            for r in conn.execute(text("SELECT filename FROM schema_migrations"))
        }
    assert set(migration_files) <= applied


def test_core_tables_exist(engine):
    from sqlalchemy import inspect

    tables = set(inspect(engine).get_table_names())
    missing = [t for t in CORE_TABLES if t not in tables]
    assert not missing, f"missing tables: {missing}"


def test_configs_seeded(engine):
    from sqlalchemy import text

    with engine.connect() as conn:
        types_present = {
            r[0]
            for r in conn.execute(
                text("SELECT config_type FROM site_configs WHERE site_id = 1")
            )
        }
    assert {"ontology", "rules", "strategies"} <= types_present


def test_admin_user_and_site(engine):
    from sqlalchemy import text

    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT u.email, m.role FROM users u "
                "JOIN site_members m ON m.user_id = u.id "
                "WHERE u.email = 'dev@test.com'"
            )
        ).fetchone()
    assert row is not None
    assert row[1] == "owner"


def test_adk_session_schema_and_roundtrip():
    """DatabaseSessionService must create its 2.x schema and round-trip a session."""
    import asyncio

    from google.adk.sessions import DatabaseSessionService
    from sqlalchemy import create_engine, inspect

    async_url = DATABASE_URL_TEST.replace("postgresql+psycopg2://", "postgresql+asyncpg://")

    async def roundtrip():
        service = DatabaseSessionService(db_url=async_url)
        session = await service.create_session(app_name="aicdp_test", user_id="t-user")
        return await service.get_session(
            app_name="aicdp_test", user_id="t-user", session_id=session.id
        ), session

    fetched, session = asyncio.run(roundtrip())
    assert fetched is not None and fetched.id == session.id

    eng = create_engine(DATABASE_URL_TEST)
    try:
        insp = inspect(eng)
        tables = set(insp.get_table_names())
        missing = ADK_TABLES - tables
        assert not missing, f"ADK 2.x session tables missing: {missing}"
        event_cols = {c["name"] for c in insp.get_columns("events")}
        assert "event_data" in event_cols, (
            "events.event_data missing — schema looks like ADK 1.x; "
            "2.x must not share session storage with 1.x"
        )
    finally:
        eng.dispose()
