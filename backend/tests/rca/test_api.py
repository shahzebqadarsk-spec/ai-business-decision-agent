from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.usefixtures("seeded_fact_sales_file_id")


def _detect(client: TestClient, period_key: str = "2025") -> Any:
    response = client.post(
        "/api/v1/issues/detect",
        json={"granularity": "year", "period_key": period_key, "comparison_type": "YoY"},
    )
    assert response.status_code == 200
    return response.json()


def test_detect_returns_a_completed_analysis_run(client: TestClient) -> None:
    run = _detect(client)
    assert run["analysis_type"] == "issue_detection"
    assert run["status"] == "completed"
    assert run["comparison_period_key"] == "2024"
    assert len(run["issue_ids"]) == run["result_summary"]["issues_detected"]


def test_detect_rejects_an_invalid_period_with_400(client: TestClient) -> None:
    response = client.post(
        "/api/v1/issues/detect",
        json={"granularity": "year", "period_key": "not-a-year", "comparison_type": "YoY"},
    )
    assert response.status_code == 400


def test_list_issues_and_get_one(client: TestClient) -> None:
    run = _detect(client)
    issue_id = run["issue_ids"][0]

    listed = client.get("/api/v1/issues", params={"period_key": "2025"})
    assert listed.status_code == 200
    assert any(i["id"] == issue_id for i in listed.json())

    got = client.get(f"/api/v1/issues/{issue_id}")
    assert got.status_code == 200
    assert got.json()["id"] == issue_id
    assert got.json()["status"] == "detected"
    assert got.json()["decomposition"] is None


def test_get_unknown_issue_404s(client: TestClient) -> None:
    response = client.get("/api/v1/issues/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_list_issues_filters_by_issue_type(client: TestClient) -> None:
    _detect(client)
    response = client.get("/api/v1/issues", params={"issue_type": "regional_performance_deterioration"})
    assert response.status_code == 200
    for issue in response.json():
        assert issue["issue_type"] == "regional_performance_deterioration"


def test_analyze_issue_fills_in_decomposition_and_returns_it(client: TestClient) -> None:
    run = _detect(client)
    issue_id = run["issue_ids"][0]

    analyzed = client.post(f"/api/v1/issues/{issue_id}/analyze")
    assert analyzed.status_code == 200
    body = analyzed.json()
    assert body["status"] == "analyzed"
    assert body["decomposition"] is not None
    assert body["analyzed_at"] is not None
    assert len(body["evidence_ids"]) >= 1


def test_analyze_unknown_issue_404s(client: TestClient) -> None:
    response = client.post("/api/v1/issues/00000000-0000-0000-0000-000000000000/analyze")
    assert response.status_code == 404


def test_issue_evidence_endpoint_lists_rows_for_that_issue_only(client: TestClient) -> None:
    run = _detect(client)
    issue_id = run["issue_ids"][0]
    client.post(f"/api/v1/issues/{issue_id}/analyze")

    response = client.get(f"/api/v1/issues/{issue_id}/evidence")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) >= 2  # at least the detection FACT + one analysis CONTRIBUTION row
    assert all(r["issue_id"] == issue_id for r in rows)


def test_issue_evidence_for_unknown_issue_404s(client: TestClient) -> None:
    response = client.get("/api/v1/issues/00000000-0000-0000-0000-000000000000/evidence")
    assert response.status_code == 404


def test_get_single_evidence_row(client: TestClient) -> None:
    run = _detect(client)
    issue_id = run["issue_ids"][0]
    evidence_list = client.get(f"/api/v1/issues/{issue_id}/evidence").json()
    evidence_id = evidence_list[0]["id"]

    response = client.get(f"/api/v1/evidence/{evidence_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == evidence_id
    assert body["claim"]
    assert body["claim_type"] in ("fact", "contribution")
    # Never "caused"/"root cause"/"because of" -- change is not causation (spec section 9).
    lowered = body["claim"].lower()
    for forbidden in ("caused", "root cause", "because of"):
        assert forbidden not in lowered


def test_get_unknown_evidence_404s(client: TestClient) -> None:
    response = client.get("/api/v1/evidence/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_get_analysis_run_reports_its_issues_and_evidence(client: TestClient) -> None:
    run = _detect(client)
    response = client.get(f"/api/v1/analysis-runs/{run['id']}")
    assert response.status_code == 200
    body = response.json()
    assert set(body["issue_ids"]) == set(run["issue_ids"])
    assert len(body["evidence_ids"]) >= len(run["issue_ids"])  # >=1 FACT evidence per issue


def test_get_unknown_analysis_run_404s(client: TestClient) -> None:
    response = client.get("/api/v1/analysis-runs/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_qoq_detection_on_a_quarter_works_end_to_end(client: TestClient) -> None:
    response = client.post(
        "/api/v1/issues/detect",
        json={"granularity": "quarter", "period_key": "2025-Q4", "comparison_type": "QoQ"},
    )
    assert response.status_code == 200
    assert response.json()["comparison_type"] == "QoQ"
