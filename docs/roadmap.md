# AI-CDP Roadmap

## What's Done

### Phase 1: Foundation (complete)
- Request-scoped auth via contextvars (`backend/context.py`)
- Google OAuth + session JWT (`backend/auth.py`)
- SiteResourceManager with per-site cache (`backend/site_resources.py`)
- AlloyDB on GCP with migration runner (`deploy/init_db.py`)
- GCP deploy scripts — Cloud Run + AlloyDB (`deploy/gcp/`)
- Centralized settings (`backend/settings.py`) + DEV_MODE
- Centralized logging with rotation (`backend/logging_config.py`)
- DS-STAR session state clearing between invocations
- 90 unit tests

### Ontology v3 Consolidation (complete)
- Unified 3 parallel config systems (v1 entity-relationship, v2 flat nodes, label_rules) into single v3 property graph
- 3 discriminated node types: `DataSourceNode`, `AttributeNode`, `SegmentNode`
- Shared scoring engine: `score()`, `evaluate_segment()`, `build_taxonomy_context()`
- Generic scoring naming (not quiz-specific): `ScoringConfig`, `ScoringError`, `score_tool()`
- Lifecycle status on all nodes: `experimental → active → deprecated → archived`
- Field-level audit diff in AlloyDB (added/removed/changed nodes)
- Action execution log table for observability
- ~1,100 lines of dead code removed
- Migration tooling removed after v3 cutover (recover from git history if a v2 config resurfaces)

### Platform Migration + Skill Layer (complete, 2026-06)
- App DB migrated AlloyDB → plain **PostgreSQL 12** (local docker-compose); repos
  renamed `AlloyDb*`→`Db*`; AlloyDB scripts moved to `deploy/legacy/`; new
  DB-agnostic `deploy/gcp/deploy.sh` (DB URL via Secret Manager)
- **ADK 1.22 → 2.2.0** (aiohttp pinned ≥3.14 for google-genai streaming)
- Ontology cleanup: removed deprecated v1/v2 models, `migration.py`,
  `label_rules.json`, dead `OrderRule`/`conditionExpression` fields
- **Chat history + long-term memory**: `PostgresMemoryService` (ADK
  `BaseMemoryService`, distilled facts only, site-scoped, tsvector); chat-history
  API; `/ag-ui` now persists sessions via the shared session+memory services
- **Skill layer + intent router**: skill registry, `ExternalActionAdapter`+DryRun,
  per-site `guardrail_level` HITL on writes. The IntentRouter front door was
  later removed (DS-STAR is the root unconditionally; specialist sub-agents kept
  unwired). See `docs/system-architecture.md`, `docs/adr/0001-ds-star-baseagent.md`

## What's Next

### 0. Wire the real external CDP connector
- Implement `ExternalActionAdapter` for the customer's CDP (REST or ADK MCPToolset)
- Register per-site in `services/external_actions.py`; DryRun stays the default
- Real-time behavior-data ingestion + uploaded-file analysis (see ADR 0001)

### 1. Graph RAG Lite (next session)
- Add DataSource nodes to `config/ontology.json` (physical table mappings)
- Embed ontology nodes in Vertex AI Vector Search (reuse persona infrastructure)
- Add `search_ontology_tool(query)` with 1-hop graph expansion
- Replace full-dump `format_ontology_for_prompt()` with focused subgraph injection
- See `docs/graph-rag-optimization.md` for full plan

### 2. Hybrid Segment Discovery
- Semantic search over attribute options (semanticDefinition field)
- Map matched options → attributes → segments
- Agent can discover segments by natural language instead of exact keys

### 3. Deferred (Phase 3)
- Cloud Trace / Cloud Logging export (`ENABLE_CLOUD_TRACE`, `ENABLE_CLOUD_LOGGING`)
- Persona vector store + ontology integration
- Spanner Graph (only if ontology exceeds ~200 nodes)
- RBAC beyond admin/member roles
- Frontend auth guard refinement
- Generic operational ontology runtime (see `docs/operational-ontology-guide.md`)

## Docs Index

| Doc | Purpose | Status |
|-----|---------|--------|
| `README.md` | Entry point — overview, local run, private-server deploy | Current |
| `CLAUDE.md` | Project conventions, quick start, env vars, known gotchas | Current |
| `docs/system-architecture.md` | End-to-end calling diagram + component layers (current build) | Current |
| `docs/architecture.md` | Production architecture: security, audit, monitoring (8 sections) | Current |
| `docs/adr/0001-ds-star-baseagent.md` | DS-STAR on BaseAgent; router = sub-agent transfer | Current |
| `docs/api-reference.md` | HTTP endpoint reference (24 endpoints) | Current |
| `docs/roadmap.md` | This file — what's done and what's next | Current |
| `docs/graph-rag-optimization.md` | Graph RAG implementation plan for AI-CDP | Current |
| `docs/operational-ontology-guide.md` | Generic object/action runtime design (deferred) | Current |
| `docs/persona-classification.md` | Jungian archetype classification system | Current |
