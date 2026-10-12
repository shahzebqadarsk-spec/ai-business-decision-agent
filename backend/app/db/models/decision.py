"""Phase 7: deterministic Decision Scoring (replaces the Phase 0 `DecisionOption` placeholder
that lived in `app/db/models/analysis.py`, the same way Phase 5 replaced the Phase 0 `Forecast`
placeholder with `app/db/models/forecasting.py` and Phase 6 replaced the Phase 0 `Scenario`
placeholder with `app/db/models/scenario.py`).

Scope decision (independent judgment, no formal spec for this phase -- see
`docs/PHASE_7_DECISION_SCORING.md`): Decision Scoring is a deterministic, weighted
multi-criteria RANKING of existing Phase 6 `Scenario` rows against each other -- never a new
projection, never an LLM call, and never the AI-narrator-written, human-approved
`Recommendation` text (that stays a separate, later-phase placeholder in
`app/db/models/recommendations.py`, untouched here). This phase closes the loop on
`Evidence.claim_type`'s `"recommendation"` value, reserved since Phase 4 but never produced
until now: one FACT Evidence row per `DecisionRun` (what was compared, with what weights), and
one RECOMMENDATION Evidence row per ranked `DecisionOption`, both explicitly framed as advisory
-- "the AI recommends; a human approves" (the README's own governing principle), never a
guaranteed outcome.

`DecisionRun` is one named comparison (which criteria weights were used, whether every
requested `Scenario` had enough data to be scored); `DecisionOption` is one scenario's result
within that comparison -- its composite score, its per-criterion breakdown, and its rank.

`scenario_id` deliberately mirrors `Scenario.revenue_forecast_run_id`/`cogs_forecast_run_id`'s
own `SET NULL` pattern rather than `CASCADE`: a `DecisionOption`'s score, breakdown, and
rationale are themselves a historical record with independent value (what the AI recommended,
when) -- deleting the `Scenario` it was computed from must not silently destroy that record,
only lose its traceability link. `decision_run_id` is true ownership (an option has no meaning
outside the run that produced it), so it stays `NOT NULL`/`CASCADE`, the same way
`ScenarioResult.scenario_id` and `Issue.detection_run_id` are."""

from __future__ import annotations

import uuid

from sqlalchemy import JSON, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin, check_in, enum_column

DECISION_STATUSES = ("completed", "insufficient_data")

# The three criteria this phase's scoring engine computes from Phase 6 ScenarioResult rows.
# Kept as a plain tuple (not a DB enum) because criteria_weights/criteria_breakdown are JSON
# keyed by these names, not a column value that needs a CHECK constraint.
DECISION_CRITERIA = ("profitability", "growth", "cost_efficiency")


class DecisionRun(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """One named comparison of two or more `Scenario`s against each other. Reproducible by
    construction: re-running with the same scenario ids and weights against the same
    `ScenarioResult` rows reproduces the same `DecisionOption` scores -- no hidden state, no
    randomness, exactly like Phase 6's own `Scenario`."""

    __tablename__ = "decision_runs"
    __table_args__ = (check_in("status", DECISION_STATUSES, constraint_name="status_valid"),)

    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # {"profitability": 0.33, "growth": 0.33, "cost_efficiency": 0.34} -- the weights actually
    # used (either caller-supplied, validated to sum to ~1.0, or the default equal split).
    # Stored explicitly so a DecisionRun is self-describing without recomputing anything.
    criteria_weights: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)

    status: Mapped[str] = enum_column(length=24, default="completed")
    status_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class DecisionOption(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """One `Scenario`'s result within a `DecisionRun`. `score` is `None` (never fabricated via
    partial reweighting) when the scenario lacked data for one or more requested criteria;
    `rank` is `None` whenever `score` is, since an unscored option cannot be meaningfully
    ordered against the others."""

    __tablename__ = "decision_options"

    decision_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("decision_runs.id", ondelete="CASCADE"), index=True
    )
    # SET NULL, not CASCADE -- see module docstring. Nullable so that link-loss on scenario
    # deletion never forces this row's own deletion.
    scenario_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("scenarios.id", ondelete="SET NULL"), nullable=True, index=True
    )

    title: Mapped[str] = mapped_column(String(255))
    # Numeric(12, 4), not the Phase 0 placeholder's original Numeric(6, 3): `score` is a
    # weighted average of ScenarioResult.delta_percentage values, which can themselves reach
    # the same +/-1000% range a Scenario's own adjustment_pct is allowed to (see
    # app/api/schemas/scenario.py) -- widened to match ScenarioResult.delta_percentage's own
    # precision and avoid a numeric-overflow error on a legitimate extreme scenario.
    score: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    rank: Mapped[int | None] = mapped_column(nullable=True)

    # {"profitability": {"weight": 0.33, "value": 4.2, "weighted": 1.386}, ...} -- per-criterion
    # inputs to the composite score, kept explicit so a user can see exactly how `score` was
    # built rather than trusting an opaque number.
    criteria_breakdown: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)

    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)


__all__ = ["DECISION_CRITERIA", "DECISION_STATUSES", "DecisionOption", "DecisionRun"]
