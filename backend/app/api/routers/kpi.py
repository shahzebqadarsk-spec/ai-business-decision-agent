"""Deterministic KPI API: catalog, availability, calculate, dimensional breakdown, and the
Executive Dashboard aggregator. No endpoint here accepts free-form SQL, an expression, or
anything else that would let a caller (human or LLM) compute something outside the registry.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.api.schemas.kpi import (
    AvailabilityOut,
    BreakdownOut,
    BreakdownRequest,
    CalculateRequest,
    DashboardOut,
    DimensionBreakdownRowOut,
    KpiDefinitionOut,
    KpiResultOut,
)
from app.config import Settings, get_settings
from app.db.models.clients import Client
from app.kpi import dashboard as dashboard_module
from app.kpi import engine
from app.kpi.models import DimensionBreakdownRow, KPIDefinition
from app.kpi.periods import InvalidPeriodError
from app.kpi.registry import get_kpi_definition, list_kpi_definitions

router = APIRouter(tags=["kpi"])


def _cid(client_id: UUID | None) -> str | None:
    """The engine layer's `client_id` params are typed `str | None` (see app/kpi/periods.py's
    `PeriodWindow`) -- FastAPI hands this router a `uuid.UUID` instance instead, so every call
    into the engine converts at this one boundary rather than widening every signature below
    it just to accept a type that was never meant to flow past the API layer."""
    return str(client_id) if client_id is not None else None


def _client_currency(session: Session, client_id: UUID | None) -> str | None:
    """A client's own resolved `reporting_currency` (Phase 9) -- `None` if no client was
    named, or if that client has none resolved yet (no upload has reached it)."""
    if client_id is None:
        return None
    client = session.get(Client, client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Client not found.")
    return client.reporting_currency


def _definition_out(definition: KPIDefinition) -> KpiDefinitionOut:
    return KpiDefinitionOut(
        kpi_id=definition.kpi_id,
        name=definition.name,
        description=definition.description,
        category=definition.category.value,
        unit=definition.unit.value,
        currency=definition.currency,
        required_canonical_tables=definition.required_canonical_tables,
        required_fields=definition.required_fields,
        aggregation_method=definition.aggregation_method,
        supported_dimensions=definition.supported_dimensions,
        supported_granularities=definition.supported_granularities,
        comparison_types=definition.comparison_types,
        implemented=definition.implemented,
    )


def _result_out(result: engine.KPIResult) -> KpiResultOut:
    return KpiResultOut(
        kpi_id=result.kpi_id,
        name=result.name,
        unit=result.unit,
        currency=result.currency,
        granularity=result.granularity,
        period_key=result.period_key,
        status=result.status.value,
        status_reason=result.status_reason,
        value=result.value,
        comparison_type=result.comparison_type,
        comparison_period_key=result.comparison_period_key,
        comparison_value=result.comparison_value,
        absolute_change=result.absolute_change,
        percentage_change=result.percentage_change,
        percentage_change_status=result.percentage_change_status,
        data_coverage=result.data_coverage,
        source_file_ids=result.source_file_ids,
        source_fields=result.source_fields,
        calculation_version=result.calculation_version,
        calculated_at=result.calculated_at,
    )


def _row_out(row: DimensionBreakdownRow) -> DimensionBreakdownRowOut:
    return DimensionBreakdownRowOut(
        dimension_value=row.dimension_value,
        value=row.value,
        status=row.status.value,
        rank=row.rank,
        share_pct=row.share_pct,
    )


@router.get("/kpis", response_model=list[KpiDefinitionOut])
def list_kpis() -> list[KpiDefinitionOut]:
    return [_definition_out(d) for d in list_kpi_definitions()]


@router.get("/kpis/{kpi_id}", response_model=KpiDefinitionOut)
def get_kpi(kpi_id: str) -> KpiDefinitionOut:
    definition = get_kpi_definition(kpi_id)
    if definition is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Unknown KPI id '{kpi_id}'.")
    return _definition_out(definition)


@router.get("/kpis/{kpi_id}/availability", response_model=AvailabilityOut)
def get_availability(
    kpi_id: str,
    granularity: str,
    period_key: str,
    client_id: UUID | None = None,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> AvailabilityOut:
    if get_kpi_definition(kpi_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Unknown KPI id '{kpi_id}'.")
    try:
        kpi_status, reason = engine.check_availability(
            kpi_id,
            granularity,
            period_key,
            session,
            fiscal_year_start_month=settings.fiscal_year_start_month,
            client_id=_cid(client_id),
        )
    except InvalidPeriodError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return AvailabilityOut(
        kpi_id=kpi_id,
        granularity=granularity,
        period_key=period_key,
        status=kpi_status.value,
        status_reason=reason,
    )


@router.post("/kpis/{kpi_id}/calculate", response_model=KpiResultOut)
def calculate(
    kpi_id: str,
    body: CalculateRequest,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> KpiResultOut:
    client_currency = _client_currency(session, body.client_id)
    try:
        result = engine.calculate_kpi(
            session,
            kpi_id,
            body.granularity,
            body.period_key,
            comparison_type=body.comparison_type,
            fiscal_year_start_month=settings.fiscal_year_start_month,
            client_id=_cid(body.client_id),
            client_currency=client_currency,
        )
    except engine.UnknownKpiError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidPeriodError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _result_out(result)


@router.post("/kpis/{kpi_id}/breakdown", response_model=BreakdownOut)
def breakdown(
    kpi_id: str,
    body: BreakdownRequest,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> BreakdownOut:
    try:
        definition, window, rows = engine.calculate_breakdown(
            session,
            kpi_id,
            body.granularity,
            body.period_key,
            body.dimension,
            fiscal_year_start_month=settings.fiscal_year_start_month,
            client_id=_cid(body.client_id),
        )
    except engine.UnknownKpiError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except engine.UnsupportedBreakdownError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except InvalidPeriodError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    currency = _client_currency(session, body.client_id) or definition.currency
    return BreakdownOut(
        kpi_id=definition.kpi_id,
        name=definition.name,
        unit=definition.unit.value,
        currency=currency,
        granularity=window.granularity,
        period_key=window.period_key,
        dimension=body.dimension,
        rows=[_row_out(r) for r in rows],
    )


@router.get("/dashboard", response_model=DashboardOut)
def get_dashboard(
    granularity: str = "year",
    period_key: str | None = None,
    comparison_type: str = "YoY",
    client_id: UUID | None = None,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> DashboardOut:
    client_currency = _client_currency(session, client_id)
    try:
        payload = dashboard_module.build_dashboard(
            session,
            granularity=granularity,
            period_key=period_key,
            comparison_type=comparison_type,
            fiscal_year_start_month=settings.fiscal_year_start_month,
            client_id=_cid(client_id),
            client_currency=client_currency,
        )
    except InvalidPeriodError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return DashboardOut(
        granularity=payload.granularity,
        period_key=payload.period_key,
        comparison_type=payload.comparison_type,
        cards=[_result_out(c) for c in payload.cards],
        revenue_trend=[_row_out(r) for r in payload.revenue_trend],
        revenue_by_region=[_row_out(r) for r in payload.revenue_by_region],
        revenue_by_product=[_row_out(r) for r in payload.revenue_by_product],
        top_customers=[_row_out(r) for r in payload.top_customers],
        bottom_customers=[_row_out(r) for r in payload.bottom_customers],
    )
