"""SQL execution, validation, and plan submission tools."""

import json
from typing import Dict, Any
from google.adk.tools import ToolContext

from dbtoolbox import categorize_sql_error, get_error_suggestion
from revive_agent.tools._infra import get_query_service


def submit_execution_plan(plan_json: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Submit your execution plan. CALL THIS TOOL to submit your JSON execution plan.
    This is REQUIRED - you must call this tool with your plan after gathering context.

    Args:
        plan_json: The execution plan as a JSON string. Must include:
            - goal: The user's query goal
            - segment_type: "existing_label" or "new_segment"
            - label_matched: The matched label_id or null
            - tables_needed: List of tables with columns
            - execution_method: "sql"

    Returns:
        Success status and message.

    Example:
        submit_execution_plan('{"goal": "Find abandoned cart users", "segment_type": "existing_label", "label_matched": "abandoned_cart", "tables_needed": [{"name": "report.smb_abandon_list", "columns": ["sitemember", "is_abandont"]}], "execution_method": "sql"}')
    """
    try:
        plan = json.loads(plan_json)
        if "goal" not in plan:
            return {"success": False, "error": "Plan must include 'goal' field"}

        tool_context.state["temp:submitted_plan"] = plan_json

        return {
            "success": True,
            "message": "Execution plan submitted successfully",
            "plan": plan
        }
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"Invalid JSON: {e}"}
    except Exception as e:
        return {"success": False, "error": f"Failed to submit plan: {e}"}


def dry_run_sql_tool(sql_query: str) -> Dict[str, Any]:
    """
    Validates a SQL query using EXPLAIN to check for syntax and schema errors.
    ALWAYS use this to check your SQL before executing.

    Args:
        sql_query: The raw SQL string to validate.

    Returns:
        {"valid": True, "message": "SQL syntax and schema validated"}
        OR
        {"valid": False, "error": "...", "error_type": "column_not_found|table_not_found|etc", "suggestion": "..."}
    """
    try:
        result = get_query_service().dry_run(sql_query)
    except Exception as e:
        result = {"valid": False, "error": str(e), "error_type": categorize_sql_error(str(e))}

    if result.get("valid"):
        return {"valid": True, "message": "SQL syntax and schema validated successfully"}

    error_type = result.get("error_type") or "unknown_error"
    return {
        "valid": False,
        "error": result.get("error", "Unknown error"),
        "error_type": error_type,
        "suggestion": get_error_suggestion(error_type),
    }


def run_sql_preview_tool(sql_query: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Executes a SQL query with LIMIT 10 and returns the results as a preview.
    IMPORTANT: Always call dry_run_sql_tool first to validate!

    Args:
        sql_query: The SQL SELECT statement to execute.

    Returns:
        {"success": True, "data": [...], "row_count": N, "message": "..."}
        OR
        {"success": False, "error": "...", "error_type": "...", "suggestion": "..."}
    """
    result = get_query_service().preview(sql_query, limit=10)
    tool_context.state["temp:sql_preview"] = result
    return result
