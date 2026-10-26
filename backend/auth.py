"""
Authentication: Google OAuth ID token verification + session JWT.

Flow:
  1. Frontend sends Google ID token to POST /api/auth/login
  2. Backend verifies via google.oauth2.id_token
  3. Backend upserts user, resolves site membership
  4. Backend returns a signed session JWT
  5. Subsequent requests send Authorization: Bearer <session-jwt>

Dev mode: DEV_USER_EMAIL env var bypasses Google OAuth for local development.
"""

import time
import hmac
import hashlib
import json
import base64
import logging
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import settings

logger = logging.getLogger(__name__)

GOOGLE_CLIENT_ID = settings.GOOGLE_CLIENT_ID
JWT_SECRET = settings.JWT_SECRET
JWT_EXPIRY_SECONDS = settings.JWT_EXPIRY_SECONDS
DEV_USER_EMAIL = settings.DEV_USER_EMAIL
_API_KEY = settings.API_KEY

_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class UserContext:
    user_id: int
    email: str
    name: str
    site_id: int
    role: str


_DEV_CTX = UserContext(
    user_id=1, email=DEV_USER_EMAIL or "dev@localhost",
    name="Dev User", site_id=1, role="admin",
)



def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    return base64.urlsafe_b64decode(s + "=" * padding)


def create_session_jwt(payload: dict) -> str:
    """Create a minimal HMAC-SHA256 signed JWT."""
    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload_with_exp = {**payload, "exp": int(time.time()) + JWT_EXPIRY_SECONDS}
    body = _b64url_encode(json.dumps(payload_with_exp).encode())
    signature = hmac.new(JWT_SECRET.encode(), f"{header}.{body}".encode(), hashlib.sha256).digest()
    sig = _b64url_encode(signature)
    return f"{header}.{body}.{sig}"


def verify_session_jwt(token: str) -> dict:
    """Verify and decode a session JWT. Raises HTTPException on failure."""
    try:
        header_b64, body_b64, sig_b64 = token.split(".")
    except ValueError:
        raise HTTPException(status_code=401, detail="Malformed token")

    expected_sig = hmac.new(
        JWT_SECRET.encode(), f"{header_b64}.{body_b64}".encode(), hashlib.sha256
    ).digest()

    if not hmac.compare_digest(expected_sig, _b64url_decode(sig_b64)):
        raise HTTPException(status_code=401, detail="Invalid token signature")

    payload = json.loads(_b64url_decode(body_b64))

    if payload.get("exp", 0) < time.time():
        raise HTTPException(status_code=401, detail="Token expired")

    return payload


def verify_google_id_token(id_token_str: str) -> dict:
    """Verify a Google ID token and return the payload (sub, email, name, picture)."""
    from google.oauth2 import id_token
    from google.auth.transport import requests as google_requests

    if not GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=500,
            detail="GOOGLE_CLIENT_ID not configured",
        )

    try:
        idinfo = id_token.verify_oauth2_token(
            id_token_str, google_requests.Request(), GOOGLE_CLIENT_ID
        )
    except ValueError as e:
        raise HTTPException(status_code=401, detail=f"Invalid Google ID token: {e}")

    return {
        "google_id": idinfo["sub"],
        "email": idinfo["email"],
        "name": idinfo.get("name", ""),
        "avatar_url": idinfo.get("picture", ""),
    }


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> UserContext:
    """Verify session JWT and return UserContext.

    Priority:
      1. Bearer token (session JWT) — normal flow, honored even in DEV_MODE
         so role/site semantics stay testable
      2. X-API-Key header — legacy backward compat
      3. DEV_MODE with no credentials — dev admin context
    """
    if settings.DEV_MODE and not (credentials and credentials.credentials):
        return _DEV_CTX

    if credentials and credentials.credentials:
        payload = verify_session_jwt(credentials.credentials)
        return UserContext(
            user_id=payload["user_id"],
            email=payload["email"],
            name=payload.get("name", ""),
            site_id=payload["site_id"],
            role=payload["role"],
        )

    api_key = request.headers.get("X-API-Key")
    if _API_KEY and api_key == _API_KEY:
        return UserContext(
            user_id=1,
            email="api-key-user@legacy",
            name="API Key User",
            site_id=1,
            role="admin",
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing or invalid authentication",
    )


def require_role(*allowed_roles: str):
    """Factory for role-based access control dependency."""
    async def check(user: UserContext = Depends(get_current_user)) -> UserContext:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role}' not authorized",
            )
        return user
    return check


require_admin = require_role("admin", "owner")
require_member = require_role("admin", "owner", "member")
