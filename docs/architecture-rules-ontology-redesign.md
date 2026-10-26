# Architecture Redesign: Rules Engine, Ontology & DS-STAR

## Context

The current system has **three parallel systems** that overlap significantly:

1. **ZEN/GoRules engine** (`backend/scoring/rules_engine.py`) — wraps GoRules SDK, evaluates JDM decision graphs
2. **Ontology config** (`config/ontology.json`) — defines DataSource→Attribute→Segment→Action with embedded RuleDef
3. **DS-STAR agents** (ADK) — orchestrates SQL generation with ontology tools as sidecar

**The problem:** These three systems duplicate logic and create architectural tension:

| Concern | Where it lives today |
|---------|---------------------|
| Quiz answer → archetype mapping | Ontology (`QuizOptionConfig.mappings`) **AND** ZEN decision table (`archetype-scoring.json`) |
| Score aggregation | `engine.py:score()` **AND** ZEN `scoreAggregator` custom handler |
| Segment matching | `engine.py:evaluate_segment()` (pure Python) — ZEN not used here |
| NBA/NBO resolution | `SegmentActionsConfig` in ontology **AND** ZEN `NbaTuneResolver` decision table |
| Visual editing | Frontend edits JDM files (parallel format), not the ontology directly |

ZEN adds a GoRules dependency + JDM file format for what amounts to dictionary lookups + aggregation. The ontology already defines the same rules declaratively.

---

## Architectural Assessment

### What each layer should do

| Layer | Responsibility | Best tool |
|-------|---------------|-----------|
| **Ontology** (config) | Declare WHAT exists — nodes, relationships, rules | JSON/DB config |
| **Rule Evaluator** (engine) | Execute rules deterministically — HOW to compute | Pure Python |
| **ADK Agents** (intelligence) | Decide WHEN/WHY to apply rules, plan SQL, reason about results | LLM |

### Why ZEN should be removed

1. **Only 1 JDM file exists** (`archetype-scoring.json`) — not enough to justify a rule engine dependency
2. **Decision tables are simple lookups** — 23 rules mapping Q1-Q3 → archetype. This is a dict, not a decision graph
3. **Custom handlers are plain Python** — `scoreAggregator` (30 lines) and `resultMerger` (40 lines) are aggregation code, not graph logic
4. **Creates data drift** — JDM file defines quiz→archetype mappings, but ontology also defines them in `QuizOptionConfig.mappings`. Two sources of truth
5. **Visual editor edits the wrong thing** — frontend edits JDM graphs, but the ontology is the real config. Should edit ontology directly

### Why rules should NOT be an ADK agent

Rule evaluation is **deterministic** — "Q1=A → ruler +1 point" doesn't need LLM reasoning. Making it an agent would:
- Waste tokens on mechanical computation
- Add latency (LLM call vs microsecond dict lookup)
- Introduce non-determinism where we need exactness

ADK agents should **consume** rule results, not **compute** them.

### The ontology IS the rule graph

```
DataSourceNode ──provides──> AttributeNode ──resolves──> SegmentNode ──triggers──> Action
   (tables)                   (rules[])                   (conditions[])           (nba/nbo)
```

This is already a DAG. What's missing is a proper **evaluation pipeline** that walks it.

---

## Recommended Architecture

### Remove ZEN, build native Ontology Graph Evaluator

```
┌─────────────────────────────────────────────────────┐
│  Ontology Config (single source of truth)           │
│  ┌──────────┐  ┌─────────────┐  ┌──────────────┐   │
│  │DataSource│→ │ Attribute   │→ │  Segment     │   │
│  │  .table  │  │  .rules[]   │  │  .conditions │   │
│  │  .columns│  │  .options   │  │  .actions    │   │
│  └──────────┘  └─────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────┐
│  Ontology Evaluator (pure Python, deterministic)    │
│                                                     │
│  evaluate_attribute(key, input)  → computed value    │
│  evaluate_segment(key, attrs)    → match + reasoning │
│  resolve_action(segment_key)     → NBA/NBO config    │
│  evaluate_pipeline(input)        → full graph walk   │
│                                                     │
│  (replaces: engine.py + rules_engine.py + ZEN)      │
└─────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────┐
│  ADK Agents (intelligent consumers)                 │
│                                                     │
│  DS-Agent: reads ontology, calls evaluator tools,   │
│            plans which segments to target            │
│  DE-Agent: generates SQL from plan                  │
│  Verifier: validates results against rules           │
└─────────────────────────────────────────────────────┘
```

### What changes

| Component | Current | Proposed |
|-----------|---------|----------|
| `backend/scoring/rules_engine.py` | ZEN SDK wrapper | **Remove** |
| `backend/scoring/rules_repository.py` | JDM file storage | **Remove** |
| `backend/scoring/rules_engine_factory.py` | ZEN factory | **Remove** |
| `config/rules/archetype-scoring.json` | JDM decision graph | **Remove** (data lives in ontology) |
| `backend/scoring/engine.py` | Quiz scoring + segment eval | **Keep & extend** as the unified evaluator |
| `backend/routers/rules.py` | JDM CRUD API | **Replace** with ontology graph API |
| Frontend rules editor | Edits JDM files via Foblex | **Redesign** to edit ontology graph |
| `backend/revive_agent/tools/ontology_tools.py` | Calls engine.py | **Simplify** — same tools, cleaner internals |
| GoRules `zen` dependency | `requirements.txt` | **Remove** |

### What stays the same

- **DS-STAR orchestrator** — no changes needed, agents are already consumers
- **Ontology config schema** — `RuleDef` with `ruleType: sql|quiz|scoring|ml` stays
- **Tool interface** — `score_tool()`, `resolve_segments_tool()`, etc. keep same signatures
- **Persistence** — `QuizPersistence` to Greenplum stays
- **ConfigManager** — stays as the access layer

### Unified evaluator design (`backend/scoring/engine.py`)

```python
class OntologyEvaluator:
    """Walks the ontology graph to evaluate rules deterministically."""

    def __init__(self, config: UnifiedOntologyConfig):
        self.config = config

    def evaluate_attribute(self, key: str, input: dict) -> dict:
        """Evaluate all rules on an attribute node.
        - quiz rules: map responses → scores via QuizOptionConfig.mappings
        - sql rules: return SQL expression (for DE-Agent to execute)
        - scoring rules: aggregate/threshold logic
        """

    def evaluate_segment(self, key: str, attributes: dict) -> tuple[bool, list[str]]:
        """Match attribute values against segment conditions.
        (Already exists — keep as-is)
        """

    def resolve_action(self, segment_key: str) -> dict:
        """Resolve NBA/NBO from segment actions config.
        Replaces ZEN NbaTuneResolver.
        """

    def evaluate_pipeline(self, input: dict) -> dict:
        """Full graph traversal: input → attributes → segments → actions.
        Replaces the entire ZEN archetype-scoring.json graph.
        """
```

### Visual editor redesign

Instead of editing JDM graphs, the frontend should visualize the **ontology graph**:
- **Nodes**: DataSource, Attribute, Segment (from ontology.json)
- **Edges**: DataSource→Attribute (via `rules[].sources`), Attribute→Segment (via `conditions[].attribute`)
- **Editing**: Click a node to edit its rules/conditions inline
- **The Foblex/dagre graph canvas already built** can be reused — just point it at ontology data instead of JDM data

---

## Implementation Plan

### Phase 1: Unify the evaluator (backend only, no frontend changes)

1. **Extend `engine.py`** — add `OntologyEvaluator` class with `evaluate_pipeline()` that does what the ZEN archetype-scoring graph does, using ontology data only
2. **Remove ZEN calls** from `engine.py:evaluate_zen()` — replace with native logic
3. **Update `ontology_tools.py`** — remove ZEN references, use unified evaluator
4. **Remove** `rules_engine.py`, `rules_repository.py`, `rules_engine_factory.py`
5. **Remove** `config/rules/archetype-scoring.json`
6. **Remove** `zen` from `requirements.txt`
7. **Remove/simplify** `backend/routers/rules.py`

### Phase 2: Redesign visual editor (frontend)

1. **Rules editor → Ontology graph editor** — show DataSource→Attribute→Segment graph
2. **Reuse Foblex canvas** — same dagre layout, different data source
3. **Inline editing** — click node to edit rules/conditions (reuse decision-table-editor pattern)
4. **API** — use existing `/api/ontology/nodes` endpoints instead of `/api/rules`

### Phase 3: Enhance agent integration

1. **Add `evaluate_pipeline_tool()`** to ontology_tools — full graph traversal as a single tool call
2. **Verifier uses evaluator** — validate SQL results against segment conditions deterministically
3. **DS-Agent uses evaluator** — pre-check which segments match before planning SQL

---

## Verification Plan

1. **Unit tests**: Ensure `evaluate_pipeline()` produces identical results to ZEN for the archetype-scoring case
2. **Integration test**: Run DS-STAR flow end-to-end, verify ontology tools still work
3. **Frontend test**: MCP chrome tools to verify graph editor shows ontology nodes
4. **Regression**: `python -m pytest tests/ -v` — all existing tests pass
5. **Manual**: Score a quiz via API, verify results match pre-refactor

---

## Key Files

| File | Action |
|------|--------|
| `backend/scoring/engine.py` | Extend with OntologyEvaluator class |
| `backend/scoring/rules_engine.py` | Delete |
| `backend/scoring/rules_repository.py` | Delete |
| `backend/scoring/rules_engine_factory.py` | Delete |
| `backend/routers/rules.py` | Remove or replace with ontology graph endpoints |
| `config/rules/archetype-scoring.json` | Delete |
| `backend/revive_agent/tools/ontology_tools.py` | Simplify (remove ZEN refs) |
| `frontend/src/app/features/rules/rules-editor.component.ts` | Redesign to show ontology graph |
| `frontend/src/app/shared/services/rules.service.ts` | Replace with ontology service calls |
| `requirements.txt` | Remove `zen` dependency |

---

**Status (2026-06-11):** Implemented. The unified evaluator, ontology/rules/strategies
split, and native scoring shipped on `feat/ontology-rule-split`. The v1/v2 deprecated
models, `migration.py`, `label_rules.json`, and the one-shot split scripts were removed
in the phase-2 cleanup; recover from git history if ever needed.
