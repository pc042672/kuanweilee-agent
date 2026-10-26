"""Pydantic models for persona classification results."""

from typing import Dict, List, Optional
from pydantic import BaseModel


class ArchetypeScore(BaseModel):
    """Aggregated score for a single Jungian archetype."""
    archetype: str          # e.g. "jungian-ruler"
    score: float            # Normalized 0-1
    category_breakdown: Dict[str, float] = {}  # main_class -> contribution
    match_count: int = 0


class MatchDetail(BaseModel):
    """A single match from vector search."""
    archetype: str          # sub_class
    category: str           # main_class
    matched_text: str       # keyword/sentence that matched
    similarity: float       # Raw cosine similarity
    weighted_score: float   # similarity * relation * (percentage / 100)
    entry_type: str         # "keyword" or "sentence"
    relation: float         # Original relation weight
    percentage: float       # Category distribution weight


class PersonaSearchResult(BaseModel):
    """Result from persona classification."""
    archetypes: List[ArchetypeScore]
    top_matches: List[MatchDetail]
    content_analyzed: str
    mode: str = "fast"      # "fast" or "advanced"


class PersonaAnalysis(BaseModel):
    """Detailed analysis from advanced (agentic) mode."""
    primary_archetype: ArchetypeScore
    secondary_archetypes: List[ArchetypeScore] = []
    category_affinities: List[Dict[str, float]] = []
    reasoning: str = ""
    confidence: str = "medium"  # "high", "medium", "low"
    mode: str = "advanced"


# --- API Request/Response Models ---

class PersonaClassifyRequest(BaseModel):
    """Request for fast persona classification."""
    content: str
    top_k: int = 20
    category_filter: Optional[str] = None

class PersonaBatchClassifyRequest(BaseModel):
    """Request for batch persona classification."""
    contents: List[str]
    top_k: int = 20
    category_filter: Optional[str] = None

class PersonaAnalyzeRequest(BaseModel):
    """Request for advanced persona analysis."""
    content: str
    session_id: str = "default"
