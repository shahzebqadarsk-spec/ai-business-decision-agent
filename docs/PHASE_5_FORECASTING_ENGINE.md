# Phase 5: Forecasting Engine

This document is the reference for everything Phase 5 added: the self-scoping decision that
produced it, the forecasting methodology, data-sufficiency gating, the backtest diagnostic,
the Evidence integration (the first production use of `claim_type="inference"`), the API, the
UI, and what is deliberately deferred.

**Governing principle:** a forecast is an INFERENCE, never a FACT. Every forecasted point is a
statistical projection of future, not-yet-observed data, fit by a closed-form deterministic
method against the complete available canonical history — never an LLM call, never a number
the model invents. The UI and every generated claim say so explicitly, and never present a
point estimate or interval as a guaranteed outcome.

## 0. Scope decision: Phase 5 is Forecasting only

The spec's own Phase 5 label bundles forecasting, scenario/what-if analysis, decision scoring,
an AI narrator, a verifier, and chat orchestration into one phase. Following the same
disciplined narrow-scoping this project used in Phase 4 (which built only the issue-detection/
RCA slice of its own spec section and explicitly deferred procurement/overtime RCA), Phase 5
was independently scoped — by engineering judgment, per this project's standing instruction to
use that judgment wherever the governing spec text is ambiguous or too broad for one disciplined
increment — to the **Forecasting Engine only**. Scenario/what-if analysis, decision scoring,
the AI narrator, the verifier, and chat orchestration are explicitly **not** built here and are
left for later phases, each of which deserves its own full build-test-document cycle rather than
being rushed alongside this one.

## 1. Method: classical two-stage trend + seasonal decomposition

`backend/app/forecasting/model.py` implements a fully closed-form, deterministic method — no
ARIMA, no Prophet, no ML library, nothing stochastic or trained:

1. **Stage 1 — linear trend.** Ordinary least squares on `y = intercept + slope·t` (`t` = 0, 1,
   2, ... in observation order), ignoring seasonality.
2. **Stage 2 — seasonal indices.** Group the stage-1 residuals by calendar month (1-12) and
   average each group; center the 12 averages to sum to exactly zero (subtract their mean), so
   the seasonal component never biases the trend's own long-run level.
3. **Prediction** (`predict_point`): `intercept + slope·t + seasonal_indices[month(t)]` for any
   `t`, observed or future.
4. **Prediction intervals** (`predict_interval`): the standard OLS leverage-based formula,
   `se_pred(t) = residual_std · sqrt(1 + leverage(t))`, `leverage(t) = 1/n + (t − t̄)² / Σ(i − t̄)²`,
   `margin = Z[confidence_level] · se_pred(t)`. This is the reason the shaded band in the UI
   **visibly widens** the further a forecasted period sits past the historical window — a
   fixed `±X%` band would not have that property, and a linear trend extrapolated further from
   what it was fit on is honestly less certain.
   `Z_SCORES = {0.80: 1.2816, 0.90: 1.6449, 0.95: 1.9600, 0.99: 2.5758}` is hardcoded (two-sided
   normal critical values) because `scipy` is **not** a project dependency — confirmed by
   `python -c "import scipy"` failing with `ModuleNotFoundError`. `numpy`/`pandas` already are
   dependencies and are reused for the closed-form math and for independent cross-checks in
   tests, without adding anything new.
5. **Degrees of freedom**: `n_observations − 13` (2 trend parameters + 11 free seasonal
   parameters; the 12th seasonal index is fixed by the sum-to-zero constraint).

**A genuine, documented mathematical property — not a bug:** this two-stage method is *not* an
exact-reconstruction method in general. An arbitrary seasonal pattern sampled over a finite
window is not guaranteed to be orthogonal to the linear trend regressor, so stage 1's OLS trend
can absorb a small amount of the seasonal pattern, producing a small deterministic bias even
with zero noise. The exact condition under which this vanishes was derived and used to build an
orthogonality-safe test fixture (`season(m) == season(13 − m)` for every month, and
`Σ season(1..6) == 0`) specifically so one test could assert exact recovery; every other test
uses noisy, arbitrary-pattern data and cross-checks the result against an independent numpy
computation instead of expecting exactness. `tests/forecasting/test_model.py`'s own comments
carry the full derivation.

## 2. Scope: which metrics, which granularity, how far out

- **`FORECAST_METRICS = ("revenue", "sales_quantity", "cogs")`** — the three KPIs that are a
  single summed `fact_sales` column, matching Phase 3's KPI engine exactly. `gross_margin_pct`
  is deliberately excluded: it is a ratio of two independently-uncertain forecasts, and this
  method gives no rigorous way to combine their confidence intervals into one for the ratio.
  `gross_profit` is not independently fitted in v1 either (it would need its own seasonal
  pattern, not `revenue_forecast − cogs_forecast`, which would silently understate its
  uncertainty) — both are scope limitations, the same kind Phase 4 documented for procurement/
  overtime RCA, not oversights.
- **`FORECAST_GRANULARITIES = ("month",)`** — the seasonal model needs a clean 12-period annual
  cycle to estimate monthly seasonal indices; quarter/year forecasting would need its own
  calibration (a different seasonal period, different minimum-history rule) and is deferred.
- **`MIN_HORIZON_PERIODS = 1`, `MAX_HORIZON_PERIODS = 24`** — a linear trend extrapolated more
  than 2 years past 3 years of history stretches well past what this model can responsibly
  claim; this is a considered cap, not an arbitrary API limit.
- **A forecast is always "as of now, using everything available," never "for a caller-chosen
  window."** `sufficiency.check_history_sufficiency()` and `engine.generate_forecast()` always
  evaluate the complete canonical history for the metric — there is no parameter to forecast
  from an earlier cutoff. A forecast describes what the model can say today, not a
  re-creatable historical snapshot.

## 3. Data sufficiency

`backend/app/forecasting/sufficiency.py::check_history_sufficiency()`:

- **`MIN_HISTORY_PERIODS = 24`** (2 full annual cycles) — ensures every calendar month has at
  least 2 observations for a meaningful seasonal index, and keeps degrees of freedom
  comfortably positive (`24 − 13 = 11`).
- **Gap detection** — compares the expected contiguous list of calendar months against the
  months actually present and reports any missing month by name, rather than silently fitting
  across a hole in the data.
- Returns an explicit `status="insufficient_data"` with a human-readable `reason` whenever
  either check fails — `generate_forecast()` persists this as a `ForecastRun` with
  `status="insufficient_data"` and **zero** `Forecast` rows, never a fabricated result. The API
  surfaces this as a 200 with that status (not a 4xx — "we checked and there isn't enough data"
  is itself a valid, informative answer), and the UI shows the reason verbatim.

## 4. Backtest / holdout diagnostic

`backend/app/forecasting/backtest.py::run_backtest()`, `DEFAULT_HOLDOUT_PERIODS = 6`: refits the
model on history **minus** the last 6 observations, measures MAE and MAPE% against those
held-out actuals, and the result is persisted on `ForecastRun.holdout_mae` /
`holdout_mape_pct` / `holdout_periods` purely as a **transparency diagnostic** — "here is roughly
how wrong this method was on data it didn't get to see." It never changes which fit produces
the delivered forecast; that one is always refit on the complete history, as in section 2.
Returns `None` (not a fabricated number) when there isn't enough history to hold out 6 periods
and still meet `MIN_HISTORY_FOR_FIT`, and `mape_pct=None` specifically when every held-out
actual is exactly zero (percentage error undefined, not infinite).

## 5. Evidence integration

Two nullable foreign keys were added to the existing `Evidence` model (mirroring the existing
`analysis_run_id`/`issue_id` pattern from Phase 4): `forecast_run_id`, `forecast_id`. Every
`generate_forecast()` call writes:

- **One `claim_type="fact"` Evidence row per run** (`forecast_run_id` set, `forecast_id` null),
  describing the fit itself — trend/seasonal parameters and the backtest diagnostic. This is a
  FACT because it describes what was actually fit, not a projection.
- **One `claim_type="inference"` Evidence row per forecasted point** (`forecast_id` set),
  always naming the metric, period, point estimate, and confidence interval, and always
  containing the literal phrase *"not a fact and not a guaranteed outcome"*. This is the first
  production use of `claim_type="inference"` — Phase 4 reserved the enum value specifically for
  this purpose and never produced one itself.

## 6. Data model

- **`ForecastRun`**: metric, granularity, `history_start_period`/`history_end_period`/
  `history_periods`, `horizon_periods`, `status` (`completed` | `insufficient_data`),
  `status_reason`, `method_name`/`method_version`, `parameters` (JSON: intercept, slope,
  seasonal indices, residual std, degrees of freedom), `confidence_level`, `holdout_periods`/
  `holdout_mae`/`holdout_mape_pct`, `source_file_ids`, `created_at`.
- **`Forecast`**: `forecast_run_id` (FK), metric, `period_key`, `horizon_index` (1-based),
  `point_estimate`, `lower_bound`, `upper_bound`. Has its own `CHECK (metric IN (...))`
  constraint, hand-added to the migration — Alembic's autogenerate reliably catches a
  CheckConstraint on a **brand-new table** (`forecast_runs`) but misses one on an **existing
  table's altered column** (`forecasts.metric`), the same gap observed in every prior phase's
  migration.

## 7. API

All endpoints are under `/api/v1`, take a validated Pydantic model, and never accept a
caller-supplied history window (section 2):

| Method | Path | Purpose |
|---|---|---|
| POST | `/forecasts/generate` | `{metric, horizon_periods, confidence_level}` → fit against the complete history, persist the run + forecasts + Evidence |
| GET | `/forecasts/runs` | List past runs (optional `?metric=`) |
| GET | `/forecasts/runs/{run_id}` | One run with its forecasted points and Evidence IDs |
| GET | `/evidence/{evidence_id}` | Reused unchanged from Phase 4 — one Evidence row, full lineage, for a forecast's fact or inference records too |

An unknown metric or an unsupported `confidence_level` returns `400`; an out-of-range
`horizon_periods` is rejected by Pydantic's own field validation (`422`) before the engine is
ever called.

## 8. UI

`frontend/src/pages/ForecastPage.tsx` ("Forecasting" tab): metric / horizon / confidence-level
controls and a "Generate forecast" action; a list of past runs for the selected metric; and,
once a run exists:

- **`ForecastChart`** (Recharts) — historical actuals (solid line) feeding into the forecasted
  horizon (dashed line) with a shaded prediction-interval band that visibly widens with
  distance from the historical window, matching section 1's leverage-based formula. The forecast
  API itself only returns the fitted/forecasted points, not the historical actuals it was fit
  on, so the historical series is reached the same way the Executive Dashboard's own revenue
  trend chart reaches it — Phase 3's generic KPI breakdown endpoint
  (`POST /kpis/{metric}/breakdown`, `dimension="month"`) — one call per calendar year (the
  public API only resolves a single year's `period_key` at a time), merged chronologically by
  `useHistoricalSeries`.
- A forecasted-periods table (point estimate, interval, a link to that point's Evidence).
- A fit-diagnostics panel (history window used, method/version, holdout MAE/MAPE%) and a link
  to the run's own fact-Evidence record.
- `EvidenceDrawer`/`ClaimTypeBadge` — **relocated** from `components/rca/` to
  `components/evidence/`, since Evidence is shared by RCA and Forecasting (and will be by any
  later phase), not RCA-specific. `types/rca.ts`'s own `Evidence`/`ClaimType` exports and
  `useRca.ts`'s `useEvidence` are kept as re-exports of the new shared modules
  (`types/evidence.ts`, `api/evidence.ts`, `hooks/useEvidence.ts`) so no existing RCA import
  site needed to change.

## 9. A pre-existing test-suite fragility this phase exposed and fixed

Adding `tests/forecasting/` surfaced a latent bug in the test suite's own design, not in the
forecasting engine: the session-scoped `seeded_fact_sales_file_id` fixture
(`tests/conftest.py`), shared by `tests/kpi/`, `tests/rca/`, and now `tests/forecasting/`, wipes
and reloads `fact_sales` with the clean seed-42 dataset the first time any test requests it —
and its own docstring explicitly assumed Phase 2's `tests/ingestion/` tests (which materialize
their own small, never-cleaned-up synthetic slices into the same table) would already have run
and finished by then, so that wipe clears their leftover pollution first. This was only ever
true **by accident of pytest's default alphabetical directory-collection order**
(`ingestion` < `kpi`, `rca`). `tests/forecasting/` sorts as `f`, before `ingestion`'s `i` — so
in a true full-suite run it triggered the fixture first, loading clean data, and ingestion's
tests then ran afterward and re-polluted the table, corrupting the company-wide sums every
kpi/rca test depends on (19 previously-passing tests failed). Fixed with an explicit
`pytest_collection_modifyitems` hook in `tests/conftest.py` that sorts `tests/ingestion/` items
first regardless of any other directory's name, so this dependency is no longer an accident of
naming.

## 10. Testing and verification

39 new backend tests (`tests/forecasting/`): pure math (`test_model.py`, cross-checked against
independent numpy computations), the backtest helper (`test_backtest.py`), DB-backed
sufficiency checks against the real seed-42 data (`test_sufficiency.py`), orchestration/
persistence (`test_engine.py`), and the HTTP layer (`test_api.py`, including that forecast
Evidence is reachable via the generic `/evidence/{id}` endpoint and reads as `inference`). Full
backend regression: **299/299 passing**, ruff + mypy `--strict` clean. 2 new frontend tests
(`ForecastChart.test.tsx`); full frontend suite **18/18 passing**, ESLint + `tsc` clean. Live
smoke-tested against the real dev database: `POST /forecasts/generate` for `revenue`/6 months
returns a `completed` run with a sensible trend+seasonal fit, a backtest MAPE ≈ 3.8%, and every
forecasted point's Evidence reachable and correctly typed `inference` with the required
"not a fact and not a guaranteed outcome" language.
