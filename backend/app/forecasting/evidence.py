"""Builds and persists `Evidence` rows for forecasts (Phase 5).

A forecasted value is this system's first genuinely INFERENCE claim -- Phase 4 already
reserved that `claim_type` on `Evidence` for exactly this use (its module docstring names
`inference` as a claim type Phase 4 itself never produces). It is an extrapolation beyond
observed data, never a FACT or a measured CONTRIBUTION, and the claim text says so explicitly
-- always reporting the interval alongside the point estimate, never a bare number dressed up
as certain. Same no-calculation-here rule as `app/rca/evidence.py`: this module only formats
and persists numbers `engine.py` already computed.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.db.models.analysis import Evidence
from app.db.models.forecasting import Forecast

FORECASTING_CALCULATION_VERSION = "1.0.0"


def record_forecast_point(
    session: Session,
    *,
    forecast_run_id: uuid.UUID,
    forecast: Forecast,
    confidence_level: float,
    method_name: str,
    method_version: str,
) -> Evidence:
    interval_text = (
        f"{confidence_level:.0%} interval: {forecast.lower_bound:,.2f} to {forecast.upper_bound:,.2f}"
        if forecast.lower_bound is not None and forecast.upper_bound is not None
        else "no interval available"
    )
    claim = (
        f"Projected {forecast.metric} for {forecast.period_key} is {forecast.point_estimate:,.2f} "
        f"({interval_text}), based on a trend+seasonal model fitted to historical canonical "
        f"data. This is a statistical projection of future, not-yet-observed data -- not a "
        f"fact and not a guaranteed outcome."
    )
    evidence = Evidence(
        forecast_run_id=forecast_run_id,
        forecast_id=forecast.id,
        claim_type="inference",
        claim=claim,
        metric=forecast.metric,
        granularity="month",
        period_key=forecast.period_key,
        value=forecast.point_estimate,
        calculation_name=method_name,
        calculation_version=method_version,
        calculation_parameters={
            "confidence_level": confidence_level,
            "horizon_index": forecast.horizon_index,
        },
        quality_metadata={"lower_bound": forecast.lower_bound, "upper_bound": forecast.upper_bound},
    )
    session.add(evidence)
    session.flush()
    return evidence


def record_fit_summary(
    session: Session,
    *,
    forecast_run_id: uuid.UUID,
    method_name: str,
    method_version: str,
    parameters: dict[str, object],
    holdout_mae: float | None,
    holdout_mape_pct: float | None,
) -> Evidence:
    """One FACT evidence row per run describing the fitted model itself (trend, seasonal
    indices, backtest error) -- not a forecasted value, but the methodology every forecasted
    value in the run was produced by."""
    backtest_text = (
        f"backtest MAE {holdout_mae:,.2f}, MAPE {holdout_mape_pct:.1f}%"
        if holdout_mae is not None and holdout_mape_pct is not None
        else "backtest not available (insufficient history to hold out a diagnostic window)"
    )
    claim = f"Forecast model fitted using {method_name} v{method_version} ({backtest_text})."
    evidence = Evidence(
        forecast_run_id=forecast_run_id,
        claim_type="fact",
        claim=claim,
        calculation_name=method_name,
        calculation_version=method_version,
        calculation_parameters=parameters,
        quality_metadata={"holdout_mae": holdout_mae, "holdout_mape_pct": holdout_mape_pct},
    )
    session.add(evidence)
    session.flush()
    return evidence


__all__ = ["FORECASTING_CALCULATION_VERSION", "record_fit_summary", "record_forecast_point"]
