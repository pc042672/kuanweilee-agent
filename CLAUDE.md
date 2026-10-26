# CLAUDE.md

## Overview

AI-CDP: AI-powered SQL generation for Greenplum using Google ADK. DS-STAR multi-agent architecture (DS-Agent plans, DE-Agent executes, Verifier validates).

## Quick Start

```bash
# Backend (from project root)
source .venv/bin/activate && python -m backend.server  # http://localhost:8000

# Frontend (from frontend/)
cd frontend && npx ng serve  # http://localhost:4200 (proxies to backend)

# Tests
python -m pytest tests/ -v
```

## Environment

Required in `.env`:
```
GEMINI_API_KEY=your-key
GP_HOST=host GP_PORT=5432 GP_USER=user GP_PASSWORD=pass GP_DBNAME=db
GP_READONLY_USER=readonly_user GP_READONLY_PASSWORD=pass  # optional, falls back to GP_USER
CORS_ORIGINS=  # comma-separated origins (empty = localhost only)
DEV_USER_EMAIL=dev@test.com  # sets DEV_MODE=true, bypasses all auth
DEV_MODE=true                # explicit dev mode (auto-enabled when DEV_USER_EMAIL is set)
```

Production (set `DATABASE_URL` to switch from dev to production):
```
DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/ai_cdp  # enables PostgreSQL-backed sessions + config
GOOGLE_CLIENT_ID=...           # required for Google OAuth in production
JWT_SECRET=...                 # required in production (defaults to dev secret)
LOG_LEVEL=DEBUG                # default: INFO
ENABLE_CLOUD_LOGGING=true      # Phase 3: export to Google Cloud Logging
```

## Architecture

```
ReviveOrchestrator (DS-STAR, root agent)
    ├── DS-Agent  → execution_plan (JSON)
    ├── DE-Agent  → execution_result (SQL + preview)
    └── Verifier  → verification + campaign_summary
```

Specialist agents (StrategyAgent, RuleAgent, OntologyAgent, SkillExecutor) live
in `backend/revive_agent/skills/agents.py` — currently unwired (the IntentRouter
front door was removed); kept for a future routing mechanism.
Full end-to-end calling diagram: `docs/system-architecture.md`.

## Workflow Plans

Plans in `config/plans.json` define multi-phase workflows matched by keywords:
- `abandoned-cart-analysis` - Find users who abandoned carts
- `vip-customer-analysis` - Identify high-value customers
- `brand-analysis-workflow` - Complete brand + campaign workflow (10 phases)

DS-Agent uses `load_plan_tool(match_query="...")` to match and load plans.

## Key Files

| Path | Purpose |
|------|---------|
| `backend/server.py` | FastAPI + AG-UI endpoint, ADK adapter, root-agent selection |
| `backend/revive_agent/orchestrator.py` | DS-STAR loop coordinator |
| `backend/revive_agent/agent.py` | Agent definitions + memory after-callback |
| `backend/revive_agent/skills/agents.py` | strategy / rule / ontology / executor sub-agents (unwired) |
| `backend/revive_agent/instructions.py` | Agent prompts (static + dynamic) |
| `backend/revive_agent/tools/` | Tool modules; `config_write_tools`, `skill_exec_tools`; `_infra.py` per-site factories |
| `backend/skills/registry.py` | Skill registry (executable capabilities) |
| `backend/services/external_actions.py` | ExternalActionAdapter + DryRunAdapter + registry |
| `backend/services/guardrails.py` | Tool-boundary authZ + per-site HITL + audit |
| `backend/memory/postgres_memory_service.py` | Postgres-backed ADK BaseMemoryService |
| `backend/auth.py` | Google OAuth + session JWT auth, UserContext |
| `backend/context.py` | Request-scoped UserContext via contextvars |
| `backend/site_resources.py` | Per-site SQLAlchemy engine + config cache |
| `backend/routers/` | FastAPI routers (ontology, brand, config, chat_history, persona) |
| `backend/config/` | Unified ontology v3 config (schemas, loader, scoring, repository) |
| `backend/config/db_repository.py` | PostgreSQL implementation of OntologyRepository Protocol |
| `config/plans.json` | Workflow plans (abandoned cart, VIP, brand analysis) |
| `frontend/` | Angular + CopilotKit UI |
| `docs/system-architecture.md` | End-to-end calling diagram (current build) |

## Database Init & Migrations

```bash
# Zero-to-running bootstrap — ONE SQL file: schema + site + admin + configs.
# Idempotent; after it, the service runs with just DATABASE_URL (no DEV_MODE).
psql "$DATABASE_URL" -f deploy/init.sql \
  -v admin_email="admin@example.com" -v admin_name="Admin" -v site_name="My Company"

# Alternative first deploy via Python (same result, plus --seed-configs)
python deploy/init_db.py \
  --database-url "postgresql+psycopg2://postgres:pass@host:5432/aicdp" \
  --admin-email "admin@example.com" --admin-name "Admin" --site-name "My Company" \
  --seed-configs

# Schema upgrade — runs only NEW migrations
python deploy/init_db.py --database-url "postgresql+psycopg2://postgres:pass@host:5432/aicdp"
```

`deploy/init.sql` is GENERATED — after changing `config/*.json` or adding a migration, regenerate with `python deploy/generate_init_sql.py` and commit it. Adding new migrations: create `deploy/migrations/NNN_description.sql`, run `init_db.py`. Only unapplied migrations run (tracked in `schema_migrations`; init.sql pre-seeds the ledger so only newer migrations apply).

## Local Development DB (PostgreSQL 12)

```bash
docker compose -f deploy/local/docker-compose.yml up -d   # postgres:12 on localhost:5432
python deploy/init_db.py \
  --database-url "postgresql+psycopg2://postgres:aicdp-dev@localhost:5432/aicdp" \
  --admin-email "dev@test.com" --admin-name "Dev" --site-name "Dev Site"
DATABASE_URL=postgresql+psycopg2://postgres:aicdp-dev@localhost:5432/aicdp python -m backend.server
```

## Deployment

### Private server (systemd + nginx, no cloud) — primary on-prem path
```bash
# On the server, as root, with the repo at /root/ai-cdp:
cp deploy/server/.env.production /root/ai-cdp/.env && vim /root/ai-cdp/.env  # fill in secrets
python deploy/init_db.py --database-url "$DATABASE_URL" \
  --admin-email admin@company.com --admin-name Admin --site-name "My Company" --seed-configs  # first deploy
sudo ./deploy/server/deploy.sh   # venv + systemd service + frontend build + nginx
# Schema upgrade on later deploys: python deploy/init_db.py --database-url "$DATABASE_URL"
```
Backend runs as the `ai-cdp` systemd unit on `127.0.0.1:8000`; nginx serves the
Angular SPA from `/var/www/ai-cdp` and proxies `/api/*` + `/ag-ui` (SSE) to it.
Set the TLS cert paths in `deploy/server/ai-cdp.nginx`.

### GCP (Cloud Run + PostgreSQL 12+)
```bash
# Deploy app to Cloud Run against an existing PostgreSQL 12+ DB (Cloud SQL or self-hosted)
./deploy/gcp/deploy.sh --project PROJECT_ID --region us-central1 \
  --database-url "postgresql+psycopg2://user:pass@host:5432/aicdp" \
  --admin-email admin@company.com

# App-only redeploy (DB already migrated)
./deploy/gcp/deploy.sh --project PROJECT_ID --database-url "..." --skip-migrations

# Schema upgrade only (no app deploy)
./deploy/gcp/deploy.sh --project PROJECT_ID --database-url "..." --skip-deploy
```
Cloud SQL provisioning is not yet automated — see the TODO block in `deploy/gcp/deploy.sh`.

### Legacy stacks
- AlloyDB (current prod until migrated): `deploy/legacy/deploy-alloydb.sh`, `deploy/legacy/teardown-alloydb.sh`; `deploy/redeploy.sh` wraps the AlloyDB app-only redeploy.

Files: `deploy/server/` (on-prem), `deploy/gcp/deploy.sh`, `deploy/local/docker-compose.yml`, `deploy/init_db.py`, `deploy/legacy/`

## Dependencies

- `google-adk>=2.2.0` - ADK 2.x (Gemini 3 SSE streaming, memory services, request_input HITL)
- `psycopg2-binary` - Greenplum driver
- `fastapi` + `uvicorn` - API server

`backend/requirements.txt` holds loose ranges; `backend/requirements.lock` holds the exact pins (Linux x86_64 / Python 3.12) that the Dockerfile and `deploy/server/deploy.sh` install. After editing `requirements.txt`, re-run the command in the lock's header (`uv pip compile …`) and commit both files. Existing pins are kept; add `--upgrade-package NAME` to bump one package.

## ADK Reference

- `docs/llms.txt` - ADK patterns. Key: `LlmAgent`, `BaseAgent._run_async_impl`, `EventActions(escalate=True)`.
- `../adk/adk-docs/` - Official ADK documentation (local copy)
- `../adk/adk-samples/python/agents/` - ADK sample agents for reference patterns

## Conventions

- Run `/simplify` before committing to catch dead code, quality issues, and inefficiencies
- Remove stale/useless comments — don't leave `// removed`, `// TODO` placeholders, or comments restating the code
- In ADK orchestrators: always yield sub-agent events (don't consume with `pass`) — `output_key` state updates depend on event propagation
- Prefer text-based agent output with regex parsing over `output_schema` for user-facing chat agents — structured JSON breaks chat UX
- Import paths in `backend/`: use bare paths (`from utils.sql_runner`, `from config`) relative to `backend/` on sys.path — NOT `from backend.utils.sql_runner` (breaks ADK web which runs from `backend/`)
- Tools `_infra.py` pattern: use factory functions `get_runner()`, `get_profiler()`, `get_config()` — they resolve per-request site via contextvars. Never import singletons directly.
- Run `python -m pytest tests/ -v` before committing — add/update tests for any new or modified API endpoints, auth logic, or infrastructure modules
- See `docs/phase1-implementation-guide.md` for architecture decisions and patterns

## Logging & Debugging

Logs write to `backend/logs/` (gitignored):
- `ai-cdp.log` — all INFO+ logs, daily rotation, 30-day retention
- `ai-cdp-error.log` — ERROR+ only, same rotation
- Rotated files: `ai-cdp.log.2026-04-04` (date suffix)

Set `LOG_LEVEL=DEBUG` in `.env` for verbose output. Config in `backend/logging_config.py`.

To tail logs during development:
```bash
tail -f backend/logs/ai-cdp.log
tail -f backend/logs/ai-cdp-error.log  # errors only
```

Phase 3: Set `ENABLE_CLOUD_LOGGING=true` to export to Google Cloud Operations Suite.

## Integration Testing

Use the Chrome DevTools MCP extension to visually test the frontend:
```bash
# 1. Start backend + frontend
DEV_USER_EMAIL=dev@test.com python -m backend.server  # port 8000
cd frontend && npx ng serve                            # port 4200

# 2. Use MCP chrome tools to open, navigate, and inspect
#    - navigate_page to http://localhost:4200
#    - take_screenshot to verify UI state
#    - evaluate_script to check console errors
#    - list_network_requests to inspect API calls
#    - get_console_message to read frontend errors
```

This allows end-to-end testing of the AG-UI SSE streaming, auth flow, and tool execution without manual browser interaction.

## DS-STAR Session State

The orchestrator clears `_WORKFLOW_STATE_KEYS` at the start of each `_run_async_impl` invocation so a new user message on the same thread doesn't see stale results from a prior query. Same keys are cleared on backtrack. See `backend/revive_agent/orchestrator.py` line 27 for the key list.

Per-site `max_iterations` is read from `ctx.session.state.get("site:max_iterations")` at runtime, falling back to the constructor default (3).

## Database Connection (PostgreSQL 12+)

The backend uses two connection modes to the app database:
- **Sync** (`psycopg2`): `backend/db.py` engine for user upsert, config queries
- **Async** (`asyncpg`): ADK `DatabaseSessionService` (auto-converted from `DATABASE_URL`)

Local dev: `docker compose -f deploy/local/docker-compose.yml up -d` (see Local Development DB above). Legacy AlloyDB access via Auth Proxy lives in `deploy/legacy/deploy-alloydb.sh`.

## Known Gotchas

- **AG-UI adapter async context**: The AG-UI SSE adapter (`/ag-ui`) runs agent tools in async tasks that do NOT inherit the middleware's `contextvars`. The `_infra.py` factory functions fall back to `site_id=1` when context is missing. This is expected in dev — multi-tenant context via JWT works in production.
- **Starlette middleware + streaming**: Never `reset_request_context()` in a middleware `finally` block — it fires before SSE body streams complete. contextvars are per-task in ASGI and don't leak between requests.
- **FastAPI Depends in middleware**: Never call a `Depends()`-wired function manually from middleware — DI doesn't run, dependent params will be `None`. Extract auth from headers directly instead (see `_resolve_context` in `server.py`).
- **Module import paths**: `backend.auth` and `auth` are different modules in Python's import system. When patching in tests, use the full `backend.auth` path to match the server's imports.
- **ADK DatabaseSessionService requires async driver**: `psycopg2` is sync-only. The `DATABASE_URL` is auto-converted to `asyncpg` for the session service. Both `psycopg2-binary` and `asyncpg` are required in `requirements.txt`.
