"""
Vertex AI Vector Search 2.0 client wrapper for persona taxonomy.

Handles collection creation, data ingestion, and semantic search
using the vectorsearch_v1beta API with auto-embeddings.
"""

import os
import logging
from typing import Optional, List, Dict, Any

from google.cloud import vectorsearch_v1beta
from google.api_core import exceptions as gcp_exceptions

logger = logging.getLogger(__name__)

# --- Configuration ---

PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "")
LOCATION = os.environ.get("GCP_LOCATION", "us-central1")
COLLECTION_NAME = os.environ.get("PERSONA_COLLECTION_NAME", "jungian-persona-taxonomy")

# --- Collection Schema ---

DATA_SCHEMA = {
    "type": "object",
    "properties": {
        "keyword": {"type": "string"},
        "main_class": {"type": "string"},
        "sub_class": {"type": "string"},
        "entry_type": {"type": "string"},
        "relation": {"type": "number"},
        "percentage": {"type": "number"},
    }
}

VECTOR_SCHEMA = {
    "keyword_embedding": {
        "dense_vector": {
            "dimensions": 768,
            "vertex_embedding_config": {
                "model_id": "gemini-embedding-001",
                "text_template": "{keyword}",
                "task_type": "RETRIEVAL_DOCUMENT"
            }
        }
    }
}

# --- Singleton Clients ---

_admin_client: Optional[vectorsearch_v1beta.VectorSearchServiceClient] = None
_data_client: Optional[vectorsearch_v1beta.DataObjectServiceClient] = None
_search_client: Optional[vectorsearch_v1beta.DataObjectSearchServiceClient] = None


def _get_parent(project_id: Optional[str] = None, location: Optional[str] = None) -> str:
    """Get the parent resource path (per-site override, env fallback)."""
    pid = project_id or PROJECT_ID
    if not pid:
        raise ValueError("GCP_PROJECT_ID environment variable is required")
    return f"projects/{pid}/locations/{location or LOCATION}"


def _get_collection_path(
    project_id: Optional[str] = None, location: Optional[str] = None
) -> str:
    """Get the full collection resource path."""
    return f"{_get_parent(project_id, location)}/collections/{COLLECTION_NAME}"


def get_admin_client() -> vectorsearch_v1beta.VectorSearchServiceClient:
    """Get or create the admin client (singleton)."""
    global _admin_client
    if _admin_client is None:
        _admin_client = vectorsearch_v1beta.VectorSearchServiceClient()
    return _admin_client


def get_data_client() -> vectorsearch_v1beta.DataObjectServiceClient:
    """Get or create the data object client (singleton)."""
    global _data_client
    if _data_client is None:
        _data_client = vectorsearch_v1beta.DataObjectServiceClient()
    return _data_client


def get_search_client() -> vectorsearch_v1beta.DataObjectSearchServiceClient:
    """Get or create the search client (singleton)."""
    global _search_client
    if _search_client is None:
        _search_client = vectorsearch_v1beta.DataObjectSearchServiceClient()
    return _search_client


def create_collection(
    project_id: Optional[str] = None, location: Optional[str] = None
) -> str:
    """
    Create the persona taxonomy collection with auto-embedding config.
    Returns the collection resource name.
    Skips if collection already exists.
    """
    admin_client = get_admin_client()
    collection_path = _get_collection_path(project_id, location)

    # Check if collection exists
    try:
        existing = admin_client.get_collection(name=collection_path)
        logger.info(f"Collection already exists: {existing.name}")
        return existing.name
    except gcp_exceptions.NotFound:
        pass

    logger.info(f"Creating collection: {COLLECTION_NAME}")
    collection_config = {
        "data_schema": DATA_SCHEMA,
        "vector_schema": VECTOR_SCHEMA,
    }

    request = vectorsearch_v1beta.CreateCollectionRequest(
        parent=_get_parent(project_id, location),
        collection_id=COLLECTION_NAME,
        collection=collection_config,
    )
    operation = admin_client.create_collection(request=request)
    result = operation.result()
    logger.info(f"Collection created: {result.name}")
    return result.name


def batch_upsert_data_objects(
    data_objects: List[Dict[str, Any]],
    batch_size: int = 100,
    project_id: Optional[str] = None,
    location: Optional[str] = None,
) -> int:
    """
    Batch upsert data objects into the collection.
    VS2.0 auto-generates embeddings via the configured vertex_embedding_config.

    Args:
        data_objects: List of dicts with 'data_object_id' and 'data' keys
        batch_size: Max objects per batch (VS2.0 limit varies by embedding model)
        project_id: Per-site GCP project (env fallback when omitted)
        location: Per-site GCP location (env fallback when omitted)

    Returns:
        Total number of objects upserted
    """
    data_client = get_data_client()
    collection_path = _get_collection_path(project_id, location)
    total = 0

    for i in range(0, len(data_objects), batch_size):
        batch = data_objects[i:i + batch_size]
        requests = []
        for obj in batch:
            requests.append({
                "data_object_id": obj["data_object_id"],
                "data_object": {
                    "data": obj["data"],
                    "vectors": {}  # Empty = triggers auto-embedding
                }
            })

        request = vectorsearch_v1beta.BatchCreateDataObjectsRequest(
            parent=collection_path,
            requests=requests,
        )
        try:
            data_client.batch_create_data_objects(request=request)
            total += len(batch)
            logger.info(f"Upserted batch {i // batch_size + 1}: {len(batch)} objects (total: {total})")
        except Exception as e:
            logger.error(f"Failed to upsert batch {i // batch_size + 1}: {e}")
            raise

    return total


def semantic_search(
    query: str,
    top_k: int = 20,
    filter_dict: Optional[Dict[str, Any]] = None,
    project_id: Optional[str] = None,
    location: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Perform semantic search against the persona taxonomy collection.

    Args:
        query: Natural language text to search for
        top_k: Number of results to return
        filter_dict: Optional metadata filter (MongoDB-style operators)
        project_id: Per-site GCP project (env fallback when omitted)
        location: Per-site GCP location (env fallback when omitted)

    Returns:
        List of matched data objects with similarity scores
    """
    search_client = get_search_client()
    collection_path = _get_collection_path(project_id, location)

    search_kwargs = {
        "search_text": query,
        "search_field": "keyword_embedding",
        "task_type": "QUESTION_ANSWERING",
        "top_k": top_k,
        "output_fields": vectorsearch_v1beta.OutputFields(
            data_fields=["keyword", "main_class", "sub_class", "entry_type", "relation", "percentage"]
        ),
    }
    if filter_dict:
        search_kwargs["filter"] = filter_dict

    semantic = vectorsearch_v1beta.SemanticSearch(**search_kwargs)

    request = vectorsearch_v1beta.BatchSearchDataObjectsRequest(
        parent=collection_path,
        searches=[vectorsearch_v1beta.Search(semantic_search=semantic)],
    )

    response = search_client.batch_search_data_objects(request=request)
    return _parse_search_response(response)


def _parse_search_response(response) -> List[Dict[str, Any]]:
    """Parse VS2.0 search response into a flat list of dicts."""
    results = []
    if response.results:
        for res in response.results[0].results:
            data = res.data_object.data  # MapComposite, supports .get()
            # VS2.0 returns 'distance' (lower = more similar)
            # Convert to similarity: 1 - distance (capped at 0-1)
            similarity = max(0.0, 1.0 - res.distance)
            results.append({
                "similarity": round(similarity, 4),
                "keyword": data.get("keyword", ""),
                "main_class": data.get("main_class", ""),
                "sub_class": data.get("sub_class", ""),
                "entry_type": data.get("entry_type", ""),
                "relation": float(data.get("relation", 0)),
                "percentage": float(data.get("percentage", 0)),
            })
    return results


def hybrid_search(
    query: str,
    top_k: int = 20,
    filter_dict: Optional[Dict[str, Any]] = None,
    semantic_weight: float = 0.6,
    text_weight: float = 0.4,
    project_id: Optional[str] = None,
    location: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Perform hybrid search (semantic + text) with RRF ranking.

    Args:
        query: Natural language text to search for
        top_k: Number of results to return
        filter_dict: Optional metadata filter
        semantic_weight: Weight for semantic search in RRF
        text_weight: Weight for text search in RRF
        project_id: Per-site GCP project (env fallback when omitted)
        location: Per-site GCP location (env fallback when omitted)

    Returns:
        List of matched data objects with combined scores
    """
    search_client = get_search_client()
    collection_path = _get_collection_path(project_id, location)

    output_fields = vectorsearch_v1beta.OutputFields(
        data_fields=["keyword", "main_class", "sub_class", "entry_type", "relation", "percentage"]
    )

    semantic_kwargs = {
        "search_text": query,
        "search_field": "keyword_embedding",
        "task_type": "QUESTION_ANSWERING",
        "top_k": top_k,
        "output_fields": output_fields,
    }
    if filter_dict:
        semantic_kwargs["filter"] = filter_dict

    text_kwargs = {
        "search_text": query,
        "data_field_names": ["keyword"],
        "top_k": top_k,
        "output_fields": output_fields,
    }
    if filter_dict:
        text_kwargs["filter"] = filter_dict

    semantic = vectorsearch_v1beta.SemanticSearch(**semantic_kwargs)

    text = vectorsearch_v1beta.TextSearch(**text_kwargs
    )

    request = vectorsearch_v1beta.BatchSearchDataObjectsRequest(
        parent=collection_path,
        searches=[
            vectorsearch_v1beta.Search(semantic_search=semantic),
            vectorsearch_v1beta.Search(text_search=text),
        ],
        combine=vectorsearch_v1beta.BatchSearchDataObjectsRequest.CombineResultsOptions(
            ranker=vectorsearch_v1beta.Ranker(
                rrf=vectorsearch_v1beta.ReciprocalRankFusion(
                    weights=[semantic_weight, text_weight]
                )
            )
        ),
    )

    response = search_client.batch_search_data_objects(request=request)
    return _parse_search_response(response)
