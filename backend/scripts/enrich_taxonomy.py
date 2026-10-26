"""
Enrich Jungian persona taxonomy with archetype-specific sentences via Gemini.

Generates 3 unique sentences per (archetype, category) pair that describe
HOW that specific persona type engages with that product category.

Usage:
    python -m backend.scripts.enrich_taxonomy [--output PATH] [--batch-size N]
"""

import os
import csv
import json
import time
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Any

import google.generativeai as genai

logger = logging.getLogger(__name__)

# Data files live alongside the persona module
_PERSONA_DATA_DIR = Path(__file__).resolve().parent.parent / "persona" / "data"
DEFAULT_CSV = _PERSONA_DATA_DIR / "jungian_product_semantic_v4_with_percentage.csv"
DEFAULT_OUTPUT = _PERSONA_DATA_DIR / "jungian_product_semantic_v4_enriched.csv"

# --- Archetype Descriptions for Prompt ---

ARCHETYPE_TRAITS = {
    "jungian-ruler": "領導力、權威、掌控、品質至上、追求頂級",
    "jungian-caregiver": "關懷、保護、照顧家人、重視安全與健康",
    "jungian-creator": "創新、自我表達、設計美感、獨特品味",
    "jungian-everyman": "實用、親民、性價比、日常需求、大眾認同",
    "jungian-explorer": "冒險、探索新事物、自由、追求新體驗",
    "jungian-hero": "挑戰自我、追求卓越、成就感、突破極限",
    "jungian-innocent": "純真、簡單、信任品牌、追求幸福與美好",
    "jungian-jester": "樂趣、幽默、享受當下、追求歡樂體驗",
    "jungian-lover": "感官享受、美學品味、浪漫、追求極致體驗",
    "jungian-magician": "變革、科技創新、未來趨勢、神奇體驗",
    "jungian-outlaw": "叛逆、打破常規、獨樹一幟、不隨波逐流",
    "jungian-sage": "深度研究、理性分析、專業知識、數據驅動決策",
}

PROMPT_TEMPLATE = """你是一個消費者行為分析專家。請為以下榮格人格原型與產品類別組合，生成3句獨特的中文句子。

每句話必須：
1. 以第一人稱「我」開頭
2. 明確表達該人格原型的獨特消費動機和態度（不能是通用描述）
3. 自然融入產品類別
4. 每句話的語義必須有明顯區別

人格原型: {archetype_name}
原型特質: {traits}
產品類別: {category}

請直接輸出3句話，每行一句，不要編號、不要其他說明文字。"""


def get_unique_pairs(csv_path: Path) -> List[Dict[str, Any]]:
    """Extract unique (archetype, category) pairs with their percentage from CSV."""
    pairs = {}
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row["sub_class"].strip(), row["main_class"].strip())
            if key not in pairs:
                pairs[key] = {
                    "sub_class": row["sub_class"].strip(),
                    "main_class": row["main_class"].strip(),
                    "percentage": float(row.get("percentage", "0").strip()),
                }
    return list(pairs.values())


def generate_sentences(
    archetype: str,
    category: str,
    model: genai.GenerativeModel,
) -> List[str]:
    """Generate 3 archetype-specific sentences for a (archetype, category) pair."""
    traits = ARCHETYPE_TRAITS.get(archetype, "")
    archetype_name = archetype.replace("jungian-", "").capitalize()

    prompt = PROMPT_TEMPLATE.format(
        archetype_name=archetype_name,
        traits=traits,
        category=category,
    )

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        sentences = [s.strip() for s in text.split("\n") if s.strip()]
        # Take first 3 valid sentences
        return sentences[:3]
    except Exception as e:
        logger.error(f"Failed to generate for {archetype}/{category}: {e}")
        return []


def enrich(
    csv_path: Path = DEFAULT_CSV,
    output_path: Path = DEFAULT_OUTPUT,
    batch_size: int = 10,
    sentences_per_pair: int = 3,
) -> int:
    """
    Enrich taxonomy with archetype-specific sentences.

    1. Read original CSV
    2. Extract unique (archetype, category) pairs
    3. Generate sentences via Gemini for each pair
    4. Write enriched CSV (original + new sentences)

    Returns total new sentences generated.
    """
    # Configure Gemini
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is required")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    # Read original data
    original_rows = []
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            original_rows.append(row)

    logger.info(f"Original CSV: {len(original_rows)} rows")

    # Get unique pairs
    pairs = get_unique_pairs(csv_path)
    logger.info(f"Unique (archetype, category) pairs: {len(pairs)}")

    # Generate enriched sentences
    new_rows = []
    total_generated = 0

    for i, pair in enumerate(pairs):
        archetype = pair["sub_class"]
        category = pair["main_class"]
        percentage = pair["percentage"]

        sentences = generate_sentences(archetype, category, model)

        for j, sentence in enumerate(sentences):
            relation_weights = [1.0, 0.95, 0.90]
            new_rows.append({
                "source": "enriched_v1",
                "main_class": category,
                "sub_class": archetype,
                "relation": str(relation_weights[j] if j < len(relation_weights) else 0.90),
                "keyword": sentence,
                "id": "6000",  # Enriched entries use id 6000
                "llm_threshold": "N/A",
                "type": "sentence",
                "percentage": str(percentage),
            })
            total_generated += 1

        if (i + 1) % batch_size == 0:
            logger.info(f"  Progress: {i + 1}/{len(pairs)} pairs, {total_generated} sentences generated")
            time.sleep(0.5)  # Rate limiting

    logger.info(f"Generated {total_generated} new sentences")

    # Write enriched CSV
    all_rows = original_rows + new_rows
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    logger.info(f"Enriched CSV written to: {output_path} ({len(all_rows)} total rows)")
    return total_generated


def main():
    parser = argparse.ArgumentParser(description="Enrich Jungian persona taxonomy with archetype-specific sentences")
    parser.add_argument("--csv", type=str, default=str(DEFAULT_CSV), help="Input CSV path")
    parser.add_argument("--output", type=str, default=str(DEFAULT_OUTPUT), help="Output enriched CSV path")
    parser.add_argument("--batch-size", type=int, default=10, help="Log progress every N pairs")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    total = enrich(
        csv_path=Path(args.csv),
        output_path=Path(args.output),
        batch_size=args.batch_size,
    )
    print(f"\nDone! Generated {total} enriched sentences.")


if __name__ == "__main__":
    main()
