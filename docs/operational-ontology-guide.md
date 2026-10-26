# Operational Ontology — Implementation Guide

## Status: Deferred (cherry-picks applied, full framework when needed)

## Context

AI-CDP's v3 ontology (DataSourceNode, AttributeNode, SegmentNode) is already a domain-specific operational ontology. This guide documents when and how to evolve it into a generic object/action runtime.

## Current State (v3 Ontology)

| Concept | Implementation |
|---|---|
| Object types | 3 fixed Pydantic types with discriminated union |
| Instance CRUD | `ConfigManager.add_node()`, `update_node()`, `delete_node()` |
| Validation | Pydantic v2 discriminated union at API layer |
| Actions | `score()`, `evaluate_segment()`, `build_taxonomy_context()` in `scoring.py` |
| Audit | `config_audit_log` table in AlloyDB (whole-config snapshots) |
| Storage | AlloyDB JSONB (`site_configs` table) or JSON files |

## Cherry-Picks Applied (v3.1)

### 1. Field-Level Audit Diff
- `alloydb_repository.py` now computes `diff_json` with `{changed: {field: {before, after}}}` format
- Stored alongside before/after snapshots in `config_audit_log`

### 2. Lifecycle Status on Nodes
- All v3 node types have `status: Literal["experimental", "active", "deprecated", "archived"]`
- Default: `"active"`
- Agent prompt formatting filters to active nodes only
- UI can show deprecated nodes with visual indicator

### 3. Action Execution Log
- New `action_executions` table tracks every scoring/segment/NBA action
- Fields: action_type, target_node_key, request/response JSON, status, actor, timing
- Migration: `deploy/migrations/005_action_executions.sql`

## When to Build the Full Generic Framework

Build the generic operational ontology runtime when **any 2 of these are true**:

1. **5+ distinct object types** beyond datasource/attribute/segment (e.g., Campaign, Offer, Journey, Audience, Channel)
2. **Non-developer users** need to define new object types via UI without code changes
3. **Multi-tenant platform** where each customer has different object schemas
4. **Action complexity** exceeds what domain-specific functions can handle (10+ action types with shared patterns)

## Generic Framework Design (For Future Reference)

### Data Model

```
interfaces
  id, name, description, status

object_types
  id, name, display_name, interface_id?, version, status, description

object_type_fields
  id, object_type_id, field_name, field_type, required, indexed,
  is_reference, reference_object_type_id?, default_value_json?,
  validation_rules_json?, display_order

action_types
  id, name, display_name, target_object_type_id, version, status,
  input_schema_json, output_schema_json, handler_key, execution_mode,
  side_effects_config_json?, description

objects
  id, object_type_id, business_key, version, status, payload_json,
  created_at, updated_at, created_by, updated_by
  UNIQUE(object_type_id, business_key)

action_executions
  id, action_type_id, target_object_id, request_json, response_json?,
  execution_status, error_message?, started_at, completed_at?,
  executed_by, correlation_id

audit_events
  id, object_id, action_execution_id?, event_type, before_json?,
  after_json?, diff_json, actor, timestamp, correlation_id
```

### Supported Field Types (v1)

`string`, `integer`, `number`, `boolean`, `datetime`, `enum`, `object_ref`, `array_string`, `array_ref`

### Handler Pattern

```python
class BaseActionHandler:
    def execute(self, obj, request, context):
        self.validate(obj, request, context)
        updated_obj = self.apply_state_change(obj, request, context)
        result = self.build_result(updated_obj, context)
        return result
```

Handler is the stable execution boundary between declarative metadata and business logic.

### Migration Path from v3

```
v3 AttributeNode  → object_type "attribute" with fields from AttributeNode model
v3 SegmentNode    → object_type "segment" with fields from SegmentNode model
v3 DataSourceNode → object_type "datasource" with fields from DataSourceNode model
v3 scoring.py     → action_type "score" with handler_key "scoring.score"
v3 evaluate_segment → action_type "evaluate_segment" with handler_key "scoring.evaluate_segment"
```

The v3 discriminated union models become seed data in the generic type registry. Existing config data migrates into the `objects` table.

### Delivery Phases (When Triggered)

| Phase | Duration | Deliverables |
|---|---|---|
| Foundation Kernel | 2-3 weeks | DB schema, metadata CRUD, object CRUD, dynamic validation, basic audit |
| Action Runtime | 2-3 weeks | Action type metadata, handler registry, execution API, side-effect dispatch |
| Control Portal | 2-4 weeks | React admin: type editor, object browser, action trigger, audit timeline |
| Hardening | 2-4 weeks | Optimistic locking, pagination, error model, observability, test coverage |

### Key Risks

| Risk | Control |
|---|---|
| Ontology becomes too flexible | Naming conventions + design review for new types |
| Handler logic gets messy | Strict template: separate mutation from side effects |
| Dynamic validation fragility | Restrict field types, unit test Pydantic generation |
| Audit volume | Compact diffs, archive later |
| Rules engine too early | Keep code-based handlers first |

## Tech Stack (When Building)

- Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic
- PostgreSQL/AlloyDB with JSONB
- React + TypeScript + JSON Schema-driven forms (RJSF)
- Handlers: synchronous in v1, queue-based later

## Key Files (Current)

| File | Role |
|---|---|
| `backend/config/schemas.py` | v3 node types (future: seed data for generic types) |
| `backend/config/loader.py` | ConfigManager CRUD (future: replaced by generic object API) |
| `backend/config/scoring.py` | Domain actions (future: registered as action handlers) |
| `backend/config/alloydb_repository.py` | Storage + audit (future: generalized for all object types) |
| `backend/routers/ontology.py` | API endpoints (future: replaced by generic object/action API) |
