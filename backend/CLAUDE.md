# Backend CLAUDE.md

## Overview

Python backend using Google ADK for AI SQL generation. DS-STAR architecture with iterative planning-verification.

## Commands

```bash
source ../.venv/bin/activate && python -m backend.server  # http://localhost:8000
adk web revive_agent  # ADK web interface
adk eval test_ds_agent revive_agent/tests/ds_agent_tools.evalset.json --print_detailed_results
```

## DS-STAR Architecture

```
ReviveOrchestrator (max 3 iterations)
├── DS-Agent: get_ontology → submit_execution_plan
├── DE-Agent: dry_run_sql → run_sql_preview → JSON result
└── Verifier: {sufficient: bool, action: complete|add_step|backtrack}
```

## Skill Layer

`ReviveOrchestrator` (DS-STAR) is the root agent. The specialist sub-agents in
`revive_agent/skills/agents.py` (StrategyAgent, RuleAgent, OntologyAgent,
SkillExecutor) are currently unwired — the IntentRouter front door was removed —
and are kept for a future routing mechanism.

Skills live in `backend/skills/registry.py` (name → Skill). External execution
goes through `backend/services/external_actions.py` (`ExternalActionAdapter` +
`DryRunAdapter` + per-site registry; real CDP MCP/API drops in later). Write
tools (`tools/config_write_tools.py`) enforce `services/guardrails.py`:
tool-boundary authZ + per-site `guardrail_level` HITL + integrity + audit.
See `docs/adr/0001-ds-star-baseagent.md`.

## Key Files

| File | Purpose |
|------|---------|
| `server.py` | FastAPI + AG-UI, CORS from `CORS_ORIGINS` env |
| `revive_agent/orchestrator.py` | DS-STAR loop, reads tool results from ToolContext session state |
| `revive_agent/agent.py` | DS-Agent, DE-Agent, Verifier definitions |
| `tools_registry.py` | Single ToolSpec registry: domains, required_services, HITL severity; agents use `tools_for()` |
| `revive_agent/tools/` | Tool implementations split by domain |
| `revive_agent/tools/_infra.py` | Per-site factories: query_service, profiler, config_manager |
| `dbtoolbox/` | Read-only SQL layer: Source (per-site engine), SecurityPolicy (SELECT-only + allowlist), QueryService. Port contract: `docs/dbtoolbox-porting.md` |
| `revive_agent/instructions.py` | Agent prompts (static + dynamic) |
| `config/ontology.json` | Unified ontology v3: datasources, attributes, segments |

## Tool Modules (`revive_agent/tools/`)

| Module | Tools |
|--------|-------|
| `schema_tools.py` | `list_tables_in_schema_tool`, `get_schema_tool` |
| `sql_tools.py` | `submit_execution_plan`, `dry_run_sql_tool`, `run_sql_preview_tool` |
| `plan_tools.py` | `load_plan_tool` |
| `skill_tools.py` | `list_skills_tool`, `get_skill_tool`, `get_skill_template_tool` |
| `ontology_tools.py` | `get_ontology_tool`, `get_attribute_tool`, `score_tool`, `resolve_segments_tool`, `resolve_nba_context_tool`, `resolve_nbo_context_tool`, `audit_ontology_tool` |
| `brand_tools.py` | `analyze_brand_tool` (ontology save in `services/brand_service.py`) |
| `persona_tools.py` | `classify_persona_tool`, `persona_search_core` |

## Session State

| Key | Source | Content |
|-----|--------|---------|
| `execution_plan` | DS-Agent | `{goal, segment_type, label_matched, tables_needed}` |
| `execution_result` | DE-Agent | `{status, sql, preview: {row_count, sample[]}}` |
| `verification` | Verifier | `{sufficient, feedback, action}` |

## ToolContext State Keys (temp: prefix = invocation-scoped)

| Key | Source | Content |
|-----|--------|---------|
| `temp:submitted_plan` | `submit_execution_plan` tool | Plan JSON from DS-Agent (via ToolContext) |
| `temp:sql_preview` | `run_sql_preview_tool` | Full preview data (via ToolContext) |

## Greenplum SQL Rules

- No MERGE statements
- No FILTER clauses
- Use DISTRIBUTED BY on DDL
- Always dry_run before preview

## Import Path Convention

Use bare paths relative to `backend/` on sys.path — NOT `from backend.xxx`:
```python
from dbtoolbox import QueryService             # correct
from config import get_config_manager          # correct
from persona.search import fast_persona_classify  # correct
# NOT: from backend.dbtoolbox ...              # breaks ADK web
```
`revive_agent/__init__.py` adds `backend/` to sys.path. The `_infra.py` module duplicates this defensively.

## ADK Reference

See `../docs/llms.txt`. Key patterns:
- `LlmAgent` with `output_key` for state
- `BaseAgent._run_async_impl` for custom orchestration
- `EventActions(escalate=True)` to exit loop
- `EventActions(state_delta={})` for frontend state updates
