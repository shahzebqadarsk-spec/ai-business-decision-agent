"""Orchestration tests: score_decision() ranks existing Scenarios against each other on
weighted criteria derived from their own ScenarioResult rows, with explicit, self-contained
control over which Scenario/ScenarioResult rows exist -- same defensive delete-then-rollback
discipline tests/scenarios/test_engine.py established, since other test files in this suite
commit real Scenario rows (persist=True) that must not leak into these tests' assumptions."""

from __future__ import annotations

import uuid

import pytest
from app.db.models.analysis import Evidence
from app.db.models.decision import DecisionOption
from app.db.models.scenario import Scenario, ScenarioResult
from app.decisions import engine
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

pytestmark = pytest.mark.usefixtures("seeded_fact_sales_file_id")


def _clean_scenarios(db_session: Session) -> None:
    """Deletes (within this test's own uncommitted transaction only) every Scenario row, so a
    freshly created one is the only thing engine.score_decision() can ever resolve by id --
    never committed, so it has no effect on any other test."""
    db_session.execute(delete(ScenarioResult))
    db_session.execute(delete(Scenario))
    db_session.flush()


def _make_scenario(
    db_session: Session,
    name: str,
    *,
    rows: list[tuple[str, str, float, float]],
) -> Scenario:
    """Builds a Scenario directly (bypassing the Scenario engine, which this phase's tests
    don't need) with explicit (metric, period_key, baseline, scenario) ScenarioResult rows --
    delta_absolute/delta_percentage computed the same way app/scenarios/engine.py does."""
    scenario = Scenario(name=name, status="completed", horizon_periods=len({r[1] for r in rows}))
    db_session.add(scenario)
    db_session.flush()
    for horizon_index, (metric, period_key, baseline, scenario_value) in enumerate(rows, start=1):
        delta_absolute = scenario_value - baseline
        delta_percentage = (delta_absolute / baseline * 100) if baseline else None
        db_session.add(
            ScenarioResult(
                scenario_id=scenario.id,
                metric=metric,
                period_key=period_key,
                horizon_index=horizon_index,
                baseline_value=baseline,
                scenario_value=scenario_value,
                delta_absolute=delta_absolute,
                delta_percentage=delta_percentage,
            )
        )
    db_session.flush()
    return scenario


def _options(db_session: Session, decision_run_id: uuid.UUID) -> list[DecisionOption]:
    query = select(DecisionOption).where(DecisionOption.decision_run_id == decision_run_id)
    return list(db_session.execute(query).scalars().all())


def _evidence(db_session: Session, decision_run_id: uuid.UUID) -> list[Evidence]:
    query = select(Evidence).where(Evidence.decision_run_id == decision_run_id)
    return list(db_session.execute(query).scalars().all())


def test_ranks_two_fully_scored_scenarios_by_default_equal_weights(db_session: Session) -> None:
    _clean_scenarios(db_session)
    # Growth scenario: strong revenue, flat cogs, flat gross_profit.
    growth = _make_scenario(
        db_session,
        "Growth push",
        rows=[
            ("revenue", "2026-01", 1_000_000.0, 1_200_000.0),
            ("cogs", "2026-01", 500_000.0, 500_000.0),
            ("gross_profit", "2026-01", 500_000.0, 700_000.0),
        ],
    )
    # Cost scenario: flat revenue, cheaper cogs, higher gross_profit.
    cost = _make_scenario(
        db_session,
        "Cost discipline",
        rows=[
            ("revenue", "2026-01", 1_000_000.0, 1_000_000.0),
            ("cogs", "2026-01", 500_000.0, 400_000.0),
            ("gross_profit", "2026-01", 500_000.0, 600_000.0),
        ],
    )

    run = engine.score_decision(
        db_session, name="Growth vs cost", scenario_ids=[growth.id, cost.id], persist=False
    )
    assert run.status == "completed"
    assert run.criteria_weights == pytest.approx(engine.DEFAULT_WEIGHTS)

    options = {o.title: o for o in _options(db_session, run.id)}
    assert options["Growth push"].score is not None
    assert options["Cost discipline"].score is not None
    # Growth push: profitability +40%, growth +20%, cost_efficiency -0% (negated 0) -> higher
    # composite than Cost discipline: profitability +20%, growth 0%, cost_efficiency +20%.
    assert float(options["Growth push"].score) > float(options["Cost discipline"].score)
    assert options["Growth push"].rank == 1
    assert options["Cost discipline"].rank == 2
    assert options["Growth push"].rationale is not None

    evidence = _evidence(db_session, run.id)
    claim_types = {e.claim_type for e in evidence}
    assert claim_types == {"fact", "recommendation"}
    recommendation_count = sum(1 for e in evidence if e.claim_type == "recommendation")
    assert recommendation_count == 2
    db_session.rollback()


def test_custom_weights_change_the_ranking(db_session: Session) -> None:
    _clean_scenarios(db_session)
    growth = _make_scenario(
        db_session,
        "Growth-heavy",
        rows=[("revenue", "2026-01", 1_000_000.0, 1_500_000.0)],
    )
    cost = _make_scenario(
        db_session,
        "Cost-heavy",
        rows=[("cogs", "2026-01", 1_000_000.0, 700_000.0)],
    )

    run = engine.score_decision(
        db_session,
        name="weight sensitivity",
        scenario_ids=[growth.id, cost.id],
        criteria_weights={"growth": 1.0},
        persist=False,
    )
    options = {o.title: o for o in _options(db_session, run.id)}
    # "Cost-heavy" has no revenue rows at all, so its "growth" criterion is unscored -- and
    # with growth weighted at 1.0, that means its composite score is None too.
    assert options["Growth-heavy"].score is not None
    assert options["Cost-heavy"].score is None
    assert options["Growth-heavy"].rank == 1
    assert options["Cost-heavy"].rank is None
    db_session.rollback()


def test_insufficient_data_when_no_compared_scenario_has_any_weighted_criterion(db_session: Session) -> None:
    _clean_scenarios(db_session)
    a = _make_scenario(db_session, "A", rows=[("revenue", "2026-01", 1_000.0, 1_100.0)])
    b = _make_scenario(db_session, "B", rows=[("revenue", "2026-02", 2_000.0, 2_200.0)])

    run = engine.score_decision(
        db_session,
        name="profitability only, neither has gross_profit",
        scenario_ids=[a.id, b.id],
        criteria_weights={"profitability": 1.0},
        persist=False,
    )
    assert run.status == "insufficient_data"
    assert run.status_reason is not None
    options = _options(db_session, run.id)
    assert all(o.score is None and o.rank is None for o in options)
    # A FACT row describing the comparison is written regardless of outcome; no recommendation
    # rows, since nothing was scored (app/decisions/evidence.py::record_recommendation is only
    # ever called per *scored* option).
    evidence = _evidence(db_session, run.id)
    assert [e.claim_type for e in evidence] == ["fact"]
    db_session.rollback()


def test_weights_not_summing_to_one_are_rejected_not_renormalized(db_session: Session) -> None:
    _clean_scenarios(db_session)
    a = _make_scenario(db_session, "A", rows=[("revenue", "2026-01", 1_000.0, 1_100.0)])
    b = _make_scenario(db_session, "B", rows=[("revenue", "2026-01", 1_000.0, 1_050.0)])
    with pytest.raises(engine.InvalidDecisionRequestError):
        engine.score_decision(
            db_session,
            name="bad weights",
            scenario_ids=[a.id, b.id],
            criteria_weights={"growth": 0.9},
            persist=False,
        )
    db_session.rollback()


def test_unknown_criterion_in_weights_is_rejected(db_session: Session) -> None:
    _clean_scenarios(db_session)
    a = _make_scenario(db_session, "A", rows=[("revenue", "2026-01", 1_000.0, 1_100.0)])
    b = _make_scenario(db_session, "B", rows=[("revenue", "2026-01", 1_000.0, 1_050.0)])
    with pytest.raises(engine.InvalidDecisionRequestError):
        engine.score_decision(
            db_session,
            name="bad criterion",
            scenario_ids=[a.id, b.id],
            criteria_weights={"made_up_criterion": 1.0},
            persist=False,
        )
    db_session.rollback()


def test_fewer_than_two_scenario_ids_is_rejected(db_session: Session) -> None:
    _clean_scenarios(db_session)
    a = _make_scenario(db_session, "A", rows=[("revenue", "2026-01", 1_000.0, 1_100.0)])
    with pytest.raises(engine.InvalidDecisionRequestError):
        engine.score_decision(db_session, name="too few", scenario_ids=[a.id], persist=False)
    db_session.rollback()


def test_duplicate_scenario_ids_are_rejected(db_session: Session) -> None:
    _clean_scenarios(db_session)
    a = _make_scenario(db_session, "A", rows=[("revenue", "2026-01", 1_000.0, 1_100.0)])
    with pytest.raises(engine.InvalidDecisionRequestError):
        engine.score_decision(db_session, name="dup", scenario_ids=[a.id, a.id], persist=False)
    db_session.rollback()


def test_unknown_scenario_id_is_rejected(db_session: Session) -> None:
    _clean_scenarios(db_session)
    a = _make_scenario(db_session, "A", rows=[("revenue", "2026-01", 1_000.0, 1_100.0)])
    with pytest.raises(engine.InvalidDecisionRequestError):
        engine.score_decision(db_session, name="bad id", scenario_ids=[a.id, uuid.uuid4()], persist=False)
    db_session.rollback()


def test_decision_table_also_accepts_persisted_commits(db_session: Session) -> None:
    """One real `persist=True` call, confirming the commit path itself works -- mirrors
    tests/scenarios/test_engine.py's own equivalent test. Deliberately does not clean up after
    itself, same as that test: a few leftover completed rows in the shared test DB are an
    accepted, already-established cost of exercising the real commit path."""
    a = _make_scenario(db_session, "Persisted A", rows=[("revenue", "2026-01", 1_000.0, 1_100.0)])
    b = _make_scenario(db_session, "Persisted B", rows=[("revenue", "2026-01", 1_000.0, 1_050.0)])
    db_session.commit()
    # Only "growth" is weighted: these two scenarios have no gross_profit/cogs rows at all, so
    # the default equal-weight-across-all-three split would correctly come back
    # insufficient_data -- this test is about the commit path, not the default-weights case
    # (covered by test_insufficient_data_when_no_compared_scenario_has_any_weighted_criterion).
    run = engine.score_decision(
        db_session, name="persisted", scenario_ids=[a.id, b.id], criteria_weights={"growth": 1.0}
    )
    found = db_session.get(type(run), run.id)
    assert found is not None
    assert found.status == "completed"
