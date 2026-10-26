"""
ADK tool functions for the PersonaAgent (advanced mode).

These tools are automatically converted to ADK FunctionTools
via the agent's tools=[...] parameter.
"""

from typing import Dict, Any


# --- Jungian Archetype Descriptions ---

ARCHETYPE_DESCRIPTIONS = {
    "jungian-ruler": {
        "name": "Ruler (統治者)",
        "traits": "Leadership, authority, control, responsibility, stability",
        "motivation": "Create a prosperous, successful family or community",
        "behavior": "Seeks premium products, values brand prestige and quality, compares specs and prices methodically",
    },
    "jungian-caregiver": {
        "name": "Caregiver (照顧者)",
        "traits": "Nurturing, generosity, compassion, service, protection",
        "motivation": "Protect and care for others",
        "behavior": "Prioritizes family/health products, values safety and reliability, responsive to emotional appeals",
    },
    "jungian-creator": {
        "name": "Creator (創造者)",
        "traits": "Innovation, imagination, self-expression, vision, artistry",
        "motivation": "Create something of enduring value",
        "behavior": "Drawn to unique/customizable products, values design and aesthetics, early adopter tendencies",
    },
    "jungian-everyman": {
        "name": "Everyman (凡人)",
        "traits": "Belonging, realism, empathy, equality, authenticity",
        "motivation": "Connect with others and fit in",
        "behavior": "Values practicality and affordability, influenced by peer reviews, seeks reliable everyday products",
    },
    "jungian-explorer": {
        "name": "Explorer (探險家)",
        "traits": "Freedom, independence, discovery, adventure, ambition",
        "motivation": "Experience a better, more authentic life",
        "behavior": "Seeks new experiences and products, values variety, responds to novelty and discovery narratives",
    },
    "jungian-hero": {
        "name": "Hero (英雄)",
        "traits": "Courage, determination, mastery, achievement, honor",
        "motivation": "Prove worth through courageous action",
        "behavior": "Attracted to performance products, values achievement and self-improvement, responds to challenge framing",
    },
    "jungian-innocent": {
        "name": "Innocent (天真者)",
        "traits": "Optimism, simplicity, trust, purity, happiness",
        "motivation": "Experience happiness and paradise",
        "behavior": "Prefers simple/trustworthy products, values transparency, responds to positive/wholesome messaging",
    },
    "jungian-jester": {
        "name": "Jester (弄臣)",
        "traits": "Joy, humor, playfulness, spontaneity, living in the moment",
        "motivation": "Have a great time and lighten up the world",
        "behavior": "Drawn to fun/entertaining products, values experiences over possessions, responds to humor in marketing",
    },
    "jungian-lover": {
        "name": "Lover (情人)",
        "traits": "Passion, intimacy, sensuality, appreciation, commitment",
        "motivation": "Achieve intimacy and experience sensual pleasure",
        "behavior": "Values aesthetics and sensory experience, drawn to luxury/beauty products, responds to emotional storytelling",
    },
    "jungian-magician": {
        "name": "Magician (魔法師)",
        "traits": "Transformation, vision, innovation, knowledge, charisma",
        "motivation": "Make dreams come true through understanding",
        "behavior": "Attracted to transformative products, values innovation and technology, responds to visionary messaging",
    },
    "jungian-outlaw": {
        "name": "Outlaw (叛逆者)",
        "traits": "Revolution, disruption, liberation, radical freedom, rule-breaking",
        "motivation": "Overturn what isn't working",
        "behavior": "Seeks unconventional products, values distinctiveness, responds to counter-culture and rebellion themes",
    },
    "jungian-sage": {
        "name": "Sage (智者)",
        "traits": "Wisdom, intelligence, analysis, understanding, truth-seeking",
        "motivation": "Use intelligence to understand the world",
        "behavior": "Research-driven purchasing, values expertise and data, responds to educational and informative content",
    },
}


def persona_vector_search(
    content: str,
    top_k: int = 20,
    category_filter: str = "",
) -> Dict[str, Any]:
    """
    Search the Jungian persona taxonomy for content matches.

    Uses Vertex AI Vector Search 2.0 to find the most semantically similar
    persona keywords/sentences, then scores and aggregates by archetype.

    Args:
        content: The user content to classify (e.g., social media post, browsing interest)
        top_k: Number of vector search results to retrieve (default: 20)
        category_filter: Optional product category to filter by (e.g., "3C電子產品", "健康與保健")

    Returns:
        Dict with 'archetypes' (sorted by score) and 'top_matches' (top 10 matches with details)
    """
    from revive_agent.tools.persona_tools import persona_search_core

    data, refusal = persona_search_core(
        "persona_vector_search", content, top_k, category_filter
    )
    return refusal if refusal else data


def persona_category_breakdown(content: str) -> Dict[str, Any]:
    """
    Analyze which product categories the content most aligns with.

    Searches across ALL categories and returns a distribution showing
    which product categories are most relevant to the given content.

    Args:
        content: The user content to analyze

    Returns:
        Dict with category distribution and top category matches
    """
    from revive_agent.tools.persona_tools import persona_search_core

    data, refusal = persona_search_core("persona_category_breakdown", content, 50)
    if refusal:
        return refusal

    # Aggregate by category instead of archetype
    category_scores: Dict[str, float] = {}
    for match in data["top_matches"]:
        cat = match["category"]
        category_scores[cat] = category_scores.get(cat, 0) + match["weighted_score"]

    # Normalize
    max_score = max(category_scores.values()) if category_scores else 1.0
    if max_score == 0:
        max_score = 1.0

    distribution = {
        cat: round(score / max_score, 4)
        for cat, score in sorted(category_scores.items(), key=lambda x: x[1], reverse=True)
    }

    return {
        "content_analyzed": content,
        "category_distribution": distribution,
        "top_category": next(iter(distribution), "unknown"),
        "total_matches": len(data["top_matches"]),
    }


def get_archetype_info(archetype_name: str) -> Dict[str, Any]:
    """
    Get detailed information about a Jungian archetype.

    Use this to understand what a specific archetype represents,
    its traits, motivations, and typical consumer behavior patterns.

    Args:
        archetype_name: The archetype ID (e.g., "jungian-ruler", "jungian-sage")
                       or partial name (e.g., "ruler", "sage")

    Returns:
        Dict with archetype name, traits, motivation, and behavior description
    """
    # Normalize input
    key = archetype_name.lower().strip()
    if not key.startswith("jungian-"):
        key = f"jungian-{key}"

    info = ARCHETYPE_DESCRIPTIONS.get(key)
    if info:
        return {"archetype_id": key, **info}

    # Fuzzy match
    for k, v in ARCHETYPE_DESCRIPTIONS.items():
        if archetype_name.lower() in k or archetype_name.lower() in v["name"].lower():
            return {"archetype_id": k, **v}

    return {
        "error": f"Unknown archetype: {archetype_name}",
        "available": list(ARCHETYPE_DESCRIPTIONS.keys()),
    }
