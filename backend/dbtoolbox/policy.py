"""SecurityPolicy and SQL validation (fail-closed).

This is one of three read-only layers — the readonly DB user is the primary
enforcement, the per-connection READ ONLY session setting is the second,
and this validator is the application-level gate that produces friendly,
structured errors before SQL ever reaches the database.

Structure (kept parser-agnostic for portability — see docs/dbtoolbox-porting.md):
parse_query() is the ONLY function that touches sqlglot; it reduces a SQL
string to a plain-data ParsedQuery. Every policy decision below operates on
that plain data, so a port to another language reimplements parse_query()
over its native parser (libpg_query, JSQLParser, ...) and keeps the rest.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import FrozenSet, Optional

logger = logging.getLogger("ai_cdp.dbtoolbox.policy")


@dataclass(frozen=True)
class SecurityPolicy:
    select_only: bool = True
    allowed_tables: Optional[FrozenSet[str]] = None  # None = no allowlist configured
    max_rows: int = 10_000
    export_max_rows: int = 100_000
    statement_timeout_ms: int = 30_000
    allow_explain: bool = True
    # Schemas exempt from the allowlist (introspection queries).
    system_schemas_allowed: tuple = ("information_schema",)
    # "sqlglot" (fail-closed AST) or "regex" (legacy escape hatch when
    # sqlglot can't parse dialect-specific SQL that is actually valid).
    parser: str = "sqlglot"


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    error: Optional[str] = None
    error_type: Optional[str] = None  # policy_violation | table_authorization | parse_error
    tables: FrozenSet[str] = field(default_factory=frozenset)


def _ok(tables: FrozenSet[str] = frozenset()) -> ValidationResult:
    return ValidationResult(valid=True, tables=tables)


def _fail(error: str, error_type: str) -> ValidationResult:
    return ValidationResult(valid=False, error=error, error_type=error_type)


# ── Parser seam ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ParsedQuery:
    """Plain-data summary of one SQL string — everything the policy needs."""

    kind: str  # "select" | "explain" | "other" | "multi" | "parse_error"
    tables: FrozenSet[str] = frozenset()  # schema-qualified refs, minus CTE aliases
    statement_kind: str = ""              # raw statement kind, for error messages
    explained_sql: Optional[str] = None   # inner SQL of an EXPLAIN, when extractable
    error: Optional[str] = None           # parse failure detail


def parse_query(sql: str, dialect: str = "postgres") -> ParsedQuery:
    """Reduce SQL to a ParsedQuery via sqlglot. The only sqlglot call site."""
    import sqlglot
    from sqlglot import exp

    try:
        statements = [s for s in sqlglot.parse(sql, read=dialect) if s is not None]
    except sqlglot.errors.ParseError as e:
        return ParsedQuery(kind="parse_error", error=str(e))

    if len(statements) != 1:
        return ParsedQuery(kind="multi")

    expr = statements[0]

    if isinstance(expr, exp.Command) and expr.name.upper() == "EXPLAIN":
        # sqlglot keeps the explained statement as raw text.
        inner = expr.expression.this if isinstance(expr.expression, exp.Literal) else None
        return ParsedQuery(kind="explain", explained_sql=inner)

    cte_aliases = {cte.alias_or_name for cte in expr.find_all(exp.CTE)}
    tables = set()
    for table in expr.find_all(exp.Table):
        if table.name in cte_aliases and not table.db:
            continue
        tables.add(f"{table.db}.{table.name}" if table.db else table.name)

    is_select = isinstance(expr, (exp.Select, exp.Union, exp.Intersect, exp.Except))
    return ParsedQuery(
        kind="select" if is_select else "other",
        tables=frozenset(tables),
        statement_kind=(expr.key or type(expr).__name__).upper(),
    )


# ── Policy decisions (plain data in, plain data out) ────────────────────────

def _check_allowlist(tables: FrozenSet[str], policy: SecurityPolicy) -> Optional[ValidationResult]:
    if policy.allowed_tables is None:
        return None
    unauthorized = {
        t for t in tables
        if t not in policy.allowed_tables
        and t.split(".")[0] not in policy.system_schemas_allowed
    }
    if unauthorized:
        return _fail(
            f"Table access denied: {', '.join(sorted(unauthorized))}. "
            "Only ontology-defined data sources are permitted.",
            "table_authorization",
        )
    return None


def validate_sql(sql: str, policy: SecurityPolicy, dialect: str = "postgres") -> ValidationResult:
    """Validate SQL against the policy. Fail-closed on parse errors."""
    sql = (sql or "").strip().rstrip(";").strip()
    if not sql:
        return _fail("Empty SQL statement", "policy_violation")

    if policy.parser == "regex":
        return _validate_regex(sql, policy)

    parsed = parse_query(sql, dialect)

    if parsed.kind == "parse_error":
        logger.warning(
            "SQL policy: parse error (fail-closed): %s | sql=%s", parsed.error, sql[:300]
        )
        return _fail(f"SQL could not be parsed for validation: {parsed.error}", "parse_error")

    if parsed.kind == "multi":
        return _fail(
            "Multiple SQL statements are not allowed — submit one query at a time",
            "policy_violation",
        )

    if parsed.kind == "explain":
        if not policy.allow_explain:
            return _fail("EXPLAIN is not permitted", "policy_violation")
        if parsed.explained_sql:
            return validate_sql(parsed.explained_sql, policy, dialect)
        return _ok()

    if policy.select_only and parsed.kind != "select":
        return _fail(
            f"Only SELECT, EXPLAIN, and WITH (CTE) queries are permitted "
            f"(got {parsed.statement_kind})",
            "policy_violation",
        )

    if denied := _check_allowlist(parsed.tables, policy):
        return denied
    return _ok(parsed.tables)


# ── Legacy regex validator (escape hatch via policy.parser="regex") ─────────

_REGEX_BLOCKED = [
    re.compile(rf"\b{kw}\b", re.IGNORECASE)
    for kw in ("DROP", "TRUNCATE", "DELETE", "ALTER", "INSERT", "UPDATE",
               "CREATE", "GRANT", "REVOKE", "COPY", "SET")
]
_REGEX_TABLE_REF = re.compile(
    r'(?:FROM|JOIN)\s+("?[a-zA-Z_][a-zA-Z0-9_]*"?(?:\."?[a-zA-Z_][a-zA-Z0-9_]*"?)*)',
    re.IGNORECASE,
)
_REGEX_CTE_ALIAS = re.compile(r'\bWITH\s+(\w+)\s+AS\b|\,\s*(\w+)\s+AS\s*\(', re.IGNORECASE)


def _validate_regex(sql: str, policy: SecurityPolicy) -> ValidationResult:
    sql_upper = sql.upper()
    if policy.select_only and not sql_upper.startswith(("SELECT", "EXPLAIN", "WITH")):
        return _fail(
            "Only SELECT, EXPLAIN, and WITH (CTE) queries are permitted",
            "policy_violation",
        )
    for pattern in _REGEX_BLOCKED:
        if pattern.search(sql):
            return _fail(
                f"Policy violation: {pattern.pattern.strip(chr(92)+'b')} statements are not allowed",
                "policy_violation",
            )
    referenced = frozenset(t.replace('"', "") for t in _REGEX_TABLE_REF.findall(sql))
    cte_aliases = {m[0] or m[1] for m in _REGEX_CTE_ALIAS.findall(sql)}
    tables = frozenset(referenced - cte_aliases)
    if denied := _check_allowlist(tables, policy):
        return denied
    return _ok(tables)
