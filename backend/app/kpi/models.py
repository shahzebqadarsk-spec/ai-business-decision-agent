"""Domain types for the KPI engine: the declarative registry entry shape, and the internal
result a calculator hands back to the engine before it becomes an API response / persisted row.

`KPIDefinition.calculator` is a *function reference*, never a string formula or expression --
see docs/DECISIONS.md: a tiny expression language would be the arbitrary-expression-execution
risk Phase 3's spec explicitly rules out, so "declarative registry" means declarative metadata
pointing at ordinary, reviewed Python code, not a DSL.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum

from sqlalchemy.orm import Session

from app.kpi.periods import PeriodWindow

KPI_CALCULATION_VERSION = "1.0.0"

DIMENSIONS = ("region", "product", "category", "customer", "month", "quarter", "year")


class KPICategory(StrEnum):
    FINANCIAL = "financial"
    SALES = "sales"
    COST = "cost"
    OPERATIONS = "operations"


class KPIUnit(StrEnum):
    CURRENCY = "currency"
    COUNT = "count"
    QUANTITY = "quantity"
    PERCENTAGE = "percentage"
    RATIO = "ratio"
    DAYS = "days"
    HOURS = "hours"


class KPIStatus(StrEnum):
    AVAILABLE = "available"
    CANNOT_COMPUTE = "cannot_compute"
    INSUFFICIENT_DATA = "insufficient_data"
    INVALID_DATA = "invalid_data"


@dataclass(frozen=True)
class KPIComputation:
    """What a calculator function returns -- the engine turns this into an API KPIResult
    and a persisted KpiCalculation row, adding the period/comparison bookkeeping."""

    status: KPIStatus
    value: float | None = None
    status_reason: str | None = None
    data_coverage: dict[str, object] = field(default_factory=dict)
    source_file_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class DimensionBreakdownRow:
    dimension_value: str | None
    value: float | None
    status: KPIStatus
    rank: int | None = None
    share_pct: float | None = None


CalculatorFn = Callable[[Session, PeriodWindow], KPIComputation]
BreakdownFn = Callable[[Session, PeriodWindow, str], list[DimensionBreakdownRow]]


@dataclass(frozen=True)
class KPIDefinition:
    kpi_id: str
    name: str
    description: str
    category: KPICategory
    unit: KPIUnit
    calculator: CalculatorFn
    required_canonical_tables: tuple[str, ...] = ("fact_sales",)
    required_fields: tuple[str, ...] = ()
    aggregation_method: str = "sum"
    supported_dimensions: tuple[str, ...] = ()
    supported_granularities: tuple[str, ...] = ("month", "quarter", "year")
    comparison_types: tuple[str, ...] = ("YoY", "QoQ", "MoM")
    currency: str | None = None
    breakdown: BreakdownFn | None = None
    implemented: bool = True
    """False when the KPI's required canonical table(s) don't exist in the schema at all yet
    (vs. existing but data-insufficient, which is a per-request `status`, not a static flag)."""
