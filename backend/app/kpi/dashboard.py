"""The Executive Dashboard aggregator: one function that runs several KPI calculations and
breakdowns server-side so the frontend gets a single payload instead of N round trips.

This module adds no new calculation logic of its own -- it only calls `engine.py` and
`calculators.py` repeatedly. The LLM is still nowhere on this path.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.canonical import FactSales
from app.kpi import calculators as calc
from app.kpi import engine
from app.kpi.models import DimensionBreakdownRow
from app.kpi.periods import PeriodWindow, resolve_period

_HEADLINE_KPI_IDS = (
    "revenue",
    "sales_quantity",
    "average_selling_price",
    "customer_count",
    "transaction_count",
)
_TOP_BOTTOM_N = 5


@dataclass(frozen=True)
class DashboardPayload:
    granularity: str
    period_key: str
    comparison_type: str
    cards: list[engine.KPIResult]
    revenue_trend: list[DimensionBreakdownRow]
    revenue_by_region: list[DimensionBreakdownRow]
    revenue_by_product: list[DimensionBreakdownRow]
    top_customers: list[DimensionBreakdownRow]
    bottom_customers: list[DimensionBreakdownRow]


def latest_available_year(session: Session) -> int | None:
    max_month = session.execute(select(func.max(FactSales.month))).scalar_one_or_none()
    return max_month.year if max_month is not None else None


def earliest_available_year(session: Session) -> int | None:
    min_month = session.execute(select(func.min(FactSales.month))).scalar_one_or_none()
    return min_month.year if min_month is not None else None


def build_dashboard(
    session: Session,
    *,
    granularity: str = "year",
    period_key: str | None = None,
    comparison_type: str = "YoY",
    fiscal_year_start_month: int = 1,
) -> DashboardPayload:
    if period_key is None:
        year = latest_available_year(session)
        period_key = str(year) if year is not None else "1970"

    cards = [
        engine.calculate_kpi(
            session,
            kpi_id,
            granularity,
            period_key,
            comparison_type=comparison_type,
            fiscal_year_start_month=fiscal_year_start_month,
            persist=False,
        )
        for kpi_id in _HEADLINE_KPI_IDS
    ]

    revenue_by_region = _breakdown_or_empty(
        session, "region", granularity, period_key, fiscal_year_start_month
    )
    revenue_by_product = _breakdown_or_empty(
        session, "product", granularity, period_key, fiscal_year_start_month
    )
    all_customers = _breakdown_or_empty(session, "customer", granularity, period_key, fiscal_year_start_month)
    top_customers = all_customers[:_TOP_BOTTOM_N]
    bottom_customers = list(reversed(all_customers[-_TOP_BOTTOM_N:])) if all_customers else []

    revenue_trend = _trend(session, fiscal_year_start_month)

    return DashboardPayload(
        granularity=granularity,
        period_key=period_key,
        comparison_type=comparison_type,
        cards=cards,
        revenue_trend=revenue_trend,
        revenue_by_region=revenue_by_region,
        revenue_by_product=revenue_by_product,
        top_customers=top_customers,
        bottom_customers=bottom_customers,
    )


def _breakdown_or_empty(
    session: Session, dimension: str, granularity: str, period_key: str, fiscal_year_start_month: int
) -> list[DimensionBreakdownRow]:
    try:
        _, _, rows = engine.calculate_breakdown(
            session,
            "revenue",
            granularity,
            period_key,
            dimension,
            fiscal_year_start_month=fiscal_year_start_month,
        )
        return rows
    except (engine.UnsupportedBreakdownError, engine.InvalidPeriodError):
        return []


def _trend(session: Session, fiscal_year_start_month: int) -> list[DimensionBreakdownRow]:
    """Monthly revenue trend across the *entire* data range (not just one requested year) --
    a trend chart with a single year of points is not much of a trend."""
    first_year = earliest_available_year(session)
    last_year = latest_available_year(session)
    if first_year is None or last_year is None:
        return []
    window = PeriodWindow(
        "year",
        f"{first_year}-{last_year}",
        resolve_period("year", str(first_year), fiscal_year_start_month=fiscal_year_start_month).start_month,
        resolve_period("year", str(last_year), fiscal_year_start_month=fiscal_year_start_month).end_month,
    )
    return calc.breakdown_revenue(session, window, "month")
