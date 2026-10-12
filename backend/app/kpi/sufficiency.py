"""Deterministic data-sufficiency gates.

A KPI must never silently calculate from inadequate data (Phase 3 spec, section 5). Every
real calculator in `calculators.py` runs its fields through `check_field_sufficiency` before
touching the aggregation query, and returns `cannot_compute`/`insufficient_data` instead of a
number when the gate fails.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.canonical import FactSales
from app.kpi.models import KPIStatus
from app.kpi.periods import PeriodWindow

# A single canonical table this phase actually materializes into. Extending this set is the
# only change needed for a later phase's KPIs (procurement, payroll, inventory, ...) to stop
# being structurally `cannot_compute` -- see docs/PHASE_3_KPI_ENGINE.md.
IMPLEMENTED_CANONICAL_TABLES = frozenset({"fact_sales"})

MIN_FIELD_COVERAGE_RATIO = 0.95
MIN_ROWS_IN_PERIOD = 1


@dataclass(frozen=True)
class SufficiencyResult:
    status: KPIStatus
    reason: str | None = None
    data_coverage: dict[str, object] = field(default_factory=dict)
    row_count: int = 0


def check_tables_implemented(required_canonical_tables: tuple[str, ...]) -> SufficiencyResult:
    missing = [t for t in required_canonical_tables if t not in IMPLEMENTED_CANONICAL_TABLES]
    if missing:
        return SufficiencyResult(
            status=KPIStatus.CANNOT_COMPUTE,
            reason=(
                f"Required canonical table(s) not yet materialized: {', '.join(missing)}. "
                "This KPI's registry entry is ready to compute once that table exists."
            ),
        )
    return SufficiencyResult(status=KPIStatus.AVAILABLE)


def check_field_sufficiency(
    session: Session,
    window: PeriodWindow,
    required_fields: tuple[str, ...],
    *,
    min_coverage: float = MIN_FIELD_COVERAGE_RATIO,
) -> SufficiencyResult:
    """Checks row count in the period, then non-null coverage of each required
    `fact_sales` column within that period. Both gates are evaluated against the exact rows
    the calculator is about to aggregate -- not the whole table -- so a KPI that is fine for
    2023 but missing COGS for 2025 reports `insufficient_data` only for 2025."""
    total_row_count = session.execute(
        select(func.count())
        .select_from(FactSales)
        .where(FactSales.month.between(window.start_month, window.end_month))
    ).scalar_one()

    if total_row_count < MIN_ROWS_IN_PERIOD:
        return SufficiencyResult(
            status=KPIStatus.INSUFFICIENT_DATA,
            reason=f"No fact_sales rows found for period {window.period_key}.",
            data_coverage={"row_count": total_row_count},
            row_count=total_row_count,
        )

    coverage: dict[str, object] = {"row_count": total_row_count, "field_coverage": {}}
    for field_name in required_fields:
        column = getattr(FactSales, field_name)
        non_null_count = session.execute(
            select(func.count())
            .select_from(FactSales)
            .where(
                FactSales.month.between(window.start_month, window.end_month),
                column.is_not(None),
            )
        ).scalar_one()
        ratio = non_null_count / total_row_count
        coverage["field_coverage"][field_name] = round(ratio, 4)  # type: ignore[index]
        if ratio < min_coverage:
            return SufficiencyResult(
                status=KPIStatus.INSUFFICIENT_DATA,
                reason=(
                    f"Field '{field_name}' is populated for only {ratio:.1%} of rows in "
                    f"{window.period_key} (need >= {min_coverage:.0%})."
                ),
                data_coverage=coverage,
                row_count=total_row_count,
            )

    return SufficiencyResult(status=KPIStatus.AVAILABLE, data_coverage=coverage, row_count=total_row_count)
