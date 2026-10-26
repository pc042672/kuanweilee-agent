# AI-CDP Agent Architecture

## Dependencies

**ADK Version:** `google-adk>=1.22.0` (required for Gemini 3 compatibility)
- Progressive SSE streaming enabled by default in v1.22.0+
- Required for proper tool loop completion with Gemini 3's "Thought Signatures"
- Reference: https://github.com/google/adk-python/issues/4090

## Model Configuration

**Model:** `gemini-3-flash-preview` (Gemini 3 Flash Preview)
- Max Input: 1M tokens
- Max Output: 64K tokens
- Knowledge Cutoff: January 2025
- Reference: https://ai.google.dev/gemini-api/docs/gemini-3

**Retry Configuration:**
```python
RETRY_CONFIG = types.HttpRetryOptions(
    attempts=5,
    exp_base=7,
    initial_delay=1,
    http_status_codes=[429, 500, 503, 504],
)
```

## DS-STAR Multi-Agent Architecture

```
ReviveOrchestrator (root_agent)
├── DSAgent (Semantic Labeling) → output_key: "execution_plan"
├── DEAgent (SQL Executor)      → output_key: "execution_result"
└── Verifier                    → output_key: "verification"
```

### Agent Roles

| Agent | Role | Output Key |
|-------|------|------------|
| DSAgent | Data Scientist - semantic labeling, brand analysis | execution_plan |
| DEAgent | Data Engineer - SQL generation and validation | execution_result |
| Verifier | Evaluates if result satisfies user query | verification |

### Orchestrator Features

- Max Iterations: 3
- Error Handling: Try/catch around each agent
- Backtrack: Clears plan and restarts on verification failure
- Refinement: Passes feedback to DS-Agent for plan improvement

## Key Files

| File | Purpose |
|------|---------|
| `revive_agent/agent.py` | Agent definitions, model config |
| `revive_agent/orchestrator.py` | ReviveOrchestrator (root_agent) |
| `revive_agent/agent_tools.py` | Tool functions for agents |
| `server.py` | FastAPI server, streaming endpoint |
| `api_spec.md` | API documentation |

## Tools

### DS-Agent Tools
- `get_schema_tool` - Get table columns (ALWAYS verify before planning)
- `get_ontology_tool` - Business data model
- `get_label_rules_tool` - Predefined segment labels
- `analyze_brand_tool` - Brand website analysis
- `list_tables_in_schema_tool` - List tables
- Config CRUD: add/update/delete entity/label tools

### DE-Agent Tools
- `dry_run_sql_tool` - Validate SQL with EXPLAIN
- `run_sql_preview_tool` - Execute with LIMIT 10

## PostgreSQL Case Sensitivity

**CRITICAL:** All column names must be double-quoted:
```sql
-- Correct
SELECT "uid" FROM report.smb_rfm_result WHERE "R" = 'high'

-- Wrong (will fail)
SELECT uid FROM report.smb_rfm_result WHERE R = 'high'
```

## Commands

```bash
# Run backend server
source .venv/bin/activate && python -m backend.server

# Run ADK web interface
cd backend && adk web revive_agent

# Run frontend
cd frontend && npx ng serve
```

## STATE_DELTA Pattern (Structured Data Rendering)

Instead of parsing text to extract JSON, the orchestrator now emits `STATE_DELTA` events with structured data:

**Backend (orchestrator.py):**
```python
from google.adk.events import Event, EventActions

yield Event(
    author=self.name,
    content=types.Content(role="model", parts=[types.Part(text=message)]),
    actions=EventActions(state_delta={
        "workflow": {
            "phase": "planning" | "executing" | "verifying" | "complete" | "error" | "waiting",
            "iteration": 1,
            "max_iterations": 3,
            "message": "Status message"
        },
        "execution_plan": {...},  # Structured plan JSON
        "execution_result": {...},  # Structured result JSON
        "verification": {...}  # Structured verification JSON
    })
)
```

**Frontend (chat-panel.component.ts):**
```typescript
// State signals (no parsing needed!)
workflowState = signal<WorkflowState | null>(null);
latestPlan = signal<ExecutionPlan | null>(null);
latestResult = signal<ExecutionResult | null>(null);
latestVerification = signal<Verification | null>(null);

// Handler
onStateDeltaEvent: (event) => {
  for (const delta of event.delta || []) {
    this.applyStateDelta(delta);
  }
}
```

**Benefits:**
- No text parsing required
- Type-safe structured data
- Reliable rendering across all scenarios
- Progress tracking with phase indicators

## Endpoints

- `POST /api/chat/stream` - Streams ADK events (NDJSON)
- `POST /ag-ui` - AG-UI endpoint for CopilotKit
- `GET/PUT /api/config/ontology` - Ontology CRUD
- `GET/PUT /api/config/labels` - Label rules CRUD
- `POST /api/brand/analyze` - Brand website analysis

## Tool Result Store Pattern (Bypass LLM Truncation)

**Problem:** LLM agents may truncate or summarize tool results when outputting via `output_key`. Large data (SQL previews, execution plans) gets lost.

**Solution:** Use global stores to capture tool results directly, then merge in orchestrator.

**Implementation (agent_tools.py):**
```python
# Global stores for tool results (orchestrator reads these directly)
_execution_plan_store: dict[str, Any] = {}
_sql_preview_store: dict[str, Any] = {}

def submit_execution_plan(plan_json: str) -> str:
    """DS-Agent tool - stores plan for orchestrator to read."""
    _execution_plan_store["_latest_plan"] = plan_json
    return "Plan submitted successfully"

def run_sql_preview_tool(sql_query: str) -> str:
    """DE-Agent tool - stores full preview for orchestrator."""
    result = runner.execute_query(sql_query)
    # Store full result (not truncated by LLM)
    _sql_preview_store["_latest_preview"] = {
        "success": True,
        "sql": sql_query,
        "row_count": len(result),
        "data": result  # Full data, not summarized
    }
    return json.dumps(result[:5])  # LLM sees summary only
```

**Orchestrator reads stores (orchestrator.py):**
```python
from revive_agent.agent_tools import _execution_plan_store, _sql_preview_store

# After DS-Agent runs:
if "_latest_plan" in _execution_plan_store:
    plan = _execution_plan_store.pop("_latest_plan")
    ctx.session.state["execution_plan"] = plan

# After DE-Agent runs:
if "_latest_preview" in _sql_preview_store:
    preview = _sql_preview_store.pop("_latest_preview")
    result["preview"] = {
        "row_count": preview.get("row_count", 0),
        "sample": preview.get("data", [])
    }
```

**Benefits:**
- Full data preserved (no LLM truncation)
- Orchestrator has direct access to structured results
- LLM still sees summary for context
- Works around Gemini's tendency to summarize large outputs

## Troubleshooting

### AG-UI Empty execution_plan with Gemini 3

**Symptom:** AG-UI endpoint returns empty `execution_plan` while ADK web works correctly.

**Cause:** Gemini 3 introduces "Thought Signatures" (`thoughtSignature` field) that arrive in empty text chunks. Old parsers discard these, breaking the tool loop.

**Solution:** Upgrade to ADK v1.22.0+ which enables progressive SSE streaming by default.

**Alternative (v1.21.0):** Set environment variable `ADK_ENABLE_PROGRESSIVE_SSE_STREAMING=1`

**Reference:** https://github.com/google/adk-python/issues/4090
