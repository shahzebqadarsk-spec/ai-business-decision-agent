from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CreateScenarioRequest(BaseModel):
    name: str = Field(examples=["Faster revenue growth"])
    description: str | None = Field(default=None, examples=["What if revenue grows 5% faster than trend?"])
    # +/-100% bounds a shock to "revenue/cogs cannot go negative" at the low end; the high end
    # is a generous sanity cap, not a modeled limit -- this is a plain multiplier, not a fit.
    revenue_growth_adjustment_pct: float = Field(default=0.0, ge=-100.0, le=1000.0, examples=[5.0])
    cogs_adjustment_pct: float = Field(default=0.0, ge=-100.0, le=1000.0, examples=[-2.0])
    # Omit to use the latest completed forecast run for that metric automatically.
    revenue_forecast_run_id: uuid.UUID | None = None
    cogs_forecast_run_id: uuid.UUID | None = None


class ScenarioResultOut(BaseModel):
    id: uuid.UUID
    scenario_id: uuid.UUID
    metric: str
    period_key: str
    horizon_index: int
    baseline_value: float | None
    scenario_value: float
    delta_absolute: float | None
    delta_percentage: float | None


class ScenarioOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    revenue_growth_adjustment_pct: float
    cogs_adjustment_pct: float
    revenue_forecast_run_id: uuid.UUID | None
    cogs_forecast_run_id: uuid.UUID | None
    status: str
    status_reason: str | None
    horizon_periods: int
    created_at: datetime
    results: tuple[ScenarioResultOut, ...] = ()
