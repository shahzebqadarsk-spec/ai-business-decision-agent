# Phase 3: Deterministic KPI Engine & Executive Dashboard

This document is the reference for everything Phase 3 added: the KPI catalog, formula
definitions, availability/sufficiency rules, comparison methodology, dimensional analysis,
the provenance model, the API, and dashboard behavior.

**Governing principle:** the KPI engine, not the LLM, calculates every business number. Every
KPI value in this system is the result of a parameterized SQL aggregation against a canonical
table — nothing in `app/kpi/` or `app/api/routers/kpi.py` accepts free-form SQL, an expression
string, or anything else that would let a caller (human, frontend, or a future LLM narrator)
compute something outside the registry below.

## 1. KPI catalog

21 KPIs are registered in `backend/app/kpi/registry.py`. **8 are computable today** from
`fact_sales` (the only canonical table Phase 2 materializes); the other **13 are structural
stubs** — they never touch the database, because the canonical table they would need
(`fact_procurement`, `fact_payroll`, `fact_expenses`, `fact_production`, `fact_inventory`,
`fact_workforce`) does not exist yet. A stub always returns `cannot_compute` with a reason
naming the missing table, never a fabricated number.

| KPI ID | Name | Category | Unit | Status |
|---|---|---|---|---|
| `revenue` | Revenue | financial | currency | **computable** |
| `gross_profit` | Gross Profit | financial | currency | **computable** |
| `gross_margin_pct` | Gross Margin % | financial | percentage | **computable** |
| `cogs` | Cost of Goods Sold | financial | currency | **computable** |
| `operating_expenses` | Operating Expenses | financial | currency | stub (`fact_expenses`) |
| `operating_profit` | Operating Profit | financial | currency | stub (`fact_expenses`) |
| `operating_margin_pct` | Operating Margin % | financial | percentage | stub (`fact_expenses`) |
| `sales_quantity` | Sales Volume / Quantity | sales | quantity | **computable** |
| `average_selling_price` | Average Selling Price | sales | currency | **computable** |
| `customer_count` | Customer Count | sales | count | **computable** |
| `transaction_count` | Order / Transaction Count | sales | count | **computable** |
| `procurement_cost` | Procurement Cost | cost | currency | stub (`fact_procurement`) |
| `procurement_cost_per_unit` | Procurement Cost per Unit | cost | currency | stub (`fact_procurement`) |
| `payroll_cost` | Payroll Cost | cost | currency | stub (`fact_payroll`) |
| `overtime_cost` | Overtime Cost | cost | currency | stub (`fact_payroll`) |
| `expense_cost` | Expense Cost | cost | currency | stub (`fact_expenses`) |
| `production_quantity` | Production Quantity | operations | quantity | stub (`fact_production`) |
| `inventory_quantity` | Inventory Quantity | operations | quantity | stub (`fact_inventory`) |
| `inventory_value` | Inventory Value | operations | currency | stub (`fact_inventory`) |
| `inventory_days` | Inventory Days / Days of Cover | operations | days | stub (`fact_inventory`) |
| `overtime_hours` | Overtime Hours | operations | hours | stub (`fact_workforce`) |

**Deviation from the spec's literal list:** "Revenue by Region", "Revenue by Product" and
"Revenue by Customer" are **not** separate registry entries. They are `revenue`'s dimensional
breakdown (`POST /kpis/revenue/breakdown` with `dimension=region|product|customer`) — the
formula is identical (`SUM(net_amount_pkr)`), only the `GROUP BY` differs, so three registry
entries would just be the same formula three times over with no behavioral difference.

## 2. Formula definitions

| KPI | Formula |
|---|---|
| Revenue | `SUM(net_amount_pkr)` |
| Sales Quantity | `SUM(quantity)` |
| Average Selling Price | `Revenue / Quantity` (guarded: `invalid_data` if Quantity = 0) |
| Customer Count | `COUNT(DISTINCT customer_id)` |
| Transaction Count | `COUNT(DISTINCT sale_id)` |
| COGS | `SUM(cogs_amount_pkr)` |
| Gross Profit | `Revenue - COGS` |
| Gross Margin % | `(Revenue - COGS) / Revenue * 100` (guarded: `invalid_data` if Revenue = 0) |

All eight read `fact_sales` filtered to `month BETWEEN period.start_month AND period.end_month`
— `month` is always a first-of-month date (Phase 2 canonical schema), so period filtering is a
plain `BETWEEN`, never a derived date expression.

## 3. Canonical data limitation

Only `fact_sales` is implemented (`app/kpi/sufficiency.py::IMPLEMENTED_CANONICAL_TABLES`).
Extending that one frozenset is the *only* change a later phase needs to make once e.g.
`fact_procurement` exists — the registry entry, calculator stub, and API surface for
`procurement_cost` are already wired, waiting for the table.

## 4. Availability vs. data-sufficiency

Two independent gates, checked in this order:

1. **Table-implemented gate** (`check_tables_implemented`) — is `required_canonical_tables`
   a subset of what's actually materialized? If not: `cannot_compute`, a structural fact that
   doesn't depend on the period requested.
2. **Field-sufficiency gate** (`check_field_sufficiency`) — for the *exact rows in the
   requested period*: are there any rows at all (≥1), and is each required field populated
   for ≥95% of them? If not: `insufficient_data`, naming the period and the under-covered
   field. This is evaluated per-period, not once for the whole table — a KPI can be
   `available` for 2023 and `insufficient_data` for 2025 if a field stops being populated.

A third status, `invalid_data`, covers a different failure: the gates passed (real rows,
real coverage) but the arithmetic itself is undefined — a zero denominator in Average
Selling Price or Gross Margin %. The engine never raises `ZeroDivisionError`; it returns
`invalid_data` with a plain-language reason instead.

No KPI ever returns `0` as a stand-in for "no data." A missing value is always `null` with a
`status` and a `status_reason`.

## 5. Time-period engine & comparison methodology

- Granularities: `month` (`YYYY-MM`), `quarter` (`YYYY-Qn`), `year` (`YYYY`).
- Calendar year is locked to January–December (Phase 0 decision), but quarter/year boundaries
  are derived from `settings.fiscal_year_start_month` rather than hard-coded to January, so a
  later change to that locked decision needs no change here.
- Comparison types: `YoY` (any granularity, -12 months), `QoQ` (quarter only, -3 months),
  `MoM` (month only, -1 month). Requesting `MoM` against a `year` window (or `QoQ` against a
  `month` window) is rejected as an invalid request (400), not silently ignored.
- `percentage_change` is `null` whenever it would be undefined, with an explicit
  `percentage_change_status`:
  - `not_requested` — no `comparison_type` was given at all.
  - `undefined_missing_data` — a comparison was requested but the current or prior period's
    value isn't `available` (e.g. comparing against a period with no data).
  - `undefined_zero_denominator` — both periods have real data, but the prior period's value
    is exactly zero.
  - `ok` — a real percentage change was computed.

## 6. Dimensional analysis

Supported dimensions: `region`, `product`, `category`, `customer` (categorical — grouped,
ranked descending by value, with `share_pct` of the period total) and `month`, `quarter`,
`year` (time buckets — chronological order, `rank` is always `null`, since a trend line is
read in time order, not biggest-first). Only KPIs built from a single summed `fact_sales`
column currently expose a `breakdown` function (`revenue`, `sales_quantity`, `cogs`); a ratio
KPI like `gross_margin_pct` does not, and requesting one returns 400, not a nonsensical
per-dimension ratio.

## 7. Provenance / evidence-compatibility model

Every `calculate_kpi()` call persists a `kpi_calculations` row (`app/db/models/kpi.py`): KPI
id, calculation_version, granularity, period, comparison period, status, value, comparison
value/change, `data_coverage` (row counts and per-field non-null ratios), `source_file_ids`
(which uploaded files' rows fed this number), and `source_fields` (which canonical columns the
formula used). This is an **append-only audit trail, not a cache** — the engine always
recomputes from `fact_sales` and then records what it found; nothing ever reads a value back
out of this table instead of recalculating it.

This table is deliberately separate from the Phase 0-declared `evidence` table
(`app/db/models/analysis.py`), which is scoped to Phase 4's `analysis_run`/RCA concept that
doesn't exist yet. `kpi_calculations`' shape is designed so a future Phase 4 migration can map
one row to one `Evidence` row (`claim` = "{kpi.name} = {value} for {period}",  `data` = the
full row) without the KPI engine itself changing.

## 8. API

All endpoints are under `/api/v1`, use validated Pydantic request/response models, and accept
no free-form SQL, expression, or filter beyond a known dimension/period.

| Method | Path | Purpose |
|---|---|---|
| GET | `/kpis` | Full catalog (static metadata + `implemented` flag) |
| GET | `/kpis/{kpi_id}` | One KPI's definition |
| GET | `/kpis/{kpi_id}/availability?granularity=&period_key=` | Cheap status check (never runs the aggregation) |
| POST | `/kpis/{kpi_id}/calculate` | `{granularity, period_key, comparison_type?}` → full `KPIResult` |
| POST | `/kpis/{kpi_id}/breakdown` | `{granularity, period_key, dimension}` → ranked rows |
| GET | `/dashboard?period_key=&comparison_type=` | Executive Dashboard aggregator payload |

## 9. Dashboard behavior

The dashboard defaults to the latest year with any data and a YoY comparison. It shows:
headline cards for Revenue, Sales Volume, Average Selling Price, Customer Count, and
Transaction Count (each with its YoY change or an explicit unavailable/insufficient-data
state — see `KpiCard.tsx`); a Plotly year-over-year monthly revenue overlay (one line per
calendar year, so multiple years are visually comparable); Recharts bar breakdowns for
revenue by region and by product; and top-5/bottom-5 customer tables. A KPI the dashboard
cannot compute is never rendered as `0` — it shows "Unavailable" or "Insufficient data" plus
the engine's own reason text.

## 10. Performance

Every real calculator issues one or two aggregate SQL queries (`SUM`/`COUNT(DISTINCT)` with a
`WHERE ... BETWEEN` and, for breakdowns, a `GROUP BY`) against the full 185,400-row seed-42
`fact_sales` table — there is no path that loads rows into Python to sum them. Measured
against that table: a single KPI calculation with a YoY comparison ≈ 0.5s (two aggregate
queries plus two sufficiency checks); a dimensional breakdown ≈ 0.12s; the full Executive
Dashboard aggregator (5 KPIs × comparison, 2 category breakdowns, a 3-year monthly trend, and
customer ranking) ≈ 2.0s. No caching layer was added — this is comfortably fast without one.
