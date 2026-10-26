# API Reference

## Chat & Streaming

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/api/chat/stream` | Stream ADK events (thoughts, tool calls, answers) | JWT |
| ANY | `/ag-ui` | AG-UI middleware for CopilotKit frontend | JWT |

## Ontology — `routers/ontology.py`

Prefix: `/api/ontology` | Auth: JWT

### Full Config

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/ontology` | Get full ontology (v3 unified config) |
| PUT | `/api/ontology` | Replace full ontology |

### Node CRUD

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/ontology/nodes` | List nodes (optional `?type=datasource\|attribute\|segment`) |
| GET | `/api/ontology/nodes/{key}` | Get single node |
| POST | `/api/ontology/nodes/{key}` | Create node (discriminated by `type` field) |
| PUT | `/api/ontology/nodes/{key}` | Update node |
| DELETE | `/api/ontology/nodes/{key}` | Delete node (cascade protection) |

### Node Options (attribute type only)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/ontology/nodes/{key}/options` | Add option to attribute node |
| DELETE | `/api/ontology/nodes/{key}/options` | Remove option from attribute node |

### Scoring

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/ontology/nodes/{key}/score` | Score responses against attribute's quiz rule |

### Segment Resolution

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/ontology/resolve-segments` | Match attributes to segments |
| POST | `/api/ontology/resolve-nba-context` | Get NBA context for a segment |
| POST | `/api/ontology/resolve-nbo-context` | Get NBO context for a segment |

## Brand — `routers/brand.py`

Prefix: `/api/brand` | Auth: JWT

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/brand/analyze` | Analyze brand website, extract identity, save to ontology |

## Persona — `persona/router.py`

Prefix: `/api/persona` | Auth: JWT

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/persona/classify` | Fast persona classification via vector search |
| POST | `/api/persona/classify/batch` | Batch persona classification |
| POST | `/api/persona/analyze` | Agentic RAG persona analysis (SSE stream) |
| POST | `/api/persona/taxonomy/reload` | Re-ingest taxonomy into vector store |

## Auth — `auth.py` (inline in server.py)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/api/auth/google` | Google OAuth login, returns session JWT | None |
| GET | `/api/auth/me` | Get current user context | JWT |

## Config — `routers/config_reload.py`

Prefix: `/api/config` | Auth: JWT (admin only)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/config/reload` | Reload ontology config (agents need restart) |

## Health

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/health` | Health check | None |

---

**Total: 24 endpoints** across 5 routers + auth + health

## Node Types (v3 Ontology)

All nodes in `/api/ontology` use a discriminated union based on the `type` field:

### DataSourceNode (`type: "datasource"`)
Physical table/view mapping. Fields: `name`, `table`, `primaryKey`, `columns`, `status`.

### AttributeNode (`type: "attribute"`)
Business concept with computation rules. Fields: `name`, `valueType`, `isMultiple`, `isScored`, `options`, `rules`, `status`.

### SegmentNode (`type: "segment"`)
Business audience with conditions. Fields: `name`, `conditions`, `logic`, `orderRules`, `actions`, `status`.

### Node Status
All nodes support lifecycle: `experimental` | `active` | `deprecated` | `archived`. Default: `active`.
