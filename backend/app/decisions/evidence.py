"""Builds and persists `Evidence` rows for decision scoring (Phase 7).

Closes the loop on `Evidence.claim_type="recommendation"` -- reserved since Phase 4, never
produced until this phase. A composite decision score is this system's first genuinely
advisory claim: not a FACT (nothing was measured), not an INFERENCE (nothing about the future
is being projected), but a deterministic *ranking opinion* over `Scenario`s the user already
built -- framed explicitly per the README's own governing principle ("The AI recommends; a
human approves."), never a guaranteed outcome and never a command.

One FACT row per `DecisionRun` (what was compared, with what weights) is written regardless of
outcome; one RECOMMENDATION row per *scored* `DecisionOption` -- an unscored option gets no
recommendation, because there is nothing to recommend without a score. Same no-calculation-here
rule as every other phase's evidence module: this only formats and persists numbers
`engine.py` already computed.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.db.models.analysis import Evidence
from app.db.models.decision import DecisionOption

DECISION_CALCULATION_VERSION = "1.0.0"
METHOD_NAME = "weighted_multi_criteria_scenario_ranking"


def record_comparison_summary(
    session: Session,
    *,
    decision_run_id: uuid.UUID,
    scenario_titles: list[str],
    criteria_weights: dict[str, float],
) -> Evidence:
    weights_text = ", ".join(
        f"{criterion}={weight:.2f}" for criterion, weight in sorted(criteria_weights.items())
    )
    titles_text = ", ".join(f'"{title}"' for title in scenario_titles)
    claim = (
        f"Compared {len(scenario_titles)} scenarios ({titles_text}) using weighted criteria "
        f"({weights_text}), each criterion itself a deterministic average of that scenario's "
        f"own ScenarioResult rows. This is a ranking of hypotheticals the user already built, "
        f"not a measurement of what happened or a prediction of what will."
    )
    evidence = Evidence(
        decision_run_id=decision_run_id,
        claim_type="fact",
        claim=claim,
        calculation_name=METHOD_NAME,
        calculation_version=DECISION_CALCULATION_VERSION,
        calculation_parameters={"criteria_weights": criteria_weights, "scenario_titles": scenario_titles},
    )
    session.add(evidence)
    session.flush()
    return evidence


def record_recommendation(
    session: Session,
    *,
    decision_run_id: uuid.UUID,
    option: DecisionOption,
    total_scored: int,
) -> Evidence:
    """One row per *scored* option -- callers must not call this for an unscored one (there is
    nothing to recommend without a score)."""
    assert option.score is not None and option.rank is not None
    # option.rationale already states the rank, composite score, and driving criterion (see
    # app/decisions/engine.py::_rationale_for) -- not repeated here, just led into and framed.
    claim = (
        f'The AI recommends "{option.title}". {option.rationale or ""} '
        f"This is an advisory ranking produced by a deterministic formula, not a decision -- "
        f"a human approves before any action is taken."
    ).strip()
    evidence = Evidence(
        decision_run_id=decision_run_id,
        decision_option_id=option.id,
        claim_type="recommendation",
        claim=claim,
        value=float(option.score),
        calculation_name=METHOD_NAME,
        calculation_version=DECISION_CALCULATION_VERSION,
        calculation_parameters={"criteria_breakdown": option.criteria_breakdown},
        quality_metadata={"rank": option.rank, "total_scored": total_scored},
    )
    session.add(evidence)
    session.flush()
    return evidence


__all__ = [
    "DECISION_CALCULATION_VERSION",
    "METHOD_NAME",
    "record_comparison_summary",
    "record_recommendation",
]
