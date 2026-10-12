"""Append-only audit trail of every KPI calculation: Phase 3's "KPI result/evidence
persistence" objective. Each row is a self-contained provenance record -- which KPI, which
period, which calculation_version, which fact_sales rows (via source_file_ids) and fields
produced it -- shaped so Phase 4 can later turn a row into an `Evidence` record (see
app/db/models/analysis.py) without the KPI engine itself changing.

This is *not* a cache: the engine always recomputes from `fact_sales`, then records what it
found. Nothing ever reads a KPI value back out of this table instead of recalculating it.
"""

from __future__ import annotations

from sqlalchemy import JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin, check_in, enum_column

KPI_STATUSES = ("available", "cannot_compute", "insufficient_data", "invalid_data")
KPI_GRANULARITIES = ("month", "quarter", "year")


class KpiCalculation(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "kpi_calculations"
    __table_args__ = (
        check_in("status", KPI_STATUSES, constraint_name="status_valid"),
        check_in("granularity", KPI_GRANULARITIES, constraint_name="granularity_valid"),
    )

    kpi_id: Mapped[str] = mapped_column(String(64), index=True)
    calculation_version: Mapped[str] = mapped_column(String(32))
    granularity: Mapped[str] = enum_column(length=16)
    period_key: Mapped[str] = mapped_column(String(32), index=True)
    comparison_type: Mapped[str | None] = mapped_column(String(8), nullable=True)
    comparison_period_key: Mapped[str | None] = mapped_column(String(32), nullable=True)
    dimension: Mapped[str | None] = mapped_column(String(32), nullable=True)

    status: Mapped[str] = enum_column(length=24)
    status_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    value: Mapped[float | None] = mapped_column(Numeric(24, 4), nullable=True)
    unit: Mapped[str] = mapped_column(String(16))
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)

    comparison_value: Mapped[float | None] = mapped_column(Numeric(24, 4), nullable=True)
    absolute_change: Mapped[float | None] = mapped_column(Numeric(24, 4), nullable=True)
    percentage_change: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)

    data_coverage: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    source_file_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    source_fields: Mapped[list[str]] = mapped_column(JSON, default=list)
