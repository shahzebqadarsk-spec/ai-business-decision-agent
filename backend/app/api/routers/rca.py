"""Issue detection + RCA / driver-analysis API (Phase 4 spec, section 13).

Every endpoint takes a validated Pydantic model or a plain path/query parameter -- there is no
endpoint here that accepts a SQL string, an expression, or an LLM-generated query of any kind.
`POST /issues/{id}/analyze` takes no body at all: it only ever re-derives the issue's own
already-detected period/comparison period, never a caller-supplied one.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.api.schemas.rca import AnalysisRunOut, DetectIssuesRequest, EvidenceOut, IssueOut
from app.db.models.analysis import AnalysisRun, Evidence, Issue
from app.db.models.clients import Client
from app.kpi.periods import InvalidPeriodError
from app.rca import engine

router = APIRouter(tags=["rca"])


def _cid(client_id: uuid.UUID | None) -> str | None:
    """See app/api/routers/kpi.py's `_cid` -- same str/UUID boundary conversion."""
    return str(client_id) if client_id is not None else None


def _client_currency(session: Session, client_id: uuid.UUID | None) -> str | None:
    """See app/api/routers/kpi.py's `_client_currency` -- same resolution, so a materiality
    threshold that's denominated in a fixed currency (`min_absolute_impact_pkr`) gets
    compared against figures already converted into this client's own currency, not assumed
    to be PKR just because the deployment used to be PKR-only."""
    if client_id is None:
        return None
    client = session.get(Client, client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Client not found.")
    return client.reporting_currency


def _evidence_ids_for_issue(session: Session, issue_id: uuid.UUID) -> tuple[uuid.UUID, ...]:
    rows = session.execute(select(Evidence.id).where(Evidence.issue_id == issue_id)).scalars().all()
    return tuple(rows)


def _issue_out(session: Session, issue: Issue) -> IssueOut:
    return IssueOut(
        id=issue.id,
        issue_type=issue.issue_type,
        title=issue.title,
        severity=issue.severity,
        status=issue.status,
        granularity=issue.granularity,
        period_key=issue.period_key,
        comparison_period_key=issue.comparison_period_key,
        metric=issue.metric,
        current_value=issue.current_value,
        prior_value=issue.prior_value,
        absolute_change=issue.absolute_change,
        percentage_change=issue.percentage_change,
        affected_dimension=issue.affected_dimension,
        affected_entity=issue.affected_entity,
        materiality=issue.materiality,
        decomposition=issue.decomposition,
        detection_run_id=issue.detection_run_id,
        latest_analysis_run_id=issue.latest_analysis_run_id,
        detected_at=issue.created_at,
        analyzed_at=issue.analyzed_at,
        evidence_ids=_evidence_ids_for_issue(session, issue.id),
    )


def _evidence_out(e: Evidence) -> EvidenceOut:
    return EvidenceOut(
        id=e.id,
        analysis_run_id=e.analysis_run_id,
        issue_id=e.issue_id,
        forecast_run_id=e.forecast_run_id,
        forecast_id=e.forecast_id,
        decision_run_id=e.decision_run_id,
        decision_option_id=e.decision_option_id,
        claim_type=e.claim_type,
        claim=e.claim,
        metric=e.metric,
        unit=e.unit,
        granularity=e.granularity,
        period_key=e.period_key,
        comparison_period_key=e.comparison_period_key,
        dimension=e.dimension,
        dimension_value=e.dimension_value,
        value=e.value,
        comparison_value=e.comparison_value,
        absolute_change=e.absolute_change,
        percentage_change=e.percentage_change,
        contribution_to_total_pct=e.contribution_to_total_pct,
        source_dataset_id=e.source_dataset_id,
        source_file_ids=e.source_file_ids,
        source_fields=e.source_fields,
        calculation_name=e.calculation_name,
        calculation_version=e.calculation_version,
        calculation_parameters=e.calculation_parameters,
        quality_metadata=e.quality_metadata,
        data=e.data,
        created_at=e.created_at,
    )


def _run_out(session: Session, run: AnalysisRun) -> AnalysisRunOut:
    issue_ids = tuple(
        session.execute(select(Issue.id).where(Issue.detection_run_id == run.id)).scalars().all()
    )
    evidence_ids = tuple(
        session.execute(select(Evidence.id).where(Evidence.analysis_run_id == run.id)).scalars().all()
    )
    return AnalysisRunOut(
        id=run.id,
        dataset_id=run.dataset_id,
        analysis_type=run.analysis_type,
        granularity=run.granularity,
        period_key=run.period_key,
        comparison_type=run.comparison_type,
        comparison_period_key=run.comparison_period_key,
        parameters=run.parameters,
        status=run.status,
        result_summary=run.result_summary,
        created_at=run.created_at,
        completed_at=run.completed_at,
        issue_ids=issue_ids,
        evidence_ids=evidence_ids,
    )


@router.get("/issues", response_model=list[IssueOut])
def list_issues(
    status_filter: str | None = None,
    issue_type: str | None = None,
    granularity: str | None = None,
    period_key: str | None = None,
    client_id: uuid.UUID | None = None,
    session: Session = Depends(get_db_session),
) -> list[IssueOut]:
    query = select(Issue)
    if status_filter is not None:
        query = query.where(Issue.status == status_filter)
    if issue_type is not None:
        query = query.where(Issue.issue_type == issue_type)
    if granularity is not None:
        query = query.where(Issue.granularity == granularity)
    if period_key is not None:
        query = query.where(Issue.period_key == period_key)
    if client_id is not None:
        query = query.where(Issue.client_id == client_id)
    query = query.order_by(Issue.created_at.desc())
    rows = session.execute(query).scalars().all()
    return [_issue_out(session, row) for row in rows]


@router.get("/issues/{issue_id}", response_model=IssueOut)
def get_issue(issue_id: uuid.UUID, session: Session = Depends(get_db_session)) -> IssueOut:
    issue = session.get(Issue, issue_id)
    if issue is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Unknown issue id '{issue_id}'.")
    return _issue_out(session, issue)


@router.post("/issues/detect", response_model=AnalysisRunOut)
def detect(body: DetectIssuesRequest, session: Session = Depends(get_db_session)) -> AnalysisRunOut:
    try:
        run = engine.detect_issues(
            session,
            body.granularity,
            body.period_key,
            comparison_type=body.comparison_type,
            client_id=_cid(body.client_id),
            client_currency=_client_currency(session, body.client_id),
        )
    except InvalidPeriodError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _run_out(session, run)


@router.post("/issues/{issue_id}/analyze", response_model=IssueOut)
def analyze(issue_id: uuid.UUID, session: Session = Depends(get_db_session)) -> IssueOut:
    try:
        issue = engine.analyze_issue(session, issue_id)
    except engine.UnknownIssueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except engine.UnsupportedIssueTypeError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _issue_out(session, issue)


@router.get("/issues/{issue_id}/evidence", response_model=list[EvidenceOut])
def get_issue_evidence(issue_id: uuid.UUID, session: Session = Depends(get_db_session)) -> list[EvidenceOut]:
    if session.get(Issue, issue_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Unknown issue id '{issue_id}'.")
    rows = session.execute(select(Evidence).where(Evidence.issue_id == issue_id)).scalars().all()
    return [_evidence_out(e) for e in rows]


@router.get("/evidence/{evidence_id}", response_model=EvidenceOut)
def get_evidence(evidence_id: uuid.UUID, session: Session = Depends(get_db_session)) -> EvidenceOut:
    e = session.get(Evidence, evidence_id)
    if e is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Unknown evidence id '{evidence_id}'.")
    return _evidence_out(e)


@router.get("/analysis-runs/{run_id}", response_model=AnalysisRunOut)
def get_analysis_run(run_id: uuid.UUID, session: Session = Depends(get_db_session)) -> AnalysisRunOut:
    run = session.get(AnalysisRun, run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Unknown analysis run id '{run_id}'.")
    return _run_out(session, run)
