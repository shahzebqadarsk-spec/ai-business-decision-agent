from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class GenerateForecastRequest(BaseModel):
    metric: str = Field(examples=["revenue"])
    horizon_periods: int = Field(default=6, ge=1, le=24, examples=[6])
    confidence_level: float = Field(default=0.8, examples=[0.8])


class ForecastPointOut(BaseModel):
    id: uuid.UUID
    forecast_run_id: uuid.UUID
    metric: str
    period_key: str
    horizon_index: int
    point_estimate: float
    lower_bound: float | None
    upper_bound: float | None
    evidence_id: uuid.UUID | None


class ForecastRunOut(BaseModel):
    id: uuid.UUID
    metric: str
    granularity: str
    history_start_period: str
    history_end_period: str
    history_periods: int
    horizon_periods: int
    status: str
    status_reason: str | None
    method_name: str
    method_version: str
    confidence_level: float
    parameters: dict[str, object]
    holdout_periods: int | None
    holdout_mae: float | None
    holdout_mape_pct: float | None
    created_at: datetime
    forecasts: tuple[ForecastPointOut, ...] = ()
    fit_evidence_id: uuid.UUID | None = None
