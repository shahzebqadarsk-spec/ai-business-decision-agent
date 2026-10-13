"""Scenario / What-If API (Phase 6). Takes a validated Pydantic model or a plain path/query
parameter -- no caller-supplied SQL, expression, or arbitrary projection logic; the only
"formula" here is a percentage multiplier applied to an existing Phase 5 forecast."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.api.schemas.scenario import CreateScenarioRequest, ScenarioOut, ScenarioResultOut
from app.db.models.scenario import Scenario, ScenarioResult
from app.scenarios import engine

router = APIRouter(tags=["scenarios"])


def _cid(client_id: uuid.UUID | None) -> str | None:
    """See app/api/routers/kpi.py's `_cid` -- same str/UUID boundary conversion."""
    return str(client_id) if client_id is not None else None


def _result_out(r: ScenarioResult) -> ScenarioResultOut:
    return ScenarioResultOut(
        id=r.id,
        scenario_id=r.scenario_id,
        metric=r.metric,
        period_key=r.period_key,
        horizon_index=r.horizon_index,
        baseline_value=float(r.baseline_value) if r.baseline_value is not None else None,
        scenario_value=float(r.scenario_value),
        delta_absolute=float(r.delta_absolute) if r.delta_absolute is not None else None,
        delta_percentage=float(r.delta_percentage) if r.delta_percentage is not None else None,
    )


def _scenario_out(session: Session, scenario: Scenario) -> ScenarioOut:
    results = (
        session.execute(
            select(ScenarioResult)
            .where(ScenarioResult.scenario_id == scenario.id)
            .order_by(ScenarioResult.period_key, ScenarioResult.metric)
        )
        .scalars()
        .all()
    )
    return ScenarioOut(
        id=scenario.id,
        name=scenario.name,
        description=scenario.description,
        revenue_growth_adjustment_pct=float(scenario.revenue_growth_adjustment_pct),
        cogs_adjustment_pct=float(scenario.cogs_adjustment_pct),
        revenue_forecast_run_id=scenario.revenue_forecast_run_id,
        cogs_forecast_run_id=scenario.cogs_forecast_run_id,
        status=scenario.status,
        status_reason=scenario.status_reason,
        horizon_periods=scenario.horizon_periods,
        created_at=scenario.created_at,
        results=tuple(_result_out(r) for r in results),
    )


@router.post("/scenarios", response_model=ScenarioOut)
def generate(body: CreateScenarioRequest, session: Session = Depends(get_db_session)) -> ScenarioOut:
    try:
        scenario = engine.generate_scenario(
            session,
            name=body.name,
            description=body.description,
            revenue_growth_adjustment_pct=body.revenue_growth_adjustment_pct,
            cogs_adjustment_pct=body.cogs_adjustment_pct,
            revenue_forecast_run_id=body.revenue_forecast_run_id,
            cogs_forecast_run_id=body.cogs_forecast_run_id,
            client_id=_cid(body.client_id),
        )
    except engine.InvalidScenarioRequestError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _scenario_out(session, scenario)


@router.get("/scenarios", response_model=list[ScenarioOut])
def list_scenarios(
    client_id: uuid.UUID | None = None, session: Session = Depends(get_db_session)
) -> list[ScenarioOut]:
    query = select(Scenario)
    if client_id is not None:
        query = query.where(Scenario.client_id == client_id)
    scenarios = session.execute(query.order_by(Scenario.created_at.desc())).scalars().all()
    return [_scenario_out(session, s) for s in scenarios]


@router.get("/scenarios/{scenario_id}", response_model=ScenarioOut)
def get_scenario(scenario_id: uuid.UUID, session: Session = Depends(get_db_session)) -> ScenarioOut:
    scenario = session.get(Scenario, scenario_id)
    if scenario is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Unknown scenario id '{scenario_id}'.")
    return _scenario_out(session, scenario)
