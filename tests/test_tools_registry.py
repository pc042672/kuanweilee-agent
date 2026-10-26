"""Phase D: consolidated tools registry — agent tool lists, severity wrapping,
required-services metadata, and the skills.registry compatibility view."""

from google.adk.tools import FunctionTool

from tools_registry import get_registry, required_services_map, tools_for

REGISTRY = get_registry()


def _names(tools):
    return {t.func.__name__ if isinstance(t, FunctionTool) else t.__name__ for t in tools}


def test_registry_names_match_functions():
    for name, spec in REGISTRY.items():
        assert name == spec.fn.__name__


# Snapshot equivalence: per-agent tool sets exactly as before the refactor.

def test_ds_agent_tools_snapshot():
    assert _names(tools_for("ds")) == {
        "load_plan_tool",
        "list_tables_in_schema_tool",
        "get_schema_tool",
        "submit_execution_plan",
        "analyze_brand_tool",
        "list_skills_tool",
        "get_skill_tool",
        "get_skill_template_tool",
        "get_ontology_tool",
        "get_attribute_tool",
        "score_tool",
        "label_scores_tool",
        "resolve_segments_tool",
        "resolve_strategy_tool",
        "audit_ontology_tool",
        "classify_persona_tool",
    }


def test_de_agent_tools_snapshot():
    assert _names(tools_for("de")) == {"dry_run_sql_tool", "run_sql_preview_tool"}


def test_strategy_agent_tools_snapshot():
    assert _names(tools_for("strategy")) == {
        "resolve_strategy_tool",
        "resolve_segments_tool",
        "analyze_brand_tool",
        "classify_persona_tool",
        "get_ontology_tool",
    }


def test_rule_agent_tools_snapshot():
    assert _names(tools_for("rule")) == {
        "get_ontology_tool",
        "get_attribute_tool",
        "audit_ontology_tool",
        "upsert_rule_tool",
        "delete_rule_tool",
    }


def test_ontology_agent_tools_snapshot():
    assert _names(tools_for("ontology")) == {
        "get_ontology_tool",
        "get_attribute_tool",
        "audit_ontology_tool",
        "upsert_ontology_node_tool",
        "delete_ontology_node_tool",
    }


def test_executor_tools_snapshot():
    # python_analysis_tool excluded (PYTHON_SKILL_ENABLED off by default)
    assert _names(tools_for("skill")) == {
        "run_sql_preview_tool",
        "audience_export_tool",
        "chart_generation_tool",
        "execute_action_tool",
        "get_taxonomy_tool",
        "list_campaigns_tool",
        "run_named_query_tool",
    }


def test_severity_tools_wrapped_for_confirmation():
    by_name = {}
    for t in tools_for("rule", "ontology", "skill"):
        by_name[t.func.__name__ if isinstance(t, FunctionTool) else t.__name__] = t
    for name in ("upsert_rule_tool", "delete_rule_tool", "upsert_ontology_node_tool",
                 "delete_ontology_node_tool", "execute_action_tool"):
        assert isinstance(by_name[name], FunctionTool), f"{name} must require confirmation"
    for name in ("get_ontology_tool", "chart_generation_tool", "run_sql_preview_tool"):
        assert not isinstance(by_name[name], FunctionTool), f"{name} must not be wrapped"


def test_required_services_cover_brand_and_persona():
    assert required_services_map() == {
        "analyze_brand_tool": ("gemini",),
        "classify_persona_tool": ("vertex_ai",),
        "persona_vector_search": ("vertex_ai",),
        "persona_category_breakdown": ("vertex_ai",),
    }


def test_skills_view_matches_registry():
    from skills.registry import SKILLS, get_skill, list_skills

    assert set(SKILLS) == {
        "sql_execution", "audience_export", "chart_generation",
        "execute_action", "get_taxonomy", "list_campaigns", "named_query",
    }
    assert get_skill("sql_execution").tool is REGISTRY["run_sql_preview_tool"].fn
    assert {s["name"] for s in list_skills()} == set(SKILLS)
