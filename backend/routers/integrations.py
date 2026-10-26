"""Integrations API: per-site data sources + external service credentials.

Reads need any authenticated user; writes are admin/owner only. site_id always
comes from the caller's JWT context — never from the request body. Secret
values are write-only: no GET response ever contains them.
"""

import json
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from backend.auth import UserContext, get_current_user, require_admin
from backend.db import get_engine
from backend.dbtoolbox import SECRET_CONNECTION_KEYS
from backend.services import credentials as credentials_service
from backend.services.crypto import decrypt_json, encrypt_json
from backend.site_resources import evict_site_resources

logger = logging.getLogger("ai_cdp.integrations")

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


def _require_engine():
    engine = get_engine()
    if engine is None:
        raise HTTPException(
            status_code=503,
            detail="DATABASE_URL not configured — integrations need the app database",
        )
    return engine


# ==================== External services ====================

class ServiceCredentialsRequest(BaseModel):
    secrets: Dict[str, str] = {}
    metadata: Dict[str, str] = {}


@router.get("/services")
async def list_services(user: UserContext = Depends(get_current_user)):
    """Status of every known external service for the caller's site (no secrets).

    gated_tools maps agent tool name -> services it requires, so the UI can
    show which tools an unconfigured service disables.
    """
    from backend.tools_registry import required_services_map

    return {
        "services": list(credentials_service.status(user.site_id).values()),
        "gated_tools": {
            tool: list(services) for tool, services in required_services_map().items()
        },
    }


@router.put("/services/{service}")
async def upsert_service(
    service: str,
    request: ServiceCredentialsRequest,
    user: UserContext = Depends(require_admin),
):
    try:
        credentials_service.upsert_credentials(
            user.site_id, service, request.secrets, request.metadata, user.user_id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return {"success": True, "service": service}


@router.delete("/services/{service}")
async def delete_service(service: str, user: UserContext = Depends(require_admin)):
    if service not in credentials_service.KNOWN_SERVICES:
        raise HTTPException(status_code=400, detail=f"Unknown service '{service}'")
    credentials_service.delete_credentials(user.site_id, service, user.user_id)
    return {"success": True, "service": service}


@router.post("/services/{service}/test")
async def test_service(service: str, user: UserContext = Depends(require_admin)):
    """Live connectivity check using the site's stored (or env-fallback) credentials."""
    try:
        return credentials_service.test_credentials(user.site_id, service)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== Data sources ====================

class DataSourceRequest(BaseModel):
    name: str = "default"
    db_type: str = "greenplum"
    connection_config: Dict[str, Any] = {}
    secrets: Optional[Dict[str, str]] = None  # {password?, readonly_password?}
    is_active: bool = True


def _strip_secrets(connection_config: dict) -> dict:
    return {k: v for k, v in (connection_config or {}).items() if k not in SECRET_CONNECTION_KEYS}


def _row_response(row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "db_type": row["db_type"],
        "connection_config": _strip_secrets(row["connection_config"]),
        "is_active": row["is_active"],
        "has_secrets": row["secrets_encrypted"] is not None
        or bool(SECRET_CONNECTION_KEYS & set((row["connection_config"] or {}).keys())),
    }


def _load_row(engine, site_id: int, ds_id: int):
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT id, name, db_type, connection_config, secrets_encrypted, is_active "
                "FROM data_sources WHERE id = :id AND site_id = :sid"
            ),
            {"id": ds_id, "sid": site_id},
        ).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Data source not found")
    return row


def _audit_data_source(site_id: int, action: str, user_id: int, summary: dict) -> None:
    try:
        engine = get_engine()
        if engine is None:
            return
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO config_audit_log "
                    "(site_id, config_type, action, changed_by, new_data) "
                    "VALUES (:sid, 'data_sources', :action, :uid, :data)"
                ),
                {"sid": site_id, "action": action, "uid": user_id, "data": json.dumps(summary)},
            )
    except Exception as e:
        logger.warning("data_source audit failed: %s", e)


@router.get("/data-sources")
async def list_data_sources(user: UserContext = Depends(get_current_user)):
    engine = _require_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT id, name, db_type, connection_config, secrets_encrypted, is_active "
                "FROM data_sources WHERE site_id = :sid ORDER BY id"
            ),
            {"sid": user.site_id},
        ).mappings().all()
    return {"data_sources": [_row_response(r) for r in rows]}


@router.post("/data-sources")
async def create_data_source(
    request: DataSourceRequest, user: UserContext = Depends(require_admin)
):
    engine = _require_engine()
    blob = encrypt_json(request.secrets) if request.secrets else None
    with engine.begin() as conn:
        ds_id = conn.execute(
            text(
                "INSERT INTO data_sources "
                "(site_id, name, db_type, connection_config, secrets_encrypted, is_active) "
                "VALUES (:sid, :name, :db_type, :cfg, :blob, :active) RETURNING id"
            ),
            {
                "sid": user.site_id,
                "name": request.name,
                "db_type": request.db_type,
                "cfg": json.dumps(_strip_secrets(request.connection_config)),
                "blob": blob,
                "active": request.is_active,
            },
        ).scalar()
    _audit_data_source(
        user.site_id, "create", user.user_id,
        {"id": ds_id, "name": request.name, "db_type": request.db_type},
    )
    evict_site_resources(user.site_id)
    return {"success": True, "id": ds_id}


@router.put("/data-sources/{ds_id}")
async def update_data_source(
    ds_id: int, request: DataSourceRequest, user: UserContext = Depends(require_admin)
):
    engine = _require_engine()
    _load_row(engine, user.site_id, ds_id)  # 404 if not this site's row

    params = {
        "id": ds_id,
        "sid": user.site_id,
        "name": request.name,
        "db_type": request.db_type,
        "cfg": json.dumps(_strip_secrets(request.connection_config)),
        "active": request.is_active,
    }
    # Omitted secrets → preserve the existing encrypted blob
    secrets_clause = ""
    if request.secrets is not None:
        secrets_clause = ", secrets_encrypted = :blob"
        params["blob"] = encrypt_json(request.secrets)

    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE data_sources SET name = :name, db_type = :db_type, "
                f"connection_config = :cfg, is_active = :active, updated_at = NOW(){secrets_clause} "
                "WHERE id = :id AND site_id = :sid"
            ),
            params,
        )
    _audit_data_source(
        user.site_id, "update", user.user_id,
        {"id": ds_id, "name": request.name, "db_type": request.db_type},
    )
    evict_site_resources(user.site_id)
    return {"success": True, "id": ds_id}


@router.delete("/data-sources/{ds_id}")
async def delete_data_source(ds_id: int, user: UserContext = Depends(require_admin)):
    engine = _require_engine()
    _load_row(engine, user.site_id, ds_id)
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE data_sources SET is_active = false, updated_at = NOW() "
                "WHERE id = :id AND site_id = :sid"
            ),
            {"id": ds_id, "sid": user.site_id},
        )
    _audit_data_source(user.site_id, "delete", user.user_id, {"id": ds_id})
    evict_site_resources(user.site_id)
    return {"success": True, "id": ds_id}


@router.post("/data-sources/test")
async def test_data_source_config(
    request: DataSourceRequest, user: UserContext = Depends(require_admin)
):
    """Pre-save connectivity test from request values (secrets required here)."""
    return _test_connection(request.db_type, request.connection_config, request.secrets or {})


@router.post("/data-sources/{ds_id}/test")
async def test_data_source(ds_id: int, user: UserContext = Depends(require_admin)):
    """Connectivity test for a stored data source (uses its encrypted secrets)."""
    engine = _require_engine()
    row = _load_row(engine, user.site_id, ds_id)
    secrets = {}
    if row["secrets_encrypted"] is not None:
        try:
            secrets = decrypt_json(row["secrets_encrypted"])
        except Exception as e:
            return {"ok": False, "error": f"Could not decrypt stored secrets: {e}"}
    return _test_connection(row["db_type"], dict(row["connection_config"] or {}), secrets)


def _test_connection(db_type: str, connection_config: dict, secrets: dict) -> dict:
    from backend.dbtoolbox import Source, SourceConfig

    cfg = {**connection_config, **secrets}
    source = Source(SourceConfig.from_data_source_row(
        {"db_type": db_type, "connection_config": cfg}
    ))
    try:
        # test_connection reports all failures (incl. unsupported dialect) as ok=False
        return source.test_connection()
    finally:
        source.dispose()
