"""
Plan Loader - Loads and manages workflow plans from config/plans.json

Plans define multi-phase workflows that can be triggered by user requests.
Each plan contains phases with specific agents, tools, and outputs.
"""
import json
import os
from typing import Optional, List, Dict, Any
from pathlib import Path


# Cache for loaded plans
_plans_cache: Optional[Dict[str, Any]] = None


def get_plans_path() -> Path:
    """Get the path to plans.json config file."""
    # Try relative to backend directory first
    backend_dir = Path(__file__).parent.parent.parent
    plans_path = backend_dir / "config" / "plans.json"

    if plans_path.exists():
        return plans_path

    # Fallback to project root config
    project_root = backend_dir.parent
    return project_root / "config" / "plans.json"


def load_plans(force_reload: bool = False) -> Dict[str, Any]:
    """Load plans from config/plans.json.

    Args:
        force_reload: If True, reload from disk even if cached

    Returns:
        Dict containing plans configuration
    """
    global _plans_cache

    if _plans_cache is not None and not force_reload:
        return _plans_cache

    plans_path = get_plans_path()

    if not plans_path.exists():
        print(f"[PlanLoader] Plans file not found: {plans_path}")
        return {"version": "1.0", "plans": []}

    try:
        with open(plans_path, "r", encoding="utf-8") as f:
            _plans_cache = json.load(f)
            print(f"[PlanLoader] Loaded {len(_plans_cache.get('plans', []))} plans from {plans_path}")
            return _plans_cache
    except json.JSONDecodeError as e:
        print(f"[PlanLoader] Error parsing plans.json: {e}")
        return {"version": "1.0", "plans": []}


def get_all_plans() -> List[Dict[str, Any]]:
    """Get all available plans.

    Returns:
        List of plan configurations
    """
    plans_data = load_plans()
    return plans_data.get("plans", [])


def get_active_plans() -> List[Dict[str, Any]]:
    """Get only active plans.

    Returns:
        List of active plan configurations
    """
    return [p for p in get_all_plans() if p.get("status") == "active"]


def get_plan_by_id(plan_id: str) -> Optional[Dict[str, Any]]:
    """Get a specific plan by ID.

    Args:
        plan_id: The plan's unique identifier

    Returns:
        Plan configuration or None if not found
    """
    for plan in get_all_plans():
        if plan.get("id") == plan_id:
            return plan
    return None


def match_plan_by_keywords(user_input: str) -> Optional[Dict[str, Any]]:
    """Match user input to a plan using trigger keywords.

    Args:
        user_input: The user's request text

    Returns:
        Best matching plan or None if no match found
    """
    user_input_lower = user_input.lower()
    best_match = None
    best_score = 0

    for plan in get_active_plans():
        keywords = plan.get("trigger_keywords", [])
        score = 0

        for keyword in keywords:
            if keyword.lower() in user_input_lower:
                # Longer keyword matches are weighted higher
                score += len(keyword)

        if score > best_score:
            best_score = score
            best_match = plan

    if best_match:
        print(f"[PlanLoader] Matched plan '{best_match.get('id')}' with score {best_score}")

    return best_match


def get_plan_phases(plan_id: str) -> List[Dict[str, Any]]:
    """Get all phases for a plan.

    Args:
        plan_id: The plan's unique identifier

    Returns:
        List of phase configurations
    """
    plan = get_plan_by_id(plan_id)
    if plan:
        return plan.get("phases", [])
    return []


def get_phase_by_id(plan_id: str, phase_id: str) -> Optional[Dict[str, Any]]:
    """Get a specific phase from a plan.

    Args:
        plan_id: The plan's unique identifier
        phase_id: The phase's unique identifier

    Returns:
        Phase configuration or None if not found
    """
    for phase in get_plan_phases(plan_id):
        if phase.get("id") == phase_id:
            return phase
    return None


def format_plan_for_agent(plan: Dict[str, Any]) -> str:
    """Format a plan for inclusion in agent instructions.

    Args:
        plan: Plan configuration

    Returns:
        Formatted string describing the plan workflow
    """
    if not plan:
        return ""

    lines = [
        f"## Workflow Plan: {plan.get('name', 'Unknown')}",
        f"**Description:** {plan.get('description', 'N/A')}",
        "",
        "### Phases:",
    ]

    for i, phase in enumerate(plan.get("phases", []), 1):
        phase_name = phase.get("name", f"Phase {i}")
        phase_desc = phase.get("description", "")
        agent = phase.get("agent", "")
        tools = phase.get("tools", [])
        output_key = phase.get("output_key", "")

        lines.append(f"\n**{i}. {phase_name}** (Agent: {agent})")
        lines.append(f"   - Description: {phase_desc}")
        if tools:
            lines.append(f"   - Tools: {', '.join(tools)}")
        if output_key:
            lines.append(f"   - Output: {output_key}")

    return "\n".join(lines)


def get_plans_summary() -> str:
    """Get a summary of all available plans for agent reference.

    Returns:
        Formatted string with all plans summary
    """
    plans = get_active_plans()

    if not plans:
        return "No workflow plans available."

    lines = ["## Available Workflow Plans\n"]

    for plan in plans:
        plan_id = plan.get("id", "unknown")
        name = plan.get("name", "Unknown")
        desc = plan.get("description", "")
        keywords = plan.get("trigger_keywords", [])
        phases = plan.get("phases", [])

        lines.append(f"### {name}")
        lines.append(f"- **ID:** {plan_id}")
        lines.append(f"- **Description:** {desc}")
        lines.append(f"- **Keywords:** {', '.join(keywords)}")
        lines.append(f"- **Phases:** {len(phases)}")
        lines.append("")

    return "\n".join(lines)
