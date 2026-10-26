"""
Secret Manager integration for runtime credential access.

In production (Cloud Run), fetches secrets from Google Cloud Secret Manager.
In development, falls back to environment variables.
"""

import os
import logging

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is None:
        try:
            from google.cloud import secretmanager
            _client = secretmanager.SecretManagerServiceClient()
        except ImportError:
            logger.warning("google-cloud-secret-manager not installed, using env vars only")
    return _client


def get_secret(secret_id: str, project_id: str = None) -> str:
    """Fetch a secret value.

    In production: reads from Secret Manager.
    In development: falls back to environment variable with same name.

    Args:
        secret_id: The secret name (e.g., "db-password").
        project_id: GCP project ID. Defaults to GCP_PROJECT_ID env var.
    """
    # Dev fallback: check env var first (matches secret_id with underscores)
    env_key = secret_id.upper().replace("-", "_")
    env_val = os.environ.get(env_key)
    if env_val:
        return env_val

    client = _get_client()
    if client is None:
        raise ValueError(
            f"Secret '{secret_id}' not found in env var '{env_key}' "
            f"and Secret Manager client unavailable"
        )

    project = project_id or os.environ.get("GCP_PROJECT_ID")
    if not project:
        raise ValueError("GCP_PROJECT_ID env var required for Secret Manager")

    name = f"projects/{project}/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("utf-8")
