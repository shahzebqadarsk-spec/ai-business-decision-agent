"""Orchestration tests: generate_scenario() applies a percentage shock to an existing Phase 5
baseline forecast and re-derives gross_profit/gross_margin_pct, with explicit, self-contained
control over which ForecastRun rows exist -- other test files commit real ForecastRun rows
(persist=True), so any test that cares whether a baseline exists must delete-then-rollback
its own clean slate rather than assume the table is empty (the exact kind of hidden
cross-test-file state dependency documented in tests/conftest.py's collection-order fix)."""

from __future__ import annotations

import uuid

import pytest
from app.db.models.forecasting import Forecast, ForecastRun
from app.db.models.scenario import Scenario, ScenarioResult
from app.forecasting import engine as forecasting_engine
from app.scenarios import engine
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

pytestmark = pytest.mark.usefixtures("seeded_fact_sales_file_id")


def _clean_runs(db_session: Session, *metrics: str) -> None:
    """Deletes (within this test's own uncommitted transaction only) any ForecastRun rows for
    the given metrics, so `_latest_completed_run()` sees exactly what this test set up -- never
    committed, so it has no effect on any other test."""
    db_session.execute(delete(ForecastRun).where(ForecastRun.metric.in_(metrics)))
    db_session.flush()


def _results(db_session: Session, scenario_id: uuid.UUID) -> list[ScenarioResult]:
    query = select(ScenarioResult).where(ScenarioResult.scenario_id == scenario_id)
    return list(db_session.execute(query).scalars().all())


def _f(value: float | None) -> float:
    """Narrows `float | None` to `float` for an assertion that already knows, from the test's
    own setup, that this particular value cannot be None."""
    assert value is not None
    return float(value)


def test_adjustments_apply_and_gross_profit_margin_are_derived(db_session: Session) -> None:
    _clean_runs(db_session, "revenue", "cogs")
    revenue_run = forecasting_engine.generate_forecast(db_session, "revenue", 3, persist=False)
    cogs_run = forecasting_engine.generate_forecast(db_session, "cogs", 3, persist=False)

    scenario = engine.generate_scenario(
        db_session,
        name="Faster revenue, cheaper cogs",
        revenue_growth_adjustment_pct=10.0,
        cogs_adjustment_pct=-5.0,
        revenue_forecast_run_id=revenue_run.id,
        cogs_forecast_run_id=cogs_run.id,
        persist=False,
    )
    assert scenario.status == "completed"
    assert scenario.horizon_periods == 3

    results = _results(db_session, scenario.id)
    by_metric = {(r.metric, r.period_key): r for r in results}

    revenue_forecasts = {
        f.period_key: float(f.point_estimate)
        for f in db_session.execute(select(Forecast).where(Forecast.forecast_run_id == revenue_run.id))
        .scalars()
        .all()
    }
    cogs_forecasts = {
        f.period_key: float(f.point_estimate)
        for f in db_session.execute(select(Forecast).where(Forecast.forecast_run_id == cogs_run.id))
        .scalars()
        .all()
    }

    for period, baseline_revenue in revenue_forecasts.items():
        rev_result = by_metric[("revenue", period)]
        assert _f(rev_result.baseline_value) == pytest.approx(baseline_revenue)
        assert float(rev_result.scenario_value) == pytest.approx(baseline_revenue * 1.10)

        baseline_cogs = cogs_forecasts[period]
        cogs_result = by_metric[("cogs", period)]
        assert float(cogs_result.scenario_value) == pytest.approx(baseline_cogs * 0.95)

        gp_result = by_metric[("gross_profit", period)]
        scenario_revenue = baseline_revenue * 1.10
        scenario_cogs = baseline_cogs * 0.95
        assert _f(gp_result.baseline_value) == pytest.approx(baseline_revenue - baseline_cogs)
        assert float(gp_result.scenario_value) == pytest.approx(scenario_revenue - scenario_cogs)

        margin_result = by_metric[("gross_margin_pct", period)]
        expected_margin = (scenario_revenue - scenario_cogs) / scenario_revenue * 100
        assert float(margin_result.scenario_value) == pytest.approx(expected_margin)

    db_session.rollback()


def test_zero_adjustment_leaves_scenario_value_equal_to_baseline(db_session: Session) -> None:
    _clean_runs(db_session, "revenue", "cogs")
    revenue_run = forecasting_engine.generate_forecast(db_session, "revenue", 2, persist=False)

    scenario = engine.generate_scenario(
        db_session,
        name="No change",
        revenue_forecast_run_id=revenue_run.id,
        cogs_forecast_run_id=None,
        persist=False,
    )
    results = [r for r in _results(db_session, scenario.id) if r.metric == "revenue"]
    assert len(results) == 2
    for r in results:
        assert float(r.scenario_value) == pytest.approx(_f(r.baseline_value))
        assert _f(r.delta_absolute) == pytest.approx(0.0, abs=1e-6)
    db_session.rollback()


def test_auto_selects_latest_completed_run_when_not_specified(db_session: Session) -> None:
    _clean_runs(db_session, "revenue", "cogs")
    revenue_run = forecasting_engine.generate_forecast(db_session, "revenue", 2, persist=False)

    scenario = engine.generate_scenario(db_session, name="auto-select", persist=False)
    assert scenario.revenue_forecast_run_id == revenue_run.id
    assert scenario.cogs_forecast_run_id is None
    db_session.rollback()


def test_unknown_explicit_forecast_run_id_raises(db_session: Session) -> None:
    with pytest.raises(engine.InvalidScenarioRequestError):
        engine.generate_scenario(db_session, name="bad", revenue_forecast_run_id=uuid.uuid4(), persist=False)


def test_explicit_forecast_run_id_with_wrong_metric_raises(db_session: Session) -> None:
    _clean_runs(db_session, "sales_quantity")
    quantity_run = forecasting_engine.generate_forecast(db_session, "sales_quantity", 2, persist=False)
    with pytest.raises(engine.InvalidScenarioRequestError):
        engine.generate_scenario(
            db_session, name="bad metric", revenue_forecast_run_id=quantity_run.id, persist=False
        )
    db_session.rollback()


def test_insufficient_data_when_no_baseline_exists_for_either_metric(db_session: Session) -> None:
    _clean_runs(db_session, "revenue", "cogs")
    scenario = engine.generate_scenario(db_session, name="nothing to work with", persist=False)
    assert scenario.status == "insufficient_data"
    assert scenario.status_reason is not None
    assert scenario.horizon_periods == 0
    assert _results(db_session, scenario.id) == []
    db_session.rollback()


def test_revenue_only_scenario_produces_no_derived_metrics(db_session: Session) -> None:
    _clean_runs(db_session, "revenue", "cogs")
    revenue_run = forecasting_engine.generate_forecast(db_session, "revenue", 2, persist=False)

    scenario = engine.generate_scenario(
        db_session,
        name="revenue only",
        revenue_forecast_run_id=revenue_run.id,
        cogs_forecast_run_id=None,
        persist=False,
    )
    metrics = {r.metric for r in _results(db_session, scenario.id)}
    assert metrics == {"revenue"}
    db_session.rollback()


def test_margin_is_undefined_when_a_periods_baseline_revenue_is_zero(db_session: Session) -> None:
    """Constructed directly (bypassing the forecasting engine, which would never realistically
    predict an exact 0) to exercise the same "undefined, not fabricated" guard
    app/kpi/calculators.py::calculate_gross_margin_pct uses -- a derived gross_profit is still
    perfectly well-defined at revenue=0 (it's just `0 - cogs`), only the *margin* is not."""
    _clean_runs(db_session, "revenue", "cogs")
    revenue_run = ForecastRun(
        metric="revenue",
        granularity="month",
        history_start_period="2023-01",
        history_end_period="2025-12",
        history_periods=36,
        horizon_periods=1,
        status="completed",
        method_name="test_fixture",
        method_version="0.0.0",
    )
    cogs_run = ForecastRun(
        metric="cogs",
        granularity="month",
        history_start_period="2023-01",
        history_end_period="2025-12",
        history_periods=36,
        horizon_periods=1,
        status="completed",
        method_name="test_fixture",
        method_version="0.0.0",
    )
    db_session.add_all([revenue_run, cogs_run])
    db_session.flush()
    db_session.add_all(
        [
            Forecast(
                forecast_run_id=revenue_run.id,
                metric="revenue",
                period_key="2026-01",
                horizon_index=1,
                point_estimate=0.0,
            ),
            Forecast(
                forecast_run_id=cogs_run.id,
                metric="cogs",
                period_key="2026-01",
                horizon_index=1,
                point_estimate=10_000.0,
            ),
        ]
    )
    db_session.flush()

    scenario = engine.generate_scenario(
        db_session,
        name="zero revenue edge case",
        revenue_forecast_run_id=revenue_run.id,
        cogs_forecast_run_id=cogs_run.id,
        persist=False,
    )
    results = {r.metric: r for r in _results(db_session, scenario.id)}
    assert "gross_profit" in results
    assert float(results["gross_profit"].scenario_value) == pytest.approx(-10_000.0)
    assert "gross_margin_pct" not in results
    db_session.rollback()


def test_scenario_table_also_accepts_persisted_commits(db_session: Session) -> None:
    """One real `persist=True` call, confirming the commit path itself works -- mirrors
    tests/forecasting/test_engine.py's own equivalent test. Deliberately does not clean up
    after itself, same as that test: a few leftover completed rows in the shared test DB are
    an accepted, already-established cost of exercising the real commit path."""
    revenue_run = forecasting_engine.generate_forecast(db_session, "revenue", 1)
    scenario = engine.generate_scenario(db_session, name="persisted", revenue_forecast_run_id=revenue_run.id)
    found = db_session.get(Scenario, scenario.id)
    assert found is not None
    assert found.status == "completed"
