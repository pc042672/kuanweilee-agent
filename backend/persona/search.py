"""
Fast mode persona classification using Vector Search 2.0.

Performs semantic search against the Jungian persona taxonomy,
applies weighted scoring with type boosting, and aggregates
results by archetype using softmax normalization.
"""

import math
import logging
from collections import defaultdict
from typing import Optional, List, Dict, Any

from backend.persona.vector_store import semantic_search, hybrid_search
from backend.persona.schemas import ArchetypeScore, MatchDetail, PersonaSearchResult

logger = logging.getLogger(__name__)

# --- Scoring Configuration ---

# Sentence matches are more semantically distinctive than keyword matches
TYPE_BOOST = {"sentence": 2.0, "keyword": 1.0}

# Minimum similarity threshold — drop noise from unrelated categories
SIMILARITY_THRESHOLD = 0.90

# Softmax temperature — lower = sharper differentiation (0.5 is a good start)
SOFTMAX_TEMPERATURE = 0.5


def _build_filter(category_filter: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Build a VS2.0 metadata filter dict."""
    if not category_filter:
        return None
    return {"main_class": {"$eq": category_filter}}


def _softmax_normalize(raw_scores: Dict[str, float], temperature: float = SOFTMAX_TEMPERATURE) -> Dict[str, float]:
    """
    Softmax normalization with temperature scaling.

    Unlike max-normalization (score/max), softmax amplifies differences
    in tightly clustered scores. Lower temperature = sharper peaks.
    """
    if not raw_scores:
        return {}

    max_s = max(raw_scores.values())
    exp_scores = {}
    for k, v in raw_scores.items():
        exp_scores[k] = math.exp((v - max_s) / temperature)

    total = sum(exp_scores.values())
    if total == 0:
        return {k: 0.0 for k in raw_scores}

    return {k: round(v / total, 4) for k, v in exp_scores.items()}


def _aggregate_by_archetype(matches: List[MatchDetail]) -> List[ArchetypeScore]:
    """
    Aggregate match details into per-archetype scores.

    Uses softmax normalization to amplify differences in tightly
    clustered scores, producing meaningful separation between archetypes.
    """
    archetype_data: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"total_score": 0.0, "categories": defaultdict(float), "count": 0}
    )

    for match in matches:
        entry = archetype_data[match.archetype]
        entry["total_score"] += match.weighted_score
        entry["categories"][match.category] += match.weighted_score
        entry["count"] += 1

    # Softmax normalization — amplifies small differences
    raw_scores = {k: d["total_score"] for k, d in archetype_data.items()}
    normalized = _softmax_normalize(raw_scores)

    archetypes = []
    for archetype, data in archetype_data.items():
        archetypes.append(ArchetypeScore(
            archetype=archetype,
            score=normalized.get(archetype, 0.0),
            category_breakdown={k: round(v, 4) for k, v in data["categories"].items()},
            match_count=data["count"],
        ))

    return sorted(archetypes, key=lambda x: x.score, reverse=True)


def fast_persona_classify(
    content: str,
    top_k: int = 50,
    category_filter: Optional[str] = None,
    use_hybrid: bool = True,
    similarity_threshold: float = SIMILARITY_THRESHOLD,
    project_id: Optional[str] = None,
    location: Optional[str] = None,
) -> PersonaSearchResult:
    """
    Fast mode: classify content against Jungian persona taxonomy.

    1. Semantic (or hybrid) search against VS2.0 collection
    2. Filter by similarity threshold
    3. Apply weighted scoring: similarity * relation * (percentage / 100) * type_boost
    4. Aggregate by archetype with softmax normalization
    5. Return sorted results

    Args:
        content: User content to classify
        top_k: Number of vector search results (default: 50 for archetype diversity)
        category_filter: Optional main_class to filter by
        use_hybrid: Use hybrid search (semantic + text) with RRF
        similarity_threshold: Minimum similarity to include (default: 0.90)
        project_id: Per-site GCP project (env fallback when omitted)
        location: Per-site GCP location (env fallback when omitted)

    Returns:
        PersonaSearchResult with archetypes and top matches
    """
    filter_dict = _build_filter(category_filter)

    # Step 1: Vector search
    search_fn = hybrid_search if use_hybrid else semantic_search
    raw_results = search_fn(
        content, top_k=top_k, filter_dict=filter_dict,
        project_id=project_id, location=location,
    )

    # Step 2: Filter by similarity threshold + weighted scoring
    matches = []
    for r in raw_results:
        similarity = r["similarity"]

        # Drop low-similarity noise
        if similarity < similarity_threshold:
            continue

        relation = r["relation"]
        percentage = r["percentage"]
        entry_type = r["entry_type"]
        type_boost = TYPE_BOOST.get(entry_type, 1.0)

        weighted_score = similarity * relation * (percentage / 100.0) * type_boost

        matches.append(MatchDetail(
            archetype=r["sub_class"],
            category=r["main_class"],
            matched_text=r["keyword"],
            similarity=round(similarity, 4),
            weighted_score=round(weighted_score, 4),
            entry_type=entry_type,
            relation=relation,
            percentage=percentage,
        ))

    # Step 3: Aggregate by archetype
    archetypes = _aggregate_by_archetype(matches)

    # Step 4: Return results
    return PersonaSearchResult(
        archetypes=archetypes,
        top_matches=sorted(matches, key=lambda x: x.weighted_score, reverse=True)[:10],
        content_analyzed=content,
        mode="fast",
    )
