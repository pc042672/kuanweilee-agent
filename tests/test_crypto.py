"""Tests for backend/services/crypto.py — Fernet secret encryption."""

import pytest
from cryptography.fernet import Fernet, InvalidToken

import services.crypto as crypto


@pytest.fixture(autouse=True)
def _reset_fernet(monkeypatch):
    """Each test gets a fresh key resolution."""
    crypto._fernet = None
    yield
    crypto._fernet = None


class TestCrypto:
    def test_roundtrip(self, monkeypatch):
        monkeypatch.setenv("APP_ENCRYPTION_KEY", Fernet.generate_key().decode())
        data = {"api_key": "sk-12345", "nested": "value"}
        assert crypto.decrypt_json(crypto.encrypt_json(data)) == data

    def test_tamper_raises_invalid_token(self, monkeypatch):
        monkeypatch.setenv("APP_ENCRYPTION_KEY", Fernet.generate_key().decode())
        token = bytearray(crypto.encrypt_json({"a": 1}))
        token[-1] ^= 0xFF
        with pytest.raises(InvalidToken):
            crypto.decrypt_json(bytes(token))

    def test_wrong_key_raises(self, monkeypatch):
        monkeypatch.setenv("APP_ENCRYPTION_KEY", Fernet.generate_key().decode())
        token = crypto.encrypt_json({"a": 1})
        crypto._fernet = Fernet(Fernet.generate_key())
        with pytest.raises(InvalidToken):
            crypto.decrypt_json(token)

    def test_memoryview_token_accepted(self, monkeypatch):
        """psycopg2 returns BYTEA as memoryview."""
        monkeypatch.setenv("APP_ENCRYPTION_KEY", Fernet.generate_key().decode())
        token = crypto.encrypt_json({"a": 1})
        assert crypto.decrypt_json(memoryview(token)) == {"a": 1}

    def test_dev_mode_fallback_key(self, monkeypatch):
        monkeypatch.delenv("APP_ENCRYPTION_KEY", raising=False)
        import settings
        monkeypatch.setattr(settings, "DEV_MODE", True)
        data = {"k": "v"}
        assert crypto.decrypt_json(crypto.encrypt_json(data)) == data

    def test_prod_without_key_fails_closed(self, monkeypatch):
        monkeypatch.delenv("APP_ENCRYPTION_KEY", raising=False)
        monkeypatch.delenv("GCP_PROJECT_ID", raising=False)
        import settings
        monkeypatch.setattr(settings, "DEV_MODE", False)
        with pytest.raises(RuntimeError, match="APP_ENCRYPTION_KEY"):
            crypto.get_fernet()

    def test_key_hint_masks(self):
        assert crypto.key_hint("AIzaSyD-1234567890k3F9") == "...k3F9"
        assert crypto.key_hint("short") == "****"
