"""Parameterized SQL aggregation helpers against `fact_sales`.

Every function here builds a SQLAlchemy Core expression against a known column and a known
period window -- there is no code path from user input to a raw SQL string anywhere in the
KPI engine, satisfying Phase 3's "no arbitrary SQL / no free-form expression" requirement.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import ColumnElement, Integer, cast, extract, func, select
from sqlalchemy.orm import Session

from app.db.models.canonical import FactSales
from app.kpi.periods import PeriodWindow

_DIMENSION_COLUMNS: dict[str, Any] = {
    "region": FactSales.region_id,
    "product": FactSales.product_id,
    "category": FactSales.category_id,
    "customer": FactSales.customer_id,
}


def _period_filter(window: PeriodWindow) -> ColumnElement[bool]:
    return FactSales.month.between(window.start_month, window.end_month)


def sum_column(session: Session, column: Any, window: PeriodWindow) -> float:
    total = session.execute(
        select(func.coalesce(func.sum(column), 0)).where(_period_filter(window))
    ).scalar_one()
    return float(total)


def count_distinct_column(session: Session, column: Any, window: PeriodWindow) -> int:
    return int(
        session.execute(select(func.count(func.distinct(column))).where(_period_filter(window))).scalar_one()
    )


def row_count(session: Session, window: PeriodWindow) -> int:
    return int(
        session.execute(
            select(func.count()).select_from(FactSales).where(_period_filter(window))
        ).scalar_one()
    )


def source_file_ids(session: Session, window: PeriodWindow) -> tuple[str, ...]:
    rows = (
        session.execute(select(func.distinct(FactSales.source_file_id)).where(_period_filter(window)))
        .scalars()
        .all()
    )
    return tuple(str(r) for r in rows)


def dimension_column(dimension: str) -> Any:
    if dimension in _DIMENSION_COLUMNS:
        return _DIMENSION_COLUMNS[dimension]
    raise ValueError(f"'{dimension}' is not a categorical dimension column.")


def is_categorical_dimension(dimension: str) -> bool:
    return dimension in _DIMENSION_COLUMNS


def is_time_dimension(dimension: str) -> bool:
    return dimension in ("month", "quarter", "year")


def sum_by_dimension(
    session: Session, column: Any, window: PeriodWindow, dimension: str
) -> list[tuple[str | None, float]]:
    """Group-by aggregation for a categorical dimension (region/product/category/customer)."""
    group_col = dimension_column(dimension)
    rows = session.execute(
        select(group_col, func.coalesce(func.sum(column), 0))
        .where(_period_filter(window))
        .group_by(group_col)
        .order_by(func.sum(column).desc())
    ).all()
    return [(r[0], float(r[1])) for r in rows]


def count_distinct_by_dimension(
    session: Session, column: Any, window: PeriodWindow, dimension: str
) -> list[tuple[str | None, float]]:
    group_col = dimension_column(dimension)
    rows = session.execute(
        select(group_col, func.count(func.distinct(column)))
        .where(_period_filter(window))
        .group_by(group_col)
        .order_by(func.count(func.distinct(column)).desc())
    ).all()
    return [(r[0], float(r[1])) for r in rows]


def sum_column_filtered(
    session: Session, column: Any, window: PeriodWindow, dimension: str, value: str
) -> float:
    """Like `sum_column`, scoped to one entity of one dimension -- e.g. total revenue for
    region REG-05 only. Used by app/rca/engine.py for entity-specific driver analysis (volume
    effect, price effect) once an issue has already identified which entity is material."""
    group_col = dimension_column(dimension)
    total = session.execute(
        select(func.coalesce(func.sum(column), 0)).where(_period_filter(window), group_col == value)
    ).scalar_one()
    return float(total)


def sum_by_dimension_filtered(
    session: Session,
    column: Any,
    window: PeriodWindow,
    group_dimension: str,
    filter_dimension: str,
    filter_value: str,
) -> list[tuple[str | None, float]]:
    """Like `sum_by_dimension`, but scoped to rows matching one value of a *different*
    dimension -- e.g. revenue by product, within region REG-05 only. Powers "customer/product
    contribution within this region" driver analysis (Phase 4 spec section 4)."""
    group_col = dimension_column(group_dimension)
    filter_col = dimension_column(filter_dimension)
    rows = session.execute(
        select(group_col, func.coalesce(func.sum(column), 0))
        .where(_period_filter(window), filter_col == filter_value)
        .group_by(group_col)
        .order_by(func.sum(column).desc())
    ).all()
    return [(r[0], float(r[1])) for r in rows]


def count_by_dimension(session: Session, window: PeriodWindow, dimension: str) -> dict[str | None, int]:
    """Row (transaction) count per categorical-dimension value, in the period -- used by
    app/rca/issues.py as the "minimum sample size" materiality input, so a finding about a
    region/product/customer with only a handful of backing transactions isn't flagged."""
    group_col = dimension_column(dimension)
    rows = session.execute(
        select(group_col, func.count()).where(_period_filter(window)).group_by(group_col)
    ).all()
    return {r[0]: int(r[1]) for r in rows}


def full_month_range(session: Session) -> tuple[Any, Any] | None:
    """The earliest and latest `fact_sales.month` present across the *whole* table, with no
    period filter -- `None` (not a fabricated range) when the table is empty. Used by
    app/forecasting/sufficiency.py, which always forecasts from the complete available
    canonical history rather than a caller-chosen window."""
    row = session.execute(select(func.min(FactSales.month), func.max(FactSales.month))).one()
    if row[0] is None or row[1] is None:
        return None
    return (row[0], row[1])


def sum_by_month_bucket(session: Session, column: Any, window: PeriodWindow) -> list[tuple[str, float]]:
    """Time-series bucketing for the `month`/`quarter`/`year` pseudo-dimensions: one row per
    calendar month in the window, chronologically ordered (never ranked by value -- a trend
    line is read in time order, not biggest-first)."""
    year_expr = cast(extract("year", FactSales.month), Integer)
    month_expr = cast(extract("month", FactSales.month), Integer)
    rows = session.execute(
        select(year_expr, month_expr, func.coalesce(func.sum(column), 0))
        .where(_period_filter(window))
        .group_by(year_expr, month_expr)
        .order_by(year_expr, month_expr)
    ).all()
    return [(f"{int(year):04d}-{int(month):02d}", float(total)) for year, month, total in rows]
