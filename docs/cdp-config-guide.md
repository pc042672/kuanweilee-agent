# CDP Configuration Guide — Ontology, Rules & Strategy

*Worked example: Abandoned-Cart Archetype Recovery*

This guide explains **every configurable component** of the AI-CDP semantic layer, how
to set it (UI · API · JSON), and walks the **Abandoned-Cart Archetype Recovery** use
case end to end. All examples match the live `config/*.json` and `/api/ontology/*` API.

---

## 1. Overview — three modules, one engine

The semantic layer is split into three concerns. Each is a separate config, edited on a
separate settings page, served by a separate API, and rules/strategies reference the
ontology **by key** (validated on save — a bad reference is rejected with HTTP 400).

| Module | Concern ("what") | Config file | UI page | API |
|---|---|---|---|---|
| **Ontology** | structure — datasources, attributes, segments | `config/ontology.json` | `/ontology` | `GET/PUT /api/ontology`, `…/nodes/*` |
| **Rules** | compute — how an attribute gets its value | `config/rules.json` | `/rules` | `GET/PUT /api/ontology/rules` |
| **Strategy** | action — the tune/message fired for a segment | `config/strategies.json` | `/strategies` | `GET/PUT /api/ontology/strategies` |

The **`OntologyEvaluator`** (`backend/config/scoring.py`) binds the three configs and is
**stateless** — it scores, matches, and resolves; it holds no per-user state (callers own
any running tally). Storage: JSON files in dev; AlloyDB `site_configs` rows
(`config_type` = `ontology` / `rules` / `strategies`) in production.

```
DataSource ──(ComputeRule.sources)──▶ Attribute ──(SegmentCondition.attribute)──▶ Segment ──(Strategy.segment)──▶ Strategy
   structure          compute (sql/quiz)        structure              match               action (tune/message)

scoring loop:  responses ─▶ score ─┐
               selection  ─▶ +1     ├─▶ aggregate ─▶ label ─▶ primary / secondary
               acceptance ─▶ +1    ─┘                 (caller owns the tally)
```

---

## 2. Component reference

For each component: **purpose · fields · how to set · seeded example · add-one recipe.**

### 2.1 DataSourceNode — a physical table/view

**Purpose:** declares a table the SQL agents may read and the columns rules can source.

**Fields** (`backend/config/schemas.py`):

| Field | Type | Notes |
|---|---|---|
| `type` | `"datasource"` | discriminator |
| `name` | str | display name |
| `table` | str | physical table, e.g. `cdp.member_profile` |
| `primaryKey` | str? | key column |
| `columns` | `{colName: ColumnDef}` | `ColumnDef{dataType, description, businessTerm}` (`dataType` ∈ STR/NUM/DATE/BOOL) |
| `status` | experimental\|active\|deprecated\|archived | default `active` |

**Set it:** UI `/ontology` → **Add Node** (type `datasource`) · API `POST /api/ontology/nodes/{key}`.

**Seeded example** (`member_rfm`):
```json
{
  "type": "datasource", "name": "Member RFM", "table": "cdp.member_rfm",
  "primaryKey": "member_id",
  "columns": {
    "member_id": {"dataType": "STR"},
    "purchase_level": {"dataType": "NUM"},
    "frequency_score": {"dataType": "NUM"}
  }
}
```

**Add one:**
```bash
curl -X POST localhost:8000/api/ontology/nodes/orders \
  -H 'Content-Type: application/json' \
  -d '{"type":"datasource","name":"Orders","table":"cdp.orders","primaryKey":"order_id","columns":{"order_id":{"dataType":"STR"},"item_code":{"dataType":"STR"}}}'
```

### 2.2 AttributeNode — a business attribute / its value domain

**Purpose:** a customer attribute (the "what"). Its **value domain** is `options`; its
**computation** lives in a ComputeRule (§2.4). A scored attribute (`isScored: true`) is one
whose value carries a confidence score (e.g. `archetype`).

**Fields:** `type:"attribute"`, `name`, `valueType` (STR/NUM/DATE/BOOL), `isMultiple` (bool),
`isScored` (bool), `options: [TaxonomyOptionConfig{name, value, semanticDefinition?, metadata?}]`.

**Set it:** UI `/ontology` → Add/Edit attribute (options shown as chips) · API `POST/PUT /api/ontology/nodes/{key}`; add an option via `POST /api/ontology/nodes/{key}/options`.

**Seeded example** (`archetype` — scored, 12 Jungian options):
```json
{
  "type": "attribute", "name": "archetype", "valueType": "STR",
  "isMultiple": true, "isScored": true,
  "options": [
    {"name": "Explorer", "value": "explorer",
     "semanticDefinition": "Driven by discovery and freedom. Seeks new experiences, variety, and adventure."},
    {"name": "Hero", "value": "hero", "semanticDefinition": "Driven by achievement and mastery…"}
    /* …sage, rebel, creator, caregiver, ruler, magician, lover, jester, innocent, everyman */
  ]
}
```

**Add one** (a scored attribute you will quiz on): create the attribute with its options,
then attach a quiz ComputeRule (§2.4).

### 2.3 SegmentNode — an audience definition

**Purpose:** a group of users matching conditions over attributes (the membership rule).

**Fields:** `type:"segment"`, `name`, `conditions: [SegmentCondition]`, `logic` (`ALL`|`ANY`),
`conditionExpression?`, `orderRules?`.
`SegmentCondition{attribute(FK), operator, value, secondValue?, minScore?}` —
operators: `EQUAL`, `NOT_EQUAL`, `>=`, `<=`, `BETWEEN` (+`secondValue`), `IN` (value = list).
`minScore` gates a **scored** attribute (e.g. archetype must score ≥ 2).

**Set it:** UI `/ontology` (segment cards show conditions + which strategies attach) · API nodes CRUD.

**Seeded example** (`explorer_campaign`):
```json
{
  "type": "segment", "name": "Explorer Campaign", "logic": "ALL",
  "conditions": [
    {"attribute": "archetype", "operator": "EQUAL", "value": "explorer", "minScore": 2.0}
  ]
}
```
Others: `high_value_female` (gender EQUAL 02 **AND** purchase-power ≥ 4), `dormant_reactivation`
(frequency EQUAL DORMANT), `young_high_spender` (age IN [18-24,25-34] **AND** power ≥ 3).

### 2.4 ComputeRule — how an attribute's value is produced

**Purpose:** the behavior that fills an attribute. Two live kinds:
- **`sql`** — carries a SQL expression + `sources` (datasource.column) as a **hint** the DE-Agent executes (the sidecar does not run SQL).
- **`quiz`** — an in-process questionnaire scored by the engine.

**Fields** (`backend/config/rules_schema.py`):
`attribute` (FK), `type` (`sql`|`quiz`|`labeling_rule`), `sources: [{datasource, column}]`,
`sql?`, `quiz?: QuizSectionConfig`, `valueMappings: [{name, value, semanticDefinition?}]`.

`QuizSectionConfig{ questions: [{id, text, options:[{id, text, mappings:{value:int}}]}], scoring: ScoringConfig }`
where `ScoringConfig{ primaryThreshold=2, secondaryThreshold=1, maxPrimary=1, maxSecondary=2 }`.
An option's `mappings` may award points to **multiple** values (e.g. `{"explorer":2,"sage":1}`).

**Set it:** UI `/rules` (cards per attribute; **Edit rules.json** for the full doc) · API `GET/PUT /api/ontology/rules` (replaces the whole `RulesConfig{version, site_id, computeRules[]}`).

**Seeded SQL rule** (frequency bucket):
```json
{ "attribute": "消費行為-購買頻率", "type": "sql",
  "sources": [{"datasource": "member_rfm", "column": "frequency_score"}],
  "sql": "CASE WHEN frequency_score >= 4 THEN 'HIGH' WHEN frequency_score >= 2 THEN 'MEDIUM' WHEN frequency_score >= 1 THEN 'LOW' ELSE 'DORMANT' END" }
```

**Seeded quiz rule** (archetype — 5 questions):
```json
{ "attribute": "archetype", "type": "quiz",
  "quiz": {
    "questions": [
      {"id": "q1", "text": "When faced with a new challenge, you prefer to:",
       "options": [
         {"id": "a", "text": "Explore all possibilities", "mappings": {"explorer": 2, "sage": 1}},
         {"id": "b", "text": "Take decisive action",     "mappings": {"hero": 2, "rebel": 1}}
         /* c, d … */
       ]}
       /* q2…q5 */
    ],
    "scoring": {"primaryThreshold": 3, "secondaryThreshold": 2, "maxPrimary": 1, "maxSecondary": 2}
  }
}
```

### 2.5 Strategy — the action/tune fired for a segment

**Purpose:** generalizes NBA/NBO. Each strategy is keyed by an arbitrary `key`
(`nba`, `nbo`, `next_channel`, …) and attaches to a segment. The `template` is the **how**
(brand voice); the **what** (the actual offering) is injected at call time via `context`.

**Fields** (`backend/config/strategies_schema.py`):
`key`, `name?`, `segment` (FK), `strategy?` (methodology id), `template?` (message with `{placeholders}`), `params: {…}` (free-form tune, e.g. `tone`, `incentive_format`).

**Set it:** UI `/strategies` (cards per `key@segment`; **Edit strategies.json**) · API `GET/PUT /api/ontology/strategies` (replaces `StrategiesConfig{version, site_id, strategies[]}`).

**Seeded examples** (explorer_campaign — nba + nbo):
```json
{"key": "nba", "name": "NBA", "segment": "explorer_campaign",
 "template": "Discover {offering}! Your next adventure awaits.", "params": {"tone": "adventurous"}}
{"key": "nbo", "name": "NBO", "segment": "explorer_campaign", "strategy": "strategic_discovery"}
```

**Add a custom strategy:**
```bash
# read, append to the array, then PUT the whole config
curl -s localhost:8000/api/ontology/strategies > s.json   # edit s.json, add:
# {"key":"next_channel","segment":"explorer_campaign","strategy":"email_first","params":{"channel":"email"}}
curl -X PUT localhost:8000/api/ontology/strategies -H 'Content-Type: application/json' -d @s.json
```

### 2.6 Scoring engine — score, accumulate, label, resolve

`OntologyEvaluator` (`backend/config/scoring.py`), all stateless:

| Method / function | Purpose |
|---|---|
| `score_quiz(attr, responses)` | one-shot: sum a quiz's `mappings`, threshold → primary/secondary |
| `ScoreContribution{source, points}` | a single scoring **signal** (source is a free tag; `points` = `{value: delta}`) |
| `aggregate(contributions)` | sum points per value across all signals |
| `label(scores, ScoringConfig, names)` | threshold a score map → primary/secondary |
| `label_scores(attr, contributions, scoring?)` | aggregate + label — the **multi-signal** entry (caller passes the full tally each call); optional `scoring` overrides the attribute's quiz thresholds |
| `evaluate_segment(seg, attrs)` | does a user match a segment? → `(bool, reasoning[])` |
| `resolve_strategy(seg, key, ctx)` | render a strategy template with `params + ctx` |
| `build_taxonomy_context(seg)` | semantic definitions for a segment's attributes (LLM context) |

---

## 3. Integrity & lifecycle

- **Referential integrity** (enforced on `PUT /rules` and `/strategies`, else HTTP 400):
  every `ComputeRule.attribute` and `Strategy.segment` must resolve to a node of the right
  type; every `SourceRef.datasource` must be a datasource. `audit_ontology_tool()` reports any drift.
- **Node status:** `experimental → active → deprecated → archived` (only `active` nodes are formatted into the LLM prompt).
- **Delete cascade:** `delete_node` blocks deleting an attribute referenced by a segment
  condition or a compute-rule source. ⚠️ It does **not yet** block deleting a segment that a
  strategy points to (an orphan-strategy gap — flagged for `/code-review`).

---

## 4. Worked example — Abandoned-Cart Archetype Recovery

The use case: identify a shopper's Jungian archetype via a short quiz, then deliver a
NBA/NBO offer tuned to that archetype, confirming the archetype through behavioral signals.
It maps onto the config exactly. (Outputs below are **real** responses from the seeded config.)

### Action 1 — Identify (quiz → archetype)

`archetype` attribute (§2.2) + its quiz ComputeRule (§2.4). Score the responses:

```bash
curl -X POST localhost:8000/api/ontology/nodes/archetype/score \
  -H 'Content-Type: application/json' \
  -d '{"responses": {"q1":"a","q2":"a","q3":"a","q4":"a","q5":"a"}}'
```
```json
{"attribute_key": "archetype",
 "primary":   [{"value": "explorer", "score": 7, "name": "Explorer"}],
 "secondary": [{"value": "jester", "score": 3, "name": "Jester"},
               {"value": "sage", "score": 2, "name": "Sage"}],
 "all_scores": {"explorer": 7, "jester": 3, "sage": 2, "ruler": 2, "innocent": 1}}
```
The **top-3 shortlist** the use case asks for = `primary` (maxPrimary=1) + `secondary` (maxSecondary=2).

### Action 2 — NBA (match segment, resolve tuned offer)

Find matching campaign segments, then resolve the `nba` strategy (the offering is injected via `context`):

```bash
curl -X POST localhost:8000/api/ontology/resolve-segments \
  -H 'Content-Type: application/json' -d '{"attributes": {"archetype": {"value":"explorer","score":5}}}'
```
```json
{"matched": [{"key": "explorer_campaign", "name": "Explorer Campaign",
   "reasoning": ["MATCH: 'archetype' EQUAL explorer"], "strategies": ["nba", "nbo"]}],
 "total_segments_evaluated": 4}
```
```bash
curl -X POST localhost:8000/api/ontology/resolve-strategy \
  -H 'Content-Type: application/json' \
  -d '{"segment_key":"explorer_campaign","strategy_key":"nba","context":{"offering":"20% off new arrivals"}}'
```
```json
{"key": "nba", "segment": "explorer_campaign",
 "template": "Discover {offering}! Your next adventure awaits.",
 "message":  "Discover 20% off new arrivals! Your next adventure awaits.",
 "params": {"tone": "adventurous"},
 "taxonomy_context": ["archetype: Driven by discovery and freedom. Seeks new experiences, variety, and adventure."]}
```
The shopper **selecting** this offer is a behavioral signal (+1 to `explorer`).

### Action 3 — NBO + progressive confirmation

Resolve the `nbo` strategy (`{"strategy_key":"nbo"}` → `"strategic_discovery"` negotiation style).
A successful deal is another signal (+1). The use case's **"score = 2 ⇒ primary"** is the
**multi-signal** path: the caller owns the running tally and asks the engine to aggregate +
label all signals (assessment + selection + acceptance):

```bash
curl -X POST localhost:8000/api/ontology/nodes/archetype/label \
  -H 'Content-Type: application/json' \
  -d '{"contributions": [
        {"source": "assessment", "points": {"explorer": 2, "sage": 1}},
        {"source": "selection",  "points": {"explorer": 1}},
        {"source": "acceptance", "points": {"explorer": 1}} ]}'
```
```json
{"attribute_key": "archetype",
 "primary":   [{"value": "explorer", "score": 4.0, "name": "Explorer"}],
 "secondary": [], "all_scores": {"explorer": 4.0, "sage": 1.0}}
```
The engine never stores the tally — your app (or the DS-Agent session) accumulates the
contributions and passes them all each call. Equivalent **agent tools**:
`score_tool` → `resolve_segments_tool` → `resolve_strategy_tool` → `label_scores_tool`.

**Threshold override.** By default `/label` uses the attribute's *quiz* `ScoringConfig`
(`primaryThreshold: 3`, tuned for point-sums). For a pure **behavioral-confirmation** model —
the docx's literal *"two confirmations (selection +1, acceptance +1) ⇒ primary at score 2"* —
pass an explicit `scoring` override so 2 clears the bar:
```bash
curl -X POST localhost:8000/api/ontology/nodes/archetype/label \
  -H 'Content-Type: application/json' \
  -d '{"contributions": [{"source": "selection",  "points": {"hero": 1}},
                         {"source": "acceptance", "points": {"hero": 1}}],
       "scoring": {"primaryThreshold": 2, "secondaryThreshold": 1, "maxPrimary": 1, "maxSecondary": 2}}'
# → primary: [{"value": "hero", "score": 2.0, "name": "Hero"}]   (without the override: primary [])
```
`label_scores_tool(attribute_key, contributions, scoring?)` takes the same optional override.

---

## 5. Extend it — recipes

| To add… | Do |
|---|---|
| **a datasource** | `POST /nodes/{key}` type `datasource` (§2.1) |
| **a scored attribute + quiz** | `POST /nodes/{key}` type `attribute` (`isScored:true`, options) → add a `quiz` ComputeRule via `PUT /rules` (§2.4) |
| **a segment** | `POST /nodes/{key}` type `segment` with conditions (use `minScore` to gate a scored attribute) |
| **a custom strategy** | append to `strategies` and `PUT /strategies` — any `key` (e.g. `next_channel`) |
| **a new scoring signal** | client-side: build a `ScoreContribution{source, points}` and include it in the `label` call — no schema change |

---

## 6. Gaps vs the use-case doc (honest mapping)

| Use-case concept | Where it lives now |
|---|---|
| Per-archetype **"incentive format"** | a `Strategy.params` field (free-form) |
| **Campaign-event trigger** (Abandoned Cart) | DS-STAR workflow plans (`config/plans.json`), **not** the ontology |
| **NYOP negotiation** execution | downstream/agent — the sidecar provides the `nbo` **tune** (`strategy` + `params`), not the negotiation engine |
| **Tie-break with behavioral data** | a generic `ScoreContribution` source (e.g. `"behavioral"`) the caller supplies into `label` |
| Per-archetype **tune library keyed by archetype** | currently keyed by **segment**; for per-archetype reuse, define one segment per archetype value (or a future attribute-value-keyed strategy) |

---

## 7. Quick reference

**Module ↔ surface**

| Module | File | UI | API |
|---|---|---|---|
| Ontology | `config/ontology.json` | `/ontology` | `GET/PUT /api/ontology` · `…/nodes/{key}` (POST/PUT/DELETE) · `…/nodes/{key}/options` |
| Rules | `config/rules.json` | `/rules` | `GET/PUT /api/ontology/rules` |
| Strategy | `config/strategies.json` | `/strategies` | `GET/PUT /api/ontology/strategies` |
| Scoring | — | `/rules`·`/strategies` Test tabs | `POST …/nodes/{key}/score` · `…/nodes/{key}/label` · `…/resolve-segments` · `…/resolve-strategy` |

**Segment operators:** `EQUAL`, `NOT_EQUAL`, `>=`, `<=`, `BETWEEN` (+`secondValue`), `IN` (list).

**ScoringConfig:** `primaryThreshold` (≥ for primary), `secondaryThreshold` (≥ for secondary),
`maxPrimary` (cap), `maxSecondary` (cap).

**Agent tools** (`backend/revive_agent/tools/ontology_tools.py`):
`get_ontology_tool`, `get_attribute_tool`, `score_tool`, `label_scores_tool`,
`resolve_segments_tool`, `resolve_strategy_tool`, `audit_ontology_tool`.
