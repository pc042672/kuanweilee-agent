"""QueryService — the single validated SQL execution path.

Every read (dry-run, preview, export, introspection, declarative tools)
goes through validate → execute → serialize. Nothing else in the app
should execute SQL against a site's data source.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from dbtoolbox.errors import (
    PolicyViolation,
    categorize_dbapi_error,
    get_error_suggestion,
)
from dbtoolbox.policy import SecurityPolicy, validate_sql
from dbtoolbox.sources import Source

logger = logging.getLogger("ai_cdp.dbtoolbox.service")


def serialize_value(value: Any) -> Any:
    """Convert non-JSON-serializable types to JSON-safe equivalents."""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def serialize_row(row: Dict) -> Dict:
    """Serialize all values in a row dictionary."""
    return {k: serialize_value(v) for k, v in row.items()}


class QueryService:
    def __init__(self, source: Source, policy: SecurityPolicy):
        self.source = source
        self.policy = policy

    def _validate(self, sql: str) -> None:
        result = validate_sql(sql, self.policy, self.source.dialect.sqlglot_dialect)
        if not result.valid:
            raise PolicyViolation(result.error, result.error_type)

    def dry_run(self, sql: str) -> Dict[str, Any]:
        """EXPLAIN-validate SQL. Returns {valid, plan} or {valid: False, error, error_type}."""
        try:
            self._validate(sql)
        except PolicyViolation as e:
            return {"valid": False, "error": str(e), "error_type": e.error_type}
        try:
            with self.source.engine.connect() as conn:
                plan = conn.execute(text(self.source.dialect.explain_sql(sql))).fetchall()
            return {"valid": True, "plan": str(plan)}
        except Exception as e:
            error_type = categorize_dbapi_error(e)
            logger.warning("dry_run failed (%s): %s", error_type, e)
            return {"valid": False, "error": str(e), "error_type": error_type}

    def execute(
        self,
        sql: str,
        *,
        limit: Optional[int] = None,
        params: Optional[Dict[str, Any]] = None,
        max_rows: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Validate and execute a read query. Raises PolicyViolation on policy failure.

        The effective row cap is min(limit, max_rows or policy.max_rows).
        """
        self._validate(sql)
        cap = max_rows or self.policy.max_rows
        effective_limit = min(limit, cap) if limit else cap
        wrapped = self.source.dialect.limit_wrap(sql, effective_limit)
        with self.source.engine.connect() as conn:
            result = conn.execute(text(wrapped), params or {})
            return [serialize_row(dict(m)) for m in result.mappings()]

    def preview(self, sql: str, limit: int = 10) -> Dict[str, Any]:
        """Execute with a small limit; tool-shaped result the DE-agent expects."""
        try:
            data = self.execute(sql, limit=limit)
            return {
                "success": True,
                "data": data,
                "row_count": len(data),
                "sql": sql,
                "message": f"Query executed successfully, returned {len(data)} rows",
            }
        except PolicyViolation as e:
            return self._error_result(sql, str(e), e.error_type)
        except Exception as e:
            return self._error_result(sql, str(e), categorize_dbapi_error(e))

    def export(self, sql: str) -> List[Dict[str, Any]]:
        """Full-result read for exports, capped by policy.export_max_rows.

        Raises PolicyViolation on policy failure (callers shape the error).
        """
        return self.execute(sql, max_rows=self.policy.export_max_rows)

    @staticmethod
    def _error_result(sql: str, error: str, error_type: str) -> Dict[str, Any]:
        return {
            "success": False,
            "data": [],
            "row_count": 0,
            "sql": sql,
            "error": error,
            "error_type": error_type,
            "suggestion": get_error_suggestion(error_type),
        }
