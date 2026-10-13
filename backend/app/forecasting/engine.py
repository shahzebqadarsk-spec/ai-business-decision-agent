"""Orchestration: resolves the complete available history for a metric, checks sufficiency,
fits the trend+seasonal model, backtests it, and persists a `ForecastRun` + one `Forecast` row
per future period, with Evidence for every forecasted point plus one FACT row describing the
fit itself (Phase 5).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models.canonical import FactSales
from app.db.models.forecasting import FORECAST_METRICS, Forecast, ForecastRun
from app.forecasting import backtest as bt
from app.forecasting import evidence as ev
from app.forecasting import model as fm
from app.forecasting.sufficiency import check_history_sufficiency
from app.kpi import aggregations as agg

METHOD_NAME = "linear_trend_additive_seasonal"
METHOD_VERSION = "1.0.0"

MIN_HORIZON_PERIODS = 1
# A linear trend extrapolated more than 2 years past 3 years of history stretches well past
# what the model can responsibly claim -- a deliberate cap, not an arbitrary API limit.
MAX_HORIZON_PERIODS = 24

_METRIC_COLUMNS = {
    "revenue": FactSales.net_amount_reporting,
    "sales_quantity": FactSales.quantity,
    "cogs": FactSales.cogs_amount_reporting,
}


class UnknownMetricError(ValueError):
    pass


class InvalidForecastRequestError(ValueError):
    pass


def _period_key_after(last_period_key: str, h: int) -> str:
    year, month = (int(x) for x in last_period_key.split("-"))
    total = year * 12 + (month - 1) + h
    y, m0 = divmod(total, 12)
    return f"{y:04d}-{m0 + 1:02d}"


def generate_forecast(
    session: Session,
    metric: str,
    horizon_periods: int,
    *,
    confidence_level: float = 0.8,
    holdout_periods: int = bt.DEFAULT_HOLDOUT_PERIODS,
    persist: bool = True,
    client_id: str | None = None,
) -> ForecastRun:
    if metric not in _METRIC_COLUMNS:
        raise UnknownMetricError(
            f"'{metric}' is not a forecastable metric; expected one of {FORECAST_METRICS}."
        )
    if not (MIN_HORIZON_PERIODS <= horizon_periods <= MAX_HORIZON_PERIODS):
        raise InvalidForecastRequestError(
            f"horizon_periods must be between {MIN_HORIZON_PERIODS} and {MAX_HORIZON_PERIODS}."
        )
    if confidence_level not in fm.Z_SCORES:
        raise InvalidForecastRequestError(
            f"confidence_level must be one of {sorted(fm.Z_SCORES)}; got {confidence_level}."
        )

    column = _METRIC_COLUMNS[metric]
    sufficiency = check_history_sufficiency(session, column, client_id=client_id)

    if sufficiency.status != "sufficient":
        run = ForecastRun(
            client_id=client_id,
            metric=metric,
            granularity="month",
            history_start_period="",
            history_end_period="",
            history_periods=0,
            horizon_periods=horizon_periods,
            status="insufficient_data",
            status_reason=sufficiency.reason,
            method_name=METHOD_NAME,
            method_version=METHOD_VERSION,
            confidence_level=confidence_level,
        )
        session.add(run)
        session.flush()
        if persist:
            session.commit()
        return run

    history = sufficiency.history
    values = [v for _, v in history]
    fit = fm.fit_trend_seasonal(values, sufficiency.start_month)
    backtest_result = bt.run_backtest(values, sufficiency.start_month, holdout_periods=holdout_periods)

    assert sufficiency.window is not None
    source_files = agg.source_file_ids(session, sufficiency.window)

    run = ForecastRun(
        client_id=client_id,
        metric=metric,
        granularity="month",
        history_start_period=history[0][0],
        history_end_period=history[-1][0],
        history_periods=len(history),
        horizon_periods=horizon_periods,
        status="completed",
        method_name=METHOD_NAME,
        method_version=METHOD_VERSION,
        confidence_level=confidence_level,
        parameters={
            "intercept": fit.intercept,
            "slope": fit.slope,
            "seasonal_indices": {str(k): v for k, v in fit.seasonal_indices.items()},
            "residual_std": fit.residual_std,
            "degrees_of_freedom": fit.degrees_of_freedom,
        },
        holdout_periods=backtest_result.holdout_periods if backtest_result else None,
        holdout_mae=backtest_result.mae if backtest_result else None,
        holdout_mape_pct=backtest_result.mape_pct if backtest_result else None,
        source_file_ids=list(source_files),
    )
    session.add(run)
    session.flush()

    ev.record_fit_summary(
        session,
        forecast_run_id=run.id,
        method_name=METHOD_NAME,
        method_version=METHOD_VERSION,
        parameters=run.parameters,
        holdout_mae=run.holdout_mae,
        holdout_mape_pct=run.holdout_mape_pct,
    )

    n = fit.n_observations
    for h in range(1, horizon_periods + 1):
        t = n - 1 + h
        point = fm.predict_point(fit, t)
        lower, upper = fm.predict_interval(fit, t, confidence_level)
        period_key = _period_key_after(history[-1][0], h)
        forecast = Forecast(
            forecast_run_id=run.id,
            metric=metric,
            period_key=period_key,
            horizon_index=h,
            point_estimate=point,
            lower_bound=lower,
            upper_bound=upper,
        )
        session.add(forecast)
        session.flush()
        ev.record_forecast_point(
            session,
            forecast_run_id=run.id,
            forecast=forecast,
            confidence_level=confidence_level,
            method_name=METHOD_NAME,
            method_version=METHOD_VERSION,
        )

    if persist:
        session.commit()
    return run


__all__ = [
    "MAX_HORIZON_PERIODS",
    "MIN_HORIZON_PERIODS",
    "METHOD_NAME",
    "METHOD_VERSION",
    "InvalidForecastRequestError",
    "UnknownMetricError",
    "generate_forecast",
]
