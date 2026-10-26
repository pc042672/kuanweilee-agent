"""Tests for /api/integrations — external services + data sources.

Invariants under test: writes are admin-only, no GET response or audit row
ever contains a secret value, site isolation, and cache eviction on mutation.
"""

import json as jsonlib
import os
import sys
from contextlib import contextmanager
from datetime import datetime, timezone

import pytest
from cryptography.fernet import Fernet

os.environ.setdefault("DEV_USER_EMAIL", "test@dev.com")
os.environ.setdefault("JWT_SECRET", "test-secret-for-tests")

from fastapi.testclient import TestClient

from backend.auth import create_session_jwt
from backend.server import app

SECRET = "super-secret-value-abc123XYZ"
SITE_ID = 5


# ==================== fakes ====================

class _FakeResult:
    def __init__(self, rows=None, scalar=None):
        self._rows = [dict(r) for r in (rows or [])]
        self._scalar = scalar

    def mappings(self):
        return self

    def all(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None

    def __iter__(self):
        return iter(self._rows)

    def scalar(self):
        return self._scalar


class FakeDB:
    """In-memory app-DB double; dispatches on SQL substrings."""

    def __init__(self):
        self.credentials = {}   # (site_id, service) -> row
        self.data_sources = {}  # id -> row
        self.audit = []
        self._next_id = 1

    def execute(self, stmt, params=None):
        sql = " ".join(str(stmt).split())
        p = params or {}
        if "INSERT INTO config_audit_log" in sql:
            self.audit.append(dict(p))
            return _FakeResult()
        if "INSERT INTO external_credentials" in sql:
            self.credentials[(p["sid"], p["svc"])] = {
                "service": p["svc"],
                "credentials_encrypted": p["blob"],
                "metadata": jsonlib.loads(p["meta"]),  # mimic JSONB round-trip
                "updated_at": datetime(2026, 6, 11, tzinfo=timezone.utc),
                "is_active": True,
            }
            return _FakeResult()
        if "UPDATE external_credentials SET is_active = false" in sql:
            row = self.credentials.get((p["sid"], p["svc"]))
            if row:
                row["is_active"] = False
            return _FakeResult()
        if "SELECT credentials_encrypted, metadata FROM external_credentials" in sql:
            row = self.credentials.get((p["sid"], p["svc"]))
            return _FakeResult([row] if row and row["is_active"] else [])
        if "SELECT service, metadata, updated_at FROM external_credentials" in sql:
            rows = [r for (sid, _), r in self.credentials.items()
                    if sid == p["sid"] and r["is_active"]]
            return _FakeResult(rows)
        if "INSERT INTO data_sources" in sql:
            ds_id, self._next_id = self._next_id, self._next_id + 1
            self.data_sources[ds_id] = {
                "id": ds_id,
                "site_id": p["sid"],
                "name": p["name"],
                "db_type": p["db_type"],
                "connection_config": jsonlib.loads(p["cfg"]),
                "secrets_encrypted": p["blob"],
                "is_active": p["active"],
            }
            return _FakeResult(scalar=ds_id)
        if "UPDATE data_sources SET is_active = false" in sql:
            row = self.data_sources.get(p["id"])
            if row and row["site_id"] == p["sid"]:
                row["is_active"] = False
            return _FakeResult()
        if "UPDATE data_sources SET" in sql:
            row = self.data_sources.get(p["id"])
            if row and row["site_id"] == p["sid"]:
                row.update(
                    name=p["name"],
                    db_type=p["db_type"],
                    connection_config=jsonlib.loads(p["cfg"]),
                    is_active=p["active"],
                )
                if "blob" in p:
                    row["secrets_encrypted"] = p["blob"]
            return _FakeResult()
        if "FROM data_sources WHERE id = :id" in sql:
            row = self.data_sources.get(p["id"])
            ok = row is not None and row["site_id"] == p["sid"]
            return _FakeResult([row] if ok else [])
        if "FROM data_sources WHERE site_id = :sid" in sql:
            rows = [r for r in self.data_sources.values() if r["site_id"] == p["sid"]]
            return _FakeResult(rows)
        raise AssertionError(f"FakeDB: unhandled SQL: {sql}")


class FakeEngine:
    def __init__(self, db):
        self.db = db

    @contextmanager
    def connect(self):
        yield self.db

    @contextmanager
    def begin(self):
        yield self.db


def _assert_no_secret(obj, secret=SECRET):
    assert secret not in jsonlib.dumps(obj, default=str), f"Secret leaked in: {obj}"


# ==================== fixtures ====================

@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def no_dev_mode(monkeypatch):
    """Real auth + prod-mode crypto paths; both module instances patched."""
    import backend.settings as settings_mod
    monkeypatch.setattr(settings_mod, "DEV_MODE", False)
    if "settings" in sys.modules:
        monkeypatch.setattr(sys.modules["settings"], "DEV_MODE", False)


@pytest.fixture(autouse=True)
def _fresh_crypto_and_cache(monkeypatch):
    """Per-test Fernet key; reset both dual-import instances of crypto/cache."""
    monkeypatch.setenv("APP_ENCRYPTION_KEY", Fernet.generate_key().decode())

    def reset():
        for name in ("backend.services.crypto", "services.crypto"):
            if name in sys.modules:
                sys.modules[name]._fernet = None
        for name in ("backend.services.credentials", "services.credentials"):
            if name in sys.modules:
                sys.modules[name]._cache.clear()

    reset()
    yield
    reset()


@pytest.fixture
def fake_db(monkeypatch):
    db_double = FakeDB()
    engine = FakeEngine(db_double)
    # Router binds get_engine from backend.db at import; credentials service
    # imports it from bare `db` at call time. Patch every path.
    import backend.routers.integrations as integrations_mod
    monkeypatch.setattr(integrations_mod, "get_engine", lambda: engine)
    import backend.db as backend_db
    monkeypatch.setattr(backend_db, "get_engine", lambda: engine)
    if "db" in sys.modules:
        monkeypatch.setattr(sys.modules["db"], "get_engine", lambda: engine)
    return db_double


@pytest.fixture
def evict_spy(monkeypatch):
    calls = []
    import backend.routers.integrations as integrations_mod
    monkeypatch.setattr(integrations_mod, "evict_site_resources", calls.append)
    return calls


def _headers(role: str, site_id: int = SITE_ID):
    token = create_session_jwt({
        "user_id": 42 if role != "member" else 99,
        "email": f"{role}@example.com",
        "name": role.title(),
        "site_id": site_id,
        "role": role,
    })
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers():
    return _headers("admin")


@pytest.fixture
def member_headers():
    return _headers("member")


# ==================== authz ====================

class TestAuthZ:
    WRITE_ROUTES = [
        ("PUT", "/api/integrations/services/gemini"),
        ("DELETE", "/api/integrations/services/gemini"),
        ("POST", "/api/integrations/services/gemini/test"),
        ("POST", "/api/integrations/data-sources"),
        ("PUT", "/api/integrations/data-sources/1"),
        ("DELETE", "/api/integrations/data-sources/1"),
        ("POST", "/api/integrations/data-sources/test"),
        ("POST", "/api/integrations/data-sources/1/test"),
    ]

    @pytest.mark.parametrize("method,path", WRITE_ROUTES)
    def test_member_writes_forbidden(self, client, member_headers, fake_db, method, path):
        r = client.request(method, path, headers=member_headers, json={})
        assert r.status_code == 403

    @pytest.mark.parametrize("method,path", WRITE_ROUTES)
    def test_anonymous_writes_rejected(self, client, fake_db, method, path):
        r = client.request(method, path, json={})
        assert r.status_code == 401

    def test_member_can_read(self, client, member_headers, fake_db):
        assert client.get("/api/integrations/services",
                          headers=member_headers).status_code == 200
        assert client.get("/api/integrations/data-sources",
                          headers=member_headers).status_code == 200


# ==================== external services ====================

class TestServices:
    def test_put_then_get_configured_with_hint(self, client, admin_headers, fake_db):
        r = client.put("/api/integrations/services/gemini", headers=admin_headers,
                       json={"secrets": {"api_key": SECRET}})
        assert r.status_code == 200

        r = client.get("/api/integrations/services", headers=admin_headers)
        svc = {s["service"]: s for s in r.json()["services"]}["gemini"]
        assert svc["configured"] is True
        assert svc["source"] == "db"
        assert svc["hint"] == "..." + SECRET[-4:]

    def test_no_secret_in_get_or_audit(self, client, admin_headers, fake_db, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", SECRET)
        client.put("/api/integrations/services/gemini", headers=admin_headers,
                   json={"secrets": {"api_key": SECRET}})
        r = client.get("/api/integrations/services", headers=admin_headers)
        _assert_no_secret(r.json())
        _assert_no_secret(fake_db.audit)

    def test_stored_secret_is_encrypted_at_rest(self, client, admin_headers, fake_db):
        client.put("/api/integrations/services/gemini", headers=admin_headers,
                   json={"secrets": {"api_key": SECRET}})
        blob = fake_db.credentials[(SITE_ID, "gemini")]["credentials_encrypted"]
        assert SECRET.encode() not in bytes(blob)

    def test_delete_unconfigures(self, client, admin_headers, fake_db, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.setenv("CREDENTIAL_ENV_FALLBACK", "false")
        client.put("/api/integrations/services/gemini", headers=admin_headers,
                   json={"secrets": {"api_key": SECRET}})
        client.delete("/api/integrations/services/gemini", headers=admin_headers)
        r = client.get("/api/integrations/services", headers=admin_headers)
        svc = {s["service"]: s for s in r.json()["services"]}["gemini"]
        assert svc["configured"] is False

    def test_unknown_service_rejected(self, client, admin_headers, fake_db):
        r = client.put("/api/integrations/services/nope", headers=admin_headers,
                       json={"secrets": {"api_key": "x"}})
        assert r.status_code == 400
        assert client.delete("/api/integrations/services/nope",
                             headers=admin_headers).status_code == 400
        assert client.post("/api/integrations/services/nope/test",
                           headers=admin_headers).status_code == 400

    def test_missing_required_field_400(self, client, admin_headers, fake_db):
        r = client.put("/api/integrations/services/gemini", headers=admin_headers,
                       json={"secrets": {}})
        assert r.status_code == 400
        assert "api_key" in r.json()["detail"]

    def test_no_engine_returns_503_on_write(self, client, admin_headers, monkeypatch):
        for name in ("db", "backend.db"):
            if name in sys.modules:
                monkeypatch.setattr(sys.modules[name], "get_engine", lambda: None)
        r = client.put("/api/integrations/services/gemini", headers=admin_headers,
                       json={"secrets": {"api_key": "k"}})
        assert r.status_code == 503


# ==================== data sources ====================

def _gp_payload(secrets=None, **overrides):
    payload = {
        "name": "warehouse",
        "db_type": "greenplum",
        "connection_config": {
            "host": "gp.example.com", "port": 5432,
            "dbname": "analytics", "readonly_user": "ro_user",
        },
    }
    if secrets is not None:
        payload["secrets"] = secrets
    payload.update(overrides)
    return payload


class TestDataSources:
    def test_create_strips_secrets_from_response(self, client, admin_headers,
                                                 fake_db, evict_spy):
        r = client.post("/api/integrations/data-sources", headers=admin_headers,
                        json=_gp_payload(secrets={"readonly_password": SECRET}))
        assert r.status_code == 200
        ds_id = r.json()["id"]

        r = client.get("/api/integrations/data-sources", headers=admin_headers)
        rows = r.json()["data_sources"]
        assert len(rows) == 1 and rows[0]["id"] == ds_id
        assert rows[0]["has_secrets"] is True
        assert "password" not in rows[0]["connection_config"]
        assert "readonly_password" not in rows[0]["connection_config"]
        _assert_no_secret(r.json())

    def test_secrets_encrypted_at_rest(self, client, admin_headers, fake_db):
        client.post("/api/integrations/data-sources", headers=admin_headers,
                    json=_gp_payload(secrets={"readonly_password": SECRET}))
        blob = fake_db.data_sources[1]["secrets_encrypted"]
        assert SECRET.encode() not in bytes(blob)

    def test_plaintext_password_in_body_never_stored_in_config(
            self, client, admin_headers, fake_db):
        """Secret keys accidentally sent inside connection_config are dropped."""
        payload = _gp_payload()
        payload["connection_config"]["password"] = SECRET
        client.post("/api/integrations/data-sources", headers=admin_headers,
                    json=payload)
        _assert_no_secret(fake_db.data_sources[1]["connection_config"])
        _assert_no_secret(fake_db.audit)

    def test_legacy_plaintext_row_is_stripped_and_flagged(
            self, client, admin_headers, fake_db):
        fake_db.data_sources[7] = {
            "id": 7, "site_id": SITE_ID, "name": "legacy", "db_type": "greenplum",
            "connection_config": {"host": "h", "password": SECRET},
            "secrets_encrypted": None, "is_active": True,
        }
        r = client.get("/api/integrations/data-sources", headers=admin_headers)
        row = r.json()["data_sources"][0]
        assert row["has_secrets"] is True
        _assert_no_secret(r.json())

    def test_update_without_secrets_preserves_blob(self, client, admin_headers, fake_db):
        client.post("/api/integrations/data-sources", headers=admin_headers,
                    json=_gp_payload(secrets={"readonly_password": SECRET}))
        original_blob = fake_db.data_sources[1]["secrets_encrypted"]

        r = client.put("/api/integrations/data-sources/1", headers=admin_headers,
                       json=_gp_payload(name="renamed"))
        assert r.status_code == 200
        assert fake_db.data_sources[1]["name"] == "renamed"
        assert fake_db.data_sources[1]["secrets_encrypted"] == original_blob

        client.put("/api/integrations/data-sources/1", headers=admin_headers,
                   json=_gp_payload(secrets={"readonly_password": "rotated"}))
        assert fake_db.data_sources[1]["secrets_encrypted"] != original_blob

    def test_mutations_evict_site_resources(self, client, admin_headers,
                                            fake_db, evict_spy):
        client.post("/api/integrations/data-sources", headers=admin_headers,
                    json=_gp_payload())
        client.put("/api/integrations/data-sources/1", headers=admin_headers,
                   json=_gp_payload())
        client.delete("/api/integrations/data-sources/1", headers=admin_headers)
        assert evict_spy == [SITE_ID, SITE_ID, SITE_ID]

    def test_delete_is_soft(self, client, admin_headers, fake_db):
        client.post("/api/integrations/data-sources", headers=admin_headers,
                    json=_gp_payload())
        r = client.delete("/api/integrations/data-sources/1", headers=admin_headers)
        assert r.status_code == 200
        assert fake_db.data_sources[1]["is_active"] is False

    def test_other_sites_rows_are_invisible(self, client, admin_headers, fake_db):
        fake_db.data_sources[9] = {
            "id": 9, "site_id": 999, "name": "foreign", "db_type": "greenplum",
            "connection_config": {}, "secrets_encrypted": None, "is_active": True,
        }
        r = client.get("/api/integrations/data-sources", headers=admin_headers)
        assert r.json()["data_sources"] == []
        for method, path in [("PUT", "/api/integrations/data-sources/9"),
                             ("DELETE", "/api/integrations/data-sources/9"),
                             ("POST", "/api/integrations/data-sources/9/test")]:
            r = client.request(method, path, headers=admin_headers,
                               json=_gp_payload())
            assert r.status_code == 404

    def test_pre_save_test_unsupported_dialect(self, client, admin_headers):
        r = client.post("/api/integrations/data-sources/test", headers=admin_headers,
                        json=_gp_payload(db_type="db2"))
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is False
        assert "db2" in body["error"]
