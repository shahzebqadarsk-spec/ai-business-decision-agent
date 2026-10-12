from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.usefixtures("seeded_fact_sales_file_id")


def _generate(client: TestClient, metric: str = "revenue", horizon_periods: int = 6) -> Any:
    response = client.post(
        "/api/v1/forecasts/generate",
        json={"metric": metric, "horizon_periods": horizon_periods, "confidence_level": 0.8},
    )
    assert response.status_code == 200
    return response.json()


def test_generate_returns_a_completed_run_with_forecasts(client: TestClient) -> None:
    run = _generate(client)
    assert run["status"] == "completed"
    assert run["metric"] == "revenue"
    assert run["history_periods"] == 36
    assert len(run["forecasts"]) == 6
    assert run["fit_evidence_id"] is not None
    for point in run["forecasts"]:
        assert point["evidence_id"] is not None
        assert point["lower_bound"] <= point["point_estimate"] <= point["upper_bound"]


def test_generate_rejects_an_unknown_metric_with_400(client: TestClient) -> None:
    response = client.post(
        "/api/v1/forecasts/generate",
        json={"metric": "gross_margin_pct", "horizon_periods": 6},
    )
    assert response.status_code == 400


def test_generate_rejects_an_out_of_range_horizon_with_422(client: TestClient) -> None:
    # Pydantic's own ge/le validation on horizon_periods -- rejected before the engine ever
    # sees it, hence 422 (request-schema validation) rather than the engine's own 400.
    response = client.post(
        "/api/v1/forecasts/generate",
        json={"metric": "revenue", "horizon_periods": 100},
    )
    assert response.status_code == 422


def test_generate_rejects_an_unsupported_confidence_level_with_400(client: TestClient) -> None:
    response = client.post(
        "/api/v1/forecasts/generate",
        json={"metric": "revenue", "horizon_periods": 6, "confidence_level": 0.5},
    )
    assert response.status_code == 400


def test_list_runs_and_get_one(client: TestClient) -> None:
    run = _generate(client, metric="cogs", horizon_periods=3)

    listed = client.get("/api/v1/forecasts/runs", params={"metric": "cogs"})
    assert listed.status_code == 200
    assert any(r["id"] == run["id"] for r in listed.json())

    fetched = client.get(f"/api/v1/forecasts/runs/{run['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == run["id"]
    assert len(fetched.json()["forecasts"]) == 3


def test_get_unknown_run_returns_404(client: TestClient) -> None:
    response = client.get("/api/v1/forecasts/runs/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_each_forecast_evidence_record_is_reachable_and_reads_as_inference(
    client: TestClient,
) -> None:
    run = _generate(client, metric="sales_quantity", horizon_periods=2)
    evidence_id = run["forecasts"][0]["evidence_id"]
    response = client.get(f"/api/v1/evidence/{evidence_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["claim_type"] == "inference"
    assert "projection" in body["claim"].lower() or "projected" in body["claim"].lower()
    assert "not a fact" in body["claim"].lower() or "not a guaranteed" in body["claim"].lower()
