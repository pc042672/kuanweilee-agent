"""
Ingestion pipeline: Load Jungian persona taxonomy CSV into Vector Search 2.0.

Usage:
    python -m backend.persona.ingestion [--csv PATH] [--recreate]

The CSV is expected to have columns:
    source, main_class, sub_class, relation, keyword, id, llm_threshold, type, percentage
"""

import csv
import argparse
import logging
import re
from pathlib import Path
from typing import List, Dict, Any

from backend.persona.vector_store import create_collection, batch_upsert_data_objects

logger = logging.getLogger(__name__)

DEFAULT_CSV_PATH = Path(__file__).resolve().parent / "data" / "jungian_product_semantic_v4_with_percentage.csv"


def _sanitize_id(text: str) -> str:
    """Sanitize text for use as a data object ID."""
    return re.sub(r'[^a-zA-Z0-9_-]', '_', text)


def parse_csv(csv_path: str | Path) -> List[Dict[str, Any]]:
    """
    Parse the taxonomy CSV into data objects for VS2.0 ingestion.

    Returns list of dicts with 'data_object_id' and 'data' keys.
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    data_objects = []
    row_idx = 0

    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            main_class = row.get("main_class", "").strip()
            sub_class = row.get("sub_class", "").strip()
            keyword = row.get("keyword", "").strip()
            entry_type = row.get("type", "").strip()
            relation = row.get("relation", "0").strip()
            percentage = row.get("percentage", "0").strip()

            if not keyword or not sub_class or not main_class:
                continue

            # Generate unique ID using global row counter
            row_idx += 1
            data_object_id = f"{_sanitize_id(sub_class)}_{entry_type}_{row_idx}"

            data_objects.append({
                "data_object_id": data_object_id,
                "data": {
                    "keyword": keyword,
                    "main_class": main_class,
                    "sub_class": sub_class,
                    "entry_type": entry_type,
                    "relation": float(relation),
                    "percentage": float(percentage),
                }
            })

    return data_objects


def ingest(
    csv_path: str | Path = DEFAULT_CSV_PATH,
    project_id: str | None = None,
    location: str | None = None,
) -> int:
    """
    Full ingestion pipeline:
    1. Create collection (if not exists)
    2. Parse CSV
    3. Batch upsert into VS2.0

    project_id/location select the per-site GCP project (env fallback when omitted).
    Returns total number of objects ingested.
    """
    logger.info(f"Starting ingestion from: {csv_path}")

    # Step 1: Ensure collection exists
    collection_name = create_collection(project_id, location)
    logger.info(f"Using collection: {collection_name}")

    # Step 2: Parse CSV
    data_objects = parse_csv(csv_path)
    logger.info(f"Parsed {len(data_objects)} records from CSV")

    if not data_objects:
        logger.warning("No data objects to ingest")
        return 0

    # Step 3: Batch upsert
    total = batch_upsert_data_objects(
        data_objects, batch_size=100, project_id=project_id, location=location
    )
    logger.info(f"Ingestion complete: {total} objects upserted")

    return total


def main():
    parser = argparse.ArgumentParser(description="Ingest Jungian persona taxonomy into Vector Search 2.0")
    parser.add_argument("--csv", type=str, default=str(DEFAULT_CSV_PATH),
                        help="Path to the taxonomy CSV file")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    total = ingest(args.csv)
    print(f"\nDone! Ingested {total} records into Vector Search 2.0 collection.")


if __name__ == "__main__":
    main()
