"""Executor skills: export, chart, external action dispatch, CDP reads.

SQL execution reuses sql_tools.run_sql_preview_tool (read-only, ontology-
governed). python_analysis is gated behind PYTHON_SKILL_ENABLED (sandboxed
Docker executor; never the Gemini-side sandbox — data must not leave).
"""

import csv
import io
import json
import logging
from typing import Any, Dict

from services.guardrails import check_authz, current_user
from revive_agent.tools._infra import get_query_service, get_site_id

logger = logging.getLogger("ai_cdp.tools.skills")


def audience_export_tool(sql: str, filename: str = "audience.csv") -> Dict[str, Any]:
    """Materialize an audience query to CSV (read-only; ontology-governed tables).

    Args:
        sql: SELECT statement producing the audience (validated like previews).
        filename: Suggested file name for the export.

    Returns:
        {success, row_count, csv_preview, csv_base64-free content} or error.
    """
    from dbtoolbox import PolicyViolation, categorize_dbapi_error, get_error_suggestion

    try:
        rows = get_query_service().export(sql)
    except Exception as e:
        error_type = e.error_type if isinstance(e, PolicyViolation) else categorize_dbapi_error(e)
        return {
            "success": False,
            "error": f"Export query failed: {e}",
            "error_type": error_type,
            "suggestion": get_error_suggestion(error_type),
        }
    if not rows:
        return {"success": False, "error": "Query returned no rows"}

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    content = buf.getvalue()
    return {
        "success": True,
        "filename": filename,
        "row_count": len(rows),
        "csv_preview": "\n".join(content.splitlines()[:6]),
        "csv_content": content if len(content) < 200_000 else content[:200_000],
    }


def chart_generation_tool(
    chart_type: str, title: str, data_json: str,
    x_field: str, y_field: str, series_field: str = "",
) -> Dict[str, Any]:
    """Build a chart spec from result rows for the frontend to render.

    Args:
        chart_type: 'bar' | 'line' | 'pie' | 'scatter'.
        title: Chart title shown to the user.
        data_json: JSON array of row objects (e.g. the SQL preview sample).
        x_field: Field name for the x axis / category.
        y_field: Field name for the y axis / value.
        series_field: Optional field to split series by.

    Returns:
        {success, chart: {type, title, x, y, series, data}} for state_delta rendering.
    """
    if chart_type not in {"bar", "line", "pie", "scatter"}:
        return {"success": False, "error": f"Unsupported chart_type '{chart_type}'"}
    try:
        data = json.loads(data_json)
        if not isinstance(data, list) or not data:
            raise ValueError("data_json must be a non-empty JSON array")
    except (json.JSONDecodeError, ValueError) as e:
        return {"success": False, "error": f"Invalid data_json: {e}"}
    missing = [f for f in (x_field, y_field) if f not in data[0]]
    if missing:
        return {"success": False, "error": f"Fields not in data: {missing}"}
    return {
        "success": True,
        "chart": {
            "type": chart_type, "title": title,
            "x": x_field, "y": y_field,
            "series": series_field or None,
            "data": data[:500],
        },
    }


async def execute_action_tool(action_type: str, plan_json: str, schedule: str = "") -> Dict[str, Any]:
    """Hand a marketing plan to the external CDP system for execution.

    Action types: setup_campaign | schedule_campaign | setup_segmentation |
    setup_score_rule | setup_behavior_rule. Currently dispatches to the
    dry-run connector until the real CDP MCP/API is configured.

    Args:
        action_type: One of the action types above.
        plan_json: MarketingPlan JSON — {goal, kpi?, segmentation: {basis:
            'taxonomy'|'behavioral', segment_key?, behavior_criteria?},
            audience?, analysis_evidence?, strategy?, channel?:
            'edm'|'sms'|'web_popup', channel_rationale?, channel_params?}.
        schedule: For schedule_campaign — ISO datetime or cron expression.

    Returns:
        {success, status, adapter, detail} or {success: False, error}.
    """
    if denial := check_authz("execute_external_action"):
        return {"success": False, "error": denial}
    from services.external_actions import ExternalAction, execute_action
    try:
        plan = json.loads(plan_json)
        action = ExternalAction(
            action_type=action_type, plan=plan, schedule=schedule or None
        )
    except Exception as e:
        return {"success": False, "error": f"Invalid action payload: {e}"}
    ctx = current_user()
    record = await execute_action(
        action, site_id=get_site_id(), executed_by=ctx.user_id if ctx else None
    )
    return {"success": True, **record.model_dump()}


def run_named_query_tool(name: str = "", args_json: str = "{}") -> Dict[str, Any]:
    """Run a named, admin-defined parameterized SQL query for this site.

    Site admins define vetted SELECT statements with typed parameters
    (declarative SQL tools). Values bind at the driver level — no SQL is
    composed from user input.

    Args:
        name: The named query to run. Empty = list this site's available queries.
        args_json: JSON object of parameter values, e.g. '{"days": 30}'.

    Returns:
        {success, tool, data, row_count} on success;
        with no name: {success, queries: [{name, description, parameters}]};
        on failure: {success: False, error, error_type}.
    """
    from dbtoolbox.sqltools import load_sql_tools, run_sql_tool

    service = get_query_service()
    defs = load_sql_tools(get_site_id(), service.policy)
    if not name:
        return {
            "success": True,
            "queries": [
                {
                    "name": t.name,
                    "description": t.description,
                    "parameters": [
                        {"name": p.name, "type": p.type, "required": p.required,
                         "description": p.description}
                        for p in t.parameters
                    ],
                }
                for t in defs
            ],
        }
    tool = next((t for t in defs if t.name == name), None)
    if tool is None:
        return {
            "success": False,
            "error": f"No named query '{name}' is defined for this site",
            "error_type": "unknown_query",
            "available": [t.name for t in defs],
        }
    try:
        args = json.loads(args_json) if args_json else {}
        if not isinstance(args, dict):
            raise ValueError("args_json must be a JSON object")
    except (json.JSONDecodeError, ValueError) as e:
        return {"success": False, "error": f"Invalid args_json: {e}",
                "error_type": "invalid_arguments"}
    return run_sql_tool(service, tool, args)


def get_taxonomy_tool() -> Dict[str, Any]:
    """Fetch the segmentation taxonomy from the connected CDP (stub: internal ontology)."""
    from services.external_actions import get_taxonomy_stub
    return get_taxonomy_stub(get_site_id())


def list_campaigns_tool() -> Dict[str, Any]:
    """List campaigns known to the connected CDP (stub: past action executions)."""
    from services.external_actions import list_campaigns_stub
    return list_campaigns_stub(get_site_id())


def python_analysis_tool(code: str) -> Dict[str, Any]:
    """Sandboxed Python analysis (enabled via PYTHON_SKILL_ENABLED=true + Docker).

    Args:
        code: Python code to run in the container sandbox.
    """
    return {
        "success": False,
        "error": "python_analysis requires a configured ContainerCodeExecutor "
                 "(set PYTHON_SKILL_ENABLED=true with Docker available)",
    }
