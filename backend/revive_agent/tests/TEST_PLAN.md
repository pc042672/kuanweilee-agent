# DS-STAR Multi-Agent Test Plan

## Overview

This test plan validates the DS-STAR multi-agent architecture implementation using ADK's evaluation framework.

## Test Objectives

1. **DS-Agent Tool Usage**: Verify proactive tool calls based on keywords
2. **Execution Plan Quality**: Verify DS-Agent produces valid JSON execution plans
3. **SQL Generation**: Verify DE-Agent generates Greenplum-compatible SQL
4. **Validation Workflow**: Verify DE-Agent uses dry_run before preview
5. **Verification Logic**: Verify Verifier correctly evaluates sufficiency
6. **Full Loop**: Verify orchestrator coordinates DS→DE→Verifier cycle

## Test Categories

### Category 1: DS-Agent Proactive Tool Usage

| Test ID | Input Keyword | Expected Tool Call |
|---------|---------------|-------------------|
| DS-001 | "abandoned cart" | `get_label_rules_tool()` |
| DS-002 | "label rules" | `get_label_rules_tool()` |
| DS-003 | "high value users" | `get_label_rules_tool()` |
| DS-004 | "report schema" | `list_tables_in_schema_tool("report")` |
| DS-005 | "table report.smb_abandon_list" | `get_schema_tool("report.smb_abandon_list")` |
| DS-006 | "ontology" | `get_ontology_tool()` |

### Category 2: Execution Plan Structure

| Test ID | Description | Validation |
|---------|-------------|------------|
| EP-001 | Plan has required fields | goal, analysis, tables_needed, execution_method |
| EP-002 | Label matching | label_matched field populated for label queries |
| EP-003 | Table specification | tables_needed includes schema.table format |

### Category 3: SQL Generation (DE-Agent)

| Test ID | Description | Validation |
|---------|-------------|------------|
| SQL-001 | No MERGE statements | Generated SQL avoids MERGE |
| SQL-002 | No FILTER clause | Uses WHERE instead of FILTER |
| SQL-003 | Dry run before preview | dry_run_sql_tool called before run_sql_preview_tool |
| SQL-004 | Valid SELECT structure | Generates valid SELECT with proper JOINs |

### Category 4: Verification

| Test ID | Description | Validation |
|---------|-------------|------------|
| VER-001 | Success case | sufficient=true when query matches request |
| VER-002 | Missing columns | sufficient=false with feedback |
| VER-003 | Action routing | action field set correctly (complete/add_step/backtrack) |

### Category 5: Full Orchestration

| Test ID | Description | Validation |
|---------|-------------|------------|
| ORCH-001 | Single iteration success | Completes in 1 iteration for clear queries |
| ORCH-002 | Refinement loop | Handles add_step action correctly |
| ORCH-003 | Max iterations | Graceful termination after 3 iterations |

## ADK Evaluation Metrics

Using ADK's trajectory evaluation:

- **Tool Call Trajectory**: `any_order_match` - correct tools called in any order
- **Response Quality**: Semantic similarity to expected output
- **Execution Plan**: JSON schema validation

## Running Tests

```bash
# Run all eval sets
cd backend
adk eval revive_agent tests/ds_star_eval.evalset.json --print_detailed_results

# Run specific test cases
adk eval revive_agent tests/ds_star_eval.evalset.json:DS-001,DS-002

# Run with config
adk eval revive_agent tests/ds_star_eval.evalset.json --config_file_path tests/test_config.json
```

## Success Criteria

- All DS-Agent tool usage tests pass (Category 1)
- 90%+ of SQL generation tests produce valid Greenplum SQL
- Full orchestration completes successfully for clear queries
- No crashes or unhandled exceptions

## Test Environment

- Model: gemini-2.0-flash
- Database: Greenplum (mock for eval)
- Session: Isolated per test case
