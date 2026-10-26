"""Brand analysis ontology persistence — shared by the agent tool and the
/api/brand router (the crawl → Gemini step itself lives in tools/brand_analyzer.py)."""

import logging
from typing import Dict, Tuple

from config.schemas import ColumnDef, DataSourceNode

logger = logging.getLogger("ai_cdp.services.brand")

# Column definitions: (column, extractor(brand_data), business_term)
_BRAND_COLUMNS = [
    ("brand_name_en", lambda d: d.get("brand_name", {}).get("english", "Unknown"), "品牌英文名"),
    ("brand_name_zh", lambda d: d.get("brand_name", {}).get("chinese", ""), "品牌中文名"),
    ("industry", lambda d: d.get("brand_type", {}).get("industry", ""), "產業"),
    ("target_audience", lambda d: d.get("brand_type", {}).get("target_audience", ""), "目標受眾"),
    ("core_value", lambda d: d.get("description", {}).get("core_value", ""), "核心價值"),
    ("hot_keywords", lambda d: ", ".join(d.get("marketing", {}).get("hot_keywords", [])), "熱門關鍵字"),
    ("hot_products", lambda d: ", ".join(d.get("marketing", {}).get("hot_products", [])), "熱門產品"),
    ("promotion_slogans", lambda d: ", ".join(d.get("marketing", {}).get("promotion_slogans", [])), "促銷標語"),
    ("visual_colors", lambda d: ", ".join(d.get("visual_style", {}).get("colors", [])), "視覺顏色"),
    ("visual_vibe", lambda d: d.get("visual_style", {}).get("overall_vibe", ""), "視覺風格"),
]


def save_brand_to_ontology(brand_data: dict, cm=None) -> Tuple[str, bool]:
    """Save brand data as an ontology DataSource node. Returns (node_key, is_update)."""
    if cm is None:
        from revive_agent.tools._infra import get_config
        cm = get_config()

    brand_name = brand_data.get("brand_name", {})
    name_en = brand_name.get("english", "Unknown")
    node_key = f"Brand_{name_en.replace(' ', '_').replace('-', '_')}"

    columns = {
        col_name: ColumnDef(
            dataType="STR",
            description=str(extractor(brand_data))[:500],
            businessTerm=biz_term,
        )
        for col_name, extractor, biz_term in _BRAND_COLUMNS
    }

    node = DataSourceNode(
        name=f"Brand: {name_en}",
        table=f"brand_context.{node_key.lower()}",
        description=brand_data.get("description", {}).get("summary", f"Brand context for {name_en}"),
        primaryKey="brand_id",
        columns=columns,
    )

    try:
        cm.add_node(node_key, node)
        return node_key, False
    except ValueError:
        cm.update_node(node_key, node)
        return node_key, True


def apply_ontology_save(result: Dict, cm=None) -> Dict:
    """Annotate a successful analysis result with the ontology-save outcome.

    No-op on failed/empty analyses. Save failures are reported in-band
    (save_error) — the analysis itself succeeded and stays usable.
    """
    if not (result.get("success") and result.get("data")):
        return result
    try:
        entity_id, is_update = save_brand_to_ontology(result.get("data", {}), cm)
        result["saved_to_ontology"] = True
        result["entity_id"] = entity_id
        if is_update:
            result["updated"] = True
    except Exception as save_error:
        result["save_error"] = str(save_error)
    return result
