"""Tests for backend/services/credentials.py — per-site credential resolver."""

import pytest

import services.credentials as creds


@pytest.fixture(autouse=True)
def _clean_cache(monkeypatch):
    creds._cache.clear()
    # No app DB by default — tests exercise env fallback unless they patch _load_db_row
    import db
    monkeypatch.setattr(db, "get_engine", lambda: None)
    yield
    creds._cache.clear()


def _assert_no_secret_values(obj, secret_values):
    if isinstance(obj, dict):
        for v in obj.values():
            _assert_no_secret_values(v, secret_values)
    elif isinstance(obj, list):
        for v in obj:
            _assert_no_secret_values(v, secret_values)
    else:
        for secret in secret_values:
            assert secret not in str(obj), f"Secret value leaked: {obj}"


class TestResolvePrecedence:
    def test_env_fallback_resolves_gemini(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "env-key-123")
        result = creds.resolve_credentials(1, "gemini")
        assert result == {"api_key": "env-key-123"}

    def test_env_fallback_order(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.setenv("GOOGLE_API_KEY", "google-key")
        result = creds.resolve_credentials(1, "gemini")
        assert result == {"api_key": "google-key"}

    def test_db_takes_precedence_over_env(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "env-key")
        monkeypatch.setattr(creds, "_load_db_row", lambda s, svc: {"api_key": "db-key"})
        assert creds.resolve_credentials(1, "gemini") == {"api_key": "db-key"}

    def test_unconfigured_returns_none(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.setattr(creds, "_env_fallback_enabled", lambda: False)
        assert creds.resolve_credentials(1, "gemini") is None
        assert creds.is_configured(1, "gemini") is False

    def test_unknown_service_returns_none(self):
        assert creds.resolve_credentials(1, "nope") is None

    def test_env_fallback_disabled_strict_isolation(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "env-key")
        monkeypatch.setenv("CREDENTIAL_ENV_FALLBACK", "false")
        import settings
        monkeypatch.setattr(settings, "DEV_MODE", False)
        assert creds.resolve_credentials(1, "gemini") is None

    def test_vertex_requires_all_metadata_fields(self, monkeypatch):
        monkeypatch.setenv("GCP_PROJECT_ID", "my-project")
        monkeypatch.delenv("GCP_LOCATION", raising=False)
        # GCP_LOCATION missing → incomplete → unconfigured... unless env default
        result = creds.resolve_credentials(1, "vertex_ai")
        assert result is None


class TestCache:
    def test_cached_within_ttl(self, monkeypatch):
        calls = []

        def fake_load(site_id, service):
            calls.append(1)
            return {"api_key": "k"}

        monkeypatch.setattr(creds, "_load_db_row", fake_load)
        creds.resolve_credentials(1, "gemini")
        creds.resolve_credentials(1, "gemini")
        assert len(calls) == 1

    def test_invalidate_clears_site(self, monkeypatch):
        calls = []

        def fake_load(site_id, service):
            calls.append(1)
            return {"api_key": "k"}

        monkeypatch.setattr(creds, "_load_db_row", fake_load)
        creds.resolve_credentials(1, "gemini")
        creds.invalidate(1)
        creds.resolve_credentials(1, "gemini")
        assert len(calls) == 2

    def test_invalidate_other_site_keeps_cache(self, monkeypatch):
        monkeypatch.setattr(creds, "_load_db_row", lambda s, svc: {"api_key": "k"})
        creds.resolve_credentials(1, "gemini")
        creds.invalidate(2)
        assert (1, "gemini") in creds._cache


class TestStatus:
    def test_status_covers_all_known_services(self):
        result = creds.status(1)
        assert set(result.keys()) == set(creds.KNOWN_SERVICES.keys())
        for svc in result.values():
            assert {"service", "label", "configured", "source", "metadata",
                    "hint", "updated_at", "secret_fields", "metadata_fields"} <= set(svc.keys())

    def test_status_never_contains_secret_values(self, monkeypatch):
        secret = "super-secret-api-key-value"
        monkeypatch.setenv("GEMINI_API_KEY", secret)
        result = creds.status(1)
        _assert_no_secret_values(result, [secret])

    def test_env_configured_shows_env_source(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "env-key")
        result = creds.status(1)
        assert result["gemini"]["configured"] is True
        assert result["gemini"]["source"] == "env"


class TestUpsertValidation:
    def test_unknown_service_raises(self):
        with pytest.raises(ValueError, match="Unknown service"):
            creds.upsert_credentials(1, "nope", {}, {}, user_id=1)

    def test_missing_secret_field_raises(self):
        with pytest.raises(ValueError, match="api_key"):
            creds.upsert_credentials(1, "gemini", {}, {}, user_id=1)

    def test_no_engine_raises_runtime(self, monkeypatch):
        with pytest.raises(RuntimeError, match="DATABASE_URL"):
            creds.upsert_credentials(1, "gemini", {"api_key": "k"}, {}, user_id=1)
