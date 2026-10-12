# Phase 6: Scenario / What-If Analysis Engine

This document is the reference for everything Phase 6 added: the self-scoping decision that
produced it, the scenario methodology, why it deliberately writes no Evidence, the data model,
the API, the UI, and a real pre-existing bug this phase exposed and fixed.

**Governing principle:** a scenario is a HYPOTHETICAL the user is constructing to explore, not
a claim this system is making about reality. Every scenario number is a plain, deterministic
percentage shock applied to an existing Phase 5 baseline forecast, with `gross_profit`/
`gross_margin_pct` re-derived using the exact formulas Phase 3/4 already use for those metrics
— never a new statistical fit, never an LLM call, and never persisted as Evidence.

## 0. Scope decision: Phase 6 is Scenario / What-If Analysis only

Approved to proceed following Phase 5's completion report, with the explicit instruction "no
formal spec needed — use your own judgment." The spec's remaining bundle (scenario/what-if
analysis, decision scoring, the AI narrator, the verifier, chat orchestration) is still too
broad for one disciplined increment, so — following the same narrow-scoping discipline Phase 4
and Phase 5 both used on their own slice of the spec — this phase was scoped to **Scenario /
What-If Analysis only**. Decision scoring, the AI narrator, the verifier, and chat
orchestration remain explicitly deferred. This also follows the pipeline order the README's
own banner states (`DATA -> INSIGHT -> ROOT CAUSE -> FORECAST -> WHAT-IF -> DECISION ->
RECOMMENDATION -> EVIDENCE`): WHAT-IF is the next stage immediately after FORECAST.

## 1. Method: a percentage shock on an existing forecast, not a new fit

`backend/app/scenarios/engine.py::generate_scenario()`:

1. Resolve a baseline `ForecastRun` for `revenue` and for `cogs` — either the run id the
   caller supplied, or (if omitted) the most recently generated **completed** run for that
   metric, the same "use everything available" principle Phase 5 itself uses.
2. For every period present in either baseline's forecasted points: `scenario_value =
   baseline_value * (1 + adjustment_pct / 100)`. An adjustment of `0.0` (the default) leaves
   the scenario value identical to the baseline.
3. **Derived metrics, never independently shocked:** wherever *both* a revenue and a cogs
   baseline exist for the same period, `gross_profit = revenue - cogs` and
   `gross_margin_pct = gross_profit / revenue * 100` are computed for both the baseline and the
   scenario values — the identical formulas `app/kpi/calculators.py::calculate_gross_profit`/
   `calculate_gross_margin_pct` already use. Margin % is `None` (never fabricated as 0 or
   infinity) whenever its own period's revenue is exactly zero, matching that same calculator's
   own zero-denominator guard.
4. A scenario can legitimately adjust only one driver (e.g. revenue) and leave the other
   unadjusted (`0.0%`), or have no baseline at all for the other driver — in the latter case,
   the derived metrics for that period are simply never produced (sufficiency-gated, never
   fabricated from a half-missing input), not an error.
5. **`status="insufficient_data"`** (zero `ScenarioResult` rows) only when *neither* driver has
   any completed baseline forecast at all — the API surfaces this as a 200 with the status and
   a `status_reason` telling the caller to generate a forecast first, the same "this is itself a
   valid, informative answer" pattern Phase 5 established for its own sufficiency gate.

This is a deliberately simple method: a scenario is "what if growth/cost run `X`% hotter/colder
than the baseline trend already predicts," not a new, independently fitted alternate future. A
more elaborate approach (re-fitting a whole new trend+seasonal model under a shocked assumption)
would need its own calibration and its own sufficiency/backtest story — explicitly out of scope
for this increment, the same way Phase 5 kept a quarter/year forecast out of its own scope.

## 2. Why a scenario writes no Evidence

Phase 4 defined Evidence as backing a typed claim about what the deterministic analytics
measured (`fact`/`contribution`) or inferred (`inference`) about the real world. A scenario is
none of these — it is an explicit counterfactual the user is actively constructing ("what if
revenue grew 5% faster"), not a measurement or a projection this system is asserting. Writing it
as Evidence would blur what "Evidence" means everywhere else in the system. Every number is
still fully traceable — just via `ScenarioResult` rows and the `Scenario.revenue_forecast_run_id`/
`cogs_forecast_run_id` references to the Phase 5 `ForecastRun`s they were built from, rather
than via the `Evidence` table.

## 3. Data model

Phase 0 reserved a `Scenario` placeholder table (`name`, `description`, two opaque JSON blobs:
`assumptions`, `projected_impact`). Phase 6 replaces it with a real, normalized pair — the same
way Phase 5 replaced the Phase 0 `Forecast` placeholder — rather than filling the opaque JSON
blobs in:

- **`Scenario`**: name, description, `revenue_growth_adjustment_pct`/`cogs_adjustment_pct`
  (explicit numeric columns, not a JSON "assumptions" blob — consistent with this project's
  "every number traceable" ethos), `revenue_forecast_run_id`/`cogs_forecast_run_id` (nullable
  FKs to `forecast_runs`, `ON DELETE SET NULL` — deleting an old forecast run must never
  silently delete a scenario that was built on it, only lose its own traceability link),
  `status` (`completed` | `insufficient_data`), `status_reason`, `horizon_periods`.
- **`ScenarioResult`**: one (metric, period) row — `scenario_id` (FK), `metric` (one of
  `revenue`/`cogs`/`gross_profit`/`gross_margin_pct`), `period_key`, `horizon_index`,
  `baseline_value` (nullable — `None` only for a derived metric missing one of its two
  inputs), `scenario_value`, `delta_absolute`, `delta_percentage` (`None` when
  `baseline_value` is exactly zero, division undefined).
- **`DecisionOption`** (Phase 0 placeholder, still untouched, still deferred) continues to
  point at `scenarios.id` via its own `scenario_id` FK — the table name and primary key never
  moved, so that placeholder needed no change.

As with every prior phase's migration, Alembic's autogenerate caught the CheckConstraint on the
brand-new `scenario_results.metric` column automatically but missed the one on the *existing*
`scenarios` table's altered `status` column — hand-added, same recurring gap.

## 4. API

All endpoints are under `/api/v1`, take a validated Pydantic model or a plain path parameter:

| Method | Path | Purpose |
|---|---|---|
| POST | `/scenarios` | `{name, description?, revenue_growth_adjustment_pct?, cogs_adjustment_pct?, revenue_forecast_run_id?, cogs_forecast_run_id?}` → compute and persist a scenario |
| GET | `/scenarios` | List scenarios, most recent first |
| GET | `/scenarios/{id}` | One scenario with all its `ScenarioResult` rows |

An explicit `revenue_forecast_run_id`/`cogs_forecast_run_id` that doesn't exist, or that names
a run for the wrong metric, returns `400`. An adjustment outside `[-100, 1000]` is rejected by
Pydantic's own field validation (`422`) before the engine is ever called — `-100%` is the floor
because revenue/cogs cannot meaningfully go negative under a plain percentage multiplier.

## 5. UI

`frontend/src/pages/ScenarioPage.tsx` ("Scenario / What-If" tab): a name field, revenue/COGS
adjustment-percentage inputs, and — reusing Phase 5's own `useForecastRuns` hook — a dropdown
per driver to pick a specific baseline forecast run or leave it on "latest completed (auto)". A
"Run scenario" action, a list of previously run scenarios, a metric selector, and:

- **`ScenarioChart`** (Recharts) — baseline vs. scenario lines for the selected metric.
  Deliberately has **no** confidence band, unlike `ForecastChart`: a scenario is a
  deterministic hypothetical the user chose, not a statistically fitted estimate, so there is
  no interval to draw.
- A full results table (metric, period, baseline, scenario, delta %).

## 6. A real pre-existing bug this phase exposed and fixed

Running the new scenario tests as part of the full suite (not in isolation) surfaced a genuine,
previously-invisible bug in `tests/kpi/test_calculators.py`: its `sparse_cogs_period` and
`zero_quantity_period` fixtures each inserted a handful of synthetic rows into the shared
`fact_sales` table at far-future months (`2097-01`, `2098-06`) to exercise an edge case, and
then called `db_session.commit()` — permanently leaving those rows in the shared test database
for the rest of the pytest session, with no cleanup. This was invisible for three whole phases
(3, 4, 5) because nothing ever queried `fact_sales`'s *whole-table* min/max month range — every
KPI calculation and RCA detector works against a specific, bounded period window. Phase 5's
`check_history_sufficiency()` is the first code in the project to query that whole-table range
(`app/kpi/aggregations.py::full_month_range`), and once it did, those two leftover far-future
rows silently stretched the "expected contiguous months" window out to 2098, triggering a
"massive gaps detected" `insufficient_data` result for every forecast (and therefore every
scenario built on one) generated anywhere later in the same full-suite run. **Fixed** by
changing both fixtures from `commit()` to `flush()` — the tests that use them only ever read
through the same `db_session` object within the same transaction, so a flush was always
sufficient, and the fixture's own `session.rollback()` teardown now discards the rows exactly
as it already does for every similar edge-case fixture elsewhere in the suite. This is a
genuine bug in the test suite's own design (now fixed), not a defect in the Scenario engine or
in Phase 5's forecasting engine.

## 7. Testing and verification

23 new backend tests (`tests/scenarios/`): engine math and sufficiency-gating against the real
seed-42 data with explicit, self-contained control over which `ForecastRun` rows exist for each
test (`test_engine.py`, including a directly-constructed zero-baseline-revenue edge case for the
margin-undefined guard), and the HTTP layer (`test_api.py`). Full backend regression:
**313/313 passing**, ruff + mypy `--strict` clean. 2 new frontend tests (`ScenarioChart.test.tsx`);
full frontend suite **20/20 passing**, ESLint + `tsc` clean. Live smoke-tested against the real
dev database: generated revenue/COGS baseline forecasts, ran an 8%/−3% scenario, and confirmed
`gross_profit`/`gross_margin_pct` re-derive correctly from the adjusted values at every period.
