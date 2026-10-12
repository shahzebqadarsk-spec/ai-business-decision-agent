from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class DatasetCreate(BaseModel):
    name: str


class DatasetOut(BaseModel):
    id: UUID
    name: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class FileOut(BaseModel):
    id: UUID
    dataset_id: UUID
    original_filename: str
    status: str
    size_bytes: int
    row_count: int | None
    rejection_reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ColumnProfileOut(BaseModel):
    column_name: str
    position: int
    inferred_dtype: str
    classification: str | None
    null_count: int
    null_percentage: float
    unique_count: int
    sample_values: list[object]
    min_value: str | None
    max_value: str | None
    mean_value: float | None
    stddev_value: float | None
    date_min: date | None
    date_max: date | None

    model_config = {"from_attributes": True}


class QualityIssueOut(BaseModel):
    id: UUID
    column_name: str | None
    issue_type: str
    severity: str
    description: str
    affected_row_count: int | None

    model_config = {"from_attributes": True}


class MappingOut(BaseModel):
    id: UUID
    source_column: str
    proposed_canonical_field: str | None
    confidence: float
    method: str
    reason: str | None
    status: str
    confirmed_canonical_field: str | None
    confirmed_by: str | None

    model_config = {"from_attributes": True}


class MappingConfirmRequest(BaseModel):
    confirmed_canonical_field: str
    confirmed_by: str


class MappingRejectRequest(BaseModel):
    rejected_by: str


class MaterializeRequest(BaseModel):
    performed_by: str


class MaterializeResult(BaseModel):
    rows_written: int
    rows_skipped: int
    skipped_reasons: list[str]


class CanonicalFieldOut(BaseModel):
    name: str
    required: bool
    data_type: str
