"""dbtoolbox — declarative, read-only SQL access layer (genai-toolbox inspired).

Sources (per-site JDBC-like connections) + SecurityPolicy (SELECT-only,
table allowlist, row limits, statement timeout) + QueryService (the single
validated execution path for dry-run / preview / export / introspection).
"""

from dbtoolbox.errors import (
    PolicyViolation,
    categorize_dbapi_error,
    categorize_sql_error,
    get_error_suggestion,
)
from dbtoolbox.policy import SecurityPolicy, validate_sql
from dbtoolbox.resolver import build_query_service
from dbtoolbox.service import QueryService
from dbtoolbox.sources import SECRET_CONNECTION_KEYS, Source, SourceConfig

__all__ = [
    "PolicyViolation",
    "QueryService",
    "SECRET_CONNECTION_KEYS",
    "SecurityPolicy",
    "Source",
    "SourceConfig",
    "build_query_service",
    "categorize_dbapi_error",
    "categorize_sql_error",
    "get_error_suggestion",
    "validate_sql",
]
