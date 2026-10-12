"""Deterministic weighted multi-criteria scoring over Phase 6 `ScenarioResult` rows -- ranks
two or more existing `Scenario`s against each other on up to three criteria derived from each
scenario's own already-computed results. Never a new projection, never an LLM call, and never
the AI-narrator-written `Recommendation` text (`app/db/models/recommendations.py`, untouched):
just a deterministic ranking formula, framed in its Evidence as advisory (`app/decisions/
evidence.py`).

Three criteria, all oriented so that "higher is always better" (so a plain weighted sum, never
a mix of signs the caller has to reason about):

- **profitability** = average `gross_profit` `delta_percentage` across the scenario's periods.
- **growth**         = average `revenue` `delta_percentage` across the scenario's periods.
- **cost_efficiency** = average of the *negated* `cogs` `delta_percentage` -- a cost
  *reduction* (a negative COGS delta) scores positively, a cost increase scores negatively.

Default weighting is an equal split across all three criteria. A caller may instead supply
weights for any non-empty subset of them; the supplied weights must sum to ~1.0 and are
rejected outright (never silently renormalized) if they don't, so the request stays exactly
what was asked for. `score` is `None` for an option that lacks `ScenarioResult` data for *any
one* of the criteria actually being weighted -- never fabricated by quietly reweighting over
just the criteria that happened to have data, the same sufficiency-gating discipline every
prior phase in this project uses.
"""

from __future__ import annotations

import statistics
import uuid
from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.decision import DECISION_CRITERIA, DecisionOption, DecisionRun
from app.db.models.scenario import Scenario, ScenarioResult
from app.decisions import evidence as ev

_CRITERION_METRIC = {
    "profitability": "gross_profit",
    "growth": "revenue",
    "cost_efficiency": "cogs",
}
_NEGATED_CRITERIA = {"cost_efficiency"}

WEIGHT_SUM_TOLERANCE = 0.01
DEFAULT_WEIGHTS: dict[str, float] = {
    criterion: 1.0 / len(DECISION_CRITERIA) for criterion in DECISION_CRITERIA
}

MIN_SCENARIOS = 2


class InvalidDecisionRequestError(ValueError):
    pass


def _validate_weights(weights: dict[str, float] | None) -> dict[str, float]:
    if weights is None:
        return dict(DEFAULT_WEIGHTS)
    if not weights:
        raise InvalidDecisionRequestError(
            "criteria_weights cannot be empty; omit it for the default equal split."
        )
    unknown = sorted(set(weights) - set(DECISION_CRITERIA))
    if unknown:
        raise InvalidDecisionRequestError(
            f"Unknown criteria {unknown}; expected a subset of {DECISION_CRITERIA}."
        )
    if any(weight <= 0 for weight in weights.values()):
        raise InvalidDecisionRequestError("criteria_weights values must all be positive.")
    total = sum(weights.values())
    if abs(total - 1.0) > WEIGHT_SUM_TOLERANCE:
        raise InvalidDecisionRequestError(
            f"criteria_weights must sum to ~1.0 (within {WEIGHT_SUM_TOLERANCE}); got {total:.4f}. "
            "Not renormalized automatically, so the comparison stays exactly what was asked for."
        )
    return dict(weights)


def _criterion_value(session: Session, scenario_id: uuid.UUID, criterion: str) -> float | None:
    """Average `delta_percentage` across every period this scenario has for the criterion's
    metric, negated for cost_efficiency. `None` (never a fabricated 0) when the scenario has
    no ScenarioResult rows at all for that metric -- e.g. a revenue-only scenario has no
    gross_profit rows, since Phase 6 only derives gross_profit where both drivers had a
    baseline."""
    metric = _CRITERION_METRIC[criterion]
    rows = (
        session.execute(
            select(ScenarioResult.delta_percentage).where(
                ScenarioResult.scenario_id == scenario_id,
                ScenarioResult.metric == metric,
                ScenarioResult.delta_percentage.is_not(None),
            )
        )
        .scalars()
        .all()
    )
    deltas = [float(d) for d in rows if d is not None]
    if not deltas:
        return None
    average = statistics.fmean(deltas)
    return -average if criterion in _NEGATED_CRITERIA else average


def _score_scenario(
    session: Session, scenario_id: uuid.UUID, weights: dict[str, float]
) -> tuple[float | None, dict[str, dict[str, object]]]:
    """Returns `(composite_score, criteria_breakdown)`. `criteria_breakdown` always has one
    entry per weighted criterion (so an unscored option's breakdown still shows exactly which
    criteria were missing); `composite_score` is `None` if any one of them was."""
    breakdown: dict[str, dict[str, object]] = {}
    any_missing = False
    weighted_sum = 0.0
    for criterion, weight in weights.items():
        value = _criterion_value(session, scenario_id, criterion)
        entry: dict[str, object] = {"weight": weight, "value": value}
        if value is None:
            any_missing = True
        else:
            weighted = weight * value
            entry["weighted"] = weighted
            weighted_sum += weighted
        breakdown[criterion] = entry
    return (None if any_missing else weighted_sum), breakdown


def _rationale_for(option: DecisionOption, total_scored: int) -> str:
    # The DB column is the generic `dict[str, object]` every JSON column uses; every entry
    # `_score_scenario` builds is itself a dict, so this cast just restores that local
    # structure for mypy rather than changing anything about what's actually stored.
    breakdown = cast("dict[str, dict[str, object]]", option.criteria_breakdown)
    if option.score is None:
        missing = sorted(criterion for criterion, entry in breakdown.items() if entry.get("value") is None)
        return f"Not scored: no scenario data for {', '.join(missing)} (required by the requested weights)."
    scored_entries = {c: e for c, e in breakdown.items() if "weighted" in e}
    top_criterion = max(scored_entries, key=lambda c: cast(float, scored_entries[c]["weighted"]))
    top = scored_entries[top_criterion]
    return (
        f"Ranked {option.rank} of {total_scored} scored options with a composite score of "
        f"{float(option.score):.3f}; driven primarily by {top_criterion} "
        f"({cast(float, top['value']):.2f}% at weight {cast(float, top['weight']):.2f})."
    )


def _sort_key(option: DecisionOption) -> tuple[float, str]:
    # Only ever called on an already-filtered "score is not None" iterable (see
    # score_decision); the assert documents that invariant for mypy, the same way
    # tests/scenarios/test_engine.py's own `_f()` helper does for a Numeric column read back.
    assert option.score is not None
    return -float(option.score), option.title


def score_decision(
    session: Session,
    *,
    name: str,
    description: str | None = None,
    scenario_ids: list[uuid.UUID],
    criteria_weights: dict[str, float] | None = None,
    persist: bool = True,
) -> DecisionRun:
    if len(scenario_ids) < MIN_SCENARIOS:
        raise InvalidDecisionRequestError(f"At least {MIN_SCENARIOS} scenario_ids are required to compare.")
    if len(set(scenario_ids)) != len(scenario_ids):
        raise InvalidDecisionRequestError("scenario_ids must not contain duplicates.")

    weights = _validate_weights(criteria_weights)

    scenarios: dict[uuid.UUID, Scenario] = {}
    for scenario_id in scenario_ids:
        scenario = session.get(Scenario, scenario_id)
        if scenario is None:
            raise InvalidDecisionRequestError(f"'{scenario_id}' is not a known scenario.")
        scenarios[scenario_id] = scenario

    run = DecisionRun(name=name, description=description, criteria_weights=weights, status="completed")
    session.add(run)
    session.flush()

    options: list[DecisionOption] = []
    for scenario_id in scenario_ids:
        scenario = scenarios[scenario_id]
        score, breakdown = _score_scenario(session, scenario_id, weights)
        option = DecisionOption(
            decision_run_id=run.id,
            scenario_id=scenario_id,
            title=scenario.name,
            score=score,
            criteria_breakdown=breakdown,
        )
        session.add(option)
        options.append(option)
    session.flush()

    # Rank only the scored options, highest composite score first; ties broken by title for a
    # deterministic, reproducible order. Unscored options keep rank=None.
    scored_options = sorted((o for o in options if o.score is not None), key=_sort_key)
    for rank, option in enumerate(scored_options, start=1):
        option.rank = rank

    for option in options:
        option.rationale = _rationale_for(option, len(scored_options))
    session.flush()

    if not scored_options:
        run.status = "insufficient_data"
        run.status_reason = (
            "None of the compared scenarios had ScenarioResult data for every weighted "
            "criterion. Generate scenarios that cover gross_profit/revenue/cogs (matching the "
            "requested weights) before comparing."
        )

    ev.record_comparison_summary(
        session,
        decision_run_id=run.id,
        scenario_titles=[scenarios[sid].name for sid in scenario_ids],
        criteria_weights=weights,
    )
    for option in scored_options:
        ev.record_recommendation(
            session, decision_run_id=run.id, option=option, total_scored=len(scored_options)
        )

    if persist:
        session.commit()
    return run


__all__ = [
    "DEFAULT_WEIGHTS",
    "MIN_SCENARIOS",
    "WEIGHT_SUM_TOLERANCE",
    "InvalidDecisionRequestError",
    "score_decision",
]
