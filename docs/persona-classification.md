# Persona Classification System — Architecture & Implementation Guide

## Overview

The Persona Classification module classifies user content (social media posts, browsing behavior, product interests) against a **Jungian archetype taxonomy** using **Vertex AI Vector Search 2.0** and **Google ADK**.

Two classification modes:

| Mode | Engine | Token Usage | Use Case |
|------|--------|-------------|----------|
| **Fast** | Vector search + weighted scoring | Zero LLM tokens | Real-time tagging, batch processing |
| **Advanced** | ADK LlmAgent with tool-calling | ~2K tokens/request | Detailed analysis with reasoning |

---

## Architecture

```
                          ┌─────────────────────────────┐
                          │       FastAPI Server         │
                          │       (server.py)            │
                          └──────┬───────────┬──────────┘
                                 │           │
                    ┌────────────┘           └────────────┐
                    ▼                                     ▼
         ┌──────────────────┐                  ┌──────────────────┐
         │   Fast Mode      │                  │  Advanced Mode   │
         │   search.py      │                  │  agent.py        │
         └────────┬─────────┘                  └────────┬─────────┘
                  │                                     │
                  │                              ┌──────┴──────┐
                  │                              │ agent_tools  │
                  │                              │  .py         │
                  │                              └──────┬──────┘
                  │                                     │
                  └──────────────┬───────────────────────┘
                                 ▼
                     ┌───────────────────────┐
                     │    vector_store.py     │
                     │  (VS2.0 Client Layer) │
                     └───────────┬───────────┘
                                 │
                                 ▼
                     ┌───────────────────────┐
                     │  Vertex AI Vector     │
                     │  Search 2.0 (GCP)     │
                     │                       │
                     │  Collection:           │
                     │  jungian-persona-      │
                     │  taxonomy              │
                     │  (4,368 entries)       │
                     └───────────────────────┘
```

---

## Module Structure

```
backend/persona/
├── __init__.py          # Module exports
├── schemas.py           # Pydantic models (ArchetypeScore, MatchDetail, etc.)
├── vector_store.py      # VS2.0 client: collection CRUD, search, ingestion
├── ingestion.py         # CSV → VS2.0 pipeline (CLI tool)
├── enrich_taxonomy.py   # LLM-generated archetype-specific sentences (CLI tool)
├── search.py            # Fast mode: vector search + weighted scoring + softmax
├── agent.py             # Advanced mode: ADK LlmAgent definition
└── agent_tools.py       # ADK tool functions (wraps search.py)
```

---

## Data: Jungian Persona Taxonomy

### Structure

12 Jungian archetypes × 28 product categories = 336 unique pairs.

Each pair has:
- **8 keywords** (generic terms like "3C電子產品推薦")
- **2 original sentences** (short descriptions)
- **3 enriched sentences** (archetype-specific, LLM-generated)

**Total: 4,368 entries** (3,360 original + 1,008 enriched)

### 12 Archetypes

| Archetype | Chinese | Core Trait |
|-----------|---------|------------|
| Ruler | 統治者 | Authority, premium quality |
| Caregiver | 照顧者 | Nurturing, family-oriented |
| Creator | 創造者 | Innovation, self-expression |
| Everyman | 凡人 | Practicality, affordability |
| Explorer | 探險家 | Freedom, discovery |
| Hero | 英雄 | Achievement, performance |
| Innocent | 天真者 | Simplicity, trust |
| Jester | 弄臣 | Joy, humor |
| Lover | 情人 | Passion, aesthetics |
| Magician | 魔法師 | Transformation, technology |
| Outlaw | 叛逆者 | Rebellion, distinctiveness |
| Sage | 智者 | Research, expertise |

### 8 Product Categories

3C電子產品, 一般食品與飲品, 人文與社會, 健康與保健, 售票活動, 寵物, 日用品, 線上社群服務

### CSV Schema

```
source, main_class, sub_class, relation, keyword, id, llm_threshold, type, percentage
```

| Column | Description |
|--------|-------------|
| `main_class` | Product category (e.g., "3C電子產品") |
| `sub_class` | Archetype (e.g., "jungian-ruler") |
| `relation` | Relevance weight (0.0–1.0) |
| `keyword` | The text to embed (keyword or sentence) |
| `type` | "keyword" or "sentence" |
| `percentage` | Category distribution weight per archetype |

---

## Vector Search 2.0 Setup

### Collection Schema

```python
# Auto-embedding: VS2.0 generates embeddings at write time
VECTOR_SCHEMA = {
    "keyword_embedding": {
        "dense_vector": {
            "dimensions": 768,
            "vertex_embedding_config": {
                "model_id": "gemini-embedding-001",
                "text_template": "{keyword}",
                "task_type": "RETRIEVAL_DOCUMENT"  # Index-time task type
            }
        }
    }
}
```

At search time, `task_type: "QUESTION_ANSWERING"` is used — this asymmetric pairing is recommended by Google for retrieval workloads.

### GCP Requirements

1. **API**: Enable `vectorsearch.googleapis.com` (separate from Vertex AI API)
2. **IAM**: Service account needs `roles/vectorsearch.admin`
3. **Env vars**:
   ```
   GCP_PROJECT_ID=your-project
   GCP_LOCATION=us-central1
   GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account-key.json
   ```

---

## Data Pipeline

### 1. Enrichment (one-time)

Generate archetype-specific sentences that create **distinct embeddings** per archetype:

```bash
# Requires GEMINI_API_KEY env var
python -m backend.persona.enrich_taxonomy
```

This produces `docs/jungian_product_semantic_v4_enriched.csv` with 1,008 new entries.

**Why enrichment matters**: Generic keywords like "3C電子產品推薦" have identical embeddings for all 12 archetypes. Enriched sentences like:
- Ruler: "我只選擇頂級品牌的3C產品，因為品質代表我的品味和地位"
- Explorer: "我喜歡嘗試最新的3C科技產品，體驗前所未有的功能和創新"

...produce **different embeddings** that vector search can differentiate.

### 2. Ingestion

```bash
# Ingest enriched CSV into VS2.0
python -m backend.persona.ingestion --csv docs/jungian_product_semantic_v4_enriched.csv
```

Process:
1. Creates collection (if not exists) with auto-embedding config
2. Parses CSV into data objects with unique IDs
3. Batch upserts in groups of 100
4. VS2.0 auto-generates embeddings via `gemini-embedding-001`

---

## Fast Mode: Scoring Algorithm

### Pipeline

```
User Content
    │
    ▼
Hybrid Search (semantic + text, RRF)  ← top_k=50
    │
    ▼
Similarity Threshold Filter            ← drop < 0.90
    │
    ▼
Weighted Scoring                       ← per match
    │
    ▼
Aggregate by Archetype                 ← sum scores
    │
    ▼
Softmax Normalization                  ← temperature=0.5
    │
    ▼
Sorted ArchetypeScores
```

### Scoring Formula

```
weighted_score = similarity × relation × (percentage / 100) × type_boost
```

| Factor | Source | Range | Purpose |
|--------|--------|-------|---------|
| `similarity` | VS2.0 distance → `1 - distance` | 0.0–1.0 | Semantic relevance |
| `relation` | CSV column | 0.0–1.0 | Taxonomy weight |
| `percentage` | CSV column | 0–100 | Category distribution |
| `type_boost` | Entry type | sentence=2.0, keyword=1.0 | Reward distinctive matches |

### Softmax Normalization

Replaces naive max-normalization (`score / max_score`) which compresses tightly-clustered scores to ~1.0.

```python
def _softmax_normalize(raw_scores, temperature=0.5):
    max_s = max(raw_scores.values())
    exp_scores = {k: exp((v - max_s) / temperature) for k, v in raw_scores.items()}
    total = sum(exp_scores.values())
    return {k: v / total for k, v in exp_scores.items()}
```

- `temperature < 1.0` → sharper peaks (amplifies differences)
- `temperature = 0.5` → good default for 12-archetype classification

### Configuration Constants

```python
TYPE_BOOST = {"sentence": 2.0, "keyword": 1.0}
SIMILARITY_THRESHOLD = 0.90
SOFTMAX_TEMPERATURE = 0.5
```

---

## Advanced Mode: ADK Agent

Uses Google ADK `LlmAgent` (Gemini 2.5 Flash) with three tools:

| Tool | Purpose |
|------|---------|
| `persona_vector_search` | Search taxonomy, return scored archetypes |
| `persona_category_breakdown` | Analyze category distribution |
| `get_archetype_info` | Look up archetype traits and behavior |

### Agent Workflow

1. **Initial Classification** — call `persona_vector_search` with user content
2. **Category Analysis** — call `persona_category_breakdown` for interest areas
3. **Deep Dive** — if top archetypes are close, filter by category to disambiguate
4. **Synthesize** — produce detailed analysis with reasoning and marketing recommendations

### Output Format

```
Primary Archetype: [name] (Score: X.XX, Confidence: High/Medium/Low)
Secondary Archetypes: [list with scores]
Category Affinities: [top product categories]
Key Signals: [matched keywords/sentences]
Marketing Recommendations: [targeting advice]
```

---

## API Endpoints

### POST `/api/persona/classify`

Fast mode classification.

```json
// Request
{
  "content": "我最近在研究3C電子產品開箱評測",
  "top_k": 50,
  "category_filter": null
}

// Response
{
  "archetypes": [
    {"archetype": "jungian-sage", "score": 0.42, "match_count": 8, "category_breakdown": {...}},
    {"archetype": "jungian-ruler", "score": 0.15, ...}
  ],
  "top_matches": [
    {"archetype": "jungian-sage", "category": "3C電子產品", "matched_text": "...", "similarity": 0.95, ...}
  ],
  "content_analyzed": "...",
  "mode": "fast"
}
```

### POST `/api/persona/classify/batch`

Batch fast mode for multiple content items.

```json
{
  "contents": ["content1", "content2", ...],
  "top_k": 50
}
```

### POST `/api/persona/analyze`

Advanced mode with SSE streaming (returns LLM-generated analysis).

```json
{
  "content": "我最近在研究3C電子產品開箱評測",
  "session_id": "user-123"
}
```

### POST `/api/persona/taxonomy/reload`

Re-ingest taxonomy CSV into VS2.0 collection.

---

## DS-Agent Integration

The fast mode is also available as a tool within the DS-STAR orchestrator:

```python
# In revive_agent/agent_tools.py
def persona_classify_tool(content: str, category_filter: str = "") -> dict:
    """Classify content against Jungian persona taxonomy."""
    result = fast_persona_classify(content=content, ...)
    return result.model_dump()
```

This allows DS-Agent to use persona classification as part of larger data analysis workflows.

---

## Performance Results

After optimization (enrichment + softmax + type boost):

| Query | Top Archetype | Score | Spread (top/bottom) |
|-------|--------------|-------|---------------------|
| Family health content | Caregiver | 0.97 | 442x |
| Travel exploration | Explorer | 0.31 | 8x |
| Tech review research | Sage | ~0.4 | ~10x |

Before optimization, all archetypes scored ~1.0 (no differentiation).

---

## Setup Checklist

1. Enable `vectorsearch.googleapis.com` API in GCP console
2. Grant `roles/vectorsearch.admin` to your service account
3. Set environment variables:
   ```bash
   export GCP_PROJECT_ID=your-project
   export GCP_LOCATION=us-central1
   export GOOGLE_APPLICATION_CREDENTIALS=path/to/key.json
   export GEMINI_API_KEY=your-gemini-key  # for enrichment only
   ```
4. Run enrichment (one-time): `python -m backend.persona.enrich_taxonomy`
5. Run ingestion: `python -m backend.persona.ingestion --csv docs/jungian_product_semantic_v4_enriched.csv`
6. Start server: `python -m backend.server`
7. Test: `curl -X POST http://localhost:8000/api/persona/classify -H 'Content-Type: application/json' -d '{"content":"我喜歡研究最新的3C科技產品"}'`
