# AI-CDP Production Architecture

> Production deployment guide for Google Cloud Platform.
> Covers security, observability, quality assurance, and operational procedures.

---

## Table of Contents

1. [End-to-End Production Architecture](#1-end-to-end-production-architecture)
2. [Data Authority & Multi-Tenant Security](#2-data-authority--multi-tenant-security)
3. [SQL Injection & Prompt Injection Prevention](#3-sql-injection--prompt-injection-prevention)
4. [Business Metric Accuracy & Hallucination Prevention](#4-business-metric-accuracy--hallucination-prevention)
5. [Production Audit & Tracing](#5-production-audit--tracing)
6. [Token Usage Monitoring](#6-token-usage-monitoring)
7. [Response Quality Measurement](#7-response-quality-measurement)
8. [Ontology Update Process](#8-ontology-update-process)

---

## 1. End-to-End Production Architecture

### 1.1 Request Flow

```
                                    INTERNET
                                       |
                            ┌──────────┴──────────┐
                            │  Cloud Armor (WAF)   │  L7 DDoS, OWASP rules, geo-blocking
                            └──────────┬──────────┘
                                       |
                            ┌──────────┴──────────┐
                            │  Cloud Load Balancer │  SSL termination, path routing
                            │  (HTTPS LB)          │  *.aicdp.example.com
                            └──────────┬──────────┘
                                       |
                    ┌──────────────────┴──────────────────┐
                    |                                      |
          ┌────────┴────────┐                   ┌─────────┴─────────┐
          │  Cloud Run       │                   │  Cloud CDN         │
          │  (Backend)       │                   │  (Static Assets)   │
          │  FastAPI + ADK   │                   │  Angular SPA       │
          │  min: 1, max: 10 │                   └───────────────────┘
          └────────┬────────┘
                   |
     ┌─────────────┼──────────────────────┐
     |             |                      |
     v             v                      v
┌─────────┐  ┌──────────┐  ┌───────────────────────┐
│ Gemini  │  │ AlloyDB  │  │ Customer Analytics DB  │
│ API     │  │ (Config) │  │ (Greenplum/AlloyDB)    │
│         │  │          │  │                        │
│ Models: │  │ Tables:  │  │ Per-site data source   │
│ gemini- │  │ sites    │  │ configured in          │
│ 3-flash │  │ users    │  │ data_sources table     │
│         │  │ configs  │  └───────────┬────────────┘
│ gemini- │  │ sessions │              |
│ embed   │  │ audit    │    ┌─────────┴──────────┐
└─────────┘  └──────────┘    │ Vertex AI Vector   │
                              │ Search 2.0         │
                              │ (Persona taxonomy) │
                              └────────────────────┘
```

### 1.2 GCP Service Map

| Layer | Service | Purpose | Config |
|-------|---------|---------|--------|
| **DNS** | Cloud DNS | Domain management | A/AAAA records to LB |
| **Edge** | Cloud Armor | WAF, rate limiting, geo-blocking | Preconfigured OWASP rules |
| **Load Balancing** | External HTTPS LB | SSL termination, path routing | Managed SSL cert |
| **CDN** | Cloud CDN | Angular static assets | Cache-Control headers |
| **Compute** | Cloud Run | FastAPI backend (stateless) | min=1, max=10, 2 vCPU, 4Gi |
| **Config DB** | AlloyDB | Users, sessions, ontology, audit | Primary + read replica |
| **Analytics DB** | Greenplum / AlloyDB | Customer data (per-site) | Readonly connection |
| **Vector** | Vertex AI Vector Search 2.0 | Persona classification | Auto-embedding index |
| **AI** | Vertex AI (Gemini) | Agent reasoning, embeddings | gemini-3-flash-preview |
| **Secrets** | Secret Manager | DB passwords, JWT secret, API keys | IAM-bound to Cloud Run SA |
| **Logs** | Cloud Logging | Centralized log sink | ai-cdp log name |
| **Traces** | Cloud Trace | Distributed tracing | OpenTelemetry export |
| **Monitoring** | Cloud Monitoring | Dashboards, alerts | Custom metrics + uptime |
| **IAM** | Workload Identity | Cloud Run service account | Least-privilege roles |

### 1.3 Cloud Run Configuration

```yaml
# Recommended Cloud Run settings
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/minScale: "1"      # Avoid cold starts
        autoscaling.knative.dev/maxScale: "10"
        run.googleapis.com/cpu-throttling: "false"  # Always-on CPU for SSE
    spec:
      containerConcurrency: 80
      timeoutSeconds: 300                           # Agent iterations can be slow
      containers:
        - resources:
            limits:
              cpu: "2"
              memory: "4Gi"
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef: {name: db-url, key: latest}
            - name: JWT_SECRET
              valueFrom:
                secretKeyRef: {name: jwt-secret, key: latest}
            - name: GOOGLE_CLIENT_ID
              value: "your-client-id.apps.googleusercontent.com"
            - name: ENABLE_CLOUD_LOGGING
              value: "true"
            - name: ENABLE_CLOUD_TRACE
              value: "true"
```

Key decisions:
- **cpu-throttling: false** -- SSE streaming requires CPU outside of request handling
- **containerConcurrency: 80** -- each agent request holds a connection for 5-30s
- **minScale: 1** -- eliminates cold start for first request
- **timeoutSeconds: 300** -- DS-STAR loop can run 3 iterations x ~30s each

### 1.4 Network Architecture

```
┌─────────────────────────────────────────────────────┐
│  VPC: aicdp-vpc                                     │
│                                                     │
│  ┌──────────────┐         ┌──────────────────────┐  │
│  │ Cloud Run     │────────│ VPC Connector         │  │
│  │ (Serverless)  │        │ (Serverless VPC       │  │
│  └──────────────┘        │  Access)               │  │
│                           └──────────┬───────────┘  │
│                                      │               │
│                           ┌──────────┴───────────┐  │
│                           │ AlloyDB               │  │
│                           │ Private IP only       │  │
│                           │ (no public endpoint)  │  │
│                           └──────────────────────┘  │
│                                                     │
│  Firewall rules:                                    │
│  - Allow Cloud Run → AlloyDB (5432)                 │
│  - Allow Cloud Run → Greenplum (site-specific)      │
│  - Deny all other internal traffic                  │
└─────────────────────────────────────────────────────┘
```

The app database is PostgreSQL 12+ (Cloud SQL or self-hosted); when on private IP,
Cloud Run reaches it via a Serverless VPC Access connector (`--vpc-connector`).
`deploy/gcp/deploy.sh` deploys against an existing database (`--database-url`).
The legacy AlloyDB stack (private-IP cluster + VPC peering provisioning) lives in
`deploy/legacy/deploy-alloydb.sh`.

---

## 2. Data Authority & Multi-Tenant Security

### 2.1 Current Tenant Isolation Model

The system uses **site-scoped resource isolation** at the application layer:

```
Request → Auth Middleware → UserContext(site_id) → contextvars
                                                       │
                                                       ▼
                                              SiteResourceManager
                                                       │
                                          ┌────────────┼────────────┐
                                          │            │            │
                                     GreenplumRunner  Profiler  ConfigManager
                                     (per-site conn)  (per-site)  (per-site)
```

**How it works today:**

1. JWT contains `site_id` and `role` claims (set at login from `site_members` table)
2. Auth middleware extracts JWT, creates `UserContext(user_id, site_id, role)`, stores in `contextvars`
3. Agent tools call `_infra.py:get_runner()` which reads `site_id` from contextvars
4. `SiteResourceManager` returns a site-specific `GreenplumRunner` with its own connection config
5. Each site's data source credentials come from the `data_sources` table

**Code path** (from `backend/revive_agent/tools/_infra.py`):
```python
def _get_resources():
    ctx = get_request_context_or_none()
    site_id = ctx.site_id if ctx is not None else _DEFAULT_SITE_ID
    return get_site_resources(site_id)
```

### 2.2 Isolation Layers

| Layer | Mechanism | Status |
|-------|-----------|--------|
| **Application** | `UserContext.site_id` in contextvars, per-site `SiteResourceManager` | Implemented |
| **Connection** | Each site gets its own `GreenplumRunner` with separate credentials | Implemented |
| **Database role** | SQL runner uses `GP_READONLY_USER` (SELECT/EXPLAIN only) | Implemented |
| **Config** | `site_configs` table scoped by `site_id` | Implemented |
| **Audit** | `config_audit_log` and `action_executions` include `site_id` | Implemented |
| **Row-level security** | PostgreSQL RLS policies on AlloyDB config tables | Not yet |
| **Schema-level isolation** | Separate Greenplum schemas per site | Site-dependent |

### 2.3 Recommended Enhancements

#### 2.3.1 AlloyDB Row-Level Security (Config Tables)

Add RLS to config tables so even a bug in application code cannot leak cross-site data:

```sql
-- Enable RLS on config tables
ALTER TABLE site_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE config_audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE action_executions ENABLE ROW LEVEL SECURITY;

-- Create policy: app sets current_setting('app.site_id') per connection
CREATE POLICY site_isolation_configs ON site_configs
    USING (site_id = current_setting('app.site_id')::int);

CREATE POLICY site_isolation_audit ON config_audit_log
    USING (site_id = current_setting('app.site_id')::int);

CREATE POLICY site_isolation_actions ON action_executions
    USING (site_id = current_setting('app.site_id')::int);
```

Set the session variable in the connection factory:
```python
# In SiteResourceManager._create_resources():
conn.execute(text("SET app.site_id = :sid"), {"sid": site_id})
```

#### 2.3.2 Greenplum Schema Isolation

For enterprise deployments where each tenant has their own analytics data:

| Strategy | When to Use | Trade-off |
|----------|-------------|-----------|
| **Separate database** | < 10 tenants, strict compliance | Most isolation, highest ops cost |
| **Separate schema** | 10-100 tenants | Good isolation, moderate ops cost |
| **Shared schema + RLS** | 100+ tenants | Least isolation, lowest ops cost |

The current `data_sources` table already supports separate databases per site.
For schema isolation, the readonly user should only have `USAGE` on their site's schema:

```sql
-- Per-site readonly role
CREATE ROLE site_42_readonly LOGIN PASSWORD '...';
GRANT USAGE ON SCHEMA site_42 TO site_42_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA site_42 TO site_42_readonly;
```

#### 2.3.3 Agent Tool Parameter Injection

All agent SQL tools already resolve the runner per-site via contextvars. The key guarantee is:

1. The agent never sees raw database credentials
2. The agent cannot switch site context -- it is bound by the JWT
3. SQL execution always goes through `GreenplumRunner(role="readonly")`
4. The `SQLSafetyPlugin` blocks all non-SELECT operations before they reach the database

**Gap to close:** In the AG-UI SSE adapter path, contextvars may not propagate to async tasks.
The `_infra.py` falls back to `_DEFAULT_SITE_ID = 1`. For multi-tenant production, ensure the
AG-UI adapter propagates the `UserContext` into the runner's async context. See "Known Gotchas"
in CLAUDE.md for details.

---

## 3. SQL Injection & Prompt Injection Prevention

### 3.1 Defense-in-Depth Stack

```
Layer 1: SQLSafetyPlugin (ADK Plugin)
  │  Intercepts ALL SQL tool calls at Runner level
  │  Blocks: DROP, TRUNCATE, DELETE, ALTER, INSERT, UPDATE, CREATE, GRANT, REVOKE, COPY
  │  Allows: SELECT, EXPLAIN, WITH (CTE)
  │
Layer 2: EXPLAIN Dry-Run
  │  dry_run_sql_tool() runs EXPLAIN before any execution
  │  Catches: syntax errors, missing columns/tables, permission errors
  │  Does NOT execute the query
  │
Layer 3: Readonly Database User
  │  GreenplumRunner uses GP_READONLY_USER with SELECT/EXPLAIN only
  │  Even if Layer 1+2 fail, the DB refuses writes
  │
Layer 4: Connection Pool Isolation
  │  Per-site connection pool via SiteResourceManager
  │  Sites cannot access each other's database connections
  │
Layer 5: Result Limiting
     run_sql_preview_tool() wraps queries in LIMIT 10 subquery
     Prevents full-table extraction
```

### 3.2 SQL Safety Plugin Implementation

From `backend/revive_agent/plugins.py`:

```python
class SQLSafetyPlugin(BasePlugin):
    """Intercepts SQL tool calls and blocks non-SELECT queries.
    Defense-in-depth that cannot be bypassed by prompt injection."""

    async def before_tool_callback(self, *, tool, tool_args, tool_context):
        if tool.name not in {"dry_run_sql_tool", "run_sql_preview_tool"}:
            return None

        sql_upper = tool_args.get("sql_query", "").strip().upper()

        # Must start with SELECT, EXPLAIN, or WITH
        if not (sql_upper.startswith("SELECT") or
                sql_upper.startswith("EXPLAIN") or
                sql_upper.startswith("WITH")):
            return {"valid": False, "error": "Only SELECT queries permitted"}

        # Check for embedded DML (e.g., SELECT ... ; DROP TABLE ...)
        for pattern, name in _BLOCKED_SQL_PATTERNS:
            if re.search(pattern, sql, re.IGNORECASE):
                return {"valid": False, "error": f"{name} not allowed"}

        return None  # Allow the tool call to proceed
```

The plugin runs at the ADK `Runner` level, meaning it applies to all agents regardless of
which agent generated the SQL. A prompt injection that convinces the agent to write
`DELETE FROM users` will be caught here before it reaches the database.

### 3.3 SQL Injection Vectors & Mitigations

| Vector | Mitigation | File |
|--------|------------|------|
| Agent generates DML | SQLSafetyPlugin blocks all non-SELECT | `plugins.py` |
| Jinja template injection | `render_sql()` uses Jinja2 (not f-strings) but templates are agent-generated; readonly user limits damage | `sql_runner.py` |
| Semicolon stacking | SQLSafetyPlugin regex scans full query body | `plugins.py` |
| `COPY TO` data exfil | `COPY` is in blocked patterns list | `plugins.py` |
| Subquery with side effects | PostgreSQL readonly role prevents writes even in subqueries | DB-level |

**Remaining risk:** The `render_sql()` method in `GreenplumRunner` uses Jinja2 templates, which
could theoretically allow server-side template injection if agent-generated params contain Jinja
syntax. In practice this is mitigated by:
1. The params come from agent tool arguments, not raw user input
2. The readonly database user limits blast radius
3. Recommendation: switch to parameterized queries (`psycopg2` `%s` placeholders) for any
   user-supplied filter values

### 3.4 Prompt Injection Prevention

| Layer | Mechanism | Status |
|-------|-----------|--------|
| **Input boundary** | Agent instructions clearly delineate user input vs system instructions | Implemented |
| **Tool output validation** | Tools return structured dicts, not raw text injected into prompts | Implemented |
| **Output validation** | `parse_json_from_text()` extracts only expected JSON from agent output | Implemented |
| **Safety settings** | Gemini built-in content safety filters | Default (Gemini API) |
| **SQL guardrail** | SQLSafetyPlugin blocks dangerous SQL regardless of prompt | Implemented |
| **Scope limitation** | Agents only have tools for SELECT queries and config reads | Implemented |

**Prompt injection attack surface:**
- User message is the primary injection vector (via `/ag-ui` or `/api/chat/stream`)
- The DS-STAR orchestrator treats user messages as untrusted data passed to agents
- Even if an attacker convinces the agent to generate malicious SQL, the SQLSafetyPlugin
  and readonly DB user provide defense-in-depth

**Recommended additions for hardening:**
1. Add Gemini safety settings to agent config:
   ```python
   safety_settings=[
       types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_LOW_AND_ABOVE"),
   ]
   ```
2. Log all agent tool calls with input/output for forensic review (LoggingPlugin already does this)
3. Rate-limit the `/ag-ui` endpoint per user via Cloud Armor

---

## 4. Business Metric Accuracy & Hallucination Prevention

### 4.1 Ontology-Grounded Architecture

The DS-STAR pipeline prevents hallucination by grounding all agent decisions in the ontology:

```
User Query: "Find VIP customers who spent over $1000"
     │
     ▼
 DS-Agent
     │
     ├── get_ontology_tool() → loads ontology nodes
     │   Returns: DataSourceNode (tables/columns), AttributeNode (dimensions),
     │            SegmentNode (pre-defined segments with SQL conditions)
     │
     ├── Matches query to existing segments (SegmentNode.conditions)
     │   or identifies required tables/columns from DataSourceNodes
     │
     ├── submit_execution_plan() → structured JSON with:
     │   {goal, segment_type, label_matched, tables_needed, execution_method}
     │
     ▼
 DE-Agent
     │
     ├── Generates SQL referencing ONLY tables/columns from the plan
     ├── dry_run_sql_tool() → EXPLAIN validates against real DB schema
     │   Catches: non-existent columns, wrong table names, syntax errors
     ├── run_sql_preview_tool() → executes with LIMIT 10
     │
     ▼
 Verifier
     │
     ├── Compares execution_result against execution_plan.goal
     ├── Checks: row_count > 0, columns match expected, SQL is reasonable
     ├── If insufficient → feedback → loop (up to 3 iterations)
     └── If sufficient → campaign_summary + escalate
```

### 4.2 Accuracy Guarantees

| Guarantee | Mechanism | Code Reference |
|-----------|-----------|----------------|
| **Tables exist** | `EXPLAIN` dry-run catches `UndefinedTable` | `sql_runner.py:dry_run()` |
| **Columns exist** | `EXPLAIN` dry-run catches `UndefinedColumn` | `sql_runner.py:dry_run()` |
| **SQL is valid** | `EXPLAIN` catches syntax errors before execution | `sql_runner.py:dry_run()` |
| **Results are reasonable** | Verifier checks row_count, column names | `orchestrator.py` |
| **Schema awareness** | DS-Agent uses `get_schema_tool()` for column introspection | `schema_tools.py` |
| **Segment grounding** | Pre-defined segments have validated SQL conditions | `ontology.json` |
| **Iterative refinement** | Up to 3 iterations to fix errors | `orchestrator.py` |

### 4.3 Error Recovery Flow

```
Iteration 1:
  DS-Agent → plan with wrong table name
  DE-Agent → dry_run fails: "relation 'foo' does not exist"
  Verifier → {sufficient: false, action: "backtrack", feedback: "table not found"}

Iteration 2:
  DS-Agent → uses list_tables_in_schema_tool to find correct table
  DE-Agent → dry_run passes, preview returns 0 rows
  Verifier → {sufficient: false, action: "add_step", feedback: "no results, check filters"}

Iteration 3:
  DS-Agent → adjusts filter conditions
  DE-Agent → preview returns 47 rows
  Verifier → {sufficient: true, action: "complete"}
```

### 4.4 Confidence Indicators

The system provides multiple signals for result confidence:

| Signal | Source | Interpretation |
|--------|--------|----------------|
| `verification.sufficient` | Verifier agent | Boolean -- did the result satisfy the goal? |
| `execution_result.preview.row_count` | SQL execution | 0 rows suggests wrong filters |
| `dry_run.valid` | EXPLAIN | false = SQL is invalid |
| `iteration count` | Orchestrator | Higher = more difficulty, lower confidence |
| `verification.action` | Verifier | "backtrack" = fundamental plan error |

**Recommended enhancement: explicit confidence scoring**

Add a confidence field to the Verifier's output schema:
```json
{
  "sufficient": true,
  "confidence": 0.85,
  "confidence_factors": {
    "schema_match": 1.0,
    "filter_specificity": 0.8,
    "result_reasonableness": 0.75
  }
}
```

---

## 5. Production Audit & Tracing

### 5.1 Existing Audit Infrastructure

The system has two audit tables in AlloyDB:

#### config_audit_log (config changes)

```sql
CREATE TABLE config_audit_log (
    id SERIAL PRIMARY KEY,
    site_id INTEGER NOT NULL,
    config_type VARCHAR(32) NOT NULL,    -- 'ontology', 'label_rules', etc.
    action VARCHAR(16) NOT NULL,          -- 'create', 'update', 'delete'
    changed_by INTEGER NOT NULL,          -- user_id
    previous_data JSONB,                  -- full snapshot before
    new_data JSONB,                       -- full snapshot after
    diff_json JSONB,                      -- field-level diff
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

Written by `DbOntologyRepository.save()` -- every ontology change records who changed what,
with a field-level diff showing exactly which nodes were added/removed/modified.

#### action_executions (runtime actions)

```sql
CREATE TABLE action_executions (
    id SERIAL PRIMARY KEY,
    site_id INTEGER NOT NULL,
    action_type TEXT NOT NULL,            -- 'score', 'resolve_segment', 'nba', etc.
    target_node_key TEXT,                 -- ontology node affected
    request_json JSONB,                   -- input parameters
    response_json JSONB,                  -- output data
    execution_status TEXT NOT NULL,        -- 'succeeded', 'failed'
    error_message TEXT,
    executed_by INTEGER,                  -- user_id
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    correlation_id TEXT                   -- links related actions
);
```

Written by `log_action()` in `backend/config/action_log.py`. Fire-and-forget (never raises).
Currently logs: scoring actions, segment evaluations, NBA/NBO resolutions.

### 5.2 Existing Logging Infrastructure

From `backend/logging_config.py`:

| Log | Level | Rotation | Retention |
|-----|-------|----------|-----------|
| `ai-cdp.log` | INFO+ | Daily (midnight) | 30 days |
| `ai-cdp-error.log` | ERROR+ | Daily (midnight) | 30 days |
| Cloud Logging | INFO+ | N/A (managed) | Configurable (30-365 days) |

The `LoggingPlugin` (ADK Plugin) provides structured logging for all agent and tool lifecycle:
- `[ORCHESTRATOR] Invocation started | session=xxx`
- `[DSAgent] Agent started` / `Agent completed | duration=2.34s`
- `[TOOL] dry_run_sql_tool called | args={sql_query: "SELECT..."}` / `completed | duration=0.12s`

### 5.3 Cloud Trace Integration

Currently implemented via environment flags in `backend/settings.py`:

```python
ENABLE_CLOUD_TRACE = os.environ.get("ENABLE_CLOUD_TRACE", "").lower() == "true"
```

When enabled, `server.py` sets ADK's OpenTelemetry env vars before import:
```python
if settings.ENABLE_CLOUD_TRACE:
    os.environ.setdefault("ENABLE_TRACING", "true")
    os.environ.setdefault("TRACE_EXPORTER", "cloud_trace")
```

This enables ADK's built-in OpenTelemetry instrumentation which traces:
- Agent invocations (DS-Agent, DE-Agent, Verifier)
- Tool calls (with duration)
- LLM API calls (with token counts)

### 5.4 Recommended Production Observability Stack

```
┌──────────────────────────────────────────────────────────┐
│                    Cloud Monitoring                       │
│                                                          │
│  Dashboard: "AI-CDP Production"                          │
│  ┌────────────┐ ┌────────────┐ ┌──────────────────────┐  │
│  │ Latency    │ │ Error Rate │ │ Token Usage          │  │
│  │ p50/p95/p99│ │ 5xx / 4xx  │ │ per model per site   │  │
│  └────────────┘ └────────────┘ └──────────────────────┘  │
│  ┌────────────┐ ┌────────────┐ ┌──────────────────────┐  │
│  │ Agent Iter │ │ SQL Errors │ │ Ontology Changes     │  │
│  │ per request│ │ dry-run    │ │ per day              │  │
│  └────────────┘ └────────────┘ └──────────────────────┘  │
└──────────────────────────────────────────────────────────┘
         │                │                │
         ▼                ▼                ▼
   Cloud Trace      Cloud Logging     Custom Metrics
   (OTel spans)     (structured)      (Prometheus)
```

#### Custom Metrics to Export

```python
# Recommended OpenTelemetry metrics to add
from opentelemetry import metrics

meter = metrics.get_meter("ai_cdp")

# Agent metrics
agent_duration = meter.create_histogram("agent.duration_seconds", unit="s")
agent_iterations = meter.create_histogram("agent.iterations_count")
agent_errors = meter.create_counter("agent.errors_total")

# SQL metrics
sql_dry_run_failures = meter.create_counter("sql.dry_run_failures_total")
sql_preview_duration = meter.create_histogram("sql.preview_duration_seconds", unit="s")

# Token metrics (see Section 6)
token_usage = meter.create_counter("llm.token_usage_total",
    description="Token usage by model, direction, site")
```

#### Alert Policies

| Alert | Condition | Severity | Action |
|-------|-----------|----------|--------|
| High error rate | 5xx > 5% over 5 min | Critical | Page on-call |
| Agent timeout | p95 latency > 60s | Warning | Investigate slow queries |
| Max iterations reached | > 10% of requests hit 3 iterations | Warning | Review agent instructions |
| SQL dry-run failure spike | > 30% failures over 15 min | Warning | Check schema changes |
| Token budget exceeded | Daily spend > $X | Critical | Rate-limit or pause |
| AlloyDB connection errors | Any connection failure | Critical | Check VPC connectivity |

### 5.5 Implementation Steps

1. **Enable Cloud Trace** -- set `ENABLE_CLOUD_TRACE=true` (already supported)
2. **Enable Cloud Logging** -- set `ENABLE_CLOUD_LOGGING=true` (already supported)
3. **Add OpenTelemetry instrumentation** to middleware and tools:
   ```bash
   pip install opentelemetry-api opentelemetry-sdk \
       opentelemetry-exporter-gcp-trace \
       opentelemetry-exporter-gcp-monitoring
   ```
4. **Create Cloud Monitoring dashboard** with the metrics above
5. **Set up alert policies** in Cloud Monitoring
6. **Configure log-based metrics** for agent iteration counts and SQL error rates

---

## 6. Token Usage Monitoring

### 6.1 Token Flow

```
Each DS-STAR request generates LLM calls across 3+ agents:

  DS-Agent:    ~2K input (instruction + ontology) + ~500 output (plan)
  DE-Agent:    ~1.5K input (instruction + plan) + ~300 output (SQL)
  Verifier:    ~2K input (instruction + plan + result) + ~500 output (verification)
  ─────────────────────────────────────────────────────────
  Total:       ~6K input + ~1.3K output per iteration
  Max (3 iter): ~18K input + ~3.9K output per request

  Additional tool calls (schema introspection, ontology) add ~500-2K tokens
```

### 6.2 Tracking Token Usage

ADK's OpenTelemetry integration reports token usage in trace spans. When `ENABLE_CLOUD_TRACE=true`,
each LLM call span includes:
- `gen_ai.usage.input_tokens`
- `gen_ai.usage.output_tokens`
- `gen_ai.request.model`

To aggregate these into Cloud Monitoring metrics:

```python
# In LoggingPlugin.after_run_callback or a custom plugin:
from opentelemetry import metrics

meter = metrics.get_meter("ai_cdp")
token_counter = meter.create_counter("llm.token_usage")

class TokenTrackingPlugin(BasePlugin):
    """Track token usage per request for billing and budget alerts."""

    async def after_agent_callback(self, *, agent, callback_context):
        # ADK exposes usage in the invocation context
        usage = callback_context.state.get(f"temp:token_usage_{agent.name}")
        if usage:
            ctx = get_request_context_or_none()
            site_id = str(ctx.site_id) if ctx else "unknown"
            token_counter.add(usage.get("input_tokens", 0),
                attributes={"direction": "input", "model": MODEL_NAME,
                            "agent": agent.name, "site_id": site_id})
            token_counter.add(usage.get("output_tokens", 0),
                attributes={"direction": "output", "model": MODEL_NAME,
                            "agent": agent.name, "site_id": site_id})
```

### 6.3 Budget Controls

| Control | Implementation | GCP Service |
|---------|---------------|-------------|
| **Daily budget alert** | Cloud Monitoring alert on `llm.token_usage` counter | Cloud Monitoring |
| **Per-site quota** | Check `site.settings.token_budget` before agent invocation | Application code |
| **Rate limiting** | Cloud Armor rate-limit rule per authenticated user | Cloud Armor |
| **Cost dashboard** | Token count x model pricing, grouped by site | Cloud Monitoring |

**Gemini 3 Flash pricing (as of 2026):**
- Input: $0.10 / 1M tokens (< 200K context), $0.40 / 1M tokens (> 200K context)
- Output: $0.40 / 1M tokens

**Estimated cost per DS-STAR request:** ~$0.001 (1 iteration) to ~$0.003 (3 iterations)

### 6.4 Per-Site Token Budget

Add to the `sites.settings` JSONB:
```json
{
  "max_iterations": 3,
  "daily_token_budget": 1000000,
  "monthly_token_budget": 20000000
}
```

Check at orchestrator entry:
```python
# In ReviveOrchestrator._run_async_impl():
budget = ctx.session.state.get("site:daily_token_budget")
used = get_daily_token_usage(site_id)  # Query from metrics or DB
if budget and used >= budget:
    yield create_state_delta_event(author=self.name, phase="error",
        error="Daily token budget exceeded")
    return
```

---

## 7. Response Quality Measurement

### 7.1 Quality Signals Available Today

| Signal | Source | How to Use |
|--------|--------|------------|
| **Verifier verdict** | `verification.sufficient` | Binary success/fail per request |
| **Iteration count** | Orchestrator loop counter | Lower = higher confidence |
| **SQL dry-run result** | `dry_run_sql_tool` | Tracks schema accuracy |
| **action_executions log** | AlloyDB table | Full replay of every scoring/segment action |
| **LoggingPlugin timing** | Agent/tool duration | Identifies slow or stuck agents |

### 7.2 Offline Evaluation

Build evaluation datasets from production `action_executions` and agent session logs:

```
┌────────────────────────────────────────────────┐
│  Evaluation Pipeline                            │
│                                                 │
│  1. Collect (weekly):                           │
│     - Sample 100 agent sessions from logs       │
│     - Extract: user_query, execution_plan,      │
│       sql_generated, preview_data, verification │
│                                                 │
│  2. Label (human review):                       │
│     - SQL correctness (does it answer the Q?)   │
│     - Result accuracy (are the numbers right?)  │
│     - Plan quality (did it pick right tables?)  │
│                                                 │
│  3. Score (automated):                          │
│     - SQL syntax validity (dry-run)             │
│     - Table/column existence (schema check)     │
│     - Result set stability (re-run, compare)    │
│                                                 │
│  4. Track (dashboard):                          │
│     - Accuracy trend over time                  │
│     - Regression detection after model updates  │
│     - Per-category breakdown (VIP, cart, brand)  │
└────────────────────────────────────────────────┘
```

### 7.3 ADK Eval Integration

ADK has built-in evaluation support. Use existing evalset format:

```bash
# Run evaluation against test cases
adk eval test_ds_agent revive_agent/tests/ds_agent_tools.evalset.json --print_detailed_results
```

Create eval datasets for each query category:
- `tests/eval_abandoned_cart.evalset.json`
- `tests/eval_vip_customer.evalset.json`
- `tests/eval_brand_analysis.evalset.json`

### 7.4 Human Feedback Loop

```
User submits query
     │
     ▼
Agent produces result
     │
     ▼
Frontend shows result + thumbs up/down
     │
     ├── Thumbs up: log to action_executions(action_type='feedback_positive')
     │
     └── Thumbs down + optional comment:
         log to action_executions(action_type='feedback_negative',
                                  request_json={comment: "..."})
         │
         ▼
     Weekly review: analyst examines negative feedback,
     creates eval test cases from failures
```

**Implementation:** Add a feedback endpoint:
```python
@router.post("/api/feedback")
async def submit_feedback(session_id: str, rating: str, comment: str = "",
                          user: UserContext = Depends(get_current_user)):
    log_action(engine, user.site_id, f"feedback_{rating}",
               request_data={"session_id": session_id, "comment": comment},
               executed_by=user.user_id)
```

### 7.5 Agent Behavior Replay

The `action_executions` table with `correlation_id` enables full session replay:

```sql
-- Replay all actions for a specific agent session
SELECT action_type, target_node_key, request_json, response_json,
       execution_status, started_at, completed_at
FROM action_executions
WHERE correlation_id = 'session-abc-123'
ORDER BY started_at;
```

This provides a forensic audit trail: what ontology nodes were consulted, what scores
were computed, what segments matched -- all with timestamps and user attribution.

---

## 8. Ontology Update Process

### 8.1 Current Ontology Architecture (v3)

The ontology defines three node types stored as JSONB in AlloyDB:

```
UnifiedOntologyConfig (v3)
├── site_id: str
├── version: str (e.g. "3.0")
├── nodes: Dict[str, Node]
│   ├── DataSourceNode  -- tables, columns, descriptions
│   │   └── tables: [{name, columns: [{name, type, description}]}]
│   ├── AttributeNode   -- customer dimensions with quiz rules
│   │   ├── options: [{name, value, semanticDefinition}]
│   │   ├── rules: [{quiz, valueMappings}]
│   │   └── lifecycle: experimental | active | deprecated | archived
│   └── SegmentNode     -- pre-defined customer segments
│       ├── conditions: [{attribute, operator, value}]
│       ├── actions: {nba, nbo}
│       └── lifecycle: experimental | active | deprecated | archived
```

### 8.2 CRUD API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/ontology` | Full ontology config |
| PUT | `/api/ontology` | Replace entire ontology |
| GET | `/api/ontology/nodes` | List all nodes (filter by `?type=`) |
| GET | `/api/ontology/nodes/{key}` | Get single node |
| POST | `/api/ontology/nodes/{key}` | Create node |
| PUT | `/api/ontology/nodes/{key}` | Update node |
| DELETE | `/api/ontology/nodes/{key}` | Delete node (cascade protection) |
| POST | `/api/ontology/nodes/{key}/options` | Add option to attribute |
| DELETE | `/api/ontology/nodes/{key}/options` | Remove option from attribute |
| POST | `/api/ontology/nodes/{key}/score` | Score quiz responses |
| POST | `/api/ontology/resolve-segments` | Match segments to attributes |

All endpoints require authentication (`Depends(get_current_user)`).

### 8.3 Lifecycle Status Workflow

```
   ┌──────────────┐
   │ experimental │  New nodes start here. Agents can see but
   │              │  flag as "experimental" in responses.
   └──────┬───────┘
          │ validate + promote
          ▼
   ┌──────────────┐
   │    active     │  Production-ready. Agents use for planning
   │              │  and SQL generation.
   └──────┬───────┘
          │ sunset
          ▼
   ┌──────────────┐
   │  deprecated  │  Agents avoid using. Existing references
   │              │  still resolve. Migration period.
   └──────┬───────┘
          │ remove
          ▼
   ┌──────────────┐
   │   archived   │  Hidden from agents. Retained in DB
   │              │  for audit history.
   └──────────────┘
```

Update lifecycle via the node update API:
```bash
curl -X PUT /api/ontology/nodes/vip_segment \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"type": "segment", "lifecycle": "deprecated", ...}'
```

### 8.4 Audit Trail

Every ontology change is recorded in `config_audit_log` with field-level diffs:

```json
// Example audit record
{
  "site_id": 1,
  "config_type": "ontology",
  "action": "update",
  "changed_by": 42,
  "diff_json": {
    "changed": {
      "vip_segment": {
        "before": {"lifecycle": "active", "conditions": [...]},
        "after": {"lifecycle": "deprecated", "conditions": [...]}
      }
    }
  },
  "created_at": "2026-04-06T10:30:00Z"
}
```

The diff is computed by `_compute_diff()` in `db_repository.py`, comparing
the previous and new JSONB snapshots at the node level.

### 8.5 Hot-Reload

After updating the ontology via API, reload the in-memory config:

```bash
curl -X POST /api/config/reload \
  -H "Authorization: Bearer $TOKEN"
```

This clears the `ConfigManager` cache and evicts the `SiteResourceManager` cache,
so the next agent invocation picks up the new ontology. No server restart required.

**Important:** Agent instructions are baked at startup (in `agent.py`). The hot-reload
refreshes tool responses (ontology data returned by `get_ontology_tool()`), but does not
change agent system prompts. If agent instructions reference specific node names, those
references become stale until server restart.

### 8.6 Version Control Strategy

| Approach | When | How |
|----------|------|-----|
| **AlloyDB audit log** | Every change | Automatic via `DbOntologyRepository.save()` |
| **Export to git** | Before major releases | `GET /api/ontology` > `config/ontology.json`, commit |
| **Migration scripts** | Schema version bumps | `deploy/migrations/NNN_description.sql` |

**Recommended workflow for ontology changes:**

```
1. Developer creates node in "experimental" status via API
2. Test with agent queries, verify SQL generation
3. Promote to "active" via PUT /api/ontology/nodes/{key}
4. Export snapshot: GET /api/ontology > config/ontology.json
5. Commit snapshot to git for version control
6. Hot-reload: POST /api/config/reload
```

### 8.7 Migration (v2 to v3)

The v2-to-v3 migration unified separate entity/label/taxonomy files into a single
`UnifiedOntologyConfig`. For sites still on v2:

1. Run the migration script (transforms separate JSONs into unified format)
2. Upload via `PUT /api/ontology`
3. Verify via `GET /api/ontology/nodes?type=datasource` (should list all tables)
4. Test agent queries to confirm SQL generation works

---

## Appendix A: Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Prod | None | AlloyDB connection (enables DB sessions + config) |
| `GOOGLE_CLIENT_ID` | Prod | None | Google OAuth client ID |
| `JWT_SECRET` | Prod | `dev-secret-...` | HMAC key for session JWTs |
| `JWT_EXPIRY_SECONDS` | No | `86400` | JWT lifetime (24h default) |
| `GP_HOST` | Yes | `localhost` | Greenplum host |
| `GP_PORT` | Yes | `5432` | Greenplum port |
| `GP_USER` | Yes | `gpadmin` | Greenplum admin user |
| `GP_READONLY_USER` | Rec | `GP_USER` | Greenplum readonly user |
| `GP_READONLY_PASSWORD` | Rec | `GP_PASSWORD` | Readonly user password |
| `CORS_ORIGINS` | Prod | localhost | Comma-separated origins |
| `LOG_LEVEL` | No | `INFO` | Python log level |
| `ENABLE_CLOUD_LOGGING` | Prod | `false` | Export logs to Cloud Logging |
| `ENABLE_CLOUD_TRACE` | Prod | `false` | Export traces to Cloud Trace |
| `GCP_PROJECT_ID` | Prod | None | GCP project for Cloud services |
| `GCP_LOCATION` | No | `us-central1` | GCP region |
| `DEV_USER_EMAIL` | Dev | None | Bypasses auth (sets DEV_MODE=true) |
| `DEV_MODE` | Dev | `false` | Explicit dev mode flag |
| `API_KEY` | No | None | Legacy API key auth |

## Appendix B: Database Schema (AlloyDB)

```sql
-- Tenant registry
sites (id, name, slug, settings JSONB, created_at)

-- Per-site database connections
data_sources (id, site_id FK, name, db_type, connection_config JSONB, is_active)

-- Google-authenticated users
users (id, google_id UNIQUE, email, name, avatar_url, created_at)

-- Site membership with roles (owner, admin, member)
site_members (site_id FK, user_id FK, role, created_at) PK(site_id, user_id)

-- Per-site config storage (ontology, label_rules, plans, etc.)
site_configs (id, site_id FK, config_type, config_data JSONB, version, updated_by FK)
  UNIQUE(site_id, config_type)

-- Audit trail for config changes
config_audit_log (id, site_id, config_type, action, changed_by FK,
                  previous_data JSONB, new_data JSONB, diff_json JSONB, created_at)

-- Action execution log
action_executions (id, site_id FK, action_type, target_node_key,
                   request_json JSONB, response_json JSONB,
                   execution_status, error_message, executed_by FK,
                   started_at, completed_at, correlation_id)

-- Schema migrations tracker
schema_migrations (filename PRIMARY KEY, applied_at)
```

## Appendix C: Deployment Commands

```bash
# Deploy (DB migrations + app) against an existing PostgreSQL 12+
./deploy/gcp/deploy.sh \
  --project PROJECT_ID \
  --region us-central1 \
  --database-url "postgresql+psycopg2://user:pass@host:5432/aicdp" \
  --admin-email admin@company.com

# App-only redeploy (DB already migrated)
./deploy/gcp/deploy.sh --project PROJECT_ID --database-url "..." --skip-migrations

# Schema migration only
./deploy/gcp/deploy.sh --project PROJECT_ID --database-url "..." --skip-deploy

# Legacy AlloyDB stack (current prod until migrated)
./deploy/legacy/deploy-alloydb.sh --project PROJECT_ID --skip-infra
./deploy/legacy/teardown-alloydb.sh --project PROJECT_ID

# Local dev with PostgreSQL 12
docker compose -f deploy/local/docker-compose.yml up -d
DATABASE_URL=postgresql+psycopg2://postgres:aicdp-dev@localhost:5432/aicdp \
  python -m backend.server
```
