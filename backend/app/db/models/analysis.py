"""Phase 4: issue detection + RCA run model + the Evidence system.

`Recommendation`/`VerificationReport` (in `app/db/models/recommendations.py`) remain untouched
placeholders for a later phase (the AI narrator's written-up, human-approved recommendation,
and the verifier that checks it) -- explicitly out of scope through Phase 7. `Forecast` was a
Phase 0 placeholder here too; Phase 5 replaced it with a real `ForecastRun`/`Forecast` pair in
`app/db/models/forecasting.py` (its own file, mirroring how KPI calculations got
`app/db/models/kpi.py` rather than living in this one) -- `Evidence` below gained two nullable
FKs (`forecast_run_id`, `forecast_id`) so a forecasted point's Evidence row is reachable the
same way an Issue's is. `Scenario` was a Phase 0 placeholder here too; Phase 6 replaced it the
same way, with a real `Scenario`/`ScenarioResult` pair in `app/db/models/scenario.py`.
`DecisionOption` was a Phase 0 placeholder here too; Phase 7 replaced it the same way, with a
real `DecisionRun`/`DecisionOption` pair in `app/db/models/decision.py` -- `Evidence` below
gained two more nullable FKs (`decision_run_id`, `decision_option_id`) for the same reason, and
is the first production user of `claim_type="recommendation"`.

`AnalysisRun` and `Evidence` existed as thin Phase 0 placeholders ("Phase 3+ (KPI/RCA, ...)")
and are now filled in for real, per the Phase 4 spec's "RCA run model" and "Evidence system"
requirements. `Issue` is new.

Design note on normalization: the spec lists "evidence references" as a field of an Issue, and
"detected issues" / "evidence IDs" as fields of an AnalysisRun. Rather than storing redundant
ID-array columns that could drift from the rows they list, this schema stores the relationship
once (`Evidence.issue_id`, `Evidence.analysis_run_id`, `Issue.detection_run_id`) and the API
layer (app/api/routers/rca.py) derives those "field" views with a query -- the normalized form
the spec's own field list is describing, not a deviation from it.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin, check_in, enum_column

# --- Phase 4: issue detection + RCA -----------------------------------------------------

ANALYSIS_RUN_TYPES = ("issue_detection", "rca")
ANALYSIS_RUN_STATUSES = ("pending", "running", "completed", "failed")

ISSUE_TYPES = (
    "revenue_decline",
    "revenue_growth_slowdown",
    "margin_deterioration",
    "regional_performance_deterioration",
    "product_margin_deterioration",
    "unusual_cost_movement",
    "unusual_volume_movement",
    "customer_concentration_change",
    # Reserved vocabulary, no detector registered yet -- the canonical table each needs
    # (fact_inventory / fact_workforce) is not materialized (Phase 2 scope: fact_sales only).
    # Listed here, same as the Phase 3 KPI registry's "stub" entries, so a later phase adds a
    # detector function, not a migration.
    "material_inventory_issue",
    "overtime_issue",
)
ISSUE_SEVERITIES = ("low", "medium", "high", "critical")
ISSUE_STATUSES = ("detected", "analyzed", "unavailable")
ISSUE_GRANULARITIES = ("month", "quarter", "year")

EVIDENCE_CLAIM_TYPES = ("fact", "contribution", "inference", "recommendation")


class AnalysisRun(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """One execution of the issue-detection engine or the RCA decomposition engine.

    Reproducible by construction: `analysis_type` + `parameters` (the exact granularity/
    period/comparison/dataset the run was invoked with) is enough to redo it, since both
    engines are pure functions of canonical data -- there is no hidden state."""

    __tablename__ = "analysis_runs"
    __table_args__ = (
        check_in("analysis_type", ANALYSIS_RUN_TYPES, constraint_name="analysis_type_valid"),
        check_in("status", ANALYSIS_RUN_STATUSES, constraint_name="status_valid"),
        check_in("granularity", ISSUE_GRANULARITIES, constraint_name="granularity_valid"),
    )

    dataset_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("datasets.id", ondelete="SET NULL"), nullable=True
    )
    analysis_type: Mapped[str] = enum_column(length=32)
    granularity: Mapped[str] = enum_column(length=16)
    period_key: Mapped[str] = mapped_column(String(32))
    comparison_type: Mapped[str | None] = mapped_column(String(8), nullable=True)
    comparison_period_key: Mapped[str | None] = mapped_column(String(32), nullable=True)
    parameters: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = enum_column(length=32, default="pending")
    result_summary: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def mark_completed(self, summary: dict[str, object]) -> None:
        self.status = "completed"
        self.result_summary = summary
        self.completed_at = datetime.now(UTC)


class Issue(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """A deterministically detected, materiality-screened business change.

    Carries only FACTS at detection time (current/prior value, change, which materiality
    rule(s) fired). `decomposition` is filled in by `POST /issues/{id}/analyze` and holds the
    *persisted* driver-analysis summary so `GET /issues/{id}` doesn't recompute -- but it is a
    cache of what the Evidence rows already say, never a second source of truth: every number
    inside it names the Evidence ID that backs it (see app/rca/evidence.py)."""

    __tablename__ = "issues"
    __table_args__ = (
        check_in("issue_type", ISSUE_TYPES, constraint_name="issue_type_valid"),
        check_in("severity", ISSUE_SEVERITIES, constraint_name="severity_valid"),
        check_in("status", ISSUE_STATUSES, constraint_name="status_valid"),
        check_in("granularity", ISSUE_GRANULARITIES, constraint_name="granularity_valid"),
    )

    detection_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True
    )
    latest_analysis_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="SET NULL"), nullable=True
    )

    issue_type: Mapped[str] = enum_column(length=48)
    title: Mapped[str] = mapped_column(String(255))
    severity: Mapped[str] = enum_column(length=16)
    status: Mapped[str] = enum_column(length=16, default="detected")

    granularity: Mapped[str] = enum_column(length=16)
    period_key: Mapped[str] = mapped_column(String(32))
    comparison_period_key: Mapped[str | None] = mapped_column(String(32), nullable=True)

    metric: Mapped[str] = mapped_column(String(64))
    current_value: Mapped[float | None] = mapped_column(Numeric(24, 4), nullable=True)
    prior_value: Mapped[float | None] = mapped_column(Numeric(24, 4), nullable=True)
    absolute_change: Mapped[float | None] = mapped_column(Numeric(24, 4), nullable=True)
    percentage_change: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)

    affected_dimension: Mapped[str | None] = mapped_column(String(32), nullable=True)
    affected_entity: Mapped[str | None] = mapped_column(String(64), nullable=True)

    materiality: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    decomposition: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Evidence(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """A typed, traceable analytical claim. Every number an issue or its driver analysis
    shows must trace back to exactly one row here (spec section 10/11): what was claimed, the
    exact metric/period/dimension it's about, which canonical rows and fields fed it, and the
    deterministic calculation (name + version + parameters) that produced it -- enough for a
    future LLM narrator to read Evidence rows and write a narrative without ever touching the
    database itself, and without being able to alter what's recorded here."""

    __tablename__ = "evidence"
    __table_args__ = (check_in("claim_type", EVIDENCE_CLAIM_TYPES, constraint_name="claim_type_valid"),)

    analysis_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    issue_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("issues.id", ondelete="CASCADE"), nullable=True, index=True
    )
    # Phase 5: the same run/child pattern as analysis_run_id/issue_id, for forecast evidence
    # (claim_type="inference"). Both nullable and independent of the Phase 4 pair above -- one
    # Evidence row never belongs to both an Issue and a Forecast.
    forecast_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("forecast_runs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    forecast_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("forecasts.id", ondelete="CASCADE"), nullable=True, index=True
    )
    # Phase 7: same run/child pattern again, for decision-scoring evidence
    # (claim_type="recommendation" -- reserved since Phase 4, used for real for the first time
    # here). Independent of both pairs above -- one Evidence row never belongs to more than
    # one of Issue, Forecast, or DecisionOption.
    decision_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("decision_runs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    decision_option_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("decision_options.id", ondelete="CASCADE"), nullable=True, index=True
    )

    claim_type: Mapped[str] = enum_column(length=16, default="fact")
    claim: Mapped[str] = mapped_column(Text)

    metric: Mapped[str | None] = mapped_column(String(64), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(16), nullable=True)
    granularity: Mapped[str | None] = mapped_column(String(16), nullable=True)
    period_key: Mapped[str | None] = mapped_column(String(32), nullable=True)
    comparison_period_key: Mapped[str | None] = mapped_column(String(32), nullable=True)
    dimension: Mapped[str | None] = mapped_column(String(32), nullable=True)
    dimension_value: Mapped[str | None] = mapped_column(String(64), nullable=True)

    value: Mapped[float | None] = mapped_column(Numeric(24, 4), nullable=True)
    comparison_value: Mapped[float | None] = mapped_column(Numeric(24, 4), nullable=True)
    absolute_change: Mapped[float | None] = mapped_column(Numeric(24, 4), nullable=True)
    percentage_change: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    contribution_to_total_pct: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)

    source_dataset_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("datasets.id", ondelete="SET NULL"), nullable=True
    )
    source_file_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    source_fields: Mapped[list[str]] = mapped_column(JSON, default=list)

    calculation_name: Mapped[str] = mapped_column(String(96))
    calculation_version: Mapped[str] = mapped_column(String(32))
    calculation_parameters: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)

    # Deliberately not named "confidence": nothing here is a probability estimate -- it is
    # data-quality/method metadata about a deterministic calculation (e.g. partition coverage,
    # which decomposition method was used). Calling it "confidence" would imply a statistical
    # property this engine does not compute.
    quality_metadata: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)

    data: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
