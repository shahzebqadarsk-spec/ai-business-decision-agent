"""Raw-ingestion-side tables (Phase 2 builds on these; Phase 0/1 only declare them).

CanonicalRecord is a *placeholder*: Phase 2 replaces it with typed fact/dim
tables (see app/db/models/canonical.py) plus row-level lineage. It is kept
here, unused by Phase 2's materializer, only so a pre-Phase-2 migration
history stays readable.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin, check_in, enum_column

DATASET_STATUSES = ("uploaded", "profiling", "profiled", "mapping", "mapped", "materialized", "failed")
FILE_STATUSES = ("pending", "validated", "rejected")
MAPPING_STATUSES = ("proposed", "confirmed", "rejected", "unresolved")
MAPPING_METHODS = ("rule", "llm", "manual")
QUALITY_SEVERITIES = ("info", "warning", "error")


class Dataset(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "datasets"
    __table_args__ = (check_in("status", DATASET_STATUSES, constraint_name="status_valid"),)

    name: Mapped[str] = mapped_column(String(255))
    source_kind: Mapped[str] = enum_column(length=32, default="upload")
    status: Mapped[str] = enum_column(length=32, default="uploaded")
    uploaded_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Phase 9: which client this dataset's data belongs to (see app/db/models/clients.py).
    # Nullable only for backward compatibility with pre-Phase-9 rows; every dataset created
    # through the API from here on must name a client.
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("clients.id", ondelete="SET NULL"), nullable=True, index=True
    )

    files: Mapped[list[DatasetFile]] = relationship(back_populates="dataset", cascade="all, delete-orphan")


class DatasetFile(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "dataset_files"
    __table_args__ = (check_in("status", FILE_STATUSES, constraint_name="status_valid"),)

    dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(255))
    storage_path: Mapped[str] = mapped_column(String(1024))
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    detected_mime: Mapped[str | None] = mapped_column(String(128), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = enum_column(length=32, default="pending")
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    dataset: Mapped[Dataset] = relationship(back_populates="files")
    columns: Mapped[list[ColumnProfile]] = relationship(back_populates="file", cascade="all, delete-orphan")
    quality_issues: Mapped[list[DataQualityIssue]] = relationship(
        back_populates="file", cascade="all, delete-orphan"
    )
    mappings: Mapped[list[ColumnMapping]] = relationship(back_populates="file", cascade="all, delete-orphan")


class ColumnProfile(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "column_profiles"

    file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dataset_files.id", ondelete="CASCADE"), index=True)
    column_name: Mapped[str] = mapped_column(String(255))
    position: Mapped[int] = mapped_column(Integer)
    inferred_dtype: Mapped[str] = mapped_column(String(32))
    classification: Mapped[str | None] = mapped_column(String(32), nullable=True)
    null_count: Mapped[int] = mapped_column(Integer, default=0)
    null_percentage: Mapped[float] = mapped_column(Numeric(6, 3), default=0)
    unique_count: Mapped[int] = mapped_column(Integer, default=0)
    sample_values: Mapped[list[object]] = mapped_column(JSON, default=list)
    min_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    max_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mean_value: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    stddev_value: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    date_min: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_max: Mapped[date | None] = mapped_column(Date, nullable=True)

    file: Mapped[DatasetFile] = relationship(back_populates="columns")


class DataQualityIssue(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "data_quality_issues"
    __table_args__ = (check_in("severity", QUALITY_SEVERITIES, constraint_name="severity_valid"),)

    file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dataset_files.id", ondelete="CASCADE"), index=True)
    column_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    issue_type: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = enum_column(length=16, default="warning")
    description: Mapped[str] = mapped_column(Text)
    affected_row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    details: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)

    file: Mapped[DatasetFile] = relationship(back_populates="quality_issues")


class ColumnMapping(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "column_mappings"
    __table_args__ = (
        check_in("status", MAPPING_STATUSES, constraint_name="status_valid"),
        check_in("method", MAPPING_METHODS, constraint_name="method_valid"),
    )

    file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dataset_files.id", ondelete="CASCADE"), index=True)
    source_column: Mapped[str] = mapped_column(String(255))
    proposed_canonical_field: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confidence: Mapped[float] = mapped_column(Numeric(5, 4), default=0)
    method: Mapped[str] = enum_column(length=16, default="rule")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = enum_column(length=16, default="proposed")
    confirmed_canonical_field: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confirmed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    file: Mapped[DatasetFile] = relationship(back_populates="mappings")


class CanonicalRecord(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """Phase 0 placeholder kept only for migration-history continuity. Unused from Phase 2 on."""

    __tablename__ = "canonical_records"

    dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"))
    canonical_table: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, object]] = mapped_column(JSON)
