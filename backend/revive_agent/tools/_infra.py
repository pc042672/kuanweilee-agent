"""
Shared infrastructure factories used across tool modules.

Tools call get_query_service() / get_profiler() / get_config() instead of
importing module-level singletons. Resources are cached per-site via
SiteResourceManager.
"""

import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from context import get_request_context_or_none
from site_resources import get_site_resources

_DEFAULT_SITE_ID = 1


def get_site_id() -> int:
    """Caller's site from request context, falling back to the dev default."""
    ctx = get_request_context_or_none()
    return ctx.site_id if ctx is not None else _DEFAULT_SITE_ID


def resolve_or_refuse(tool_name: str, service: str):
    """(creds, None) when the site's integration resolves, else (None, refusal)."""
    from services.credentials import resolve_credentials, service_not_configured_result

    creds = resolve_credentials(get_site_id(), service)
    if creds is None:
        return None, service_not_configured_result(tool_name, service)
    return creds, None


def _get_resources():
    return get_site_resources(get_site_id())


def get_query_service():
    return _get_resources().query_service


def get_profiler():
    return _get_resources().profiler


def get_config():
    return _get_resources().config_manager
