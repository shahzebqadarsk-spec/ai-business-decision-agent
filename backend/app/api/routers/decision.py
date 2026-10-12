"""Decision Scoring API (Phase 7). Takes a validated Pydantic model or a plain path parameter
-- no caller-supplied SQL, expression, or arbitrary projection logic; the only "formula" here
is the deterministic weighted-average scoring `app/decisions/engine.py` computes over existing
`ScenarioResult` rows."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.api.schemas.decision import CreateDecisionRequest, DecisionOptionOut, DecisionRunOut
from app.db.models.analysis import Evidence
from app.db.models.decision import DecisionOption, DecisionRun
from app.decisions import engine

router = APIRouter(tags=["decisions"])


def _option_evidence_id(session: Session, option_id: uuid.UUID) -> uuid.UUID | None:
    return session.execute(
        select(Evidence.id).where(Evidence.decision_option_id == option_id)
    ).scalar_one_or_none()


def _fact_evidence_id(session: Session, run_id: uuid.UUID) -> uuid.UUID | None:
    return session.execute(
        select(Evidence.id).where(Evidence.decision_run_id == run_id, Evidence.claim_type == "fact")
    ).scalar_one_or_none()


def _option_out(session: Session, o: DecisionOption) -> DecisionOptionOut:
    return DecisionOptionOut(
        id=o.id,
        decision_run_id=o.decision_run_id,
        scenario_id=o.scenario_id,
        title=o.title,
        score=float(o.score) if o.score is not None else None,
        rank=o.rank,
        criteria_breakdown=o.criteria_breakdown,
        rationale=o.rationale,
        evidence_id=_option_evidence_id(session, o.id),
    )


def _run_out(session: Session, run: DecisionRun) -> DecisionRunOut:
    options = (
        session.execute(
            select(DecisionOption)
            .where(DecisionOption.decision_run_id == run.id)
            .order_by(DecisionOption.rank.is_(None), DecisionOption.rank, DecisionOption.title)
        )
        .scalars()
        .all()
    )
    return DecisionRunOut(
        id=run.id,
        name=run.name,
        description=run.description,
        criteria_weights=run.criteria_weights,
        status=run.status,
        status_reason=run.status_reason,
        created_at=run.created_at,
        options=tuple(_option_out(session, o) for o in options),
        fact_evidence_id=_fact_evidence_id(session, run.id),
    )


@router.post("/decisions", response_model=DecisionRunOut)
def compare(body: CreateDecisionRequest, session: Session = Depends(get_db_session)) -> DecisionRunOut:
    try:
        run = engine.score_decision(
            session,
            name=body.name,
            description=body.description,
            scenario_ids=body.scenario_ids,
            criteria_weights=body.criteria_weights,
        )
    except engine.InvalidDecisionRequestError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _run_out(session, run)


@router.get("/decisions", response_model=list[DecisionRunOut])
def list_decisions(session: Session = Depends(get_db_session)) -> list[DecisionRunOut]:
    runs = session.execute(select(DecisionRun).order_by(DecisionRun.created_at.desc())).scalars().all()
    return [_run_out(session, r) for r in runs]


@router.get("/decisions/{decision_run_id}", response_model=DecisionRunOut)
def get_decision(decision_run_id: uuid.UUID, session: Session = Depends(get_db_session)) -> DecisionRunOut:
    run = session.get(DecisionRun, decision_run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Unknown decision run id '{decision_run_id}'.")
    return _run_out(session, run)
