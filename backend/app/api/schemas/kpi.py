from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.kpi.periods import GRANULARITIES


class KpiDefinitionOut(BaseModel):
    kpi_id: str
    name: str
    description: str
    category: str
    unit: str
    currency: str | None
    required_canonical_tables: tuple[str, ...]
    required_fields: tuple[str, ...]
    aggregation_method: str
    supported_dimensions: tuple[str, ...]
    supported_granularities: tuple[str, ...]
    comparison_types: tuple[str, ...]
    implemented: bool


class CalculateRequest(BaseModel):
    granularity: str = Field(examples=["year"])
    period_key: str = Field(examples=["2024"])
    comparison_type: str | None = Field(default=None, examples=["YoY"])
    client_id: UUID | None = None


class BreakdownRequest(BaseModel):
    granularity: str = Field(examples=["year"])
    period_key: str = Field(examples=["2024"])
    dimension: str = Field(examples=["region"])
    client_id: UUID | None = None


class KpiResultOut(BaseModel):
    kpi_id: str
    name: str
    unit: str
    currency: str | None
    granularity: str
    period_key: str
    status: str
    status_reason: str | None
    value: float | None
    comparison_type: str | None
    comparison_period_key: str | None
    comparison_value: float | None
    absolute_change: float | None
    percentage_change: float | None
    percentage_change_status: str
    data_coverage: dict[str, object]
    source_file_ids: tuple[str, ...]
    source_fields: tuple[str, ...]
    calculation_version: str
    calculated_at: datetime


class AvailabilityOut(BaseModel):
    kpi_id: str
    granularity: str
    period_key: str
    status: str
    status_reason: str | None


class DimensionBreakdownRowOut(BaseModel):
    dimension_value: str | None
    value: float | None
    status: str
    rank: int | None
    share_pct: float | None


class BreakdownOut(BaseModel):
    kpi_id: str
    name: str
    unit: str
    currency: str | None
    granularity: str
    period_key: str
    dimension: str
    rows: list[DimensionBreakdownRowOut]


class DashboardOut(BaseModel):
    granularity: str
    period_key: str
    comparison_type: str
    cards: list[KpiResultOut]
    revenue_trend: list[DimensionBreakdownRowOut]
    revenue_by_region: list[DimensionBreakdownRowOut]
    revenue_by_product: list[DimensionBreakdownRowOut]
    top_customers: list[DimensionBreakdownRowOut]
    bottom_customers: list[DimensionBreakdownRowOut]


__all__ = [
    "GRANULARITIES",
    "AvailabilityOut",
    "BreakdownOut",
    "BreakdownRequest",
    "CalculateRequest",
    "DashboardOut",
    "DimensionBreakdownRowOut",
    "KpiDefinitionOut",
    "KpiResultOut",
]
