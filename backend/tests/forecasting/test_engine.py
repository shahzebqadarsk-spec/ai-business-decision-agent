"""Orchestration tests: generate_forecast() persists the right rows with the right
relationships, and every forecasted point's Evidence is reachable and correctly typed
(mirrors tests/rca/test_engine.py's own structure for Phase 4)."""

from __future__ import annotations

from datetime import date

import pytest
from app.db.models.analysis import Evidence
from app.db.models.canonical import FactSales
from app.db.models.forecasting import Forecast, ForecastRun
from app.forecasting import engine
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

pytestmark = pytest.mark.usefixtures("seeded_fact_sales_file_id")


def test_generate_forecast_persists_a_completed_run_with_the_right_number_of_forecasts(
    db_session: Session,
) -> None:
    run = engine.generate_forecast(db_session, "revenue", 6)
    assert run.status == "completed"
    assert run.metric == "revenue"
    assert run.history_periods == 36
    assert run.history_start_period == "2023-01"
    assert run.history_end_period == "2025-12"
    assert run.horizon_periods == 6

    forecasts = db_session.execute(select(Forecast).where(Forecast.forecast_run_id == run.id)).scalars().all()
    assert len(forecasts) == 6
    periods = sorted(f.period_key for f in forecasts)
    assert periods == ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06"]
    for f in forecasts:
        assert f.lower_bound is not None
        assert f.upper_bound is not None
        assert f.lower_bound <= f.point_estimate <= f.upper_bound


def test_every_forecast_point_has_an_inference_evidence_row(db_session: Session) -> None:
    run = engine.generate_forecast(db_session, "sales_quantity", 3)
    forecasts = db_session.execute(select(Forecast).where(Forecast.forecast_run_id == run.id)).scalars().all()
    for f in forecasts:
        rows = db_session.execute(select(Evidence).where(Evidence.forecast_id == f.id)).scalars().all()
        assert len(rows) == 1
        assert rows[0].claim_type == "inference"
        assert rows[0].forecast_run_id == run.id
        assert "projection" in rows[0].claim.lower() or "projected" in rows[0].claim.lower()


def test_run_gets_one_fact_evidence_row_describing_the_fit(db_session: Session) -> None:
    run = engine.generate_forecast(db_session, "cogs", 2)
    rows = (
        db_session.execute(
            select(Evidence).where(Evidence.forecast_run_id == run.id, Evidence.claim_type == "fact")
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].forecast_id is None  # describes the run, not one point


def test_run_records_a_backtest_diagnostic_when_history_is_long_enough(db_session: Session) -> None:
    run = engine.generate_forecast(db_session, "revenue", 1)
    assert run.holdout_periods == 6
    assert run.holdout_mae is not None
    assert run.holdout_mape_pct is not None


def test_unknown_metric_raises(db_session: Session) -> None:
    with pytest.raises(engine.UnknownMetricError):
        engine.generate_forecast(db_session, "gross_margin_pct", 3)


def test_horizon_out_of_bounds_raises(db_session: Session) -> None:
    with pytest.raises(engine.InvalidForecastRequestError):
        engine.generate_forecast(db_session, "revenue", 0)
    with pytest.raises(engine.InvalidForecastRequestError):
        engine.generate_forecast(db_session, "revenue", 25)


def test_unsupported_confidence_level_raises(db_session: Session) -> None:
    with pytest.raises(engine.InvalidForecastRequestError):
        engine.generate_forecast(db_session, "revenue", 3, confidence_level=0.5)


def test_insufficient_history_persists_an_insufficient_run_with_no_forecasts(
    db_session: Session,
) -> None:
    # Keep only 12 months to force insufficiency.
    db_session.execute(delete(FactSales).where(FactSales.month >= date(2024, 1, 1)))
    db_session.flush()

    run = engine.generate_forecast(db_session, "revenue", 3, persist=False)
    assert run.status == "insufficient_data"
    assert run.status_reason is not None
    assert run.history_periods == 0

    forecasts = db_session.execute(select(Forecast).where(Forecast.forecast_run_id == run.id)).scalars().all()
    assert forecasts == []
    db_session.rollback()


def test_run_is_reproducible_in_shape_across_two_calls(db_session: Session) -> None:
    """Same metric/horizon against the same unchanged canonical data should produce the same
    point estimates both times -- the engine has no hidden state."""
    run_a = engine.generate_forecast(db_session, "revenue", 3, persist=False)
    run_b = engine.generate_forecast(db_session, "revenue", 3, persist=False)
    a_points = [
        f.point_estimate
        for f in db_session.execute(select(Forecast).where(Forecast.forecast_run_id == run_a.id))
        .scalars()
        .all()
    ]
    b_points = [
        f.point_estimate
        for f in db_session.execute(select(Forecast).where(Forecast.forecast_run_id == run_b.id))
        .scalars()
        .all()
    ]
    assert sorted(a_points) == sorted(b_points)
    db_session.rollback()


def test_forecast_run_table_also_accepts_persisted_commits(db_session: Session) -> None:
    """One real `persist=True` call (the default), confirming the commit path itself works,
    not just the `persist=False`-everywhere pattern most tests above use to keep the shared
    session-scoped fixture data untouched across tests."""
    run = engine.generate_forecast(db_session, "revenue", 2)
    found = db_session.get(ForecastRun, run.id)
    assert found is not None
    assert found.status == "completed"
