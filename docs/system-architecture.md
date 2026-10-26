# AI-CDP System Architecture (current)

End-to-end map of the system after the PG12 / ADK 2.2 / chat-memory / skill-router
work. For the production security/observability deep-dive see `architecture.md`;
for the semantic-layer reference see `cdp-config-guide.md`.

Stack: Angular + CopilotKit/AG-UI frontend · FastAPI + Google ADK 2.2 backend ·
PostgreSQL 12 app DB · per-site Greenplum 6.22 / PG12 analytics DB · Gemini.

---

## 1. Component layers

```
┌─────────────────────────────────────────────────────────────────────────┐
│ FRONTEND  (Angular 18 + CopilotKit/AG-UI)                                 │
│   workspace.component → chat-panel.component (injectAgentStore)           │
│   HttpAgent → /ag-ui              auth.interceptor → Bearer on /api/*      │
│   ChatSessionService (backend sync + localStorage fallback)               │
└───────────────┬──────────────────────────────┬────────────────────────────┘
                │ /ag-ui (SSE)                  │ /api/* (REST)
┌───────────────▼──────────────────────────────▼────────────────────────────┐
│ FASTAPI  (backend/server.py)                                              │
│   middleware: rate-limit → request-context (UserContext via contextvars)  │
│   ADK adapter: ADKAgent.from_app(session_service, memory_service,         │
│                user_id_extractor, use_thread_id_as_session_id)            │
│   routers: ontology · brand · config · chat_history · persona            │
└───────┬───────────────────────────┬───────────────────────┬───────────────┘
        │                           │                       │
┌───────▼─────────┐   ┌─────────────▼───────────┐   ┌───────▼────────────────┐
│ AGENT LAYER     │   │ CONFIG / ONTOLOGY       │   │ PERSISTENCE            │
│ (ADK App)       │   │ ConfigManager (per-site)│   │ session_service (ADK)  │
│ root = router   │   │  ontology / rules /     │   │ memory_service (PG)    │
│  or orchestrator│   │  strategies + evaluator │   │ db.get_engine (app DB) │
└───────┬─────────┘   └─────────────────────────┘   └────────────────────────┘
        │
┌───────▼───────────────────────────────────────────────────────────────────┐
│ TOOLS + SKILLS + SERVICES                                                  │
│  tools/: schema · sql · ontology · brand · plan · skill · config_write ·   │
│          skill_exec   (all reach _infra factories: get_runner/get_config)  │
│  skills/registry · services/{external_actions, guardrails}                 │
│  memory/postgres_memory_service                                           │
└───────┬───────────────────────────────────────────────────────────────────┘
        │ get_runner() per-site (contextvars → SiteResourceManager)
┌───────▼─────────────┐   ┌──────────────────────┐   ┌───────────────────────┐
│ Greenplum 6.22 /    │   │ Gemini (3-flash)     │   │ External CDP (future) │
│ PG12 analytics DB   │   │ via ADK / google-genai│   │ ExternalActionAdapter │
│ (read-only runner)  │   │                      │   │  DryRunAdapter now    │
└─────────────────────┘   └──────────────────────┘   └───────────────────────┘
```

---

## 2. Chat request — end-to-end call sequence

Two transports reach the same agent graph: **`/ag-ui`** (CopilotKit, the
default UI path, SSE) and **`/api/chat/stream`** (raw NDJSON, used by tests and
quick-action buttons). Both run the ADK `Runner` with the shared session +
memory services.

```
User types in chat-panel
   │
   ▼
HttpAgent.runAgent()  ──POST /ag-ui (SSE)──►  ADKAgent (ag_ui_adk)
   │                                              │ user_id = UserContext.email
   │                                              │ session_id = thread_id
   ▼                                              ▼
                                            Runner.run_async(app, session_service, memory_service)
                                                  │
                                                  ▼
                          ┌─────────────  root_agent  ─────────────┐
                          │        ReviveOrchestrator (DS-STAR)     │
                          └───────────────┬─────────────────────────┘
                                          │
    (Specialist agents — StrategyAgent / RuleAgent / OntologyAgent /
     SkillExecutor in revive_agent/skills/agents.py — are currently
     unwired; kept for a future routing mechanism.)
            │
            │  _run_async_impl loop (≤ site:max_iterations, default 3)
            │
   ┌────────┼──────────────────────────────────────────────┐
   │  1. DS-Agent  (plan)                                   │
   │       get_ontology_tool → ConfigManager.format_…      │
   │       PreloadMemoryTool → memory_service.search_memory │
   │       submit_execution_plan → state.execution_plan     │
   │  2. DE-Agent  (execute)                                │
   │       dry_run_sql_tool  ┐ SQLSafetyPlugin.before_tool: │
   │       run_sql_preview_tool ┘ SELECT-only + ontology     │
   │           → get_runner() → analytics DB (read-only)     │
   │       → state.execution_result                         │
   │  3. Verifier  (judge)                                  │
   │       → {sufficient, action} + campaign_summary        │
   │       action=backtrack? loop : escalate(complete)      │
   └────────┬──────────────────────────────────────────────┘
            │ each phase yields create_state_delta_event(...)
            ▼
   EventActions(state_delta={execution_plan, execution_result,
                             verification, campaign_summary, workflow})
            │
            ▼ (stream back out through Runner → adapter → SSE)
   chat-panel parses state_delta → renders plan / SQL / preview / campaign cards
            │
            ▼ after_agent_callback (orchestrator finishes)
   ctx.add_session_to_memory() → PostgresMemoryService._distill
        stores campaign_summary + execution_plan + user preferences (not transcript)
```

### Tool → infrastructure resolution

Every tool reaches shared resources through `revive_agent/tools/_infra.py`
factories, which resolve the **per-site** resource bundle from the request's
`UserContext` (contextvars):

```
tool()  →  get_runner()/get_config()/get_profiler()
              → _get_resources()
                  → get_request_context_or_none().site_id   (or _DEFAULT_SITE_ID=1)
                  → SiteResourceManager.get(site_id)
                      → SiteResources{ GreenplumRunner(read-only), DatabaseProfiler,
                                       ConfigManager(ontology/rules/strategies) }
```

---

## 3. Write path (rule / ontology / campaign) — guardrails

LLM-invoked mutations go through three enforced layers (financial-grade;
`services/guardrails.py`):

```
config_write_tools / skill_exec_tools.execute_action
   │
   ▼  ① authZ at the tool boundary
   check_authz()  → UserContext.role ∈ {owner,admin,editor}?  (else refuse)
   │
   ▼  ② HITL — per-site policy
   FunctionTool(require_confirmation = needs_confirmation(severity))
   guardrail_level(site)  strict→confirm all · standard→destructive+sends · trusted→none
   → ADK emits requested_tool_confirmation; agent shows before/after diff; user approves
   │
   ▼  ③ validated apply + audit
   ConfigManager.save_* (integrity.py refs check)  |  ExternalAction → adapter
   record_action() → action_executions  (shared audit primitive)
```

External execution is pluggable: `ExternalActionAdapter` ABC + per-site
registry. Today only `DryRunAdapter` (logs + audits, nothing leaves). A real
CDP MCP/REST connector drops in behind the same ABC. The payload is a typed
`MarketingPlan` (goal, KPI, segmentation taxonomy|behavioral, audience,
evidence, strategy, channel + rationale) — the plan states WHAT/WHY, the skill
encodes HOW.

---

## 4. Persistence

| Store | Driver | Holds | Code |
|---|---|---|---|
| App DB (PostgreSQL 12) — sync | psycopg2 | sites, users, site_members, site_configs, action_executions, **memories** | `db.get_engine()` |
| App DB — async | asyncpg | ADK sessions + events (chat history) | `DatabaseSessionService` |
| Memory | sync engine | distilled facts (tsvector search), site-scoped | `PostgresMemoryService` |
| Analytics DB (per-site) | psycopg2 (read-only) | customer data (Greenplum 6.22 / PG12) | `GreenplumRunner` via `_infra` |

Dev (no `DATABASE_URL`): ADK falls back to `InMemorySessionService` +
`InMemoryMemoryService`; `_infra` falls back to env-var Greenplum and `site_id=1`.
Migrations: `deploy/migrations/NNN_*.sql` via `deploy/init_db.py` (tracked in
`schema_migrations`). `--seed-configs` loads `config/*.json` into `site_configs`.

---

## 5. Config flags

| Flag | Default | Effect |
|---|---|---|
| `DATABASE_URL` | unset | set → Postgres session/memory/config; unset → in-memory dev |
| `PYTHON_SKILL_ENABLED` | off | on → register sandboxed `python_analysis` skill (needs Docker) |
| `ENABLE_MODEL_GUARD` | off | on → PII ModelGuardPlugin |
| guardrail_level (per-site `sites.settings`) | strict | strict / standard / trusted HITL policy |

---

## 6. Key files

| Path | Role |
|---|---|
| `backend/server.py` | FastAPI app, ADK adapter, routers |
| `backend/revive_agent/agent.py` | DS/DE/Verifier agents, orchestrator wiring, memory callback |
| `backend/revive_agent/orchestrator.py` | DS-STAR `_run_async_impl` loop + state_delta events |
| `backend/revive_agent/skills/agents.py` | strategy / rule / ontology / executor sub-agents (unwired) |
| `backend/revive_agent/tools/` | tool modules; `_infra.py` per-site factories |
| `backend/skills/registry.py` | skill registry (executable capabilities) |
| `backend/services/external_actions.py` | ExternalActionAdapter + DryRunAdapter + registry |
| `backend/services/guardrails.py` | authZ + per-site HITL + audit |
| `backend/memory/postgres_memory_service.py` | Postgres BaseMemoryService |
| `backend/config/` | ontology/rules/strategies schemas, loader, evaluator, repos |
| `backend/site_resources.py` | per-site engine/runner/config cache |
| `backend/routers/chat_history.py` | session list / messages / delete / capabilities |
| `docs/adr/0001-ds-star-baseagent.md` | why DS-STAR stays BaseAgent; router = transfer |
```
