"""Single registry of every agent tool.

Each tool is registered exactly once as a ToolSpec carrying the metadata that
used to be scattered across agent modules: which agents expose it (domains),
which external integrations it needs (required_services — consumed by
ServiceGatingPlugin and the Integrations UI), whether mutations need HITL
confirmation (severity), and the executable-skill alias for skills.registry.

Agents build their tool lists with tools_for(*domains); per-site availability
stays a runtime check (agents are module-level singletons shared across sites).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Tuple

from google.adk.tools import FunctionTool

from services.guardrails import DESTRUCTIVE, MUTATING, needs_confirmation


@dataclass(frozen=True)
class ToolSpec:
    name: str
    fn: Callable[..., Any]
    description: str
    domains: Tuple[str, ...]
    required_services: Tuple[str, ...] = ()
    severity: Optional[str] = None       # None | guardrails.MUTATING | DESTRUCTIVE
    skill_name: Optional[str] = None     # exposed in skills.registry.SKILLS as this
    enabled: bool = True


def _build_registry() -> Dict[str, ToolSpec]:
    from persona.agent_tools import (
        get_archetype_info,
        persona_category_breakdown,
        persona_vector_search,
    )
    from revive_agent.tools.brand_tools import analyze_brand_tool
    from revive_agent.tools.config_write_tools import (
        delete_ontology_node_tool,
        delete_rule_tool,
        upsert_ontology_node_tool,
        upsert_rule_tool,
    )
    from revive_agent.tools.ontology_tools import (
        audit_ontology_tool,
        get_attribute_tool,
        get_ontology_tool,
        label_scores_tool,
        resolve_segments_tool,
        resolve_strategy_tool,
        score_tool,
    )
    from revive_agent.tools.persona_tools import classify_persona_tool
    from revive_agent.tools.plan_tools import load_plan_tool
    from revive_agent.tools.schema_tools import get_schema_tool, list_tables_in_schema_tool
    from revive_agent.tools.skill_exec_tools import (
        audience_export_tool,
        chart_generation_tool,
        execute_action_tool,
        get_taxonomy_tool,
        list_campaigns_tool,
        python_analysis_tool,
        run_named_query_tool,
    )
    from revive_agent.tools.skill_tools import (
        get_skill_template_tool,
        get_skill_tool,
        list_skills_tool,
    )
    from revive_agent.tools.sql_tools import (
        dry_run_sql_tool,
        run_sql_preview_tool,
        submit_execution_plan,
    )

    python_skill_enabled = os.environ.get("PYTHON_SKILL_ENABLED", "").lower() == "true"

    specs = [
        # --- DS-Agent: planning, schema exploration, semantic context ---
        ToolSpec("load_plan_tool", load_plan_tool,
                 "Load a workflow plan by ID or by matching the user query", ("ds",)),
        ToolSpec("list_tables_in_schema_tool", list_tables_in_schema_tool,
                 "List tables visible in a database schema", ("ds",)),
        ToolSpec("get_schema_tool", get_schema_tool,
                 "Profile a table's columns and sample values", ("ds",)),
        ToolSpec("submit_execution_plan", submit_execution_plan,
                 "Submit the structured execution plan for the DE-Agent", ("ds",)),
        ToolSpec("analyze_brand_tool", analyze_brand_tool,
                 "Crawl a brand website, extract identity via Gemini, save to ontology",
                 ("ds", "strategy"), required_services=("gemini",)),
        ToolSpec("list_skills_tool", list_skills_tool,
                 "List skill guideline documents", ("ds",)),
        ToolSpec("get_skill_tool", get_skill_tool,
                 "Load a skill guideline document by name", ("ds",)),
        ToolSpec("get_skill_template_tool", get_skill_template_tool,
                 "Load a template file from a skill guideline", ("ds",)),
        # --- Ontology (semantic sidecar) reads, shared across agents ---
        ToolSpec("get_ontology_tool", get_ontology_tool,
                 "Read the site ontology (datasources, attributes, segments)",
                 ("ds", "strategy", "rule", "ontology")),
        ToolSpec("get_attribute_tool", get_attribute_tool,
                 "Read one ontology attribute incl. its compute rule",
                 ("ds", "rule", "ontology")),
        ToolSpec("score_tool", score_tool,
                 "Compute a scoring-rule value from answers", ("ds",)),
        ToolSpec("label_scores_tool", label_scores_tool,
                 "Resolve label scores for a member", ("ds",)),
        ToolSpec("resolve_segments_tool", resolve_segments_tool,
                 "Resolve segment definitions to SQL conditions", ("ds", "strategy")),
        ToolSpec("resolve_strategy_tool", resolve_strategy_tool,
                 "Render the configured message strategy for a segment", ("ds", "strategy")),
        ToolSpec("audit_ontology_tool", audit_ontology_tool,
                 "Integrity-audit the ontology config", ("ds", "rule", "ontology")),
        ToolSpec("classify_persona_tool", classify_persona_tool,
                 "Classify content against the Jungian persona taxonomy",
                 ("ds", "strategy"), required_services=("vertex_ai",)),
        # --- DE-Agent: SQL execution path (result shapes are a hard contract) ---
        ToolSpec("dry_run_sql_tool", dry_run_sql_tool,
                 "Validate SQL via EXPLAIN without executing", ("de",)),
        ToolSpec("run_sql_preview_tool", run_sql_preview_tool,
                 "Run read-only SQL against the site's analytics DB (ontology-governed)",
                 ("de", "skill"), skill_name="sql_execution"),
        # --- Config writes (per-site HITL confirmation via severity) ---
        ToolSpec("upsert_rule_tool", upsert_rule_tool,
                 "Create or update a compute rule", ("rule",), severity=MUTATING),
        ToolSpec("delete_rule_tool", delete_rule_tool,
                 "Delete a compute rule", ("rule",), severity=DESTRUCTIVE),
        ToolSpec("upsert_ontology_node_tool", upsert_ontology_node_tool,
                 "Create or update an ontology node", ("ontology",), severity=MUTATING),
        ToolSpec("delete_ontology_node_tool", delete_ontology_node_tool,
                 "Delete an ontology node", ("ontology",), severity=DESTRUCTIVE),
        # --- Executor skills (skills.registry view) ---
        ToolSpec("audience_export_tool", audience_export_tool,
                 "Materialize an audience query to CSV for download/handoff",
                 ("skill",), skill_name="audience_export"),
        ToolSpec("chart_generation_tool", chart_generation_tool,
                 "Produce a chart spec (JSON) from result rows for frontend rendering",
                 ("skill",), skill_name="chart_generation"),
        ToolSpec("execute_action_tool", execute_action_tool,
                 "Hand a MarketingPlan to the external CDP (setup/schedule campaign, "
                 "segmentation, score/behavior rules) via the connector registry",
                 ("skill",), severity=DESTRUCTIVE, skill_name="execute_action"),
        ToolSpec("get_taxonomy_tool", get_taxonomy_tool,
                 "Fetch the taxonomy from the connected CDP",
                 ("skill",), skill_name="get_taxonomy"),
        ToolSpec("list_campaigns_tool", list_campaigns_tool,
                 "List campaigns known to the connected CDP",
                 ("skill",), skill_name="list_campaigns"),
        ToolSpec("run_named_query_tool", run_named_query_tool,
                 "Run a named, admin-defined parameterized SQL query (declarative tools)",
                 ("skill",), skill_name="named_query"),
        ToolSpec("python_analysis_tool", python_analysis_tool,
                 "Run sandboxed Python over result data (Docker container executor)",
                 ("skill",), skill_name="python_analysis", enabled=python_skill_enabled),
        # --- PersonaAgent (advanced mode, runs under its own Runner) ---
        ToolSpec("persona_vector_search", persona_vector_search,
                 "Vector-search the persona taxonomy for content matches",
                 ("persona",), required_services=("vertex_ai",)),
        ToolSpec("persona_category_breakdown", persona_category_breakdown,
                 "Distribution of product categories matching the content",
                 ("persona",), required_services=("vertex_ai",)),
        ToolSpec("get_archetype_info", get_archetype_info,
                 "Describe a Jungian archetype (traits, motivation, behavior)",
                 ("persona",)),
    ]

    registry: Dict[str, ToolSpec] = {}
    for spec in specs:
        if spec.name != spec.fn.__name__:
            raise ValueError(f"ToolSpec '{spec.name}' does not match function "
                             f"name '{spec.fn.__name__}'")
        if spec.name in registry:
            raise ValueError(f"Duplicate tool '{spec.name}' in registry")
        registry[spec.name] = spec
    return registry


# Built lazily: revive_agent/__init__ imports agent.py which imports this
# module, so building at import time would be a circular import. By the time
# an agent constructor calls tools_for(), the tool submodules import cleanly.
_REGISTRY: Optional[Dict[str, ToolSpec]] = None


def get_registry() -> Dict[str, ToolSpec]:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = _build_registry()
    return _REGISTRY


def tools_for(*domains: str) -> list:
    """ADK-ready tool list for an agent; severity wraps in HITL confirmation."""
    wanted = set(domains)
    tools = []
    for spec in get_registry().values():
        if not spec.enabled or wanted.isdisjoint(spec.domains):
            continue
        if spec.severity is not None:
            tools.append(FunctionTool(
                spec.fn, require_confirmation=needs_confirmation(spec.severity)))
        else:
            tools.append(spec.fn)
    return tools


def required_services_map() -> Dict[str, Tuple[str, ...]]:
    """Tool name -> integrations it needs (ServiceGatingPlugin + Integrations UI)."""
    return {s.name: s.required_services
            for s in get_registry().values() if s.required_services}
