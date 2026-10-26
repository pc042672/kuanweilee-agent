"""AuthZ for /api/ontology — config writes are admin-only.

Mirrors tests/test_integrations_api.py::TestAuthZ: a member token gets 403 on
every mutating route; reads stay open to any authenticated user.
"""

import os

import pytest

os.environ.setdefault("DEV_USER_EMAIL", "test@dev.com")
os.environ.setdefault("JWT_SECRET", "test-secret-for-tests")

from fastapi.testclient import TestClient

from backend.auth import create_session_jwt
from backend.server import app

WRITE_ROUTES = [
    ("PUT", "/api/ontology"),
    ("POST", "/api/ontology/nodes/some_key"),
    ("PUT", "/api/ontology/nodes/some_key"),
    ("DELETE", "/api/ontology/nodes/some_key"),
    ("POST", "/api/ontology/nodes/some_key/options"),
    ("DELETE", "/api/ontology/nodes/some_key/options"),
    ("PUT", "/api/ontology/rules"),
    ("PUT", "/api/ontology/strategies"),
]


@pytest.fixture
def client():
    return TestClient(app)


def _headers(role: str):
    token = create_session_jwt({
        "user_id": 99,
        "email": f"{role}@example.com",
        "name": role.title(),
        "site_id": 1,
        "role": role,
    })
    return {"Authorization": f"Bearer {token}"}


class TestOntologyWriteAuthZ:
    @pytest.mark.parametrize("method,path", WRITE_ROUTES)
    def test_member_writes_forbidden(self, client, method, path):
        r = client.request(method, path, headers=_headers("member"), json={})
        assert r.status_code == 403

    @pytest.mark.parametrize("method,path", WRITE_ROUTES)
    def test_viewer_writes_forbidden(self, client, method, path):
        r = client.request(method, path, headers=_headers("viewer"), json={})
        assert r.status_code == 403

    def test_member_can_read(self, client):
        r = client.get("/api/ontology/nodes", headers=_headers("member"))
        assert r.status_code in (200, 404)  # 404 only if no ontology configured
