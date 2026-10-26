# Backend API Specification

## Overview

FastAPI server providing AI-powered SQL generation for Greenplum databases using Google ADK multi-agent architecture.

**Base URL:** `http://localhost:8000`

## Dependencies

| Package | Version | Notes |
|---------|---------|-------|
| `google-adk` | ≥1.22.0 | Required for Gemini 3's progressive SSE streaming |
| `psycopg2-binary` | latest | PostgreSQL/Greenplum driver |
| `fastapi` | latest | API server |
| `uvicorn` | latest | ASGI server |

**Important:** ADK v1.22.0+ is required for proper AG-UI endpoint operation with Gemini 3 models. Earlier versions have issues with Gemini 3's "Thought Signatures" in SSE streaming mode.

## Model Configuration

| Setting | Value |
|---------|-------|
| **Model** | `gemini-3-flash-preview` (Gemini 3 Flash Preview) |
| **Max Input Tokens** | 1M |
| **Max Output Tokens** | 64K |
| **Knowledge Cutoff** | January 2025 |
| **Retry Config** | 5 attempts, exponential backoff for 429/500/503/504 |

Reference: [Gemini 3 Flash Documentation](https://ai.google.dev/gemini-api/docs/gemini-3)

## Endpoints

### 1. Chat Stream

Streams ADK Events (agent thoughts, tool calls, results) to the frontend.

```
POST /api/chat/stream
```

#### Request

```json
{
  "session_id": "string",      // Unique session identifier
  "message": "string",         // User message
  "user_id": "string"          // Optional, defaults to "default_user"
}
```

#### Response

**Content-Type:** `application/x-ndjson` (Newline-delimited JSON)

Streams ADK Event objects, one per line:

```json
{"author":"DSAgent","content":{"role":"model","parts":[{"text":"..."}]},"actions":{}}
{"author":"DEAgent","content":{"role":"model","parts":[{"text":"..."}]},"actions":{}}
```

#### Event Structure

```typescript
interface ADKEvent {
  author: string;              // Agent name: "DSAgent", "DEAgent", "Verifier", "ReviveOrchestrator"
  content?: {
    role: "model" | "user";
    parts: Array<{ text?: string; functionCall?: object; functionResponse?: object }>;
  };
  actions?: {
    escalate?: boolean;        // True when task is complete
  };
}
```

#### Example

```bash
curl -X POST "http://localhost:8000/api/chat/stream" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "sess_123", "message": "Find abandoned cart users", "user_id": "user_1"}'
```

---

### 2. AG-UI Endpoint (CopilotKit)

AG-UI middleware endpoint for CopilotKit frontend integration.

```
POST /ag-ui
```

This endpoint follows the AG-UI protocol for CopilotKit. See [AG-UI documentation](https://github.com/ag-ui-protocol/ag-ui) for details.

**Requirements:**
- ADK v1.22.0+ (required for Gemini 3 compatibility)
- Progressive SSE streaming is enabled by default in v1.22.0+
- This fixes Gemini 3's "Thought Signatures" which arrive in empty text chunks
- Reference: [google/adk-python#4090](https://github.com/google/adk-python/issues/4090)

---

## Configuration API (CRUD)

Full CRUD operations for ontology and label rules configuration.

### Ontology Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/config/ontology` | Get full ontology |
| PUT | `/api/config/ontology` | Replace full ontology |
| GET | `/api/config/ontology/entities/{entity_id}` | Get single entity |
| POST | `/api/config/ontology/entities/{entity_id}` | Create entity |
| PUT | `/api/config/ontology/entities/{entity_id}` | Update entity |
| DELETE | `/api/config/ontology/entities/{entity_id}` | Delete entity |
| POST | `/api/config/ontology/relationships` | Add relationship |
| DELETE | `/api/config/ontology/relationships/{index}` | Delete relationship by index |

### Label Rules Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/config/labels` | Get all labels |
| PUT | `/api/config/labels` | Replace all labels |
| GET | `/api/config/labels/{label_id}` | Get single label |
| POST | `/api/config/labels/{label_id}` | Create label |
| PUT | `/api/config/labels/{label_id}` | Update label |
| DELETE | `/api/config/labels/{label_id}` | Delete label |

### Brand Analyzer

```
POST /api/brand/analyze
```

Analyze a brand website to extract brand identity information using headless browser + Gemini AI.

**Request:**
```json
{
  "url": "https://www.example.com/",
  "save_to_ontology": true
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "brand_name": {"english": "Brand", "chinese": "品牌"},
    "brand_type": {"industry": "...", "niche": "...", "target_audience": "..."},
    "description": {"core_value": "...", "key_products": [...], "summary": "..."},
    "visual_style": {"colors": [...], "font_style_inference": "...", "overall_vibe": "..."},
    "marketing": {"hot_keywords": [...], "hot_products": [...], "promotion_slogans": [...]}
  },
  "url": "https://www.example.com/",
  "saved_to_ontology": true,
  "entity_id": "Brand_Example"
}
```

### Reload Configuration

```
POST /api/config/reload
```

Hot-reload configuration files without full server restart.

---

### Request/Response Schemas

#### EntityRequest (POST/PUT /api/config/ontology/entities/{id})

```json
{
  "table": "schema.table_name",
  "description": "Entity description",
  "primary_key": "column_name",
  "columns": {
    "column_name": {
      "description": "Column description",
      "business_term": "Business term",
      "data_type": "VARCHAR"
    }
  }
}
```

#### RelationshipRequest (POST /api/config/ontology/relationships)

```json
{
  "from_entity": "EntityA",
  "to_entity": "EntityB",
  "type": "one_to_many",
  "foreign_key": {
    "from_column": "id",
    "to_column": "entity_a_id"
  },
  "description": "Relationship description"
}
```

#### LabelRequest (POST/PUT /api/config/labels/{id})

```json
{
  "name": "Label Display Name",
  "description": "Label description",
  "conditions": [
    {
      "entity": "EntityName",
      "column": "column_name",
      "operator": "equals",
      "value": "some_value"
    }
  ],
  "sql_hint": "WHERE column = 'value'"
}
```

#### Success Response

```json
{
  "status": "success",
  "message": "Operation completed",
  "entity": {...}  // or "label": {...}
}
```

#### Error Response

```json
{
  "detail": "Error message"
}
```

---

### API Examples

#### Get Ontology

```bash
curl http://localhost:8000/api/config/ontology
```

#### Create Entity

```bash
curl -X POST http://localhost:8000/api/config/ontology/entities/NewEntity \
  -H "Content-Type: application/json" \
  -d '{
    "table": "report.new_table",
    "description": "New entity description",
    "primary_key": "id"
  }'
```

#### Create Label

```bash
curl -X POST http://localhost:8000/api/config/labels/new_label \
  -H "Content-Type: application/json" \
  -d '{
    "name": "New Label",
    "description": "New label description",
    "conditions": [
      {"entity": "WebTraffic", "column": "stage", "operator": "equals", "value": "1進站"}
    ],
    "sql_hint": "WHERE stage = '\''1進站'\''"
  }'
```

#### Delete Label

```bash
curl -X DELETE http://localhost:8000/api/config/labels/label_to_delete
```

---

## Session State

The multi-agent system maintains session state with the following keys:

| Key | Type | Description |
|-----|------|-------------|
| `execution_plan` | JSON | DS-Agent's proposed execution plan |
| `execution_result` | JSON | DE-Agent's SQL execution result |
| `verification` | JSON | Verifier's evaluation of result sufficiency |
| `last_feedback` | string | Feedback from failed verification for refinement |

### execution_plan Schema

```json
{
  "goal": "User's confirmed segment goal",
  "segment_type": "existing_label | new_segment",
  "label_matched": "label_id or null",
  "segment_definition": {
    "name": "Segment name",
    "description": "What this segment represents",
    "criteria": [
      {"entity": "Entity", "column": "column", "operator": "=", "value": "value"}
    ]
  },
  "tables_needed": [
    {"name": "schema.table", "columns": ["col1", "col2"], "role": "description"}
  ],
  "execution_method": "sql"
}
```

### execution_result Schema

```json
{
  "status": "success" | "error" | "needs_refinement",
  "sql": "Generated SQL query",
  "validation": {
    "dry_run": "passed" | "failed",
    "error": "error message",
    "error_type": "column_not_found" | "table_not_found" | "syntax_error" | "permission_error",
    "suggestion": "Use get_schema_tool to verify exact column names..."
  },
  "preview": {"row_count": 10, "sample": [...]},
  "explanation": "What this query does"
}
```

**Error Types:**
| Type | Description |
|------|-------------|
| `column_not_found` | Column doesn't exist (check case sensitivity) |
| `table_not_found` | Table/relation doesn't exist |
| `syntax_error` | SQL syntax error (check Greenplum compatibility) |
| `permission_error` | Insufficient privileges |

### verification Schema

```json
{
  "sufficient": true | false,
  "feedback": "What's missing or wrong",
  "action": "complete" | "add_step" | "backtrack"
}
```

---

## Multi-Agent Architecture

The backend uses a DS-STAR inspired multi-agent system with semantic labeling:

```
ReviveOrchestrator (root_agent)
├── DSAgent (Semantic Labeling) → output_key: "execution_plan"
├── DEAgent (SQL Executor)      → output_key: "execution_result"
└── Verifier                    → output_key: "verification"
```

### Orchestrator Features

| Feature | Description |
|---------|-------------|
| **Max Iterations** | 3 (planning-verification loop) |
| **Error Handling** | Try/catch around each agent with error messages |
| **Backtrack** | Clears plan and restarts on verification failure |
| **Refinement** | Passes feedback to DS-Agent for plan improvement |

### DS-Agent Tools

| Tool | Description |
|------|-------------|
| `list_tables_in_schema_tool` | List tables in a schema |
| `get_schema_tool` | Get table columns/types |
| `get_ontology_tool` | Get business data model |
| `get_label_rules_tool` | Get predefined label rules |
| `list_entities_tool` | List all ontology entities |
| `list_labels_tool` | List all labels |
| `add_entity_tool` | Add new entity to ontology |
| `add_label_tool` | Add new label rule |
| `update_label_tool` | Update existing label |
| `delete_label_tool` | Delete label rule |
| `analyze_brand_tool` | Crawl brand website and extract brand identity |

### DE-Agent Tools

| Tool | Description |
|------|-------------|
| `dry_run_sql_tool` | Validate SQL with EXPLAIN (returns error_type + suggestion) |
| `run_sql_preview_tool` | Execute SQL with LIMIT 10 |

### PostgreSQL Case Sensitivity

DE-Agent enforces double-quoted column names for case-sensitive PostgreSQL/Greenplum columns:

```sql
-- Correct (double-quoted columns)
SELECT "uid" FROM report.smb_rfm_result WHERE "R" = 'high' AND "F" = 'high'

-- Wrong (will fail with "column r does not exist")
SELECT uid FROM report.smb_rfm_result WHERE R = 'high' AND F = 'high'
```

**Rule:** All column names in generated SQL are wrapped in double quotes to avoid case sensitivity issues.

---

## Configuration Files

Located at project root `/config/`:

- `ontology.json` - Business data model (entities, tables, relationships)
- `label_rules.json` - Predefined business label definitions

---

## CORS

Allowed origins:
- `http://localhost:4200` (Angular frontend)
- `http://127.0.0.1:4200` (Angular frontend alternate)

**Note:** CORS middleware must be added before AG-UI endpoint for proper preflight handling.

---

## Error Handling

All endpoints return standard HTTP status codes:

- `200` - Success
- `400` - Bad Request (validation error, entity already exists)
- `404` - Not Found (entity/label not found)
- `500` - Internal Server Error

Error response format:

```json
{
  "detail": "Error message"
}
```
