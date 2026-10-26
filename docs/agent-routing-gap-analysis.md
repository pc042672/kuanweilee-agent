# Agent-Routing Architecture — Gap Analysis

Comparing the **current** implementation against the **proposed** intent-routed,
multi-agent architecture. Goal: see exactly what exists, what's partial, what's new,
and sequence the work. No design decisions here — this is the gap map.

## 1. Current architecture (as built)

Single-path DS-STAR loop; no routing, no specialist agents.

```
AG-UI (server.py) → ReviveOrchestrator (BaseAgent, max 3 iterations)
    loop: planning → executing → verifying → route(complete | add_step | backtrack)
      ├── DS-Agent   (agent.py:80)  output_key=execution_plan
      ├── DE-Agent   (agent.py:118) output_key=execution_result
      └── Verifier   (agent.py:131) output_key=verification (+ campaign_summary)
```

- **DS-Agent** — one overloaded agent (~12 tools): `load_plan`, `list/get_schema`,
  `submit_execution_plan`, `analyze_brand`, `list/get/get_skill_template`,
  `get_ontology`/`get_attribute`/`score`/`label_scores`/`resolve_segments`/`resolve_strategy`/`audit`,
  `classify_persona`. Instruction is a 2-step: `get_ontology_tool()` → `submit_execution_plan()`.
- **DE-Agent** — `dry_run_sql_tool` → `run_sql_preview_tool` (SQL only).
- **Verifier** — checks SQL exists / dry-run passed / preview present / "addresses query",
  emits `{sufficient, feedback, action}` **and** a marketing `campaign_summary`.
- **Loop** (`orchestrator.py:253`) re-runs DS-Agent on `backtrack`; `max_iterations` per site.

Key observations:
- **No intent routing / task classification** — every request goes through the same loop.
- **DS-Agent is overloaded** — planning + ontology + scoring + persona + brand on one agent.
- **Verification is post-execution only** and **conflated** (plan-check + result-check + insight in one agent); result checks are shallow (`row_count >= 0`).
- **Skill Executor = SQL only** (no Python / chart / export).

## 2. Proposed architecture (target)

```
User → Intent Router → Task Classifier
   ├── Data Analysis     → DS-STAR (8 steps)
   ├── Campaign Strategy  → Strategy Agent
   ├── Rule Editing       → Rule Agent      (edits rules.json)
   ├── Ontology Editing   → Ontology Agent  (edits ontology.json)
   └── Execution          → Skill Executor

DS-STAR: Data Context Analyzer → Ontology Mapper → Plan Generator →
         Plan Verifier → Plan Refiner → Skill Executor → Result Verifier → Insight Writer
```

## 3. Gap table

Legend: ✅ exists · ◑ partial · ❌ missing.

| Proposed component | Current state | Gap | Effort | Depends on |
|---|---|---|---|---|
| **Intent Router** | ❌ single orchestrator | new coordinator agent that dispatches by intent | M | — |
| **Task Classifier** | ❌ | classify into 5 task types (LLM or rules) | S–M | router |
| **Strategy Agent** | ◑ tools only (`resolve_strategy`, brand) on DS-Agent | dedicated agent + path | M | router |
| **Rule Agent** (edits rules.json) | ❌ (tools exist; no agent) | agent over `/rules` CRUD + integrity | S | router, split ✅ |
| **Ontology Agent** (edits ontology.json) | ❌ (tools exist; no agent) | agent over `/nodes` CRUD | S | router, split ✅ |
| **Skill Executor** | ◑ DE-Agent (SQL) + skill_tools | broaden to Python/chart/export | M–L | — |
| DS-STAR · 1 Data Context Analyzer | ◑ schema tools on DS-Agent, no step | explicit column summary + data-quality scan | M | — |
| DS-STAR · 2 **Ontology Mapper** | ◑ `get_ontology` dumps model; no mapping | map columns→Attribute/Segment, verify refs, anti-hallucination | M | ontology ✅ |
| DS-STAR · 3 Plan Generator | ✅ DS-Agent `submit_execution_plan` | keep; narrow its scope | — | — |
| DS-STAR · 4 **Plan Verifier** | ◑ Verifier checks post-exec, shallow | **pre-execution** gate: can plan answer Q? missing data/joins? | M | — |
| DS-STAR · 5 Plan Refiner | ◑ orchestrator loops on backtrack | targeted refine-until-sufficient with feedback | S | plan verifier |
| DS-STAR · 6 Skill Executor | ✅ DE-Agent (SQL) | same as Skill Executor row | — | — |
| DS-STAR · 7 **Result Verifier** | ◑ `row_count>=0` only | row/null/outlier/business-sanity checks | M | split from Verifier |
| DS-STAR · 8 Insight Writer | ◑ `campaign_summary` (marketing-only) | general cited business explanation | S | — |

## 4. Cross-cutting findings

- **G1 — Routing is the central missing layer.** Everything funnels through one loop; intent is never classified, so a "rename this segment" request and a "find abandoned-cart users" request take the same heavy path. This is the highest-leverage gap.
- **G2 — DS-Agent is a god-agent.** Its ~12 tools span five of the proposed task types. Splitting into Strategy / Rule / Ontology / DS-STAR agents is mostly *re-grouping existing tools* behind a router, not writing new leaf logic.
- **G3 — Ontology Mapper is the real semantic gap.** Today `get_ontology_tool()` dumps the whole model into the prompt; nothing maps a query's columns onto Attribute/Segment nodes or *verifies* referenced entities exist. This is the step that prevents hallucinated semantics and is the payoff of having an ontology.
- **G4 — Verification is conflated and late.** One Verifier does plan-check + result-check + insight, all *after* SQL runs. Proposed splits a **pre-exec Plan Verifier** (cheap, catches bad plans before execution) from a **post-exec Result Verifier** (data sanity), with Insight Writer as its own step.
- **G5 — Skill Executor is SQL-only.** Python/chart/export are proposed but absent.

## 5. Foundation already in place (enablers)

The recent backend work is exactly what this architecture consumes — the gap is **orchestration/routing, not leaf capability**:

- **Split configs** (`ontology.json` structure / `rules.json` behavior) → clean, disjoint **Ontology Agent** vs **Rule Agent** boundaries (impossible under the old "everything is a typed node" model).
- **Stateless `OntologyEvaluator` + integrity validator** → Ontology Mapper can validate references; Rule Agent edits via `PUT /rules` with integrity errors surfaced.
- **Generic scoring** (`ScoreContribution`/`aggregate`/`label`) → multi-signal scoring without business hardcode.
- **Tool inventory** already covers most leaf actions (ontology CRUD, score/label, resolve, schema, SQL, skills, brand, persona). Most "new agents" are **tool re-grouping behind a router**, not new tools.

## 6. Effort & risk summary

| Phase | Scope | Effort | Risk |
|---|---|---|---|
| A | Ontology Agent + Rule Agent (re-group tools; smallest, leverages split) | S | low |
| B | Intent Router + Task Classifier (ADK coordinator w/ sub_agents) | M | medium (misroute) |
| C | Ontology Mapper + split Plan/Result Verifier + Insight Writer | M | medium |
| D | Strategy Agent path; broaden Skill Executor (Python/chart/export) | M–L | medium |
| E | Frontend: minimal re-sync + read-only viewer (agent-driven edits) | S–M | low |

**Lowest-risk, highest-leverage start: Phase A** — it banks the value of the config split immediately and shrinks the god-agent, with no routing risk. The router (B) is where care is needed: keep it a lightweight ADK coordinator, not a bespoke classifier service.

## 7. Out of scope / open questions

- Does the router need a real classifier, or is an ADK coordinator-with-sub_agents (LLM transfer by description) enough? (Recommend the latter first.)
- Skill Executor breadth (Python/chart/export) — real near-term need, or SQL-only for now?
- Insight Writer: keep marketing `campaign_summary`, or generalize to cited business explanation?
