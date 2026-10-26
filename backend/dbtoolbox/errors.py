"""Single source of truth for SQL error categorization and suggestions."""

from __future__ import annotations


class PolicyViolation(Exception):
    """Raised when SQL fails SecurityPolicy validation."""

    def __init__(self, message: str, error_type: str = "policy_violation"):
        super().__init__(message)
        self.error_type = error_type


def categorize_sql_error(error_msg: str) -> str:
    """Categorize a SQL error message string for better debugging."""
    error_lower = error_msg.lower()
    if "does not exist" in error_lower:
        if "column" in error_lower:
            return "column_not_found"
        if "table" in error_lower or "relation" in error_lower:
            return "table_not_found"
    elif "syntax error" in error_lower:
        return "syntax_error"
    elif "permission denied" in error_lower or "read-only" in error_lower:
        return "permission_error"
    elif "statement timeout" in error_lower or "canceling statement" in error_lower:
        return "timeout"
    return "unknown_error"


# SQLSTATE → category. Five-char SQLSTATE codes are standardized across
# databases and drivers (every language's Postgres driver exposes them),
# unlike driver-specific exception classes.
_SQLSTATE_CATEGORIES = {
    "42703": "column_not_found",   # undefined_column
    "42P01": "table_not_found",    # undefined_table
    "42601": "syntax_error",
    "42501": "permission_error",   # insufficient_privilege
    "25006": "permission_error",   # read_only_sql_transaction
    "57014": "timeout",            # query_canceled
}


def categorize_dbapi_error(exc: Exception) -> str:
    """Categorize a DBAPI/SQLAlchemy exception via its SQLSTATE code.

    Falls back to message-based categorization for drivers that don't expose
    one (e.g. SQLite in tests). psycopg2 exposes `pgcode`, asyncpg `sqlstate`.
    """
    orig = getattr(exc, "orig", exc)
    sqlstate = getattr(orig, "pgcode", None) or getattr(orig, "sqlstate", None)
    category = _SQLSTATE_CATEGORIES.get(sqlstate or "")
    return category or categorize_sql_error(str(orig))


def get_error_suggestion(error_type: str) -> str:
    """Provide helpful suggestions based on error type."""
    suggestions = {
        "column_not_found": "Use get_schema_tool to verify exact column names. PostgreSQL is case-sensitive!",
        "table_not_found": "Use list_tables_in_schema_tool to verify table exists",
        "syntax_error": "Check SQL syntax for Greenplum compatibility (no MERGE, no FILTER)",
        "permission_error": "Table may require different permissions",
        "timeout": "Query exceeded the statement timeout — narrow the date range or add filters",
        "policy_violation": "Rewrite as a SELECT query",
        "table_authorization": "Only ontology-defined data sources are permitted",
        "parse_error": "Simplify the SQL — the statement could not be parsed for validation",
    }
    return suggestions.get(error_type, "Review the error message and adjust SQL")
