# Graph RAG Optimization Proposal for AI-CDP

## Context

Analysis of the "Multimodal Graph RAG on Google Cloud" design doc against AI-CDP's existing architecture. This proposal identifies what to adopt, what to skip, and the implementation sequence.

## What You Already Have (Don't Rebuild)

| Capability | Your System | Doc's Proposal |
|---|---|---|
| **Graph schema** | v3 ontology: 3 node types, discriminated union, JSONB storage | Spanner Graph — overkill at 14 nodes |
| **Agent orchestration** | Google ADK + DS-STAR (3-agent loop) | ADK — same |
| **Extraction** | Rule-based (SQL, quiz scoring) | Gemini extraction — heavier |
| **Vector search** | Vertex AI Vector Search for persona taxonomy | Vertex AI — same |
| **Storage** | AlloyDB (JSONB) + Greenplum (analytics) | Spanner — unnecessary migration |

## What the Doc Gets Right

1. **Entity-centric, not document-centric** — the v3 ontology already does this
2. **Hybrid retrieval** — currently missing, high value
3. **Offline-first extraction** — rules are precomputed, good
4. **Versioning** — config versioning exists, but no embedding versioning

## What the Doc Over-Engineers

1. **Spanner Graph** — at 14-200 nodes, AlloyDB JSONB + in-memory traversal is fine. Spanner adds cost/complexity for no benefit.
2. **Full multimodal ingestion** — the CDP is structured data (transactions, profiles). Images/video are irrelevant.
3. **Memory Bank** — session state + AlloyDB config already handles user context. Vertex AI Memory Bank is for chat-style personalization not needed yet.

---

## 3 High-Value Changes (Ordered by ROI)

### 1. Add Ontology Embeddings (~1 week)

**Problem:** `get_ontology_tool()` dumps the entire ontology into the prompt. At 200+ nodes, this wastes tokens and degrades LLM reasoning.

**Solution:** Embed each ontology node, then retrieve only the relevant subgraph.

```
User: "find dormant members"
  -> embed query
  -> top-k similar nodes: [dormant_reactivation, purchase_frequency, recency_days]
  -> expand: follow segment.conditions -> referenced attributes
  -> expand: follow attribute.rules.sources -> datasource nodes
  -> inject only this 5-node subgraph into prompt (not all 200)
```

**Implementation:**
- Reuse existing Vertex AI Vector Search infrastructure (`backend/persona/vector_store.py`)
- Create a second collection `ontology-nodes` with node name + description + options as text
- Add `search_ontology_tool(query)` that returns top-k nodes + 1-hop expansion
- Replace the full-dump `format_ontology_for_prompt()` with focused subgraph serialization

This is the "Graph RAG Lite" from the roadmap — dict-lookup traversal, no NetworkX needed.

### 2. Add DataSource Nodes to Ontology (~2 days)

**Problem:** Attributes reference `"datasource": "member_rfm"` but no DataSource nodes exist in ontology.json. The graph is incomplete — agents can't trace data lineage.

**Solution:** Define DataSource nodes for physical tables:

```json
"member_profile": {
  "type": "datasource",
  "name": "Member Profile",
  "table": "cdp.member_profile",
  "columns": {
    "gender_code": {"dataType": "STR", "description": "Gender code (01=Male, 02=Female)"},
    "birth_date": {"dataType": "DATE", "description": "Member birth date"}
  }
},
"member_rfm": {
  "type": "datasource",
  "name": "Member RFM",
  "table": "cdp.member_rfm",
  "columns": {
    "frequency_score": {"dataType": "NUM", "description": "Purchase frequency score"},
    "recency_days": {"dataType": "NUM", "description": "Days since last purchase"}
  }
}
```

**Why:** Enables the full traversal chain: Segment -> Attribute -> Rule -> DataSource -> SQL generation. Currently agents guess table names from schema exploration.

### 3. Hybrid Retrieval in Segment Discovery (~3 days)

**Problem:** `resolve_segments_tool` does exact-match evaluation only. If a user asks "find customers interested in outdoor activities," there's no semantic matching — the agent must already know the exact attribute keys.

**Solution:** Add a semantic pre-filter step:

```
User query -> embed
  -> vector search against attribute options (semanticDefinition field)
  -> map matched options back to attributes
  -> find segments whose conditions reference those attributes
  -> return candidate segments with relevance scores
```

This is the hybrid retrieval the doc describes: vector search narrows candidates, graph traversal expands context, exact rules filter results.

---

## What NOT to Do (From the Doc)

| Doc Suggestion | Why Skip It |
|---|---|
| Migrate to Spanner Graph | AlloyDB handles this scale. Revisit at 1000+ nodes |
| Multi-hop GQL queries | Dict-lookup chains work at 200 nodes |
| Vertex AI Memory Bank | AlloyDB session/config storage suffices |
| Full multimodal ingestion | Data is structured tables, not images/video |
| Evaluation framework (Phase 3) | Premature — get hybrid retrieval working first |

---

## Implementation Sequence

### Week 1: DataSource nodes + ontology embeddings
- Define DataSource nodes in ontology.json
- Create ontology embedding collection in Vertex AI
- Add `search_ontology_tool(query)` with 1-hop expansion

### Week 2: Graph-aware agent prompts
- Replace full-dump `format_ontology_for_prompt()` with subgraph injection
- Update DS-Agent instruction: "search ontology first, then plan"
- Measure token reduction + response quality

### Week 3: Hybrid segment discovery
- Semantic search over attribute options
- Graph expansion from matched attributes -> segments
- Agent can now discover segments by natural language

---

## Key Files

| File | Role |
|---|---|
| `backend/config/schemas.py` | v3 ontology models (DataSourceNode, AttributeNode, SegmentNode) |
| `backend/config/loader.py` | ConfigManager + `format_ontology_for_prompt()` (to be replaced) |
| `backend/config/scoring.py` | Shared scoring + segment evaluation |
| `backend/persona/vector_store.py` | Vertex AI Vector Search client (reuse for ontology embeddings) |
| `backend/revive_agent/tools/ontology_tools.py` | Agent tools (add `search_ontology_tool`) |
| `config/ontology.json` | Ontology data (add DataSource nodes) |

## Summary

This gets 80% of Graph RAG value with 20% of the doc's complexity, built on infrastructure already in place.
