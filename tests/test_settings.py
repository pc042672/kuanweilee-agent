"""Tests for backend/settings.py — centralized configuration."""

import os
import importlib
import pytest


@pytest.fixture(autouse=True)
def _restore_settings_module():
    """Reload settings AFTER monkeypatch restores env vars.

    Tests here reload the settings module with mutated env; without this,
    the module object keeps stale values (e.g. an unreachable DATABASE_URL)
    that poison every test that runs afterwards.
    """
    yield
    import settings
    importlib.reload(settings)


class TestSettings:
    def test_defaults_when_no_env(self):
        import settings
        # LOG_LEVEL comes from env var or config/env/{APP_ENV}.json
        assert settings.LOG_LEVEL in ("INFO", "DEBUG")
        assert settings.JWT_EXPIRY_SECONDS == int(os.environ.get("JWT_EXPIRY_SECONDS", "86400"))
        assert settings.GCP_LOCATION == os.environ.get("GCP_LOCATION", "us-central1")
        assert settings.GP_PORT == os.environ.get("GP_PORT", "5432")

    def test_database_url_from_env(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg2://user:pass@host:5432/testdb")
        import settings
        importlib.reload(settings)
        assert settings.DATABASE_URL == "postgresql+psycopg2://user:pass@host:5432/testdb"

    def test_database_url_none_when_unset(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        import settings
        importlib.reload(settings)
        assert settings.DATABASE_URL is None

    def test_gcp_project_id(self, monkeypatch):
        monkeypatch.setenv("GCP_PROJECT_ID", "gen-lang-client-0415822016")
        import settings
        importlib.reload(settings)
        assert settings.GCP_PROJECT_ID == "gen-lang-client-0415822016"

    def test_dev_user_email(self, monkeypatch):
        monkeypatch.setenv("DEV_USER_EMAIL", "dev@test.com")
        import settings
        importlib.reload(settings)
        assert settings.DEV_USER_EMAIL == "dev@test.com"

    def test_dev_user_email_none_in_production(self, monkeypatch):
        monkeypatch.delenv("DEV_USER_EMAIL", raising=False)
        import settings
        importlib.reload(settings)
        assert settings.DEV_USER_EMAIL is None

    def test_google_client_id(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "123456.apps.googleusercontent.com")
        import settings
        importlib.reload(settings)
        assert settings.GOOGLE_CLIENT_ID == "123456.apps.googleusercontent.com"

    def test_jwt_secret_default(self, monkeypatch):
        monkeypatch.delenv("JWT_SECRET", raising=False)
        import settings
        importlib.reload(settings)
        assert settings.JWT_SECRET == "dev-secret-change-in-production"

    def test_cors_origins(self, monkeypatch):
        monkeypatch.setenv("CORS_ORIGINS", "https://app.example.com,https://admin.example.com")
        import settings
        importlib.reload(settings)
        assert "https://app.example.com" in settings.CORS_ORIGINS

    def test_enable_cloud_logging_bool(self, monkeypatch):
        monkeypatch.setenv("ENABLE_CLOUD_LOGGING", "true")
        import settings
        importlib.reload(settings)
        assert settings.ENABLE_CLOUD_LOGGING is True

    def test_enable_cloud_logging_false_by_default(self, monkeypatch):
        monkeypatch.delenv("ENABLE_CLOUD_LOGGING", raising=False)
        import settings
        importlib.reload(settings)
        assert settings.ENABLE_CLOUD_LOGGING is False

    def test_gp_readonly_falls_back_to_gp_user(self, monkeypatch):
        monkeypatch.setenv("GP_USER", "myuser")
        monkeypatch.delenv("GP_READONLY_USER", raising=False)
        import settings
        importlib.reload(settings)
        assert settings.GP_READONLY_USER == "myuser"

    def test_all_settings_importable(self):
        """Verify all expected settings exist as module attributes."""
        import settings
        expected = [
            "DATABASE_URL", "GOOGLE_CLIENT_ID", "JWT_SECRET", "JWT_EXPIRY_SECONDS",
            "DEV_USER_EMAIL", "API_KEY", "CORS_ORIGINS", "LOG_LEVEL",
            "ENABLE_CLOUD_LOGGING", "GCP_PROJECT_ID", "GCP_LOCATION",
            "GP_HOST", "GP_PORT", "GP_USER", "GP_PASSWORD", "GP_DBNAME",
            "GP_READONLY_USER", "GP_READONLY_PASSWORD",
        ]
        for attr in expected:
            assert hasattr(settings, attr), f"Missing setting: {attr}"


class TestSettingsIntegrationWithGCP:
    """Test with AI CDP Dev project configuration."""

    def test_gcp_project_config(self, monkeypatch):
        monkeypatch.setenv("GCP_PROJECT_ID", "gen-lang-client-0415822016")
        monkeypatch.setenv("GCP_LOCATION", "us-central1")
        import settings
        importlib.reload(settings)
        assert settings.GCP_PROJECT_ID == "gen-lang-client-0415822016"
        assert settings.GCP_LOCATION == "us-central1"

    def test_production_like_config(self, monkeypatch):
        """Simulate a production-like configuration."""
        monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg2://app:secret@10.0.0.1:5432/ai_cdp")
        monkeypatch.setenv("GCP_PROJECT_ID", "gen-lang-client-0415822016")
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "0415822016.apps.googleusercontent.com")
        monkeypatch.setenv("JWT_SECRET", "production-secret-key-here")
        monkeypatch.setenv("ENABLE_CLOUD_LOGGING", "true")
        monkeypatch.delenv("DEV_USER_EMAIL", raising=False)

        import settings
        importlib.reload(settings)

        assert settings.DATABASE_URL is not None
        assert settings.GCP_PROJECT_ID == "gen-lang-client-0415822016"
        assert settings.GOOGLE_CLIENT_ID is not None
        assert settings.JWT_SECRET != "dev-secret-change-in-production"
        assert settings.ENABLE_CLOUD_LOGGING is True
        assert settings.DEV_USER_EMAIL is None
