"""Tests for API endpoints — auth, health, config routes."""

import os
import pytest

os.environ.setdefault("DEV_USER_EMAIL", "test@dev.com")
os.environ.setdefault("JWT_SECRET", "test-secret-for-tests")

from fastapi.testclient import TestClient
from backend.server import app
from backend.auth import create_session_jwt


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def no_dev_mode(monkeypatch):
    """Disable DEV_MODE so real auth paths are exercised.

    Patches both ``backend.settings`` (used by server.py) and the bare
    ``settings`` module (used by auth.py) since they are separate objects
    in sys.modules.
    """
    import sys
    import backend.settings as settings_mod
    monkeypatch.setattr(settings_mod, "DEV_MODE", False)
    if "settings" in sys.modules:
        monkeypatch.setattr(sys.modules["settings"], "DEV_MODE", False)


@pytest.fixture
def auth_headers():
    """Create a valid JWT and return auth headers."""
    token = create_session_jwt({
        "user_id": 42,
        "email": "alice@example.com",
        "name": "Alice",
        "site_id": 5,
        "role": "admin",
    })
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def member_headers():
    """Create a JWT with member role."""
    token = create_session_jwt({
        "user_id": 99,
        "email": "bob@example.com",
        "name": "Bob",
        "site_id": 3,
        "role": "member",
    })
    return {"Authorization": f"Bearer {token}"}


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert "persistent_sessions" in body

    def test_health_requires_no_auth(self, client):
        r = client.get("/health")
        assert r.status_code == 200


class TestAuthMe:
    def test_dev_mode_returns_dev_user(self, client):
        r = client.get("/api/auth/me")
        assert r.status_code == 200
        data = r.json()
        assert data["email"] == "test@dev.com"
        assert data["role"] == "admin"

    def test_jwt_returns_correct_user(self, client, auth_headers, no_dev_mode):
        r = client.get("/api/auth/me", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["user_id"] == 42
        assert data["email"] == "alice@example.com"
        assert data["site_id"] == 5
        assert data["role"] == "admin"

    def test_member_jwt_returns_member_role(self, client, member_headers, no_dev_mode):
        r = client.get("/api/auth/me", headers=member_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["user_id"] == 99
        assert data["site_id"] == 3
        assert data["role"] == "member"


class TestAuthConfig:
    def test_returns_client_id(self, client, monkeypatch):
        import backend.settings as settings_mod
        monkeypatch.setattr(settings_mod, "GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
        r = client.get("/api/auth/config")
        assert r.status_code == 200
        assert r.json() == {"google_client_id": "test-client-id.apps.googleusercontent.com"}

    def test_requires_no_auth(self, client, monkeypatch, no_dev_mode):
        import backend.settings as settings_mod
        monkeypatch.setattr(settings_mod, "GOOGLE_CLIENT_ID", None)
        r = client.get("/api/auth/config")
        assert r.status_code == 200
        assert r.json() == {"google_client_id": None}


class TestContextMiddleware:
    def test_jwt_sets_correct_context(self, client, auth_headers, no_dev_mode):
        """Verify middleware extracts JWT and sets context with correct site_id."""
        r = client.get("/api/auth/me", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["site_id"] == 5

    def test_different_sites_resolve_correctly(self, client, no_dev_mode):
        for site_id in [1, 3, 7]:
            token = create_session_jwt({
                "user_id": 1, "email": "x@x.com", "name": "X",
                "site_id": site_id, "role": "admin",
            })
            r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
            assert r.json()["site_id"] == site_id


class TestProtectedRoutes:
    def test_ontology_accessible(self, client):
        r = client.get("/api/ontology")
        assert r.status_code == 200

    def test_config_reload_accessible_admin(self, client, auth_headers):
        r = client.post("/api/config/reload", headers=auth_headers)
        assert r.status_code == 200


class TestInvalidAuth:
    def test_expired_jwt_returns_401_on_route(self, client, no_dev_mode):
        import backend.auth as auth_mod
        original = auth_mod.JWT_EXPIRY_SECONDS
        auth_mod.JWT_EXPIRY_SECONDS = -1
        try:
            token = create_session_jwt({
                "user_id": 1, "email": "x@x.com", "name": "X",
                "site_id": 1, "role": "admin",
            })
        finally:
            auth_mod.JWT_EXPIRY_SECONDS = original

        r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401

    def test_malformed_jwt_returns_401(self, client, no_dev_mode):
        r = client.get("/api/auth/me", headers={"Authorization": "Bearer not.a.valid.jwt"})
        assert r.status_code == 401
