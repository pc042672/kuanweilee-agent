# dac_dev Ontology Proposal — tenant siteid 122

Status: **proposal** — files are in `config/sites/dac_dev/`; nothing has been loaded
into the app database. (An earlier all-tenant draft was loaded into Cloud SQL
site 1 on 2026-09-26; loading these files replaces it.)

## Why

The shipped `config/ontology.json` is sample data that points at
`cdp.member_profile` / `cdp.member_rfm`. Greenplum `dac_dev` has no `cdp`
schema, so every generated query failed `table_not_found`, and the allowlist
blocked the agent's attempts to use the real tables.

## Tenant model

`report.*` tables are multi-tenant, keyed by `siteid` (`data.icem_item` uses
`site_id`). This app site maps to **GP siteid 122**. Member tables join on
`(siteid, uid)`. `dac.dac_taxonomy` is shared reference data (no tenant column).

## Data sources (the SQL allowlist)

| Key | Table | Notes |
|---|---|---|
| `member_profile` | `report.smb_member_info` | 34,777 members for 122; one row per member with latest-order snapshot (2019-03 → 2023-07). PII columns omitted |
| `member_rfm` | `report.smb_rfm_result` | 52,239 rows for 122, 45,700 RFM-scored; snapshot 2026-01-15, last purchase 2025-08-11 |
| `dac_taxonomy` | `dac.dac_taxonomy` | 11,484 labels; shared |

Excluded for 122 (no rows): `report.smb_abandon_list` (siteid 141 only),
`data.icem_item` (site_id 141 only).

## RFM semantics (derived from the data)

- `segment` 1–8 = R/F/M high/low combination (1=HHH … 8=LLL); 0 = no purchases.
- R high ⇔ `recency` ≤ 244 days; F high ⇔ `frequency` (visits/year) > 1;
  M high ⇔ `avg_amount` ≥ 1660.

## Attributes

| Attribute | Source | Buckets (siteid 122 counts) |
|---|---|---|
| 消費行為-購買力等級 | `avg_amount` quintiles 317 / 999 / 1330 / 1525.68 | 1: 9,036 · 2: 5,614 · 3: 12,224 · 4: 9,686 · 5: 9,140 (uneven 2/3 from price-point ties) |
| 消費行為-購買頻率 | `frequency` | HIGH ≥ 2.67 (top 10%): 4,542 · MEDIUM > 1: 5,837 · LOW: 35,321 |
| 消費行為-活躍狀態 (new) | `recency` | ACTIVE ≤ 180: 203 · COOLING ≤ 365: 1,428 · AT_RISK ≤ 730: 9,870 · DORMANT: 34,199 |
| 消費行為-RFM分群 (new) | `segment` | 1: 35 · 3: 1,149 · 4: 3,175 · 7: 8,861 · 8: 31,943 · others < 350 |
| 消費行為-最近購買天數 | `recency` | raw days |

Recency moved out of 購買頻率 into 活躍狀態: with stale data (no purchase in
the last 90 days for anyone), a 365-day "dormant" rule would label 96% of
members dormant and hide the frequency signal.

**Deprecated for 122** (hidden from the agent, kept because strategies
reference them): 性別, 年齡區間 (no source column), 居住城市, 會員等級 (NULL for
every 122 member); segments `high_value_female`, `young_high_spender`.

## Segments

| Segment | Definition | Size |
|---|---|---|
| `dormant_reactivation` | 活躍狀態 = DORMANT (730+ days) | 34,199 |
| `active_customers` (new) | 活躍狀態 IN (ACTIVE, COOLING) | 1,631 |
| `high_purchasing_power` (new) | 購買力等級 ≥ 4 | 18,826 |
| `rfm_champions` (new) | RFM 1 | 35 |
| `rfm_at_risk_high_value` (new) | RFM 3 | 1,149 |
| `rfm_lapsed_big_spenders` (new) | RFM 4 | 3,175 |

Archetype quiz attribute and campaign segments are unchanged.

## Enforcement gaps (proposed code changes — not implemented)

The ontology can only *tell* the agent to filter `siteid = 122` and avoid PII
columns; today nothing enforces either. `dbtoolbox/policy.py` checks tables
only. Proposed, following the plain-data `ParsedQuery` seam:

1. **Tenant scoping.** Add `tenantColumn: Optional[str]` to `DataSourceNode`
   and `tenant: {value: 122}` to the site config. `parse_query()` also
   extracts, per table reference, the equality predicates in `WHERE`/`ON`;
   the policy rejects any query touching a tenant-scoped table without
   `<alias>.siteid = 122` (fail-closed, `error_type="tenant_scope"`).
   Alternative: the query service wraps each tenant table in a
   `siteid = 122` subquery before execution.
2. **PII column denylist.** Add `deniedColumns: List[str]` to `DataSourceNode`
   (`Member_Name`, `Member_Email`, `Member_Phone`, `Account`, `address`,
   `store_address`). `parse_query()` extracts referenced columns; the policy
   rejects denied columns and `SELECT *` / `t.*` on tables with a denylist.
   The DB-side equivalent — a readonly role with column-level `GRANT`s, or a
   PII-free view — is stronger and should be the target for production.

Both belong in the policy layer, not the prompt, to meet the
financial-compliance bar (configurable, production-grade, fail-closed).

## Plans

`config/plans.json` `brand-analysis-workflow` SQL templates fixed to the
real columns (`dac_taxonomy`: `label_level_1/2`, `label`, `label_type`;
`icem_item`: `id`, `code`, `name`, plus `site_id` filter). Still open:
phases reference tools that do not exist (`map_brand_to_taxonomy_tool`,
`add_entity_tool`), and `data.icem_item` is not in this allowlist.

## Loading (when approved)

Save through `DbOntologyRepository.save(..., changed_by=<admin id>)` and
`DbRulesRepository.save(...)` so integrity is validated and the ontology
change is audit-logged; then roll a new Cloud Run revision (per-instance
config cache TTL is 1 hour).
