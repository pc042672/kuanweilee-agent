"""Tests for the chat-history API (list/messages/delete + auth scoping)."""

import asyncio

import pytest
from fastapi.testclient import TestClient
from google.genai import types


@pytest.fixture(scope="module")
def client():
    from backend.server import app

    return TestClient(app)


@pytest.fixture(scope="module")
def seeded_session():
    """Create a session with messages via the in-process session service."""
    from backend.server import session_service
    from google.adk.events.event import Event

    async def seed():
        session = await session_service.create_session(
            app_name="revive_ai", user_id="test@dev.com", session_id="hist-1"
        )
        await session_service.append_event(session, Event(
            author="user", invocation_id="inv1",
            content=types.Content(role="user", parts=[types.Part(text="find vip users")]),
        ))
        await session_service.append_event(session, Event(
            author="ReviveOrchestrator", invocation_id="inv1",
            content=types.Content(role="model", parts=[types.Part(text="Found 42 VIP users")]),
        ))
        return session

    return asyncio.run(seed())


def test_capabilities_flag(client):
    res = client.get("/api/chat/capabilities")
    assert res.status_code == 200
    assert "persistent_sessions" in res.json()


def test_list_sessions(client, seeded_session):
    res = client.get("/api/chat/sessions")
    assert res.status_code == 200
    ids = [s["id"] for s in res.json()["sessions"]]
    assert "hist-1" in ids


def test_get_messages_shape(client, seeded_session):
    res = client.get("/api/chat/sessions/hist-1/messages")
    assert res.status_code == 200
    messages = res.json()["messages"]
    assert messages[0]["role"] == "user"
    assert messages[0]["text"] == "find vip users"
    assert messages[1]["role"] == "assistant"
    assert "timestamp" in messages[0]


def test_messages_404_for_other_users_session(client, seeded_session):
    """DEV user is test@dev.com; a session owned by someone else must 404."""
    from backend.server import session_service

    asyncio.run(session_service.create_session(
        app_name="revive_ai", user_id="other@dev.com", session_id="hist-other"
    ))
    res = client.get("/api/chat/sessions/hist-other/messages")
    assert res.status_code == 404


def test_delete_session(client, seeded_session):
    res = client.delete("/api/chat/sessions/hist-1")
    assert res.status_code == 200
    assert client.get("/api/chat/sessions/hist-1/messages").status_code == 404
