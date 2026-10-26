# ADR 0001 — DS-STAR stays a BaseAgent; intent router uses sub-agent transfer

Status: Accepted (2026-06-11). Amended 2026-06-11: decision 2's IntentRouter
was removed — `ReviveOrchestrator` is the root agent unconditionally; the
specialist sub-agents remain in `revive_agent/skills/agents.py`, unwired, for a
future routing mechanism. Decision 1 stands.

## Context

ADK 2.0 introduced an experimental, pre-GA graph **Workflow API** (nodes/edges/
routes, HITL, ParallelWorker, Task Mode). The product's DS-STAR loop (context →
ontology mapping → plan → verify → refine → execute → result-verify → insight)
is naturally graph-shaped, and the skill layer needs an intent router over five
task types.

## Decision

1. **Keep `ReviveOrchestrator` as a `BaseAgent` with `_run_async_impl`.** It runs
   unchanged as a root agent under the Runner and as a sub-agent under the
   coordinator. `_run_async_impl` is superseded-but-supported in 2.2.0.
2. **Intent router = coordinator `LlmAgent` + `sub_agents` (chat-mode transfer)**,
   not 2.0 Task Mode. Routing is LLM-driven by sub-agent descriptions; the
   DS-STAR orchestrator is both a sub-agent and the explicit default, so
   misrouting degrades to today's behavior. Gated by `INTENT_ROUTER_ENABLED`.

## Rationale

- The Workflow graph API is pre-GA and already broke its own base class between
  2.0 and 2.2 (`BaseAgent` ABC restoration). A financial-compliance product
  should not put its core analysis path on a churning execution engine.
- The current loop works, is tested, and the rewrite is pure churn with no user
  benefit today.
- `sub_agents` transfer is stable and 1.x-compatible; Task Mode shares the
  graph API's churn surface.

## Consequences

- Revisit the graph rewrite when the Workflow API reaches GA (re-open this ADR).
- The `**kwargs` passthrough in `ReviveOrchestrator.__init__` lets the BaseAgent
  carry `after_agent_callback` (memory ingestion) and `description` (routing).

## Deferred (not in this cycle)

- Real-time behavior-data ingestion connector.
- Uploaded-data-file analysis (candidate: upload → temp table via runner, or the
  gated `python_analysis` skill).
- Cloud SQL provisioning automation (`deploy/gcp/deploy.sh` TODO).
- Whether external CDP systems mount as ADK `MCPToolset` or REST adapters —
  both fit behind `ExternalActionAdapter`; decide when the real API arrives.
