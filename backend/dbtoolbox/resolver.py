"""Per-site Source/Policy/QueryService resolution.

Reads the site's active data_sources row (app DB) and sql_policy settings;
falls back to GP_* env vars when no app DB or no row is configured (dev).
"""

from __future__ import annotations

import logging
from typing import Optional

from dbtoolbox.policy import SecurityPolicy
from dbtoolbox.service import QueryService
from dbtoolbox.sources import Source, SourceConfig

logger = logging.getLogger("ai_cdp.dbtoolbox.resolver")

_POLICY_DEFAULTS = {"max_rows": 10_000, "export_max_rows": 100_000,
                    "statement_timeout_ms": 30_000, "parser": "sqlglot"}


def load_active_data_source(site_id: int) -> Optional[dict]:
    """The site's active data_sources row, or None (env fallback)."""
    try:
        from db import get_engine
        from sqlalchemy import text

        engine = get_engine()
        if engine is None:
            return None
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT id, db_type, connection_config FROM data_sources "
                    "WHERE site_id = :sid AND is_active ORDER BY id LIMIT 1"
                ),
                {"sid": site_id},
            ).mappings().first()
        return dict(row) if row else None
    except Exception as e:
        logger.warning("data_sources lookup failed for site %s: %s", site_id, e)
        return None


def _load_sql_policy_settings(site_id: int) -> dict:
    """sites.settings["sql_policy"] JSONB, merged over defaults."""
    merged = dict(_POLICY_DEFAULTS)
    try:
        from db import get_engine
        from sqlalchemy import text

        engine = get_engine()
        if engine is None:
            return merged
        with engine.connect() as conn:
            settings_json = conn.execute(
                text("SELECT settings FROM sites WHERE id = :sid"), {"sid": site_id}
            ).scalar()
        if isinstance(settings_json, dict):
            merged.update(settings_json.get("sql_policy") or {})
    except Exception as e:
        logger.warning("sql_policy lookup failed for site %s: %s", site_id, e)
    return merged


def build_policy(site_id: int, config_manager) -> SecurityPolicy:
    try:
        allowed = config_manager.get_allowed_tables()
    except Exception as e:
        # Same fail-open-on-lookup-error semantics as SQLSafetyPlugin; the
        # plugin layer re-checks the allowlist on every tool call.
        logger.warning("allowed_tables lookup failed for site %s: %s", site_id, e)
        allowed = None
    opts = _load_sql_policy_settings(site_id)
    return SecurityPolicy(
        allowed_tables=frozenset(allowed) if allowed else None,
        max_rows=int(opts["max_rows"]),
        export_max_rows=int(opts["export_max_rows"]),
        statement_timeout_ms=int(opts["statement_timeout_ms"]),
        parser=str(opts["parser"]),
    )


def build_query_service(site_id: int, config_manager) -> QueryService:
    """Build the site's QueryService (called by SiteResourceManager, cached there)."""
    policy = build_policy(site_id, config_manager)
    row = load_active_data_source(site_id)
    if row:
        config = SourceConfig.from_data_source_row(
            row, statement_timeout_ms=policy.statement_timeout_ms
        )
        logger.info("Site %s uses data_source id=%s (%s)", site_id, row["id"], config.db_type)
    else:
        config = SourceConfig.from_env(statement_timeout_ms=policy.statement_timeout_ms)
    return QueryService(Source(config), policy)
