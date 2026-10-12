"""Orchestration: resolves the baseline revenue/COGS forecast (the caller's choice of
`ForecastRun`, or the latest completed run for that metric if not given), applies the
requested percentage shocks, re-derives gross_profit/gross_margin_pct from the two
(possibly-adjusted) series using Phase 3/4's own formulas, and persists one `Scenario` + one
`ScenarioResult` row per (metric, period)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.forecasting import Forecast, ForecastRun
from app.db.models.scenario import Scenario, ScenarioResult

DRIVER_METRICS = ("revenue", "cogs")
DERIVED_METRICS = ("gross_profit", "gross_margin_pct")


class InvalidScenarioRequestError(ValueError):
    pass


def _latest_completed_run(session: Session, metric: str) -> ForecastRun | None:
    """ "Use everything available" the same way Phase 5 itself does: if the caller doesn't name
    a specific baseline run, the most recently generated completed one for that metric is it."""
    return session.execute(
        select(ForecastRun)
        .where(ForecastRun.metric == metric, ForecastRun.status == "completed")
        .order_by(ForecastRun.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def _resolve_run(session: Session, metric: str, run_id: uuid.UUID | None) -> ForecastRun | None:
    if run_id is None:
        return _latest_completed_run(session, metric)
    run = session.get(ForecastRun, run_id)
    if run is None or run.metric != metric:
        raise InvalidScenarioRequestError(f"'{run_id}' is not a completed '{metric}' forecast run.")
    return run


def _points_by_period(session: Session, run_id: uuid.UUID) -> dict[str, tuple[float, int]]:
    """Numeric columns come back as `decimal.Decimal` once read back from the DB (same gap
    documented in `app/rca/engine.py`'s own `_analyze_product_margin_deterioration` -- explicit
    `float()` cast is required at every read, not just at the one spot a bug happened to
    surface before)."""
    rows = session.execute(select(Forecast).where(Forecast.forecast_run_id == run_id)).scalars().all()
    return {f.period_key: (float(f.point_estimate), f.horizon_index) for f in rows}


def _delta(baseline: float | None, scenario: float) -> tuple[float | None, float | None]:
    if baseline is None:
        return None, None
    delta_absolute = scenario - baseline
    delta_percentage = (delta_absolute / baseline * 100) if baseline else None
    return delta_absolute, delta_percentage


def _add_result(
    session: Session,
    *,
    scenario_id: uuid.UUID,
    metric: str,
    period_key: str,
    horizon_index: int,
    baseline_value: float | None,
    scenario_value: float,
) -> None:
    delta_absolute, delta_percentage = _delta(baseline_value, scenario_value)
    session.add(
        ScenarioResult(
            scenario_id=scenario_id,
            metric=metric,
            period_key=period_key,
            horizon_index=horizon_index,
            baseline_value=baseline_value,
            scenario_value=scenario_value,
            delta_absolute=delta_absolute,
            delta_percentage=delta_percentage,
        )
    )


def generate_scenario(
    session: Session,
    *,
    name: str,
    description: str | None = None,
    revenue_growth_adjustment_pct: float = 0.0,
    cogs_adjustment_pct: float = 0.0,
    revenue_forecast_run_id: uuid.UUID | None = None,
    cogs_forecast_run_id: uuid.UUID | None = None,
    persist: bool = True,
) -> Scenario:
    revenue_run = _resolve_run(session, "revenue", revenue_forecast_run_id)
    cogs_run = _resolve_run(session, "cogs", cogs_forecast_run_id)

    if revenue_run is None and cogs_run is None:
        scenario = Scenario(
            name=name,
            description=description,
            revenue_growth_adjustment_pct=revenue_growth_adjustment_pct,
            cogs_adjustment_pct=cogs_adjustment_pct,
            status="insufficient_data",
            status_reason=(
                "No completed forecast run exists for revenue or cogs. Generate a forecast "
                "(POST /forecasts/generate) for at least one of these metrics first."
            ),
            horizon_periods=0,
        )
        session.add(scenario)
        session.flush()
        if persist:
            session.commit()
        return scenario

    revenue_points = _points_by_period(session, revenue_run.id) if revenue_run is not None else {}
    cogs_points = _points_by_period(session, cogs_run.id) if cogs_run is not None else {}
    all_periods = sorted(set(revenue_points) | set(cogs_points))

    scenario = Scenario(
        name=name,
        description=description,
        revenue_growth_adjustment_pct=revenue_growth_adjustment_pct,
        cogs_adjustment_pct=cogs_adjustment_pct,
        revenue_forecast_run_id=revenue_run.id if revenue_run is not None else None,
        cogs_forecast_run_id=cogs_run.id if cogs_run is not None else None,
        status="completed",
        horizon_periods=len(all_periods),
    )
    session.add(scenario)
    session.flush()

    for period in all_periods:
        rev_entry = revenue_points.get(period)
        cogs_entry = cogs_points.get(period)
        rev_baseline, rev_h = rev_entry if rev_entry is not None else (None, None)
        cogs_baseline, cogs_h = cogs_entry if cogs_entry is not None else (None, None)
        horizon_index = rev_h if rev_h is not None else cogs_h
        assert horizon_index is not None  # period came from the union of the two dicts' keys

        rev_scenario = (
            rev_baseline * (1 + revenue_growth_adjustment_pct / 100) if rev_baseline is not None else None
        )
        cogs_scenario = cogs_baseline * (1 + cogs_adjustment_pct / 100) if cogs_baseline is not None else None

        if rev_baseline is not None and rev_scenario is not None:
            _add_result(
                session,
                scenario_id=scenario.id,
                metric="revenue",
                period_key=period,
                horizon_index=horizon_index,
                baseline_value=rev_baseline,
                scenario_value=rev_scenario,
            )
        if cogs_baseline is not None and cogs_scenario is not None:
            _add_result(
                session,
                scenario_id=scenario.id,
                metric="cogs",
                period_key=period,
                horizon_index=horizon_index,
                baseline_value=cogs_baseline,
                scenario_value=cogs_scenario,
            )

        # gross_profit/gross_margin_pct only where *both* drivers have a baseline at this
        # period (sufficiency-gated, same principle as Phase 4's gross-profit decomposition --
        # never fabricate a derived figure from a half-missing input).
        if rev_baseline is not None and cogs_baseline is not None:
            assert rev_scenario is not None and cogs_scenario is not None
            gp_baseline = rev_baseline - cogs_baseline
            gp_scenario = rev_scenario - cogs_scenario
            _add_result(
                session,
                scenario_id=scenario.id,
                metric="gross_profit",
                period_key=period,
                horizon_index=horizon_index,
                baseline_value=gp_baseline,
                scenario_value=gp_scenario,
            )

            # Margin % is undefined (never fabricated as 0) when its own period's revenue is
            # exactly zero -- same rule as app/kpi/calculators.py::calculate_gross_margin_pct.
            margin_baseline = (gp_baseline / rev_baseline * 100) if rev_baseline else None
            margin_scenario = (gp_scenario / rev_scenario * 100) if rev_scenario else None
            if margin_scenario is not None:
                _add_result(
                    session,
                    scenario_id=scenario.id,
                    metric="gross_margin_pct",
                    period_key=period,
                    horizon_index=horizon_index,
                    baseline_value=margin_baseline,
                    scenario_value=margin_scenario,
                )

    if persist:
        session.commit()
    return scenario


__all__ = [
    "DERIVED_METRICS",
    "DRIVER_METRICS",
    "InvalidScenarioRequestError",
    "generate_scenario",
]
