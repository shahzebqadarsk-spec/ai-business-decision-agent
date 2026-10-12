"""One small, explicit calculator function per real KPI, plus a shared stub for every KPI
whose canonical data does not exist yet. Deliberately not a generic "composition" engine: at
this KPI count, explicit functions are easier to audit than a DSL that composes them, and
auditability is the point of a deterministic KPI engine.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import Session

from app.db.models.canonical import FactSales
from app.kpi import aggregations as agg
from app.kpi.models import DimensionBreakdownRow, KPIComputation, KPIStatus
from app.kpi.periods import PeriodWindow
from app.kpi.sufficiency import SufficiencyResult, check_field_sufficiency, check_tables_implemented


def _computation_from_sufficiency(sufficiency: SufficiencyResult, value: float) -> KPIComputation:
    return KPIComputation(status=KPIStatus.AVAILABLE, value=value, data_coverage=sufficiency.data_coverage)


class _Insufficient(Exception):
    def __init__(self, computation: KPIComputation) -> None:
        self.computation = computation


def _gate(session: Session, window: PeriodWindow, required_fields: tuple[str, ...]) -> SufficiencyResult:
    """Shared sufficiency check every real calculator runs first. Returns the passing
    SufficiencyResult, or raises `_Insufficient` carrying the KPIComputation to return."""
    result = check_field_sufficiency(session, window, required_fields)
    if result.status is not KPIStatus.AVAILABLE:
        raise _Insufficient(
            KPIComputation(
                status=result.status, status_reason=result.reason, data_coverage=result.data_coverage
            )
        )
    return result


def _with_lineage(session: Session, window: PeriodWindow, computation: KPIComputation) -> KPIComputation:
    if computation.status is not KPIStatus.AVAILABLE:
        return computation
    return KPIComputation(
        status=computation.status,
        value=computation.value,
        status_reason=computation.status_reason,
        data_coverage=computation.data_coverage,
        source_file_ids=agg.source_file_ids(session, window),
    )


# --- real calculators: computable today from fact_sales alone -------------------------------


def calculate_revenue(session: Session, window: PeriodWindow) -> KPIComputation:
    try:
        sufficiency = _gate(session, window, ("net_amount_reporting",))
    except _Insufficient as exc:
        return exc.computation
    value = agg.sum_column(session, FactSales.net_amount_reporting, window)
    return _with_lineage(session, window, _computation_from_sufficiency(sufficiency, value))


def calculate_sales_quantity(session: Session, window: PeriodWindow) -> KPIComputation:
    try:
        sufficiency = _gate(session, window, ("quantity",))
    except _Insufficient as exc:
        return exc.computation
    value = agg.sum_column(session, FactSales.quantity, window)
    return _with_lineage(session, window, _computation_from_sufficiency(sufficiency, value))


def calculate_average_selling_price(session: Session, window: PeriodWindow) -> KPIComputation:
    try:
        sufficiency = _gate(session, window, ("net_amount_reporting", "quantity"))
    except _Insufficient as exc:
        return exc.computation
    revenue = agg.sum_column(session, FactSales.net_amount_reporting, window)
    quantity = agg.sum_column(session, FactSales.quantity, window)
    if quantity == 0:
        return KPIComputation(
            status=KPIStatus.INVALID_DATA,
            status_reason="Total quantity for the period is zero; average selling price is undefined.",
            data_coverage=sufficiency.data_coverage,
        )
    return _with_lineage(session, window, _computation_from_sufficiency(sufficiency, revenue / quantity))


def calculate_customer_count(session: Session, window: PeriodWindow) -> KPIComputation:
    try:
        sufficiency = _gate(session, window, ("customer_id",))
    except _Insufficient as exc:
        return exc.computation
    value = agg.count_distinct_column(session, FactSales.customer_id, window)
    return _with_lineage(session, window, _computation_from_sufficiency(sufficiency, float(value)))


def calculate_transaction_count(session: Session, window: PeriodWindow) -> KPIComputation:
    try:
        sufficiency = _gate(session, window, ("sale_id",))
    except _Insufficient as exc:
        return exc.computation
    value = agg.count_distinct_column(session, FactSales.sale_id, window)
    return _with_lineage(session, window, _computation_from_sufficiency(sufficiency, float(value)))


def calculate_cogs(session: Session, window: PeriodWindow) -> KPIComputation:
    try:
        sufficiency = _gate(session, window, ("cogs_amount_reporting",))
    except _Insufficient as exc:
        return exc.computation
    value = agg.sum_column(session, FactSales.cogs_amount_reporting, window)
    return _with_lineage(session, window, _computation_from_sufficiency(sufficiency, value))


def calculate_gross_profit(session: Session, window: PeriodWindow) -> KPIComputation:
    try:
        sufficiency = _gate(session, window, ("net_amount_reporting", "cogs_amount_reporting"))
    except _Insufficient as exc:
        return exc.computation
    revenue = agg.sum_column(session, FactSales.net_amount_reporting, window)
    cogs = agg.sum_column(session, FactSales.cogs_amount_reporting, window)
    return _with_lineage(session, window, _computation_from_sufficiency(sufficiency, revenue - cogs))


def calculate_gross_margin_pct(session: Session, window: PeriodWindow) -> KPIComputation:
    try:
        sufficiency = _gate(session, window, ("net_amount_reporting", "cogs_amount_reporting"))
    except _Insufficient as exc:
        return exc.computation
    revenue = agg.sum_column(session, FactSales.net_amount_reporting, window)
    cogs = agg.sum_column(session, FactSales.cogs_amount_reporting, window)
    if revenue == 0:
        return KPIComputation(
            status=KPIStatus.INVALID_DATA,
            status_reason="Total revenue for the period is zero; gross margin % is undefined.",
            data_coverage=sufficiency.data_coverage,
        )
    value = (revenue - cogs) / revenue * 100
    return _with_lineage(session, window, _computation_from_sufficiency(sufficiency, value))


# --- stub: every KPI whose canonical table isn't materialized yet ---------------------------


def make_cannot_compute_calculator(
    required_canonical_tables: tuple[str, ...],
) -> Callable[[Session, PeriodWindow], KPIComputation]:
    """Every "cost"/"operations" KPI (and the opex-dependent financial ones) shares this: it
    never queries the database at all, because the table it would need does not exist."""

    def _calculate(session: Session, window: PeriodWindow) -> KPIComputation:
        result = check_tables_implemented(required_canonical_tables)
        return KPIComputation(status=result.status, status_reason=result.reason)

    return _calculate


# --- dimensional breakdowns: shared by every "sum of a fact_sales column" KPI ----------------


def _breakdown_sum(column_name: str) -> Callable[[Session, PeriodWindow, str], list[DimensionBreakdownRow]]:
    def _breakdown(session: Session, window: PeriodWindow, dimension: str) -> list[DimensionBreakdownRow]:
        column = getattr(FactSales, column_name)
        if agg.is_categorical_dimension(dimension):
            rows = agg.sum_by_dimension(session, column, window, dimension)
        elif agg.is_time_dimension(dimension):
            rows = list(agg.sum_by_month_bucket(session, column, window))
        else:
            raise ValueError(f"Unsupported dimension '{dimension}'.")
        total = sum(v for _, v in rows) or None
        result: list[DimensionBreakdownRow] = []
        for i, (dim_value, value) in enumerate(rows):
            share = (value / total * 100) if total else None
            rank = None if agg.is_time_dimension(dimension) else i + 1
            result.append(
                DimensionBreakdownRow(
                    dimension_value=dim_value,
                    value=value,
                    status=KPIStatus.AVAILABLE,
                    rank=rank,
                    share_pct=share,
                )
            )
        return result

    return _breakdown


breakdown_revenue = _breakdown_sum("net_amount_reporting")
breakdown_sales_quantity = _breakdown_sum("quantity")
breakdown_cogs = _breakdown_sum("cogs_amount_reporting")
