"""Per-site external-service credential registry and resolver.

Credentials are stored Fernet-encrypted in external_credentials (one row per
site+service). Tools resolve them at the tool boundary; a service with no
credentials (and no env fallback) is unavailable for that site.

Env fallback keeps dev and existing single-tenant deployments working:
enabled when DEV_MODE or CREDENTIAL_ENV_FALLBACK=true (the default).

NOTE on the dual-import quirk (backend.* vs bare imports): two instances of
this module's cache can exist. Harmless — the TTL is short and router-path
writes call invalidate() on the instance that serves reads via backend.*.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

logger = logging.getLogger("ai_cdp.credentials")

_CACHE_TTL_SECONDS = 60


@dataclass(frozen=True)
class ServiceDef:
    key: str
    label: str
    secret_fields: Tuple[str, ...]
    metadata_fields: Tuple[str, ...] = ()
    # secret/metadata field -> env var names tried in order
    env_fallback: Dict[str, Tuple[str, ...]] = field(default_factory=dict)


KNOWN_SERVICES: Dict[str, ServiceDef] = {
    "gemini": ServiceDef(
        key="gemini",
        label="Google Gemini API",
        secret_fields=("api_key",),
        env_fallback={"api_key": ("GEMINI_API_KEY", "GOOGLE_API_KEY")},
    ),
    "vertex_ai": ServiceDef(
        key="vertex_ai",
        label="Vertex AI (Vector Search)",
        secret_fields=(),
        metadata_fields=("project_id", "location"),
        env_fallback={
            "project_id": ("GCP_PROJECT_ID",),
            "location": ("GCP_LOCATION",),
        },
    ),
}


_cache: Dict[Tuple[int, str], Tuple[float, Optional[dict]]] = {}
_cache_lock = threading.Lock()


def _env_fallback_enabled() -> bool:
    import settings

    if settings.DEV_MODE:
        return True
    return str(os.environ.get("CREDENTIAL_ENV_FALLBACK", "true")).lower() == "true"


def _resolve_from_env(service: ServiceDef) -> Optional[dict]:
    resolved = {}
    for fld, env_names in service.env_fallback.items():
        for name in env_names:
            value = os.environ.get(name)
            if value:
                resolved[fld] = value
                break
    required = set(service.secret_fields) | set(service.metadata_fields)
    if required and not required.issubset(resolved):
        return None
    return resolved or None


def _load_db_row(site_id: int, service: str) -> Optional[dict]:
    """Decrypted secrets merged with metadata, or None when not configured."""
    from db import get_engine
    from sqlalchemy import text

    engine = get_engine()
    if engine is None:
        return None
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT credentials_encrypted, metadata FROM external_credentials "
                "WHERE site_id = :sid AND service = :svc AND is_active"
            ),
            {"sid": site_id, "svc": service},
        ).mappings().first()
    if row is None:
        return None
    from services.crypto import decrypt_json

    secrets = decrypt_json(row["credentials_encrypted"])
    metadata = dict(row["metadata"] or {})
    metadata.pop("key_hint", None)
    return {**metadata, **secrets}


def resolve_credentials(site_id: int, service: str) -> Optional[dict]:
    """Resolve a site's credentials for a service: DB row, then env fallback.

    Returns the merged secret+metadata dict, or None = service unconfigured.
    """
    service_def = KNOWN_SERVICES.get(service)
    if service_def is None:
        return None

    key = (site_id, service)
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(key)
        if cached and (now - cached[0]) < _CACHE_TTL_SECONDS:
            return cached[1]

    resolved: Optional[dict] = None
    try:
        resolved = _load_db_row(site_id, service)
    except Exception as e:
        logger.warning("credential lookup failed for site=%s service=%s: %s", site_id, service, e)
    if resolved is None and _env_fallback_enabled():
        resolved = _resolve_from_env(service_def)

    with _cache_lock:
        _cache[key] = (now, resolved)
    return resolved


def is_configured(site_id: int, service: str) -> bool:
    return resolve_credentials(site_id, service) is not None


# Single user-facing sentence shared by every refusal path (plugin, tools, routers)
CONFIGURE_HINT = "An admin can configure it under Settings → Integrations → External Services."


def unavailable_detail(service: str) -> str:
    sdef = KNOWN_SERVICES.get(service)
    label = sdef.label if sdef else service
    return (
        f"The '{service}' integration ({label}) is not configured for this site. "
        f"{CONFIGURE_HINT}"
    )


def service_not_configured_result(tool_name: str, service: str) -> dict:
    """Structured refusal shared by ServiceGatingPlugin and fail-closed tools."""
    sdef = KNOWN_SERVICES.get(service)
    label = sdef.label if sdef else service
    return {
        "success": False,
        "error_type": "service_not_configured",
        "error": (
            f"{tool_name} requires the '{service}' integration ({label}), "
            "which is not configured for this site."
        ),
        "suggestion": CONFIGURE_HINT,
    }


def require_credentials(site_id: int, service: str) -> dict:
    """Resolved credentials or HTTP 409 — the router-path fail-closed guard."""
    creds = resolve_credentials(site_id, service)
    if creds is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=409, detail=unavailable_detail(service))
    return creds


def invalidate(site_id: int) -> None:
    with _cache_lock:
        for key in [k for k in _cache if k[0] == site_id]:
            del _cache[key]


def status(site_id: int) -> Dict[str, dict]:
    """Per-service status for the settings page. NEVER includes secret values."""
    from db import get_engine
    from sqlalchemy import text

    rows: Dict[str, dict] = {}
    engine = get_engine()
    if engine is not None:
        with engine.connect() as conn:
            for row in conn.execute(
                text(
                    "SELECT service, metadata, updated_at FROM external_credentials "
                    "WHERE site_id = :sid AND is_active"
                ),
                {"sid": site_id},
            ).mappings():
                rows[row["service"]] = dict(row)

    result = {}
    for key, sdef in KNOWN_SERVICES.items():
        db_row = rows.get(key)
        source = "db" if db_row else (
            "env" if _env_fallback_enabled() and _resolve_from_env(sdef) else None
        )
        metadata = dict(db_row["metadata"] or {}) if db_row else {}
        result[key] = {
            "service": key,
            "label": sdef.label,
            "configured": source is not None,
            "source": source,
            "metadata": {k: v for k, v in metadata.items() if k != "key_hint"},
            "hint": metadata.get("key_hint"),
            "updated_at": db_row["updated_at"].isoformat() if db_row else None,
            "secret_fields": list(sdef.secret_fields),
            "metadata_fields": list(sdef.metadata_fields),
        }
    return result


def _test_gemini(creds: dict) -> dict:
    from google import genai

    client = genai.Client(api_key=creds["api_key"])
    next(iter(client.models.list()), None)
    return {"ok": True}


def _test_vertex_ai(creds: dict) -> dict:
    import google.auth

    google.auth.default()
    return {"ok": True, "project_id": creds.get("project_id")}


_SERVICE_TESTS = {"gemini": _test_gemini, "vertex_ai": _test_vertex_ai}


def test_credentials(site_id: int, service: str) -> dict:
    """Live connectivity check for the settings-page Test button.

    Raises ValueError for an unknown service; never raises for test failures.
    """
    if service not in KNOWN_SERVICES:
        raise ValueError(f"Unknown service '{service}'")
    creds = resolve_credentials(site_id, service)
    if creds is None:
        return {"ok": False, "error": "Service is not configured for this site"}
    test = _SERVICE_TESTS.get(service)
    if test is None:
        return {"ok": False, "error": f"No test available for '{service}'"}
    try:
        return test(creds)
    except Exception as e:
        return {"ok": False, "error": str(e)}


def upsert_credentials(
    site_id: int, service: str, secrets: dict, metadata: dict, user_id: Optional[int]
) -> None:
    """Encrypt and store credentials; audits with redacted payload."""
    service_def = KNOWN_SERVICES.get(service)
    if service_def is None:
        raise ValueError(f"Unknown service '{service}'")
    missing = [f for f in service_def.secret_fields if not secrets.get(f)]
    missing += [f for f in service_def.metadata_fields if not metadata.get(f)]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")

    from db import get_engine
    from sqlalchemy import text
    from services.crypto import encrypt_json, key_hint

    engine = get_engine()
    if engine is None:
        raise RuntimeError("DATABASE_URL not configured — cannot store credentials")

    display_meta = {k: metadata[k] for k in service_def.metadata_fields if k in metadata}
    first_secret = next((secrets[f] for f in service_def.secret_fields if secrets.get(f)), None)
    if first_secret:
        display_meta["key_hint"] = key_hint(str(first_secret))

    import json as _json

    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO external_credentials "
                "(site_id, service, credentials_encrypted, metadata, is_active, created_by, updated_by) "
                "VALUES (:sid, :svc, :blob, :meta, true, :uid, :uid) "
                "ON CONFLICT (site_id, service) DO UPDATE SET "
                "credentials_encrypted = :blob, metadata = :meta, is_active = true, "
                "updated_by = :uid, updated_at = NOW()"
            ),
            {
                "sid": site_id,
                "svc": service,
                "blob": encrypt_json(secrets),
                "meta": _json.dumps(display_meta),
                "uid": user_id,
            },
        )
    _audit(site_id, service, "update", user_id, display_meta)
    invalidate(site_id)


def delete_credentials(site_id: int, service: str, user_id: Optional[int]) -> None:
    """Soft-delete (is_active=false); audits the revocation."""
    from db import get_engine
    from sqlalchemy import text

    engine = get_engine()
    if engine is None:
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE external_credentials SET is_active = false, "
                "updated_by = :uid, updated_at = NOW() "
                "WHERE site_id = :sid AND service = :svc"
            ),
            {"sid": site_id, "svc": service, "uid": user_id},
        )
    _audit(site_id, service, "delete", user_id, {})
    invalidate(site_id)


def _audit(site_id: int, service: str, action: str, user_id: Optional[int], redacted: dict) -> None:
    """config_audit_log row with REDACTED payload (never secret values)."""
    try:
        from db import get_engine
        from sqlalchemy import text
        import json as _json

        engine = get_engine()
        if engine is None or user_id is None:
            return
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO config_audit_log "
                    "(site_id, config_type, action, changed_by, new_data) "
                    "VALUES (:sid, 'external_credentials', :action, :uid, :data)"
                ),
                {
                    "sid": site_id,
                    "action": action,
                    "uid": user_id,
                    "data": _json.dumps({"service": service, **redacted}),
                },
            )
    except Exception as e:
        logger.warning("credential audit failed: %s", e)
