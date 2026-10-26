"""Workflow plan loader tool."""

from typing import Dict, Any


def load_plan_tool(plan_id: str = None, match_query: str = None) -> Dict[str, Any]:
    """
    Load a workflow plan by ID or by matching user query to plan keywords.

    Workflow plans define multi-phase execution sequences for complex tasks like:
    - Brand analysis and marketing campaign planning
    - Abandoned cart user analysis
    - VIP customer analysis

    Call this tool to:
    1. Get a list of all available plans (call with no arguments)
    2. Load a specific plan by ID (e.g., plan_id="abandoned-cart-analysis")
    3. Match a user query to the best plan (e.g., match_query="find abandoned cart users")

    Args:
        plan_id: Specific plan ID to load (optional)
        match_query: User query to match against plan keywords (optional)

    Returns:
        Dict containing:
        - success: Whether the operation succeeded
        - plan: The matched plan details (if found)
        - formatted: Human-readable plan description
        - plans_count: Number of available plans (if listing all)
        - summary: Summary of all plans (if listing all)

    Example:
        # List all plans
        load_plan_tool()

        # Load specific plan
        load_plan_tool(plan_id="abandoned-cart-analysis")

        # Match user query to plan
        load_plan_tool(match_query="Find users who abandoned their cart")
    """
    try:
        from config.plan_loader import (
            get_plan_by_id,
            match_plan_by_keywords,
            format_plan_for_agent,
            get_active_plans,
            get_plans_summary
        )

        if plan_id:
            plan = get_plan_by_id(plan_id)
            if plan:
                return {
                    "success": True,
                    "plan": plan,
                    "formatted": format_plan_for_agent(plan)
                }
            return {
                "success": False,
                "error": f"Plan '{plan_id}' not found"
            }

        if match_query:
            plan = match_plan_by_keywords(match_query)
            if plan:
                return {
                    "success": True,
                    "plan": plan,
                    "formatted": format_plan_for_agent(plan)
                }
            return {
                "success": False,
                "error": f"No plan matched query: {match_query}",
                "hint": "The user's request doesn't match any predefined workflow. Proceed with standard DS-STAR analysis."
            }

        return {
            "success": True,
            "plans_count": len(get_active_plans()),
            "summary": get_plans_summary()
        }

    except ImportError as e:
        return {
            "success": False,
            "error": f"Plan loader not available: {e}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to load plan: {e}"
        }
