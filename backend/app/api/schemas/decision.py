from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CreateDecisionRequest(BaseModel):
    name: str = Field(examples=["Which growth lever first?"])
    description: str | None = Field(
        default=None, examples=["Compare faster revenue growth against a cost-reduction push."]
    )
    # At least two -- comparing a single option against itself isn't a decision. The engine
    # re-validates this (app.decisions.engine.MIN_SCENARIOS); kept here too so a bad request
    # is rejected by Pydantic before a session is even opened.
    scenario_ids: list[uuid.UUID] = Field(min_length=2, examples=[[]])
    # Omit for the default equal split across all three criteria. When supplied, must cover a
    # non-empty subset of {"profitability", "growth", "cost_efficiency"} and sum to ~1.0 -- the
    # engine validates this and rejects rather than renormalizing (app.decisions.engine).
    criteria_weights: dict[str, float] | None = Field(
        default=None, examples=[{"profitability": 0.5, "growth": 0.3, "cost_efficiency": 0.2}]
    )


class DecisionOptionOut(BaseModel):
    id: uuid.UUID
    decision_run_id: uuid.UUID
    scenario_id: uuid.UUID | None
    title: str
    score: float | None
    rank: int | None
    criteria_breakdown: dict[str, object]
    rationale: str | None
    # None for an unscored option -- there is no recommendation Evidence row without a score
    # (see app/decisions/evidence.py::record_recommendation).
    evidence_id: uuid.UUID | None = None


class DecisionRunOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    criteria_weights: dict[str, object]
    status: str
    status_reason: str | None
    created_at: datetime
    options: tuple[DecisionOptionOut, ...] = ()
    # The FACT Evidence row describing the comparison itself (always present, regardless of
    # status -- see app/decisions/evidence.py::record_comparison_summary).
    fact_evidence_id: uuid.UUID | None = None
