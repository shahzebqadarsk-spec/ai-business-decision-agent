"""Orchestration tests: `detect_issues()` / `analyze_issue()` persist the right rows, with the
right relationships, and every number in a persisted `decomposition` traces to an Evidence ID
actually present in the `evidence` table (Phase 4 spec sections 10-12)."""

from __future__ import annotations

import uuid

import pytest
from app.db.models.analysis import AnalysisRun, Evidence, Issue
from app.rca import engine
from sqlalchemy import select
from sqlalchemy.orm import Session

pytestmark = pytest.mark.usefixtures("seeded_fact_sales_file_id")


def test_detect_issues_persists_a_completed_run_and_fact_evidence_per_issue(db_session: Session) -> None:
    run = engine.detect_issues(db_session, "year", "2025", comparison_type="YoY")
    assert run.status == "completed"
    assert run.analysis_type == "issue_detection"
    assert run.comparison_period_key == "2024"

    issues = db_session.execute(select(Issue).where(Issue.detection_run_id == run.id)).scalars().all()
    assert len(issues) == run.result_summary["issues_detected"]
    assert len(issues) >= 1

    for issue in issues:
        assert issue.status == "detected"
        assert issue.decomposition is None
        assert issue.analyzed_at is None
        fact_rows = (
            db_session.execute(
                select(Evidence).where(Evidence.issue_id == issue.id, Evidence.claim_type == "fact")
            )
            .scalars()
            .all()
        )
        assert len(fact_rows) == 1
        assert fact_rows[0].analysis_run_id == run.id
        assert fact_rows[0].claim  # non-empty, human-readable


def test_detect_issues_is_idempotent_in_shape_across_runs(db_session: Session) -> None:
    """Two detection runs for the same period should find the same *set* of issue types --
    the engine has no hidden state that would make a re-run diverge."""
    run_a = engine.detect_issues(db_session, "year", "2025", comparison_type="YoY")
    run_b = engine.detect_issues(db_session, "year", "2025", comparison_type="YoY")
    types_a = {
        i.issue_type
        for i in db_session.execute(select(Issue).where(Issue.detection_run_id == run_a.id)).scalars()
    }
    types_b = {
        i.issue_type
        for i in db_session.execute(select(Issue).where(Issue.detection_run_id == run_b.id)).scalars()
    }
    assert types_a == types_b


def test_analyze_issue_marks_analyzed_and_links_the_rca_run(db_session: Session) -> None:
    run = engine.detect_issues(db_session, "year", "2025", comparison_type="YoY")
    issues = db_session.execute(select(Issue).where(Issue.detection_run_id == run.id)).scalars().all()
    issue = issues[0]

    analyzed = engine.analyze_issue(db_session, issue.id)
    assert analyzed.status == "analyzed"
    assert analyzed.analyzed_at is not None
    assert analyzed.decomposition is not None
    assert analyzed.latest_analysis_run_id is not None

    rca_run = db_session.get(AnalysisRun, analyzed.latest_analysis_run_id)
    assert rca_run is not None
    assert rca_run.analysis_type == "rca"
    assert rca_run.status == "completed"


def test_analyze_issue_unknown_id_raises(db_session: Session) -> None:
    with pytest.raises(engine.UnknownIssueError):
        engine.analyze_issue(db_session, uuid.uuid4())


def test_every_decomposition_row_evidence_id_exists_and_matches_the_issue(db_session: Session) -> None:
    """Walks every evidence_id embedded anywhere in a persisted decomposition and confirms it
    names a real Evidence row belonging to the same issue -- the traceability guarantee the
    RCA UI depends on (spec section 14: "every important number should be traceable to an
    Evidence ID")."""
    run = engine.detect_issues(db_session, "year", "2025", comparison_type="YoY")
    issues = db_session.execute(select(Issue).where(Issue.detection_run_id == run.id)).scalars().all()
    assert len(issues) >= 1

    def _walk_evidence_ids(node: object) -> list[str]:
        found: list[str] = []
        if isinstance(node, dict):
            for key, value in node.items():
                if key in ("evidence_id",) and isinstance(value, str):
                    found.append(value)
                elif key == "evidence_ids" and isinstance(value, list):
                    found.extend(v for v in value if isinstance(v, str))
                else:
                    found.extend(_walk_evidence_ids(value))
        elif isinstance(node, list):
            for item in node:
                found.extend(_walk_evidence_ids(item))
        return found

    for issue in issues:
        analyzed = engine.analyze_issue(db_session, issue.id)
        evidence_ids = _walk_evidence_ids(analyzed.decomposition)
        assert len(evidence_ids) >= 1
        for raw_id in evidence_ids:
            evidence = db_session.get(Evidence, uuid.UUID(raw_id))
            assert evidence is not None, f"decomposition names evidence id {raw_id} that doesn't exist"
            assert evidence.issue_id == issue.id
            # Every number in a decomposition traces to a FACT or CONTRIBUTION row (never
            # inference/recommendation -- Phase 4 produces none of those, spec section 10).
            assert evidence.claim_type in ("fact", "contribution")


def test_analysis_run_result_summary_evidence_count_matches_actual_rows(db_session: Session) -> None:
    run = engine.detect_issues(db_session, "year", "2025", comparison_type="YoY")
    issue = db_session.execute(select(Issue).where(Issue.detection_run_id == run.id)).scalars().first()
    assert issue is not None

    analyzed_issue = engine.analyze_issue(db_session, issue.id)
    rca_run = db_session.get(AnalysisRun, analyzed_issue.latest_analysis_run_id)
    assert rca_run is not None
    actual = (
        db_session.execute(select(Evidence).where(Evidence.analysis_run_id == rca_run.id)).scalars().all()
    )
    assert rca_run.result_summary["evidence_count"] == len(actual)


def test_unsupported_issue_type_for_analysis_raises(db_session: Session) -> None:
    run = engine.detect_issues(db_session, "year", "2025", comparison_type="YoY")
    db_session.flush()
    # material_inventory_issue/overtime_issue have no analyzer registered -- simulate one by
    # constructing a minimal Issue row directly (the detectors never produce one themselves).
    fake_issue = Issue(
        detection_run_id=run.id,
        issue_type="material_inventory_issue",
        title="synthetic for this test",
        severity="low",
        status="detected",
        granularity="year",
        period_key="2025",
        comparison_period_key="2024",
        metric="inventory_quantity",
        materiality={},
    )
    db_session.add(fake_issue)
    db_session.commit()
    with pytest.raises(engine.UnsupportedIssueTypeError):
        engine.analyze_issue(db_session, fake_issue.id)
