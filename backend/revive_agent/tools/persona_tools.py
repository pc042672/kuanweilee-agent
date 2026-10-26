"""Persona classification tools — the single persona-search wrapper.

persona_search_core resolves the site's Vertex AI integration (fail-closed)
and runs fast_persona_classify; classify_persona_tool (DS/Strategy agents)
and persona/agent_tools.py (advanced-mode PersonaAgent) both build on it.
"""

import logging
from typing import Any, Dict, Optional, Tuple

from revive_agent.tools._infra import resolve_or_refuse

logger = logging.getLogger("ai_cdp.tools.persona")


def persona_search_core(
    tool_name: str, content: str, search_k: int, category_filter: str = "",
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """(result_dict, None) on success, (None, refusal) when vertex_ai is unconfigured.

    result_dict is PersonaSearchResult.model_dump(): archetypes (sorted by
    score), top_matches (top 10), content_analyzed, mode.
    """
    creds, refusal = resolve_or_refuse(tool_name, "vertex_ai")
    if refusal:
        return None, refusal

    from persona.search import fast_persona_classify

    result = fast_persona_classify(
        content=content,
        top_k=search_k,
        category_filter=category_filter or None,
        project_id=creds.get("project_id"),
        location=creds.get("location"),
    )
    return result.model_dump(), None


def classify_persona_tool(content: str, top_k: int = 5) -> Dict[str, Any]:
    """
    Classify content against Jungian persona taxonomy to identify customer archetypes.

    Use this tool to understand what kind of customer persona a query or product
    description maps to. This helps create persona-driven campaigns and audience
    segments.

    Args:
        content: Text to classify (e.g., product descriptions, browsing behavior,
                 purchase history, or user query like "users who buy premium electronics")
        top_k: Number of top archetype results to return (default: 5)

    Returns:
        Dictionary with archetype scores and match details:
        - archetypes: List of {archetype, score, category_breakdown, match_count}
        - top_matches: List of detailed match info
        - content_analyzed: The input content

    Example:
        classify_persona_tool("users who frequently buy organic food and wellness products")
        -> archetypes: [{archetype: "jungian-caregiver", score: 0.42}, ...]

    On error_type 'service_not_configured', tell the user which integration
    an admin must set up (Settings → Integrations) — do not retry.
    """
    try:
        data, refusal = persona_search_core("classify_persona_tool", content, top_k * 10)
        if refusal:
            return refusal
        data["archetypes"] = data["archetypes"][:top_k]
        data["top_matches"] = data["top_matches"][:10]
        return data
    except Exception as e:
        return {
            "success": False,
            "error": f"Persona classification failed: {e}",
            "suggestion": "Ensure the persona vector store is initialized. Check /api/persona/taxonomy/reload",
        }
