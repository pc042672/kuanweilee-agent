# dbtoolbox — language-neutral contract (porting guide)

`backend/dbtoolbox/` is the read-only SQL access layer (~850 lines). It was
deliberately structured so a port to another language (Go, Java, ...) rewrites
**two narrow seams** and carries the rest over as plain data and control flow.

## Module map

| Module | Responsibility | Portability |
|---|---|---|
| `policy.py` | `SecurityPolicy` + `validate_sql` (fail-closed) | logic is plain data; **seam 1** is `parse_query()` |
| `errors.py` | error taxonomy: SQLSTATE table + message fallback + suggestions | pure data/tables |
| `dialects.py` | per-db-type URL template, session setup, EXPLAIN/LIMIT idioms | pure data table |
| `sources.py` | `SourceConfig` (env or `data_sources` row) + lazy engine | **seam 2** is the DB driver |
| `service.py` | `QueryService`: validate → execute → serialize | thin; result shapes below |
| `sqltools.py` | declarative named queries with typed `:params` | plain data + type coercion |
| `resolver.py` | per-site source + policy resolution from the app DB | thin SQL reads |

## Seam 1 — SQL parsing (`policy.parse_query`)

The only sqlglot call site. It reduces a SQL string to plain data:

```
ParsedQuery {
  kind:           "select" | "explain" | "other" | "multi" | "parse_error"
  tables:         set of schema-qualified refs, CTE aliases excluded
  statement_kind: raw statement kind (for error messages)
  explained_sql:  inner SQL of an EXPLAIN, when extractable
  error:          parse failure detail
}
```

Every policy decision (`select_only`, allowlist, multi-statement rejection,
EXPLAIN recursion) operates on `ParsedQuery` only. A port reimplements
`parse_query` over its native parser — `libpg_query`/`pg_query_go` (Go),
JSQLParser (Java) — and MUST keep these semantics:

- **Fail closed**: unparseable SQL → `parse_error` → query refused.
- Exactly one statement; more → `multi` → refused.
- Table refs are collected minus CTE aliases; schema-qualified as `schema.table`.
- `EXPLAIN <q>` validates `<q>` recursively.

## Seam 2 — DB driver (`sources.Source`)

SQLAlchemy Core is used only as a connection pool + parameter binder; no ORM,
no reflection. A port needs, per `DialectAdapter`:

- URL template with **URL-escaped** user/password/dbname (credentials contain
  `@ : / % $`).
- On every new connection, run `session_setup_statements`: for Postgres/Greenplum
  `SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY` and
  `SET statement_timeout = <ms>`.
- Pooling: size 5, recycle 3600s, pre-ping.
- Named parameter binding at the driver level (`:name`) — never string
  interpolation.

## Read-only model (3 layers, all required)

1. Readonly DB user (primary enforcement — credentials, not code).
2. Per-connection `READ ONLY` session + statement timeout (seam 2).
3. `validate_sql` fail-closed (seam 1 + policy data).

## Result-shape contracts (hard — the DE-agent parses these)

```jsonc
// QueryService.dry_run
{"valid": true,  "plan": "..."}
{"valid": false, "error": "...", "error_type": "..."}

// QueryService.preview
{"success": true,  "data": [...], "row_count": 3, "sql": "...", "message": "..."}
{"success": false, "data": [],    "row_count": 0, "sql": "...",
 "error": "...", "error_type": "...", "suggestion": "..."}

// sqltools.run_sql_tool
{"success": true,  "tool": "name", "data": [...], "row_count": 3}
{"success": false, "tool": "name", "error": "...", "error_type": "..."}
```

Value serialization: dates/datetimes → ISO-8601 strings, decimals → floats,
bytes → UTF-8 (replace). Row caps: `min(limit, policy.max_rows)`; exports cap
at `policy.export_max_rows`.

## Error taxonomy

`error_type` values: `policy_violation`, `table_authorization`, `parse_error`,
`column_not_found`, `table_not_found`, `syntax_error`, `permission_error`,
`timeout`, `invalid_arguments`, `unknown_error`. Each has a fixed suggestion
string (`errors.get_error_suggestion`).

DBAPI errors categorize by **SQLSTATE code** (standard across drivers and
languages): `42703`→column_not_found, `42P01`→table_not_found,
`42601`→syntax_error, `42501`/`25006`→permission_error, `57014`→timeout;
anything else falls back to message substring matching.

## Configuration data (language-neutral JSON)

- `SourceConfig`: `{db_type, host, port, dbname, user, password}` from the
  site's `data_sources` row, falling back to `GP_*` env vars.
- `SecurityPolicy` overrides: `sites.settings["sql_policy"]` JSONB —
  `{max_rows, export_max_rows, statement_timeout_ms, parser}`.
- Allowlist: ontology datasource nodes (`ConfigManager.get_allowed_tables()`).
- Named queries: `site_configs` row `config_type='sql_tools'` —
  `{"tools": [{name, description, statement, parameters: [{name, type,
  description, required, default}]}]}`; statements are policy-validated at
  load time and again at execution; unknown args are dropped.
