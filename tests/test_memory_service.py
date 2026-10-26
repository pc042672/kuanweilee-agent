"""Integration tests for PostgresMemoryService against a real PostgreSQL 12.

Skipped unless DATABASE_URL_TEST is set (same convention as test_init_db.py).
"""

import asyncio
import os
import types as pytypes

import pytest

DATABASE_URL_TEST = os.environ.get("DATABASE_URL_TEST")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL_TEST, reason="DATABASE_URL_TEST not set (needs a real PostgreSQL 12)"
)


@pytest.fixture(scope="module")
def engine():
    from sqlalchemy import create_engine, text

    eng = create_engine(DATABASE_URL_TEST)
    with eng.begin() as conn:
        conn.execute(text("DELETE FROM memories WHERE app_name LIKE 'memtest%'"))
    yield eng
    with eng.begin() as conn:
        conn.execute(text("DELETE FROM memories WHERE app_name LIKE 'memtest%'"))
    eng.dispose()


@pytest.fixture
def service(engine):
    from memory.postgres_memory_service import PostgresMemoryService

    return PostgresMemoryService(engine)


def _fake_session(app="memtest", user="alice@test.com", sid="s1",
                  state=None, events=None):
    return pytypes.SimpleNamespace(
        app_name=app, user_id=user, id=sid,
        state=state or {}, events=events or [], last_update_time=1750000000.0,
    )


def _user_event(text_):
    from google.genai import types

    return pytypes.SimpleNamespace(
        author="user",
        timestamp=1750000000.0,
        content=types.Content(role="user", parts=[types.Part(text=text_)]),
    )


def test_gate_skips_trivial_sessions(service, engine):
    from sqlalchemy import text

    session = _fake_session(sid="trivial", events=[_user_event("hello there")])
    asyncio.run(service.add_session_to_memory(session))
    with engine.connect() as conn:
        count = conn.execute(text(
            "SELECT count(*) FROM memories WHERE session_id = 'trivial'"
        )).scalar()
    assert count == 0  # no campaign/plan/preference -> nothing stored


def test_state_facts_and_recall(service):
    session = _fake_session(
        sid="s-campaign",
        state={
            "campaign_summary": "Abandoned cart recovery for explorer archetype, 120 users",
            "execution_plan": {"goal": "find cart abandoners", "tables": ["report.smb_abandon_list"]},
        },
    )
    asyncio.run(service.add_session_to_memory(session))

    res = asyncio.run(service.search_memory(
        app_name="memtest", user_id="alice@test.com", query="abandoned cart recovery"
    ))
    assert res.memories, "campaign summary should be recalled"
    texts = [" ".join(p.text for p in m.content.parts if p.text) for m in res.memories]
    assert any("explorer" in t for t in texts)


def test_preference_extraction(service):
    session = _fake_session(
        sid="s-pref",
        state={"campaign_summary": "x"},
        events=[
            _user_event("always exclude staff accounts from audiences"),
            _user_event("show me vip users"),  # not a preference
        ],
    )
    asyncio.run(service.add_session_to_memory(session))

    res = asyncio.run(service.search_memory(
        app_name="memtest", user_id="alice@test.com", query="exclude staff accounts"
    ))
    bodies = [" ".join(p.text for p in m.content.parts if p.text) for m in res.memories]
    assert any("staff" in b for b in bodies)
    assert not any("vip users" in b for b in bodies)


def test_user_scoping(service):
    asyncio.run(service.add_session_to_memory(_fake_session(
        user="bob@test.com", sid="s-bob",
        state={"campaign_summary": "bob secret quarterly campaign"},
    )))
    res = asyncio.run(service.search_memory(
        app_name="memtest", user_id="alice@test.com", query="secret quarterly campaign"
    ))
    assert not res.memories  # alice must not see bob's memories


def test_replace_semantics_no_duplicates(service, engine):
    from sqlalchemy import text

    session = _fake_session(sid="s-replay", state={"campaign_summary": "replay campaign"})
    asyncio.run(service.add_session_to_memory(session))
    asyncio.run(service.add_session_to_memory(session))
    with engine.connect() as conn:
        count = conn.execute(text(
            "SELECT count(*) FROM memories WHERE session_id = 's-replay'"
        )).scalar()
    assert count == 1


def test_delete_paths(service, engine):
    from sqlalchemy import text

    asyncio.run(service.add_session_to_memory(_fake_session(
        user="carol@test.com", sid="s-c1", state={"campaign_summary": "carol c1"})))
    asyncio.run(service.add_session_to_memory(_fake_session(
        user="carol@test.com", sid="s-c2", state={"campaign_summary": "carol c2"})))

    assert service.delete_session_memories(
        app_name="memtest", user_id="carol@test.com", session_id="s-c1") == 1
    assert service.delete_memories("carol@test.com") == 1

    with engine.connect() as conn:
        count = conn.execute(text(
            "SELECT count(*) FROM memories WHERE user_id = 'carol@test.com'"
        )).scalar()
    assert count == 0
