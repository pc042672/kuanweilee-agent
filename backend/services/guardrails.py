"""Write guardrails for LLM-invoked mutation tools (financial-grade).

Three layers, applied at the TOOL boundary (an LLM can be prompt-injected
into calling a tool the user never authorized — HTTP-router auth alone is
not enough):

1. authZ — the request's UserContext must carry an editor role
2. HITL  — per-site policy decides which mutations need in-chat confirmation
   (ADK FunctionTool require_confirmation callable)
3. audit — every mutation is recorded via config/action_log

Site policy: sites.settings JSONB key "guardrail_level"
  strict   — confirm EVERY mutation (default)
  standard — confirm destructive ops + external sends only
  trusted  — audit-only, no confirmation
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("ai_cdp.guardrails")

EDITOR_ROLES = {"owner", "admin", "editor"}
DESTRUCTIVE = "destructive"   # deletes, external sends
MUTATING = "mutating"         # upserts


def current_user():
    from context import get_request_context_or_none
    return get_request_context_or_none()


def check_authz(action: str) -> Optional[str]:
    """Return an error string when the caller may not mutate config, else None."""
    ctx = current_user()
    if ctx is None:
        # Dev fallback (matches _infra site_id=1 behavior); prod always has ctx.
        import settings
        if settings.DEV_MODE:
            return None
        return f"Not authorized: no authenticated user for '{action}'"
    if ctx.role not in EDITOR_ROLES:
        logger.warning("authz denied: %s role=%s action=%s", ctx.email, ctx.role, action)
        return f"Not authorized: role '{ctx.role}' may not perform '{action}'"
    return None


def guardrail_level(site_id: Optional[int] = None) -> str:
    """Resolve the site's guardrail level (default strict)."""
    if site_id is None:
        ctx = current_user()
        site_id = ctx.site_id if ctx else 1
    try:
        from db import get_engine
        from sqlalchemy import text
        engine = get_engine()
        if engine is None:
            return "strict"
        with engine.connect() as conn:
            settings_json = conn.execute(
                text("SELECT settings FROM sites WHERE id = :sid"), {"sid": site_id}
            ).scalar()
        if settings_json and isinstance(settings_json, dict):
            return settings_json.get("guardrail_level", "strict")
    except Exception:
        logger.warning("guardrail level lookup failed; defaulting to strict")
    return "strict"


def needs_confirmation(severity: str):
    """Build a require_confirmation callable for FunctionTool.

    severity: DESTRUCTIVE or MUTATING.
    """
    def _check(**_kwargs) -> bool:
        level = guardrail_level()
        if level == "trusted":
            return False
        if level == "standard":
            return severity == DESTRUCTIVE
        return True  # strict

    return _check


def record_action(*, site_id, action_type, target=None, request_data=None,
                  response_data=None, status="succeeded", error_message=None,
                  executed_by=None) -> None:
    """Write one action_executions row (fire-and-forget). Shared audit primitive."""
    from db import get_engine
    engine = get_engine()
    if engine is None:
        return
    from config.action_log import log_action
    log_action(
        engine,
        site_id=site_id,
        action_type=action_type,
        target_node_key=target,
        request_data=request_data,
        response_data=response_data,
        status=status,
        error_message=error_message,
        executed_by=executed_by,
    )


def audit(action_type: str, target: str, request_data: dict,
          response_data: dict, status: str = "succeeded") -> None:
    """Record a config mutation, pulling site_id/actor from the request context."""
    ctx = current_user()
    record_action(
        site_id=ctx.site_id if ctx else 1,
        action_type=action_type,
        target=target,
        request_data=request_data,
        response_data=response_data,
        status=status,
        executed_by=ctx.user_id if ctx else None,
    )
