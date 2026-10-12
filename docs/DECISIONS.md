# Locked decisions and deviations

## Locked business decisions (Phase 0 approval)

| Decision | Value |
|---|---|
| Company | PakManufacture Pvt Ltd |
| Industry | Textile manufacturing |
| Period | January 2023 - December 2025 (36 months) |
| Fiscal year start | Month 1 (calendar year) |
| Currency | PKR (reporting currency; superseded by Phase 8 -- see below) |
| Default comparison | YoY (QoQ available) |
| Data | Synthetic only |

These are enforced in code, not just documentation: `app/config.py` (`Settings`) and
`synthetic_data/generator/config.py` (`GeneratorConfig`) both raise `ValueError` at
construction time if `SYNTHETIC_DATA_ONLY`, `start_month`, `months`, or `currency` are
given any other value. `CURRENCY` (`Settings.reporting_currency`) no longer rejects
every value but `"PKR"` -- see Phase 8.

## Rebuild note (read this first)

This codebase has been rebuilt from scratch **twice** after the execution container was
reclaimed between turns and the working tree was lost (the environment is ephemeral; nothing
outside the conversation record or re-attached files survives a reclaim). Both rebuilds were
done from the detailed, explicit specifications in the approved Phase 0/1/2 instructions and
the prior completion reports, with every previously-found calibration bug fixed proactively
rather than rediscovered. A local git repository (with no remote, since no GitHub account was
connected to this session) was initialized partway through this rebuild as a minimal safety
net against a third loss; it does not protect against another full container reclaim.

## Phase 0 deviations

1. **Ruff line length 110, not the 88/100 default.** Chosen to match a realistic "modern
   backend" house style without forcing excessive wrapping in already-dense generator code
   (price/cost formulas, SQLAlchemy `__table_args__`).
2. **`enum_column()` / `check_in()` split instead of inline `CheckConstraint`.** SQLAlchemy
   2.1's `mapped_column()` silently drops a positional `CheckConstraint` the way legacy
   `Column()` accepted it - the constraint simply never reaches the schema. `enum_column()`
   declares a plain `VARCHAR`; `check_in()` returns the matching `CheckConstraint` for
   `__table_args__`, which autogenerate does pick up (verified: 9 `CHECK` constraints appear
   in the generated migration, not 1).
3. **`CanonicalRecord` is a deliberate, temporary placeholder**, not the real Phase 2
   canonical model. It exists only so the Phase 0 migration history is self-consistent; Phase
   2 replaces it with typed fact/dim tables (see the Phase 2 section below) and does not
   write to it.
4. **`Purpose` is a `StrEnum`**, not `str, Enum` - functionally identical, but avoids a
   `ruff UP042` lint finding on Python 3.12.
5. **`CompletionRequest.response_schema`, not `.schema`.** Pydantic's `BaseModel` already
   defines a `schema` classmethod; naming a field `schema` shadows it (a real warning, not
   just lint noise) and breaks static analysis of the field's type. Renamed before it caused
   a real bug.

## Phase 1 deviations

1. **3 red herrings, not an exhaustive set.** The spec asks for "realistic noise and
   red-herring patterns" without a count. Three were implemented, each defeating a
   specific naive detection heuristic: a seasonal-but-non-cumulative spike (so "this changed a
   lot recently" doesn't automatically mean "planted"), a one-off reverting price spike (so
   "concentrated in one supplier" doesn't automatically mean "sustained"), and a single bad
   month for an otherwise-healthy region (so "one bad data point" doesn't automatically mean
   "declining trend"). Each directly targets the kind of false-positive a later RCA module
   would need to rule out.
2. **Deterministic supplier/material assignment for the planted procurement problem.**
   Materials are assigned their supplier from a fixed `default_supplier_id` field in the
   static catalog, not a random weighted draw. A random draw would (and, in the version of
   this generator built in the prior session, did) assign a *different* supplier to the
   planted material on 4 of 5 alternate seeds tested, silently erasing GT-01 for those seeds.
3. **CPI-deflated measurement for GT-01.** Comparing nominal (undeflated) unit prices
   conflates the planted ~17% supplier-specific repricing with macro inflation accumulated
   over the 3-year span (roughly +24% at the configured CPI rate), overshooting the target
   band by nearly 3x in earlier testing. `measure_procurement_increase()` optionally deflates
   by a `cpi_by_month` map; `test_planted_problems.py::test_gt01_undeflated_measurement_overshoots_the_planted_effect`
   is a regression test proving the deflated figure is reliably lower than the undeflated one
   for the same data - this is a change in what the metric *means* (isolating a
   supplier-specific effect from a macro one), not just a tolerance adjustment.
4. **Region decline is isolated from the company-wide demand-growth ramp.** Applying both the
   growth ramp (+60% by the final month) and the regional decline multiplier (originally
   -22%) to the same region left growth outpacing decline in net revenue terms - GT-02 came
   out *positive* in early testing. The declining region's lines are now generated with
   `growth = 1.0` (no company-wide ramp) and only the decline factor applied, so the region's
   trend is unambiguous rather than a race between two opposing effects. The decline target
   was also increased (-22% to -45% on quantity) so it dominates CPI-driven price inflation on
   the revenue metric actually measured.
5. **Overtime calibration required three passes.** Labor-hours-per-unit for the
   Knitwear/CAT-02 category, and the staffing gap on the affected line (LINE-05), were
   calibrated against actual measured output rather than guessed: an initial pass produced
   zero overtime in *every* seed (workload never reached capacity); a second pass produced
   overtime for the default seed but zero for 3 of 5 alternate seeds tested (the margin
   between workload and capacity was too thin relative to cross-seed demand variance); the
   final calibration (staffing gap raised from 6 to 9, CAT-02 labor-hours-per-unit raised to
   0.15) produces overtime that is reliably zero in year one and reliably material (triggers
   in every one of 6 tested seeds) in the final quarter, at the cost of a wider magnitude band
   (50-1600 hours/month rather than a tight range) to reflect the genuine cross-seed variance
   in how much CAT-02 demand a given seed happens to generate.
6. **Inventory overstock coefficient deliberately small (0.10, not an earlier 0.60).**
   Nothing in the model consumes excess finished-goods stock once produced, so even a modest
   sustained over-production ratio compounds into a very large months-of-cover figure over 36
   uninterrupted months; a 0.60 coefficient produced ~9.5 months of cover (plausible but high
   for a "meaningful imbalance" framing), while 0.10 lands consistently in a 2-7 month band
   across seeds.
7. **`scale` shrinks the *fact-table row volume* as well as headcount/customer counts.**
   The originally-specified `effective_sizes` property only scaled customers/employees; sales
   line-item volume was independently fixed at `_BASE_LINES_PER_MONTH`, so a small-`scale` run
   (used by the fast test fixtures) still generated full-size sales data. `generate_sales()`
   now multiplies the per-month line count by `config.scale` directly.
8. **Verification's row-count check scales with `config.scale`.** A fixed 100k-350k band only
   makes sense at `scale=1.0`; `verify_tables(..., scale=...)` computes a scaled band instead,
   so `--scale 0.05` runs (used by every fast test) don't spuriously fail row-count
   verification.

## Phase 2 (planned corrections, folded in while building - see the Phase 2 report)

Flagged during the Phase 1-to-Phase-2 architecture critique and implemented as part of
Phase 2 itself, not deferred:

1. Typed fact/dim tables replace the generic `CanonicalRecord` JSONB placeholder.
2. Row-level lineage (`source_file_id`, `source_row_number`) is added to canonical rows, not
   just column-level lineage on `column_mappings`.
3. Explicit upload ceilings: 50 MB / 500,000 rows (configurable via `MAX_UPLOAD_BYTES` /
   `MAX_UPLOAD_ROWS`), not left unspecified.
4. "Suspicious outlier" detection uses a robust statistic (IQR-based), calibrated against the
   Phase 1 dataset's deliberately Zipf-concentrated customer base, rather than a plain
   z-score that would flag legitimate large orders from the biggest customers as anomalies.

## Phase 3 (deviations from the spec - see docs/PHASE_3_KPI_ENGINE.md for the full reference)

1. **"Revenue by Region/Product/Customer" are not separate KPI registry entries.** They are
   `revenue`'s dimensional breakdown (`POST /kpis/revenue/breakdown?dimension=...`). The
   formula (`SUM(net_amount_pkr)`) is identical; only the `GROUP BY` differs, so three
   registry entries would duplicate one formula three times with no behavioral difference.
2. **COGS, Gross Profit, and Gross Margin % are implemented as real (computable) KPIs, not
   stubs.** `cogs_amount_pkr` is genuinely populated on every `fact_sales` row by Phase 2's
   materialization, so gating these behind a "not yet built" stub would withhold a number the
   data already supports.
3. **`kpi_calculations` (provenance/audit trail) is a new table, deliberately kept separate
   from the Phase 0-declared `evidence` table.** `evidence` is scoped to Phase 4's
   `analysis_run`/RCA concept, which doesn't exist yet; reusing it now would mean either
   inventing a placeholder `analysis_run` just to satisfy a foreign key, or weakening that
   table's intended constraints. `kpi_calculations`' shape (KPI id, period, status, value,
   data_coverage, source_file_ids, source_fields) is designed so a future Phase 4 migration
   can map one row to one `Evidence` row without changing the KPI engine itself.
4. **The KPI registry is Python dataclasses pointing to ordinary calculator functions, not a
   string-formula or expression DSL.** The spec's own constraint ("no arbitrary SQL/expression
   execution" via the API) is easiest to guarantee structurally - there is no parser or
   `eval`-like path anywhere between an API request and a SQL aggregate, because there is
   nothing to parse.

## Phase 4 (deviations from the spec - see docs/PHASE_4_RCA_ENGINE.md for the full reference)

1. **GT-02's entity is region REG-05, not "Karachi/R02"; GT-03's entity is product PROD-12,
   not "P14".** The spec's own prose names these literal strings, but the actual seed-42
   `_hidden/ground_truth.yaml` / `planted_config.planted` object configures REG-05
   (`region_decline_id`) and PROD-12 (`margin_decline_product_id`). The deterministic engine,
   querying canonical data alone with zero reference to the ground-truth file, independently
   found "Region REG-05 revenue decline" and "Product PROD-12 margin deterioration" during live
   smoke-testing *before* the ground-truth file was inspected to explain the discrepancy -
   confirming the spec's literal IDs are simply wrong for this seed, not that the engine is
   missing the planted pattern. Tests assert against the real configured IDs.
2. **Volume/price decomposition uses the midpoint (average-rate) method, not an anchor
   method.** The spec names "volume effect" and "price/ASP effect" but not a calculation
   method. `effect_qty = Δqty × (price₀+price₁)/2`, `effect_price = Δprice × (qty₀+qty₁)/2`
   sums to the total change exactly, with no leftover cross term; the simpler anchor method
   (`Δqty × price₀`, `Δprice × qty₁`) leaves `Δprice × Δqty` unexplained. Chosen specifically
   so "coverage" can honestly be ~100% rather than close-but-not-exact.
3. **"Evidence references" is a normalized foreign key (`Evidence.issue_id` /
   `Evidence.analysis_run_id`), not a stored ID-array column on `Issue`.** The spec describes
   evidence references as a field an issue holds; a foreign key expresses the same
   one-to-many relationship more durably (no array to keep in sync) and the API derives the
   array view on read. This is the normalized form of the requirement, not a reduction in
   capability.
4. **`Issue.decomposition` is a derived JSON summary, not a second source of truth.** It is
   written by the same call that creates each Evidence row, with every figure carrying that
   row's own `evidence_id`; it exists so the API can return a ready-to-render structure without
   the frontend re-assembling it from a flat Evidence list, and it is never recomputed
   independently of the Evidence rows that back it.
5. **`material_inventory_issue` and `overtime_issue` have no detector function at all**, rather
   than a detector that always returns an "unavailable" result. Phase 2 materializes
   `fact_sales` only, so there is no per-request decision to make ("is this issue
   available for this period?") - the canonical tables these issue types would read
   (`fact_inventory`, `fact_workforce`) don't exist at all yet, so the two issue types simply
   never appear, rather than appearing as a permanently-unavailable stub the way a Phase-3 KPI
   stub does.
6. **Procurement RCA and overtime RCA are absent, not stubbed with `status=unavailable`.**
   Same reasoning as #5: there is no issue type a caller could ask the API to analyze for
   these, so there is no per-request status to return - the raw Phase 1 synthetic files are
   never read as a shortcut around the ingestion/materialization architecture to fake this
   data into existing early.

## Phase 5 (deviations from the spec - see docs/PHASE_5_FORECASTING_ENGINE.md for the full reference)

1. **Phase 5 is scoped to the Forecasting Engine only; scenario/what-if analysis, decision
   scoring, the AI narrator, the verifier, and chat orchestration are explicitly deferred.**
   The spec bundles all of these under one "Phase 5" label. Following the same disciplined
   narrow-scoping Phase 4 used on its own spec section (built issue detection/RCA, explicitly
   deferred procurement/overtime RCA), this was an independent engineering-judgment call -
   each deferred piece deserves its own full build-test-document cycle rather than being rushed
   alongside forecasting. Approved via the standing "use your own intelligence" instruction
   after the attached "ChatGPT prompt" for this phase turned out to be a verbatim echo of this
   session's own prior output rather than a new specification.
2. **Classical two-stage trend + seasonal decomposition (closed-form OLS), not ARIMA/Prophet/
   any ML library.** No such dependency exists in the project, and the spec does not mandate a
   specific method - this one is fully deterministic and auditable (every parameter is a plain
   number in `ForecastRun.parameters`), matching the project's "every number traceable"
   principle better than a fitted black-box model would.
3. **Only `revenue`, `sales_quantity`, and `cogs` are forecastable; `gross_margin_pct` and
   `gross_profit` are not.** A margin % is a ratio of two independently-uncertain forecasts
   with no rigorous combined confidence interval under this method; a gross-profit forecast
   computed as `revenue_forecast - cogs_forecast` would silently understate its own
   uncertainty rather than modeling its own seasonal pattern. Both are documented scope
   limitations, not oversights.
4. **Forecast granularity is month-only.** The seasonal model needs a clean 12-period annual
   cycle; quarter/year forecasting would need its own calibration and is deferred.
5. **A forecast always uses the complete available history, never a caller-chosen window.**
   "Forecast as of now, using everything available" is a different (and more honest) claim than
   "forecast for an arbitrary historical cutoff," and the spec does not ask for the latter.
6. **Hardcoded normal critical values (`Z_SCORES`) instead of `scipy.stats.norm`.** `scipy` is
   not a project dependency (confirmed: `import scipy` fails); four fixed values for the
   supported confidence levels (80/90/95/99%) avoid adding a dependency for four constants.
7. **`EvidenceOut`'s shared `/evidence/{id}` schema gained `forecast_run_id`/`forecast_id`
   fields.** These two FKs were added to the `Evidence` model itself for Phase 5, but the
   generic evidence-lookup endpoint's response schema (written in Phase 4, before Forecasting
   existed) had to be updated to actually surface them - otherwise a forecast's evidence record
   was reachable and correctly typed but didn't report which forecast/run produced it.

## Phase 6 (deviations from the spec - see docs/PHASE_6_SCENARIO_ENGINE.md for the full reference)

1. **Phase 6 is scoped to Scenario/What-If Analysis only; decision scoring, the AI narrator,
   the verifier, and chat orchestration remain explicitly deferred.** Same disciplined
   narrow-scoping Phase 4 and Phase 5 both used on their own slice of the spec, and the next
   stage in the README's own DATA->INSIGHT->ROOT CAUSE->FORECAST->WHAT-IF->DECISION->
   RECOMMENDATION->EVIDENCE pipeline. Approved via the standing "use your own intelligence"
   instruction with no new formal spec provided for this phase either.
2. **A scenario is a plain percentage shock on an existing Phase 5 baseline forecast, never an
   independent re-fit.** `scenario_value = baseline_value * (1 + adjustment_pct / 100)`;
   `gross_profit`/`gross_margin_pct` are re-derived with Phase 3/4's own formulas
   (`GP = Revenue - COGS`, `margin% = GP / Revenue * 100`) from the two (possibly adjusted)
   driver series, never independently shocked or fitted. A more elaborate re-fit-under-a-shocked-
   assumption method would need its own calibration and sufficiency story, out of scope here.
3. **A scenario writes no Evidence rows.** Evidence (Phase 4) backs a claim about what the
   analytics measured or inferred about the real world; a scenario is an explicit counterfactual
   the user is constructing to explore, not a claim about reality. Every number is still fully
   traceable via `ScenarioResult` rows and the `Scenario.revenue_forecast_run_id`/
   `cogs_forecast_run_id` references, just not via the `Evidence` table.
4. **The Phase 0 `Scenario` placeholder's opaque `assumptions`/`projected_impact` JSON blobs
   are replaced with explicit numeric columns and a normalized `ScenarioResult` child table**,
   not filled in as originally shaped - consistent with how Phase 4 normalized "evidence
   references" and Phase 5 replaced the `Forecast` placeholder outright, rather than writing an
   opaque blob that isn't individually queryable or traceable per number.
5. **Fixed a real pre-existing bug this phase's full-suite test run exposed**:
   `tests/kpi/test_calculators.py`'s `sparse_cogs_period`/`zero_quantity_period` fixtures
   committed synthetic far-future (2097/2098) `fact_sales` rows with no cleanup, invisible for
   three phases because nothing queried the whole-table min/max month range until Phase 5's
   `check_history_sufficiency()` did. Fixed by changing `commit()` to `flush()` in both
   fixtures (the tests only ever needed same-transaction visibility).

## Phase 7 (deviations from the spec - see docs/PHASE_7_DECISION_SCORING.md for the full reference)

1. **Phase 7 is scoped to Decision Scoring only; the AI narrator, the recommendation-approval
   workflow, the verifier, and chat orchestration remain explicitly deferred.** Same disciplined
   narrow-scoping Phase 4, 5, and 6 each used on their own slice of the spec, and the next stage
   in the README's own DATA->INSIGHT->ROOT CAUSE->FORECAST->WHAT-IF->DECISION->RECOMMENDATION->
   EVIDENCE pipeline. Approved via the standing "use your own intelligence" instruction with no
   new formal spec provided for this phase either. Verified against the codebase (not just
   inferred) by reading `app/db/models/recommendations.py` in full before writing any code.
2. **A decision score is a weighted average of a scenario's own `ScenarioResult.delta_percentage`
   values on up to three criteria (profitability, growth, cost_efficiency), never a new fit or
   an LLM judgment.** Default equal weights, or caller-supplied weights for a non-empty subset
   of the three that must sum to ~1.0 -- rejected with `400`, never silently renormalized, if
   they don't.
3. **`score` is `None` (never fabricated via partial reweighting) when a scenario lacks data for
   even one weighted criterion**, and `status="insufficient_data"` only when *no* compared
   scenario scored on *any* weighted criterion -- the same sufficiency-gating discipline every
   prior phase in this project uses.
4. **Unlike Phase 6's Scenario engine, this phase deliberately *does* write Evidence**: one FACT
   row per `DecisionRun` (what was compared, with what weights) and one RECOMMENDATION row per
   *scored* `DecisionOption` -- the first production use of `claim_type="recommendation"`,
   reserved since Phase 4. Framed explicitly as advisory, never a certainty claim: "The AI
   recommends; a human approves" (the README's own governing principle), matching the AI-
   narrator/recommendation-approval workflow this phase does *not* implement.
5. **The Phase 0 `DecisionOption` placeholder's `score` column was widened from `Numeric(6, 3)`
   to `Numeric(12, 4)`** before any code was written against it -- a weighted average of
   `delta_percentage` values can reach the same +/-1000% range a `Scenario`'s own
   `adjustment_pct` is allowed to, which would have overflowed the original precision on a
   legitimate extreme scenario. Matches `ScenarioResult.delta_percentage`'s own precision.
6. **`DecisionOption.scenario_id` is nullable with `ON DELETE SET NULL`, not `NOT NULL`/
   `CASCADE`**, even though every option is created from a real scenario at scoring time: a
   scored option's score/breakdown/rationale is itself a historical record with independent
   value (what the AI recommended, when), so deleting the `Scenario` it was computed from must
   not silently destroy that record -- mirrors `Scenario.revenue_forecast_run_id`/
   `cogs_forecast_run_id`'s own pattern against `ForecastRun`.

## Phase 8 (multi-currency support -- supersedes the Phase 0 "Currency: PKR" lock)

1. **The Phase 0 `CURRENCY` lock is relaxed, not removed.** `Settings.reporting_currency`
   (still the `CURRENCY` env var) now accepts any ISO 4217 code `app/fx/rates.py` has a rate
   for, instead of rejecting everything but `"PKR"`. It still raises `ValueError` -- on an
   unsupported code -- rather than silently accepting something it can't actually convert.
   This was a deliberate, requested scope change (a single-country pilot product becoming a
   global one), not a discovered bug.
2. **A dataset's rows can mix native currencies freely; a deployment has exactly one
   *reporting* currency.** `fact_sales.currency` (already present since Phase 2, unused until
   now) holds each row's own native currency. Every KPI/RCA/forecast calculation reads the new
   `unit_price_reporting` / `net_amount_reporting` / `cogs_amount_reporting` columns -- already
   converted into `Settings.reporting_currency` -- never the original `*_pkr` columns, which
   keep their name for migration-compatibility but hold whatever currency the row's `currency`
   says, not necessarily PKR despite the name.
3. **A row's native currency is resolved in this order, and never guessed beyond what the text
   says:** (1) a confirmed `currency` column mapping, (2) a currency symbol/code detected
   directly in the price text (`numeric_format.detect_currency_code` -- only when unambiguous,
   e.g. "Rs", "€", "US$"; a bare "$" or "¥" is genuinely ambiguous across several currencies and
   is deliberately left undetected rather than guessed), (3) the deployment's configured
   `reporting_currency` as the fallback assumption for a file with no currency signal at all
   (the same assumption Phase 0-7 made implicitly for every upload).
4. **FX rates are a static, dated, manually-curated snapshot (`app/fx/rates.py`,
   `RATES_AS_OF`), never a live API call.** Two independent reasons, not one: (a) this
   project's own "every number comes from deterministic analytics, never fabricated" rule --
   a live rate makes the exact same upload produce a different KPI depending on when it's
   materialized, which breaks reproducibility outright; (b) this sandboxed build environment's
   egress allowlist generally can't reach arbitrary third-party FX APIs anyway, so a live
   dependency would fail at the worst layer -- silently, after the upload already looked
   successful. Each converted row stores the exact rate used (`fx_rate_to_reporting`) and the
   table's review date (`fx_rate_as_of`), so every number carries its own audit trail instead
   of depending on trusting the table blindly. Refreshing the table is a manual, reviewed edit,
   not a scheduled job.
5. **The synthetic generator's own `GeneratorConfig.currency` lock to `"PKR"` is untouched.**
   That lock is about what currency the *synthetic test dataset itself* is generated in, which
   is a separate concern from what currency a real uploaded file is allowed to be in or what
   currency a deployment reports in. The seed-42 dataset stays single-currency PKR; multi-
   currency behavior is exercised by hand-built mixed-currency sample files instead (see the
   ingestion pilot-test notes), not by extending the generator.
6. **New `fact_sales` columns are purely additive** (`unit_price_reporting`,
   `net_amount_reporting`, `cogs_amount_reporting`, `fx_rate_to_reporting`, `fx_rate_as_of`) --
   no existing column was renamed or dropped, so this is a non-breaking migration. Rows
   materialized before Phase 8 simply have `NULL` in the new columns rather than a migration
   computing a conversion it can't verify against the original upload.
