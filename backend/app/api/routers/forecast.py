"""Forecasting API (Phase 5). Every endpoint takes a validated Pydantic model or a plain
path/query parameter -- no raw SQL, no caller-supplied window (a forecast always runs against
the complete available canonical history, see app/forecasting/sufficiency.py)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.api.schemas.forecast import ForecastPointOut, ForecastRunOut, GenerateForecastRequest
from app.db.models.analysis import Evidence
from app.db.models.forecasting import Forecast, ForecastRun
from app.forecasting import engine

router = APIRouter(tags=["forecasting"])


def _forecast_evidence_id(session: Session, forecast_id: uuid.UUID) -> uuid.UUID | None:
    return session.execute(
        select(Evidence.id).where(Evidence.forecast_id == forecast_id)
    ).scalar_one_or_none()


def _fit_evidence_id(session: Session, run_id: uuid.UUID) -> uuid.UUID | None:
    return session.execute(
        select(Evidence.id).where(Evidence.forecast_run_id == run_id, Evidence.claim_type == "fact")
    ).scalar_one_or_none()


def _point_out(session: Session, f: Forecast) -> ForecastPointOut:
    return ForecastPointOut(
        id=f.id,
        forecast_run_id=f.forecast_run_id,
        metric=f.metric,
        period_key=f.period_key,
        horizon_index=f.horizon_index,
        point_estimate=f.point_estimate,
        lower_bound=f.lower_bound,
        upper_bound=f.upper_bound,
        evidence_id=_forecast_evidence_id(session, f.id),
    )


def _run_out(session: Session, run: ForecastRun) -> ForecastRunOut:
    points = (
        session.execute(
            select(Forecast).where(Forecast.forecast_run_id == run.id).order_by(Forecast.horizon_index)
        )
        .scalars()
        .all()
    )
    return ForecastRunOut(
        id=run.id,
        metric=run.metric,
        granularity=run.granularity,
        history_start_period=run.history_start_period,
        history_end_period=run.history_end_period,
        history_periods=run.history_periods,
        horizon_periods=run.horizon_periods,
        status=run.status,
        status_reason=run.status_reason,
        method_name=run.method_name,
        method_version=run.method_version,
        confidence_level=float(run.confidence_level),
        parameters=run.parameters,
        holdout_periods=run.holdout_periods,
        holdout_mae=run.holdout_mae,
        holdout_mape_pct=run.holdout_mape_pct,
        created_at=run.created_at,
        forecasts=tuple(_point_out(session, f) for f in points),
        fit_evidence_id=_fit_evidence_id(session, run.id),
    )


@router.post("/forecasts/generate", response_model=ForecastRunOut)
def generate(body: GenerateForecastRequest, session: Session = Depends(get_db_session)) -> ForecastRunOut:
    try:
        run = engine.generate_forecast(
            session,
            body.metric,
            body.horizon_periods,
            confidence_level=body.confidence_level,
        )
    except engine.UnknownMetricError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except engine.InvalidForecastRequestError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _run_out(session, run)


@router.get("/forecasts/runs", response_model=list[ForecastRunOut])
def list_runs(metric: str | None = None, session: Session = Depends(get_db_session)) -> list[ForecastRunOut]:
    query = select(ForecastRun)
    if metric is not None:
        query = query.where(ForecastRun.metric == metric)
    query = query.order_by(ForecastRun.created_at.desc())
    runs = session.execute(query).scalars().all()
    return [_run_out(session, r) for r in runs]


@router.get("/forecasts/runs/{run_id}", response_model=ForecastRunOut)
def get_run(run_id: uuid.UUID, session: Session = Depends(get_db_session)) -> ForecastRunOut:
    run = session.get(ForecastRun, run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Unknown forecast run id '{run_id}'.")
    return _run_out(session, run)
