# Phase 4: Problem Detection, Root-Cause / Driver Analysis & Evidence

This document is the reference for everything Phase 4 added: issue-detection rules,
materiality thresholds, RCA/decomposition formulas, the contribution/residual methodology,
causation-language limitations, the Evidence model and lineage, the API, the UI, and which
analyses remain unavailable until later canonical tables exist.

**Governing principle:** Phase 4 is primarily FACT and CONTRIBUTION, not INFERENCE. Every
number here comes from a deterministic SQL aggregation against `fact_sales`, screened by a
configuration-driven materiality rule, and written down as an immutable Evidence row before
it ever reaches the API or UI. Nothing in `app/rca/` asks the LLM whether something is
material, and nothing here claims causation — see section 6.

## 1. Issue detection

`backend/app/rca/issues.py` registers 8 detector functions (`DETECTORS`), each a plain
function: resolve a period + comparison window, read a number (from Phase 3's KPI engine for
company-level metrics, or `app/kpi/aggregations.py` for per-dimension sums), and run it
through materiality (section 2).

| Issue type | Detector | Metric | Fires when |
|---|---|---|---|
| `revenue_decline` | `detect_revenue_decline` | revenue | company revenue falls YoY/QoQ/MoM |
| `revenue_growth_slowdown` | `detect_revenue_growth_slowdown` | revenue | still growing, but the growth *rate* decelerated vs. the prior comparable period |
| `margin_deterioration` | `detect_margin_deterioration` | gross_margin_pct | company gross margin % drops (point change) |
| `regional_performance_deterioration` | `detect_regional_performance_deterioration` | revenue | a region's own revenue declines |
| `product_margin_deterioration` | `detect_product_margin_deterioration` | gross_margin_pct | a product's own margin % drops (point change) |
| `unusual_cost_movement` | `detect_unusual_cost_movement` | cogs | COGS growth rate outpaces revenue growth rate |
| `unusual_volume_movement` | `detect_unusual_volume_movement` | sales_quantity | sales volume moves unusually (either direction) |
| `customer_concentration_change` | `detect_customer_concentration_change` | revenue_customer_concentration | top-5-customer revenue share shifts materially |

Two issue types from the spec's initial list — `material_inventory_issue`,
`overtime_issue` — exist **only as DB enum vocabulary** (`ISSUE_TYPES` in
`app/db/models/analysis.py`), with **no detector function**. Their canonical tables
(`fact_inventory`, `fact_workforce`) don't exist — Phase 2 materializes `fact_sales` only —
and the spec is explicit that issues must not be manufactured for unavailable data (section
17: "RCA must refuse to produce misleading analysis ... canonical data unavailable"). Unlike a
KPI, which returns an explicit `cannot_compute` status for a specific request, there is no
analogous "issue" object to return here, so `run_all_detectors()` simply never calls a
detector for them — they produce nothing, not a placeholder.

Every registered `Issue` row carries: issue ID, issue type, title, severity, period,
comparison period, metric, current value, prior value, absolute change, percentage change,
affected dimension/entity, a `materiality` JSON (every rule *evaluated*, not just the ones
that passed — threshold and actual side by side), evidence references (via the `Evidence.issue_id`
foreign key — see section 7), and status (`detected` → `analyzed`, or `unavailable` for a
future issue type whose canonical data doesn't exist, though none of today's 8 detectors ever
produce that status since they are never invoked without their data).

## 2. Materiality (configuration, not LLM judgment)

`backend/app/rca/materiality.py` holds `MATERIALITY_CONFIG`: one `MaterialityThresholds` entry
per issue type, each a plain dataclass of optional float/int thresholds. `evaluate_materiality()`
is pure arithmetic — a rule only applies if **both** its threshold is configured **and** the
caller supplied the matching actual value, and a finding is material only if **every** applicable
rule passes (AND, never OR, so a big % move on a trivial base — or a trivial % move on a huge
base — doesn't get flagged alone).

| Issue type | min % change | min absolute PKR | min dimension share % | min sample size | min contribution share pts |
|---|---|---|---|---|---|
| `revenue_decline` | 10.0 | 5,000,000 | — | — | — |
| `revenue_growth_slowdown` | 10.0 (on deceleration) | — | — | — | — |
| `margin_deterioration` | 2.0 (points) | — | — | — | — |
| `regional_performance_deterioration` | 15.0 | — | 2.0 | 30 | — |
| `product_margin_deterioration` | 3.0 (points) | — | 1.0 | 30 | — |
| `unusual_cost_movement` | 8.0 (on COGS-vs-revenue gap) | — | — | — | — |
| `unusual_volume_movement` | 15.0 | — | — | — | — |
| `customer_concentration_change` | — | — | — | — | 5.0 |

Severity (`classify_severity`) escalates deterministically from the issue type's own primary
percentage threshold — `low` at 1–1.5x, `medium` at 1.5–2.5x, `high` at 2.5–4x, `critical` at
≥4x — never an LLM call.

## 3. RCA / driver-analysis formulas

`backend/app/rca/decomposition.py` implements two decomposition shapes, both *exact* algebraic
partitions of the total change — no forced-100% hack, no dropped cross-term:

1. **Dimensional partition** (`decompose_by_dimension`) — revenue or COGS grouped by
   region/product/customer in both periods, matched by key (union of keys across both periods,
   zero-filled where an entity is absent in one). Because `sum(current) - sum(prior)` over the
   *same* set of keys equals the total change exactly, coverage is 100% and residual is 0 by
   construction for any dimension on `fact_sales` (there is no "unallocated" row). An optional
   `filter_dimension`/`filter_value` scopes the partition to one entity of a different dimension
   (e.g. decompose REG-05's own revenue change by product, not the whole company's).
2. **Volume/price effect** (`decompose_volume_price`) — splits a revenue change into a quantity
   effect and a price effect using the **midpoint (average-rate) method**:
   `volume_effect = Δquantity × (price₀ + price₁) / 2`, `price_effect = Δprice × (quantity₀ + quantity₁) / 2`.
   This sums to the total change exactly, with no interaction/cross term left over. (The
   simpler "anchor" method — `Δqty × price₀` and `Δprice × qty₁` — leaves a cross term
   `Δprice × Δqty` unaccounted for. The spec names "volume effect" and "price/ASP effect" but
   not a method; the midpoint method was chosen specifically because it is the one with no
   unexplained leftover. See `docs/DECISIONS.md`.) Returns `None` — not a fabricated split —
   when either period's quantity is zero, since an average selling price is undefined there.
3. **Gross-profit decomposition** (`decompose_gross_profit`) — a third, even simpler case:
   `ΔGrossProfit = ΔRevenue − ΔCOGS` is an exact two-term identity (GP = Revenue − COGS), so it
   needs no partitioning method at all.

`backend/app/rca/engine.py` dispatches each issue type to one of 6 analyzer functions
(`_ANALYZERS`), each composing these primitives:

| Issue type | Decomposes into |
|---|---|
| `revenue_decline`, `revenue_growth_slowdown`, `unusual_volume_movement` | revenue by region / product / customer, plus company-wide volume/price effect |
| `unusual_cost_movement` | COGS by product / region |
| `margin_deterioration` | gross-profit revenue-effect/COGS-effect, then COGS by product / region |
| `regional_performance_deterioration` | that region's own revenue by product / customer (filtered), plus that region's own volume/price effect |
| `product_margin_deterioration` | that product's own revenue/COGS/quantity/ASP/gross-profit (current vs. prior), plus its contribution % to the company-wide gross-profit change |
| `customer_concentration_change` | revenue by customer (top 10 + "Other") |

## 4. Contribution math: coverage, residual, display

Every decomposition reports, alongside each row's absolute/percentage contribution and
direction (`positive`/`negative`/`flat`):

- **Coverage** = `sum(explained contributions) / total_change × 100` (`None`, not 0% or 100%,
  when `total_change` is exactly 0 — undefined, not a number).
- **Residual** = `total_change − sum(explained contributions)`.
- **`residual_is_material`** (`is_residual_material()`) — a residual is flagged only if it
  clears **both** an absolute floor (PKR 100,000) **and** a relative floor (1.0% of the total
  change), mirroring the materiality module's own two-threshold pattern. On this phase's data,
  every dimensional partition is an exact `GROUP BY` over the same table it's measuring, so
  residual is always ≈ 0 (observed: ~1e-9, floating-point noise) and this flag is never set
  live — the field exists because a *future* phase's dimension (e.g. an overhead allocation)
  might not partition perfectly, and the UI/API must be able to say "Material unexplained
  residual" rather than silently pretend 100% coverage.
- Contributions are **never forced to sum to 100%** — the spec's own instruction (section 8).

`top_k_with_other()` is a *display* helper only: for the customer dimension (300 customers,
vs. 5 regions / 25 products shown in full), it keeps the 10 largest-magnitude contributions and
merges the rest into one "Other" row whose own contribution is the exact sum of what it
replaces — `rows` still sums to `total_change` exactly; this is not a lossy summary, just a
smaller payload.

## 5. Data sufficiency and unavailable analyses

- **Procurement RCA** (spec section 6) and **overtime RCA** (section 7): Phase 2 only
  materializes `fact_sales`. Neither has a detector, analyzer, or API path — there is nothing
  to mark `status=unavailable` on a *per-request* basis because there is no issue type a
  caller could ask to analyze; the two reserved issue types simply never appear. (A raw Phase 1
  file is never read as a shortcut around this — see `docs/DECISIONS.md`.)
- **Company-level detectors** (`_kpi_change()`) return `None` — "cannot evaluate", never a
  fabricated number — whenever either side of the comparison isn't `status=available` or its
  `percentage_change_status` isn't `"ok"` (reusing Phase 3's own KPI-sufficiency gates
  unchanged).
- **Per-entity detectors** skip an entity outright when its prior-period value is exactly zero
  (percentage change undefined) or its current/prior revenue is zero (margin % undefined) —
  never a divide-by-zero, never a fabricated 0%.
- **`decompose_volume_price()`** returns `None` when either period's quantity is zero, for the
  same reason.
- `POST /issues/{id}/analyze` on an issue type with no registered analyzer returns
  `400 Bad Request` (`UnsupportedIssueTypeError`), not a silent no-op or a guessed decomposition.

## 6. Change ≠ causation

Every claim this phase produces is typed `FACT` or `CONTRIBUTION` (spec section 9). Nothing in
`app/rca/` or `app/rca/evidence.py` ever uses "caused", "root cause", or "because of" — claim
text is built exclusively from "contributed", "associated", "measured association, not a
causal claim", and `tests/rca/test_*` assert these forbidden words never appear in any
generated claim. The UI labels this screen "Issues & Driver Analysis" with a persistent
caveat banner, never "Root Cause Found." A region having the largest revenue *contribution* is
reported as exactly that — a partition of the same change being measured — not as proof that
the region caused the company's decline.

## 7. Evidence model and lineage

`backend/app/db/models/analysis.py::Evidence` (extended from Phase 0's placeholder) carries,
per row: evidence ID, `claim_type` (`fact` | `contribution` | `inference` | `recommendation` —
Phase 4 only ever produces the first two), the generated claim text, metric/value/unit, period
and comparison period, dimension/dimension value, `contribution_to_total_pct`, full lineage
(`source_dataset_id`, `source_file_ids`, `source_fields`), `calculation_name` +
`calculation_version` + `calculation_parameters`, `quality_metadata` (deliberately not named
"confidence" — nothing here is a probability estimate), a generic `data` catch-all, and a
creation timestamp.

**Immutability / lineage (spec section 11):** there is no code path into the `evidence` table
except from `app/rca/engine.py`, which only ever passes output it already computed in
`issues.py`/`decomposition.py` — `app/rca/evidence.py` itself does no querying or calculation,
only formatting and persistence. Nothing updates an Evidence row after it's written. A future
AI narrator is expected to receive Evidence IDs and produce a narrative *about* them, never to
modify them or compute its own numbers from raw tables.

**Evidence references are a normalized foreign key, not a stored array (deliberate deviation
from the spec's literal phrasing):** the spec describes "evidence references" as if `Issue`
stored an array of IDs. Instead, `Evidence.issue_id` / `Evidence.analysis_run_id` are foreign
keys, and the API derives the array view (`Issue.evidence_ids`) via a query
(`_evidence_ids_for_issue()` in `app/api/routers/rca.py`). This is the normalized form of the
same requirement — one `Issue` can have many `Evidence` rows, which is exactly what a foreign
key expresses — not a reduction in capability.

**`Issue.decomposition` is derived, not a second source of truth:** the JSON summary persisted
on `Issue.decomposition` is built by the same call that creates each Evidence row, and every
number inside it carries that row's own `evidence_id` (`_row_payload()`/`_breakdown_payload()`
in `engine.py`). It exists purely so the API can return a ready-to-render structure without the
frontend re-assembling it from a flat Evidence list on every request; it is never recomputed
independently of the Evidence rows that back it.

## 8. RCA run model

`AnalysisRun` (extended from Phase 0) captures: run ID, `analysis_type` (`issue_detection` |
`rca`), granularity, period, comparison type/period, `parameters` (the exact request that
produced it), execution timestamp, `status` (`pending`/`running`/`completed`/`failed`),
`result_summary`, and (via the same foreign-key pattern as Issue) the Issue IDs and Evidence
IDs it produced. A `detect_issues()` call and an `analyze_issue()` call always re-resolve their
period/comparison window from the request (or, for `analyze`, from the issue's own
already-detected period) — nothing here accepts a caller-supplied arbitrary window for a
re-analysis, so a run is reproducible: the same issue, re-analyzed, re-derives the same window
and re-queries the same canonical table.

## 9. API

All endpoints are under `/api/v1`, take a validated Pydantic model or a plain path/query
parameter, and accept no SQL string, expression, or LLM-generated query of any kind.
`POST /issues/{id}/analyze` takes no body — it only ever re-derives the issue's own period.

| Method | Path | Purpose |
|---|---|---|
| GET | `/issues` | List issues (filter by status/type/granularity/period) |
| GET | `/issues/{issue_id}` | One issue, with its decomposition if analyzed |
| POST | `/issues/detect` | `{granularity, period_key, comparison_type}` → run detection, persist issues + FACT evidence |
| POST | `/issues/{issue_id}/analyze` | Run driver analysis for one already-detected issue |
| GET | `/issues/{issue_id}/evidence` | Every Evidence row for one issue |
| GET | `/evidence/{evidence_id}` | One Evidence row, full lineage |
| GET | `/analysis-runs/{run_id}` | One run's parameters/status/issue & evidence IDs |

## 10. UI

`frontend/src/pages/DriverAnalysisPage.tsx` ("Issues & Driver Analysis" tab): granularity /
period / comparison-type controls and a "Detect issues" button
(`POST /issues/detect`); an `IssueList` of what was found; an `IssueDetail` panel for the
selected issue showing current/prior/absolute/percentage change, the materiality rules that
qualified it (threshold vs. actual, side by side), a "Run driver analysis" button when
`status=detected`, and — once analyzed — a generic renderer that walks the issue's
`decomposition` JSON and draws:

- **`ContributionBarChart`** — ranked horizontal bars for any region/product/customer/COGS
  breakdown, direction-colored (green=positive, red=negative, grey=flat), with a
  coverage-percentage label, a "Material unexplained residual" warning when flagged, and a
  permanent "measured association, not a causal claim" caption baked into the component.
- **`WaterfallChart`** — a floating-bar waterfall for the two-step effects (volume/price;
  revenue-effect/COGS-effect) that sum exactly to a total, with a neutral-colored total bar.
- A plain fact table for a product-margin issue's own revenue/COGS/quantity/ASP/gross-profit.

Every bar and fact-pair row is clickable and opens `EvidenceDrawer`, which fetches
`/evidence/{id}` on demand and shows the claim text, `ClaimTypeBadge`, and full calculation
lineage — "every important number traceable to an Evidence ID" (spec section 14), not just
asserted in the API but reachable from the UI itself.

## 11. Seed-42 acceptance (GT-02 / GT-03)

`tests/rca/test_ground_truth.py` verifies the engine recovers the two planted patterns the
spec names, **using only canonical-data queries, never `_hidden/ground_truth.yaml`** in
production code (the file is read only by the test itself, to compute an independent expected
value with pandas). Two corrections from the spec's literal text, made via independent
judgment and documented in the test module's own docstring:

- **GT-02 is region REG-05, not "Karachi/R02".** `detect_issues()` for 2025 YoY finds "Region
  REG-05 revenue decline: -16.3% YoY in 2025" from canonical data alone; the seed-42
  `planted_config.planted.region_decline_id` confirms REG-05 (not R02) is the actual planted
  entity.
- **GT-03 is product PROD-12, not "P14".** The engine finds "Product PROD-12 margin
  deterioration: -4.5 points YoY in 2025"; `planted_config.planted.margin_decline_product_id`
  confirms PROD-12.

Both were independently discovered by live smoke-testing against the real dataset before the
ground-truth file was even inspected, so the correction is not a post-hoc rationalization of a
failing test — the engine found the same entities the hidden config had actually planted.

## 12. Performance

Every detector and decomposition issues one or a handful of aggregate SQL queries (`SUM`/`GROUP BY`
with a `WHERE month BETWEEN`) against the 185,400-row seed-42 `fact_sales` table — there is no
path that loads all rows into Python. No Redis/Celery/Kafka was introduced. Measured against
the real dataset via live smoke-testing: `POST /issues/detect` for a full year (8 detectors,
including a 25-product and a 5-region per-entity scan) ≈ 2s; `POST /issues/{id}/analyze` for
the product-margin issue (5 single-entity aggregates plus one company-wide comparison) ≈ 10s;
for the region issue (two dimensional partitions — a 25-row product breakdown and a 300-customer
breakdown reduced to top-10 — plus a volume/price split, each partition querying both the
current and prior period) ≈ 26s. The per-entity dimensional partitions are the most expensive
step since each issues 4 `GROUP BY` queries (current/prior × 2 dimensions); this is comfortably
fast for an on-demand "analyze this issue" click and was not optimized further.
