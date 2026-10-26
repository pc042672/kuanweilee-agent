"""Fernet encryption for per-site secrets (credentials, data-source passwords).

Key: APP_ENCRYPTION_KEY — a urlsafe-base64 32-byte Fernet key. Resolved via
settings._get, so it can come from env, the env config file, or GCP Secret
Manager (secret id 'app-encryption-key'). Generate one with:

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Dev fallback: when unset and DEV_MODE is on, a deterministic key derived from
a fixed string is used (with a loud warning) so local development works
without setup. Rows encrypted with the dev key are NOT portable to prod.
Production with no key fails closed on first use.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
from typing import Optional

from cryptography.fernet import Fernet

logger = logging.getLogger("ai_cdp.crypto")

_fernet: Optional[Fernet] = None


def _resolve_key() -> bytes:
    import settings

    key = settings._get("APP_ENCRYPTION_KEY", "app-encryption-key")
    if key:
        return key.encode() if isinstance(key, str) else key
    if settings.DEV_MODE:
        logger.warning(
            "APP_ENCRYPTION_KEY not set — using a DEV-ONLY derived key. "
            "Secrets encrypted with it are not portable to production."
        )
        return base64.urlsafe_b64encode(hashlib.sha256(b"ai-cdp-dev-key").digest())
    raise RuntimeError(
        "APP_ENCRYPTION_KEY is required in production to store credentials. "
        "Set it in the environment or Secret Manager ('app-encryption-key')."
    )


def get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(_resolve_key())
    return _fernet


def encrypt_json(data: dict) -> bytes:
    """Encrypt a dict of secret values to a Fernet token."""
    return get_fernet().encrypt(json.dumps(data).encode())


def decrypt_json(token: bytes) -> dict:
    """Decrypt a Fernet token back to a dict. Raises InvalidToken on tamper/wrong key."""
    if isinstance(token, memoryview):
        token = bytes(token)
    return json.loads(get_fernet().decrypt(token))


def key_hint(secret: str) -> str:
    """Non-secret display hint: last 4 characters."""
    return f"...{secret[-4:]}" if len(secret) >= 8 else "****"
