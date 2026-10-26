"""Brand analysis tool — thin wrapper over tools/brand_analyzer + services/brand_service."""

import logging
from typing import Any, Dict

from revive_agent.tools._infra import resolve_or_refuse

logger = logging.getLogger("ai_cdp.tools.brand")


def analyze_brand_tool(url: str, save_to_ontology: bool = True) -> Dict[str, Any]:
    """
    Analyze a brand website to extract brand identity and automatically save it to ontology.

    This tool crawls the brand website using a headless browser and uses Gemini AI to extract:
    - Brand name (English and Chinese)
    - Industry, niche, and target audience
    - Core value, key products, and summary
    - Visual style (colors, font, vibe)
    - Marketing keywords, hot products, and promotion slogans

    The brand is automatically saved to ontology as a new entity (e.g., Brand_Apple).

    Args:
        url: The brand website URL to analyze (e.g., 'https://www.apple.com/')
        save_to_ontology: Whether to save the brand as an ontology entity (default: True)

    Returns:
        Brand analysis with brand_name, brand_type, description, visual_style, marketing info.
        If saved, includes entity_id (e.g., 'Brand_Apple').
        On error_type 'service_not_configured', tell the user which integration
        an admin must set up (Settings → Integrations) — do not retry.
    """
    try:
        creds, refusal = resolve_or_refuse("analyze_brand_tool", "gemini")
        if refusal:
            return refusal

        from services.brand_service import apply_ontology_save
        from tools.brand_analyzer import analyze_brand_sync

        logger.info("Analyzing brand from: %s", url)
        result = analyze_brand_sync(url, api_key=creds.get("api_key"))

        if save_to_ontology:
            result = apply_ontology_save(result)
        return result

    except ImportError as e:
        return {
            "success": False,
            "error": f"Brand analyzer dependencies not installed. Run: pip install playwright beautifulsoup4 && playwright install chromium. Error: {e}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to analyze brand: {e}"
        }
