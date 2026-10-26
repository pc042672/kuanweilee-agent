"""Tests for backend/auth.py — JWT, Google OAuth, FastAPI dependencies."""

import os
import time
import pytest

os.environ.setdefault("JWT_SECRET", "test-secret-for-tests")

from auth import (
    UserContext,
    create_session_jwt,
    verify_session_jwt,
    _b64url_encode,
    _b64url_decode,
    get_current_user,
    require_role,
)


class TestBase64Helpers:
    def test_roundtrip(self):
        data = b"hello world"
        encoded = _b64url_encode(data)
        assert _b64url_decode(encoded) == data

    def test_padding_stripped(self):
        encoded = _b64url_encode(b"ab")
        assert "=" not in encoded

    def test_empty_bytes(self):
        assert _b64url_decode(_b64url_encode(b"")) == b""


class TestSessionJWT:
    def test_create_and_verify(self, jwt_payload):
        token = create_session_jwt(jwt_payload)
        decoded = verify_session_jwt(token)
        assert decoded["user_id"] == 42
        assert decoded["email"] == "alice@example.com"
        assert decoded["site_id"] == 5
        assert decoded["role"] == "admin"

    def test_expiry_is_set(self, jwt_payload):
        token = create_session_jwt(jwt_payload)
        decoded = verify_session_jwt(token)
        assert "exp" in decoded
        assert decoded["exp"] > time.time()

    def test_malformed_token_raises(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            verify_session_jwt("not.valid")
        assert exc_info.value.status_code == 401

    def test_tampered_signature_raises(self, jwt_payload):
        from fastapi import HTTPException
        token = create_session_jwt(jwt_payload)
        parts = token.split(".")
        parts[2] = parts[2][::-1]  # reverse the signature
        tampered = ".".join(parts)
        with pytest.raises(HTTPException) as exc_info:
            verify_session_jwt(tampered)
        assert exc_info.value.status_code == 401

    def test_expired_token_raises(self, jwt_payload):
        from fastapi import HTTPException
        import auth
        original_expiry = auth.JWT_EXPIRY_SECONDS
        auth.JWT_EXPIRY_SECONDS = -1
        try:
            token = create_session_jwt(jwt_payload)
        finally:
            auth.JWT_EXPIRY_SECONDS = original_expiry
        with pytest.raises(HTTPException) as exc_info:
            verify_session_jwt(token)
        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    def test_preserves_extra_fields(self):
        payload = {"user_id": 1, "custom_field": "value", "site_id": 1, "role": "admin", "email": "x@x.com"}
        token = create_session_jwt(payload)
        decoded = verify_session_jwt(token)
        assert decoded["custom_field"] == "value"


class TestUserContext:
    def test_frozen(self):
        ctx = UserContext(user_id=1, email="a@b.com", name="A", site_id=1, role="admin")
        with pytest.raises(AttributeError):
            ctx.user_id = 2

    def test_fields(self):
        ctx = UserContext(user_id=1, email="a@b.com", name="A", site_id=2, role="member")
        assert ctx.user_id == 1
        assert ctx.site_id == 2
        assert ctx.role == "member"


class TestRequireRole:
    def test_factory_returns_dependency(self):
        dep = require_role("admin", "owner")
        assert callable(dep)
