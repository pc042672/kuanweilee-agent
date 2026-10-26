"""Dialect adapters: per-db-type URL templates and session/SQL idioms.

Adding a new source type = register a DialectAdapter here and install its
driver. The security policy applies uniformly above this layer.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DialectAdapter:
    name: str
    url_template: str
    sqlglot_dialect: str = "postgres"
    supports_explain: bool = True

    def session_setup_statements(self, statement_timeout_ms: int) -> list[str]:
        """Statements run on every new DBAPI connection (read-only + timeout)."""
        return []

    def explain_sql(self, sql: str) -> str:
        return f"EXPLAIN {sql}"

    def limit_wrap(self, sql: str, limit: int) -> str:
        sql = sql.strip().rstrip(";")
        return f"SELECT * FROM ({sql}) AS sub LIMIT {int(limit)}"


@dataclass(frozen=True)
class _PostgresAdapter(DialectAdapter):
    def session_setup_statements(self, statement_timeout_ms: int) -> list[str]:
        # READ ONLY session + timeout: supported on PG 8.x+ and Greenplum 5/6/7.
        # Defense-in-depth, not the security boundary — the readonly DB user
        # and the policy validator are the primary enforcement.
        return [
            "SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY",
            f"SET statement_timeout = {int(statement_timeout_ms)}",
        ]


DIALECTS: dict[str, DialectAdapter] = {
    "greenplum": _PostgresAdapter(
        name="greenplum",
        url_template="postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}",
    ),
    "postgresql": _PostgresAdapter(
        name="postgresql",
        url_template="postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}",
    ),
    "mysql": DialectAdapter(
        name="mysql",
        url_template="mysql+pymysql://{user}:{password}@{host}:{port}/{dbname}",
        sqlglot_dialect="mysql",
    ),
    "mssql": DialectAdapter(
        name="mssql",
        url_template="mssql+pyodbc://{user}:{password}@{host}:{port}/{dbname}?driver=ODBC+Driver+18+for+SQL+Server",
        sqlglot_dialect="tsql",
        supports_explain=False,
    ),
    "oracle": DialectAdapter(
        name="oracle",
        url_template="oracle+oracledb://{user}:{password}@{host}:{port}/{dbname}",
        sqlglot_dialect="oracle",
        supports_explain=False,
    ),
}


def get_dialect(db_type: str) -> DialectAdapter:
    adapter = DIALECTS.get(db_type)
    if adapter is None:
        raise ValueError(
            f"Unsupported db_type '{db_type}'. Supported: {', '.join(sorted(DIALECTS))}"
        )
    return adapter
