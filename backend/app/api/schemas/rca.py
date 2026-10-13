from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class DetectIssuesRequest(BaseModel):
    granularity: str = Field(examples=["year"])
    period_key: str = Field(examples=["2025"])
    comparison_type: str = Field(default="YoY", examples=["YoY"])
    client_id: uuid.UUID | None = None


class IssueOut(BaseModel):
    id: uuid.UUID
    issue_type: str
    title: str
    severity: str
    status: str
    granularity: str
    period_key: str
    comparison_period_key: str | None
    metric: str
    current_value: float | None
    prior_value: float | None
    absolute_change: float | None
    percentage_change: float | None
    affected_dimension: str | None
    affected_entity: str | None
    materiality: dict[str, object]
    decomposition: dict[str, object] | None
    detection_run_id: uuid.UUID
    latest_analysis_run_id: uuid.UUID | None
    detected_at: datetime
    analyzed_at: datetime | None
    evidence_ids: tuple[uuid.UUID, ...] = ()


class EvidenceOut(BaseModel):
    id: uuid.UUID
    analysis_run_id: uuid.UUID | None
    issue_id: uuid.UUID | None
    forecast_run_id: uuid.UUID | None
    forecast_id: uuid.UUID | None
    decision_run_id: uuid.UUID | None
    decision_option_id: uuid.UUID | None
    claim_type: str
    claim: str
    metric: str | None
    unit: str | None
    granularity: str | None
    period_key: str | None
    comparison_period_key: str | None
    dimension: str | None
    dimension_value: str | None
    value: float | None
    comparison_value: float | None
    absolute_change: float | None
    percentage_change: float | None
    contribution_to_total_pct: float | None
    source_dataset_id: uuid.UUID | None
    source_file_ids: list[str]
    source_fields: list[str]
    calculation_name: str
    calculation_version: str
    calculation_parameters: dict[str, object]
    quality_metadata: dict[str, object]
    data: dict[str, object]
    created_at: datetime


class AnalysisRunOut(BaseModel):
    id: uuid.UUID
    dataset_id: uuid.UUID | None
    analysis_type: str
    granularity: str
    period_key: str
    comparison_type: str | None
    comparison_period_key: str | None
    parameters: dict[str, object]
    status: str
    result_summary: dict[str, object]
    created_at: datetime
    completed_at: datetime | None
    issue_ids: tuple[uuid.UUID, ...] = ()
    evidence_ids: tuple[uuid.UUID, ...] = ()
