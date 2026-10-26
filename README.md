# AI-CDP

AI-powered SQL generation and campaign planning for a Customer Data Platform.
A multi-agent backend (Google ADK) turns a marketer's natural-language goal into
ontology-governed, read-only SQL against the analytics warehouse, plans
campaigns, and (behind guardrails) hands off to external CDP actions.

**Stack:** Angular 19 + CopilotKit/AG-UI · FastAPI + Google ADK 2.2 · PostgreSQL 12
app DB · per-site Greenplum 6.22 / PostgreSQL analytics DB · Gemini.

The agent layer is **DS-STAR**: DS-Agent plans → DE-Agent executes SQL →
Verifier validates, looping until the result is sufficient.

```
ReviveOrchestrator (DS-STAR, root agent)
    ├── DS-Agent  → execution_plan (JSON)
    ├── DE-Agent  → execution_result (SQL + preview, SELECT-only)
    └── Verifier  → verification + campaign_summary
```

For the full end-to-end calling diagram see **[docs/system-architecture.md](docs/system-architecture.md)**.

---

## Prerequisites

- Python 3.12+
- Node.js 22+ (frontend build)
- Docker (local PostgreSQL, optional)
- A Gemini API key
- Read access to a Greenplum / PostgreSQL analytics database (the customer data)

---

## Run locally

### 1. Backend

```bash
# From the project root
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt

cp deploy/server/.env.production .env   # then edit .env — see Configuration below
source .env
python -m backend.server                # http://localhost:8000
```

Local app database (Postgres 12 in Docker) — needed for chat history, memory, and
multi-tenant config. Skip it to run in **in-memory dev mode** (no `DATABASE_URL`).

```bash
docker compose -f deploy/local/docker-compose.yml up -d         # postgres:12 on :5432
python deploy/init_db.py \
  --database-url "postgresql+psycopg2://postgres:aicdp-dev@localhost:5432/aicdp" \
  --admin-email "dev@test.com" --admin-name "Dev" --site-name "Dev Site" --seed-configs
DATABASE_URL=postgresql+psycopg2://postgres:aicdp-dev@localhost:5432/aicdp python -m backend.server
```

### 2. Frontend

```bash
cd frontend
npm install
npx ng serve                            # http://localhost:4200
```

`ng serve` proxies `/api/*` and `/ag-ui` to the backend on `:8000`
(see `frontend/proxy.conf.json`), so open **http://localhost:4200**.

### Dev mode (no auth, no DB)

Set `DEV_USER_EMAIL=dev@test.com` in `.env` to bypass Google OAuth and run without
a `DATABASE_URL` (ADK falls back to in-memory sessions/memory; analytics queries use
the `GP_*` env vars and `site_id=1`). Use this only for local development.

---

## Configuration

Environment variables (in `.env`; the template is `deploy/server/.env.production`):

| Variable | Required | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | yes | Gemini model access |
| `GP_HOST` `GP_PORT` `GP_USER` `GP_PASSWORD` `GP_DBNAME` | yes | Analytics DB (read-only source the agent queries) |
| `GP_READONLY_USER` / `GP_READONLY_PASSWORD` | no | Read-only analytics role; falls back to `GP_USER` |
| `DATABASE_URL` | prod | App DB (Postgres 12+) — enables persistent sessions, memory, multi-site config. Unset = in-memory dev |
| `JWT_SECRET` | prod | Signs session JWTs (`openssl rand -hex 32`) |
| `GOOGLE_CLIENT_ID` | prod | Google OAuth client for sign-in |
| `CORS_ORIGINS` | no | Comma-separated allowed origins; empty = same-origin only |
| `DEV_USER_EMAIL` | dev | Bypasses all auth; auto-enables `DEV_MODE` |
| `LOG_LEVEL` | no | `INFO` (default) or `DEBUG` |

---

## Deploy to a private server (systemd + nginx)

Target: a single Linux host (Ubuntu/Debian) running the backend as a systemd
service behind nginx, which also serves the built Angular SPA. No cloud required.
Artifacts live in **`deploy/server/`**.

**1. Provision a PostgreSQL 12+ app database** (on the host or reachable from it).

**2. Get the code and configure** (on the server, as root; repo at `/root/ai-cdp`):

```bash
git clone <repo> /root/ai-cdp && cd /root/ai-cdp
cp deploy/server/.env.production /root/ai-cdp/.env
vim /root/ai-cdp/.env        # DATABASE_URL, JWT_SECRET, GOOGLE_CLIENT_ID, GP_*, GEMINI_API_KEY
```

**3. Initialize the database** (first deploy — idempotent, creates schema + admin + site):

```bash
python deploy/init_db.py --database-url "$DATABASE_URL" \
  --admin-email admin@company.com --admin-name Admin --site-name "My Company" --seed-configs
```

**4. Deploy** (venv + dependencies, installs/starts the systemd unit, builds the
frontend, wires nginx):

```bash
sudo ./deploy/server/deploy.sh
```

The backend runs as the `ai-cdp` unit on `127.0.0.1:8000`; nginx serves the SPA
from `/var/www/ai-cdp` and reverse-proxies `/api/*` and `/ag-ui` (SSE-aware).

**TLS:** set your certificate paths in `deploy/server/ai-cdp.nginx`
(`ssl_certificate` / `ssl_certificate_key`), then reload nginx.

**Later deploys / upgrades:**

```bash
git pull
python deploy/init_db.py --database-url "$DATABASE_URL"   # runs only NEW migrations
sudo ./deploy/server/deploy.sh                            # rebuild + restart
# Flags: --skip-build, --skip-backend, --skip-frontend
```

**Operate:**

```bash
systemctl status ai-cdp
journalctl -u ai-cdp -f          # backend logs
systemctl reload nginx
```

> Other targets: GCP Cloud Run (`deploy/gcp/deploy.sh`) and the legacy AlloyDB
> stack (`deploy/legacy/`) — see [CLAUDE.md](CLAUDE.md#deployment).

---

## Database & migrations

`deploy/init.sql` is a single-file zero-to-running bootstrap (schema + site + admin
+ configs); `deploy/init_db.py` runs it via Python and applies incremental
migrations from `deploy/migrations/NNN_*.sql` (tracked in `schema_migrations`, so
only unapplied ones run). After changing `config/*.json` or adding a migration,
regenerate with `python deploy/generate_init_sql.py` and commit `init.sql`.

---

## Tests

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

Add or update tests for any new/changed API endpoint, auth logic, or infrastructure
module. Run `/simplify` before committing.

---

## Repository layout

| Path | Purpose |
|---|---|
| `backend/server.py` | FastAPI app, AG-UI endpoint, ADK adapter, root-agent selection |
| `backend/revive_agent/` | DS-STAR orchestrator, agents, instructions, tools |
| `backend/config/` | Unified ontology v3 (schemas, loader, scoring, repository) |
| `backend/services/` | External actions adapter + guardrails (authZ/HITL/audit) |
| `backend/memory/` | Postgres-backed ADK memory service |
| `backend/routers/` | REST routers (ontology, brand, config, chat history, persona) |
| `config/plans.json` | Workflow plans (abandoned cart, VIP, brand analysis) |
| `frontend/` | Angular + CopilotKit UI |
| `deploy/server/` | Private-server deploy (systemd + nginx) |
| `deploy/gcp/`, `deploy/local/`, `deploy/legacy/` | Cloud Run, local docker, AlloyDB |
| `tests/` | Pytest suite |

---

## Documentation

| Doc | What |
|---|---|
| [CLAUDE.md](CLAUDE.md) | Conventions, quick start, env vars, known gotchas |
| [docs/system-architecture.md](docs/system-architecture.md) | End-to-end calling diagram + component layers |
| [docs/architecture.md](docs/architecture.md) | Production architecture: security, audit, monitoring |
| [docs/api-reference.md](docs/api-reference.md) | HTTP endpoint reference |
| [docs/cdp-config-guide.md](docs/cdp-config-guide.md) | Ontology / semantic-layer configuration |
| [docs/roadmap.md](docs/roadmap.md) | What's done and what's next |
| [docs/adr/](docs/adr/) | Architecture decision records |
