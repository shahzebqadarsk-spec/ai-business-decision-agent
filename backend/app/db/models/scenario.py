"""Phase 6: deterministic Scenario / What-If Analysis (replaces the Phase 0 `Scenario`
placeholder that lived in `app/db/models/analysis.py`, the same way Phase 5 replaced the
Phase 0 `Forecast` placeholder with `app/db/models/forecasting.py`).

Scope decision (independent judgment, no formal spec for this phase -- see
`docs/PHASE_6_SCENARIO_ENGINE.md`): a scenario is a deterministic percentage shock applied to
the *existing* Phase 5 revenue/COGS baseline forecasts, with `gross_profit`/`gross_margin_pct`
re-derived from the (possibly adjusted) revenue and COGS using the exact same formulas Phase 3/4
already use (`GP = Revenue - COGS`, `margin% = GP / Revenue * 100`) -- never a new, independent
forecast of its own, and never a probability-weighted or Monte-Carlo projection. Decision
scoring, the AI narrator, the verifier, and chat orchestration were explicitly deferred at the
time this file was written; `DecisionOption` (in `app/db/models/analysis.py`) was then an
untouched placeholder pointing at this table's `id` via `scenario_id`. (Historical note, not
kept current here: Phase 7 replaced that placeholder with a real `DecisionRun`/`DecisionOption`
pair in `app/db/models/decision.py`, whose `DecisionOption.scenario_id` still points here --
see that file's own module docstring.)

A scenario deliberately writes **no Evidence rows**. Evidence (Phase 4) backs a claim about
what the deterministic analytics measured or inferred about the real world (FACT/CONTRIBUTION/
INFERENCE); a scenario is an explicit hypothetical ("what if revenue grew 5% faster than
trend") that the user is constructing to explore, not a claim this system is making about
reality. Blurring that line would make "Evidence" stop meaning what Phase 4 defined it to mean.
Every number is still fully traceable, just via `ScenarioResult` rows and their own
`baseline_forecast_id` references rather than via `Evidence`.

`Scenario` is one named what-if run (the adjustment percentages applied, which baseline
`ForecastRun`s it drew from); `ScenarioResult` is one (metric, period) row of baseline vs.
scenario value belonging to a `Scenario`."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin, check_in, enum_column

# gross_profit/gross_margin_pct are *derived* here (never independently fitted) from the
# revenue/cogs scenario values -- same restriction Phase 5 documented for forecasting, kept
# consistent rather than re-litigated.
SCENARIO_METRICS = ("revenue", "cogs", "gross_profit", "gross_margin_pct")

SCENARIO_STATUSES = ("completed", "insufficient_data")


class Scenario(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """One what-if run: the adjustment percentages requested and which baseline `ForecastRun`s
    (Phase 5) they were applied to. Reproducible by construction: re-running with the same
    adjustments against the same baseline run ids reproduces the same `ScenarioResult` rows,
    since the engine is a pure function of those inputs -- no hidden state, no randomness."""

    __tablename__ = "scenarios"
    __table_args__ = (check_in("status", SCENARIO_STATUSES, constraint_name="status_valid"),)

    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Percentage shocks, e.g. 5.0 means "5% higher than the baseline forecast at every period."
    # 0.0 (the default) means "no change to this driver" -- a scenario can adjust just one of
    # the two and leave the other at its unadjusted baseline.
    revenue_growth_adjustment_pct: Mapped[float] = mapped_column(Numeric(8, 4), default=0.0)
    cogs_adjustment_pct: Mapped[float] = mapped_column(Numeric(8, 4), default=0.0)

    # Which Phase 5 ForecastRun each driver's baseline came from -- `None` when no completed
    # run existed for that metric and the caller didn't supply one (see app/scenarios/engine.py
    # sufficiency gating). SET NULL (not CASCADE): deleting an old forecast run must never
    # silently delete a scenario that was built on it; it just loses its own traceability link.
    revenue_forecast_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("forecast_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    cogs_forecast_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("forecast_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )

    status: Mapped[str] = enum_column(length=24, default="completed")
    status_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    horizon_periods: Mapped[int] = mapped_column(default=0)


class ScenarioResult(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """One (metric, period) comparison row belonging to a `Scenario`. `baseline_value` is the
    unadjusted figure (the Phase 5 forecast's own point estimate for revenue/cogs, or the
    GP/margin% derived from the two unadjusted forecasts) -- `None` only for a derived metric
    when one of its two inputs has no baseline at that period (never a fabricated 0).
    `scenario_value` is always present; it equals `baseline_value` exactly when the relevant
    adjustment_pct is 0."""

    __tablename__ = "scenario_results"
    __table_args__ = (check_in("metric", SCENARIO_METRICS, constraint_name="metric_valid"),)

    scenario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scenarios.id", ondelete="CASCADE"), index=True)
    metric: Mapped[str] = enum_column(length=32)
    period_key: Mapped[str] = mapped_column(String(32), index=True)
    horizon_index: Mapped[int] = mapped_column()

    baseline_value: Mapped[float | None] = mapped_column(Numeric(24, 4), nullable=True)
    scenario_value: Mapped[float] = mapped_column(Numeric(24, 4))
    delta_absolute: Mapped[float | None] = mapped_column(Numeric(24, 4), nullable=True)
    delta_percentage: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)


__all__ = ["SCENARIO_METRICS", "SCENARIO_STATUSES", "Scenario", "ScenarioResult"]
