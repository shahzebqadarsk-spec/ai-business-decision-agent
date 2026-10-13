"""The orchestration layer: resolves periods, calls the registry's calculator, computes an
optional comparison, and persists a `KpiCalculation` provenance row. This is the only module
that turns a `KPIComputation` (internal) into a `KPIResult` (the API/engine-facing shape).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.db.models.kpi import KpiCalculation
from app.kpi.models import (
    KPI_CALCULATION_VERSION,
    DimensionBreakdownRow,
    KPIComputation,
    KPIDefinition,
    KPIStatus,
    KPIUnit,
)
from app.kpi.periods import InvalidPeriodError, PeriodWindow, resolve_comparison_period, resolve_period
from app.kpi.registry import get_kpi_definition
from app.kpi.sufficiency import check_field_sufficiency, check_tables_implemented


class UnknownKpiError(ValueError):
    pass


class UnsupportedBreakdownError(ValueError):
    pass


@dataclass(frozen=True)
class KPIResult:
    kpi_id: str
    name: str
    unit: str
    currency: str | None
    granularity: str
    period_key: str
    status: KPIStatus
    status_reason: str | None
    value: float | None
    comparison_type: str | None = None
    comparison_period_key: str | None = None
    comparison_value: float | None = None
    absolute_change: float | None = None
    percentage_change: float | None = None
    percentage_change_status: str = "not_requested"
    data_coverage: dict[str, object] = field(default_factory=dict)
    source_file_ids: tuple[str, ...] = ()
    source_fields: tuple[str, ...] = ()
    calculation_version: str = KPI_CALCULATION_VERSION
    calculated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


def _require_definition(kpi_id: str) -> KPIDefinition:
    definition = get_kpi_definition(kpi_id)
    if definition is None:
        raise UnknownKpiError(f"Unknown KPI id '{kpi_id}'.")
    return definition


def _change(current: float | None, prior: float | None) -> tuple[float | None, float | None, str]:
    if current is None or prior is None:
        return None, None, "undefined_missing_data"
    absolute = current - prior
    if prior == 0:
        return absolute, None, "undefined_zero_denominator"
    return absolute, (current - prior) / abs(prior) * 100, "ok"


def calculate_kpi(
    session: Session,
    kpi_id: str,
    granularity: str,
    period_key: str,
    *,
    comparison_type: str | None = None,
    fiscal_year_start_month: int = 1,
    persist: bool = True,
    client_id: str | None = None,
    client_currency: str | None = None,
) -> KPIResult:
    definition = _require_definition(kpi_id)
    window = resolve_period(
        granularity, period_key, fiscal_year_start_month=fiscal_year_start_month, client_id=client_id
    )
    computation = definition.calculator(session, window)

    comparison_window: PeriodWindow | None = None
    comparison_computation: KPIComputation | None = None
    if comparison_type is not None:
        comparison_window = resolve_comparison_period(
            window, comparison_type, fiscal_year_start_month=fiscal_year_start_month
        )
        comparison_computation = definition.calculator(session, comparison_window)

    absolute_change: float | None = None
    percentage_change: float | None = None
    pct_status = "not_requested"
    comparison_value: float | None = None
    if comparison_computation is not None:
        comparison_value = (
            comparison_computation.value if comparison_computation.status is KPIStatus.AVAILABLE else None
        )
        current_value = computation.value if computation.status is KPIStatus.AVAILABLE else None
        absolute_change, percentage_change, pct_status = _change(current_value, comparison_value)

    # Phase 9: a currency-unit KPI reports in the *client's* resolved reporting currency
    # (auto-detected from that client's own uploads, see app/ingestion/materialize.py), not
    # the deployment-wide default baked into the registry at import time -- `client_currency`
    # overrides `definition.currency` whenever the caller resolved one.
    use_client_currency = bool(client_currency) and definition.unit is KPIUnit.CURRENCY
    currency = client_currency if use_client_currency else definition.currency

    result = KPIResult(
        kpi_id=definition.kpi_id,
        name=definition.name,
        unit=definition.unit.value,
        currency=currency,
        granularity=granularity,
        period_key=window.period_key,
        status=computation.status,
        status_reason=computation.status_reason,
        value=computation.value,
        comparison_type=comparison_type,
        comparison_period_key=comparison_window.period_key if comparison_window else None,
        comparison_value=comparison_value,
        absolute_change=absolute_change,
        percentage_change=percentage_change,
        percentage_change_status=pct_status,
        data_coverage=computation.data_coverage,
        source_file_ids=computation.source_file_ids,
        source_fields=definition.required_fields,
    )

    if persist:
        session.add(
            KpiCalculation(
                kpi_id=result.kpi_id,
                calculation_version=result.calculation_version,
                granularity=result.granularity,
                period_key=result.period_key,
                comparison_type=result.comparison_type,
                comparison_period_key=result.comparison_period_key,
                dimension=None,
                status=result.status.value,
                status_reason=result.status_reason,
                value=result.value,
                unit=result.unit,
                currency=result.currency,
                comparison_value=result.comparison_value,
                absolute_change=result.absolute_change,
                percentage_change=result.percentage_change,
                data_coverage=result.data_coverage,
                source_file_ids=list(result.source_file_ids),
                source_fields=list(result.source_fields),
            )
        )
        session.commit()

    return result


def check_availability(
    kpi_id: str,
    granularity: str,
    period_key: str,
    session: Session,
    *,
    fiscal_year_start_month: int = 1,
    client_id: str | None = None,
) -> tuple[KPIStatus, str | None]:
    """Cheap sufficiency check -- never runs the actual aggregation query."""
    definition = _require_definition(kpi_id)
    table_check = check_tables_implemented(definition.required_canonical_tables)
    if table_check.status is not KPIStatus.AVAILABLE:
        return table_check.status, table_check.reason
    window = resolve_period(
        granularity, period_key, fiscal_year_start_month=fiscal_year_start_month, client_id=client_id
    )
    field_check = check_field_sufficiency(session, window, definition.required_fields)
    return field_check.status, field_check.reason


def calculate_breakdown(
    session: Session,
    kpi_id: str,
    granularity: str,
    period_key: str,
    dimension: str,
    *,
    fiscal_year_start_month: int = 1,
    client_id: str | None = None,
) -> tuple[KPIDefinition, PeriodWindow, list[DimensionBreakdownRow]]:
    definition = _require_definition(kpi_id)
    if definition.breakdown is None:
        raise UnsupportedBreakdownError(f"KPI '{kpi_id}' does not support dimensional breakdown.")
    if dimension not in definition.supported_dimensions:
        raise UnsupportedBreakdownError(
            f"KPI '{kpi_id}' does not support the '{dimension}' dimension. "
            f"Supported dimensions: {', '.join(definition.supported_dimensions)}."
        )
    window = resolve_period(
        granularity, period_key, fiscal_year_start_month=fiscal_year_start_month, client_id=client_id
    )
    table_check = check_tables_implemented(definition.required_canonical_tables)
    if table_check.status is not KPIStatus.AVAILABLE:
        return definition, window, []
    field_check = check_field_sufficiency(session, window, definition.required_fields)
    if field_check.status is not KPIStatus.AVAILABLE:
        return definition, window, []
    rows = definition.breakdown(session, window, dimension)
    return definition, window, rows


__all__ = [
    "InvalidPeriodError",
    "KPIResult",
    "UnknownKpiError",
    "UnsupportedBreakdownError",
    "calculate_breakdown",
    "calculate_kpi",
    "check_availability",
]
