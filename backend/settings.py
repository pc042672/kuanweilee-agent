"""
Centralized application settings. Single source of truth for all config.

Environment is controlled by APP_ENV (dev/staging/prod).
Each environment loads defaults from config/env/{APP_ENV}.json.
Env vars override config file values. Secret Manager is the final fallback.
"""

import json
import os
from pathlib import Path

# -- Environment --
APP_ENV: str = os.environ.get("APP_ENV", "dev")  # dev | staging | prod

# Load environment config file
_env_config: dict = {}
_env_file = Path(__file__).resolve().parent.parent / "config" / "env" / f"{APP_ENV}.json"
if _env_file.exists():
    with open(_env_file) as f:
        _env_config = json.load(f)


def _get(key: str, secret_id: str = None, default=None):
    """Read: env var → env config file → Secret Manager → default."""
    val = os.environ.get(key)
    if val is not None:
        return val
    config_key = key.lower()
    if config_key in _env_config:
        return _env_config[config_key]
    if secret_id and os.environ.get("GCP_PROJECT_ID"):
        try:
            from secret_manager import get_secret
            return get_secret(secret_id)
        except Exception as e:
            import logging
            logging.getLogger(__name__).debug("Secret Manager fallback failed for %s: %s", secret_id, e)
    return default


def _bool(key: str, default: bool = False) -> bool:
    val = _get(key)
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    return str(val).lower() == "true"


# -- GCP --
GCP_PROJECT_ID: str | None = os.environ.get("GCP_PROJECT_ID")
GCP_LOCATION: str = _get("GCP_LOCATION", default="us-central1")

# -- Database --
DATABASE_URL: str | None = _get("DATABASE_URL", "database-url")

# -- Auth --
GOOGLE_CLIENT_ID: str | None = _get("GOOGLE_CLIENT_ID", "google-client-id")
JWT_SECRET: str = _get("JWT_SECRET", "jwt-secret", "dev-secret-change-in-production")
JWT_EXPIRY_SECONDS: int = int(_get("JWT_EXPIRY_SECONDS", default="86400"))
DEV_USER_EMAIL: str | None = os.environ.get("DEV_USER_EMAIL") or None
AUTH_REQUIRED: bool = _bool("AUTH_REQUIRED", default=(APP_ENV != "dev"))
# Explicit DEV_MODE env var wins; otherwise inferred from APP_ENV/DEV_USER_EMAIL.
DEV_MODE: bool = _bool("DEV_MODE", default=((APP_ENV == "dev") or DEV_USER_EMAIL is not None))
API_KEY: str | None = _get("API_KEY", "api-key")

# -- Server --
CORS_ORIGINS: str = os.environ.get("CORS_ORIGINS", "")
if not CORS_ORIGINS and isinstance(_env_config.get("cors_origins"), list):
    CORS_ORIGINS = ",".join(_env_config["cors_origins"])

# -- Security --
ENABLE_MODEL_GUARD: bool = _bool("ENABLE_MODEL_GUARD")
RATE_LIMIT_ENABLED: bool = _bool("RATE_LIMIT_ENABLED", default=(APP_ENV != "dev"))

# -- Logging & Observability --
LOG_LEVEL: str = _get("LOG_LEVEL", default="INFO")
ENABLE_CLOUD_LOGGING: bool = _bool("ENABLE_CLOUD_LOGGING")
ENABLE_CLOUD_TRACE: bool = _bool("ENABLE_CLOUD_TRACE")

# -- Greenplum / Analytics DB --
GP_HOST: str = _get("GP_HOST", default="localhost")
GP_PORT: str = _get("GP_PORT", default="5432")
GP_USER: str = _get("GP_USER", default="gpadmin")
GP_PASSWORD: str = _get("GP_PASSWORD", default="pivotal")
GP_DBNAME: str = _get("GP_DBNAME", default="dev")
GP_READONLY_USER: str = os.environ.get("GP_READONLY_USER", GP_USER)
GP_READONLY_PASSWORD: str = os.environ.get("GP_READONLY_PASSWORD", GP_PASSWORD)
