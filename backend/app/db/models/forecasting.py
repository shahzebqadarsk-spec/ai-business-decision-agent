"""Phase 5: deterministic forecasting (replaces the Phase 0 `Forecast` placeholder that lived
in `app/db/models/analysis.py`).

Scope decision (independent judgment, no formal spec for this phase -- see
`docs/PHASE_5_FORECASTING_ENGINE.md`): only a single-metric, month-granularity trend+seasonal
model is implemented. Scenario ("what-if") analysis, decision scoring, the AI narrator, the
verifier, and chat orchestration were explicitly deferred to later phases at the time this file
was written, the same way Phase 4 deferred procurement/overtime RCA. (Historical note, not kept
current here as later phases land: `Scenario` was itself a Phase 0 placeholder in
`app/db/models/analysis.py` until Phase 6 replaced it with `app/db/models/scenario.py`, and
`DecisionOption` was a Phase 0 placeholder there until Phase 7 replaced it with
`app/db/models/decision.py` -- see those files' own module docstrings for the current state.)

`ForecastRun` is one fit of the model (one metric, one historical window, one horizon);
`Forecast` is one forecasted future period belonging to a run. Every forecasted point also gets
an `Evidence` row with `claim_type="inference"` (Evidence already reserved this claim type in
Phase 4 for exactly this use -- a forecast is the first genuinely inferential claim this system
produces, as opposed to Phase 3/4's FACT/CONTRIBUTION claims about data that already happened).
"""

from __future__ import annotations

import uuid

from sqlalchemy import JSON, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin, check_in, enum_column

# Only metrics Phase 3's KPI engine can compute directly from fact_sales (a single summed
# column, no ratio) are forecastable in v1 -- gross_margin_pct is a ratio of two uncertain
# forecasts and is deliberately not forecast directly (see docs/PHASE_5_FORECASTING_ENGINE.md
# section on derived metrics); gross_profit is exposed as a *derived* point estimate
# (ΔGP = Revenue - COGS applied to the two independently-fit forecasts) without its own fitted
# model or persisted rows.
FORECAST_METRICS = ("revenue", "sales_quantity", "cogs")

# Month-only in v1: the seasonal model needs a clean, equal-length annual cycle (12), which a
# quarter/year granularity would need a different cycle length and its own calibration to
# support well. Documented scope limitation, not an oversight.
FORECAST_GRANULARITIES = ("month",)

FORECAST_RUN_STATUSES = ("completed", "insufficient_data")


class ForecastRun(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """One execution of the forecasting engine for one metric. Reproducible by construction:
    `metric` + `granularity` + `history_start_period`/`history_end_period` + `horizon_periods`
    is enough to redo it -- the engine is a pure function of canonical `fact_sales` data, same
    as Phase 4's `AnalysisRun`."""

    __tablename__ = "forecast_runs"
    __table_args__ = (
        check_in("metric", FORECAST_METRICS, constraint_name="metric_valid"),
        check_in("granularity", FORECAST_GRANULARITIES, constraint_name="granularity_valid"),
        check_in("status", FORECAST_RUN_STATUSES, constraint_name="status_valid"),
    )

    # Phase 9: which client this forecast was generated for. Nullable only for backward
    # compatibility with pre-Phase-9 rows; `GET /forecasts/runs` filters on this, and
    # app/scenarios/engine.py uses it to pick "the latest completed run for this client".
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("clients.id", ondelete="SET NULL"), nullable=True, index=True
    )

    metric: Mapped[str] = enum_column(length=32)
    granularity: Mapped[str] = enum_column(length=16)
    history_start_period: Mapped[str] = mapped_column(String(32))
    history_end_period: Mapped[str] = mapped_column(String(32))
    history_periods: Mapped[int] = mapped_column()
    horizon_periods: Mapped[int] = mapped_column()

    status: Mapped[str] = enum_column(length=24, default="completed")
    status_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    method_name: Mapped[str] = mapped_column(String(64))
    method_version: Mapped[str] = mapped_column(String(32))
    # Trend intercept/slope, seasonal indices, confidence_level, min-history threshold used --
    # the full fitted model, persisted so a re-read never has to refit to explain itself.
    parameters: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)

    confidence_level: Mapped[float] = mapped_column(Numeric(4, 3), default=0.8)

    # Backtest diagnostics (see app/forecasting/backtest.py) -- `None` when history was too
    # short to hold out a diagnostic window; never fabricated as 0.
    holdout_periods: Mapped[int | None] = mapped_column(nullable=True)
    holdout_mae: Mapped[float | None] = mapped_column(Numeric(24, 4), nullable=True)
    holdout_mape_pct: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)

    source_file_ids: Mapped[list[str]] = mapped_column(JSON, default=list)


class Forecast(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """One forecasted future period belonging to a `ForecastRun`. `point_estimate` is the
    model's central projection; `lower_bound`/`upper_bound` is a prediction interval at the
    run's `confidence_level`, derived from the fit's own residual standard error -- never a
    made-up +/-X% band."""

    __tablename__ = "forecasts"
    __table_args__ = (check_in("metric", FORECAST_METRICS, constraint_name="metric_valid"),)

    forecast_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("forecast_runs.id", ondelete="CASCADE"), index=True
    )
    metric: Mapped[str] = enum_column(length=32)
    period_key: Mapped[str] = mapped_column(String(32), index=True)
    horizon_index: Mapped[int] = mapped_column()  # 1-based: 1 is the first period past history

    point_estimate: Mapped[float] = mapped_column(Numeric(24, 4))
    lower_bound: Mapped[float | None] = mapped_column(Numeric(24, 4), nullable=True)
    upper_bound: Mapped[float | None] = mapped_column(Numeric(24, 4), nullable=True)


__all__ = [
    "FORECAST_GRANULARITIES",
    "FORECAST_METRICS",
    "FORECAST_RUN_STATUSES",
    "Forecast",
    "ForecastRun",
]
