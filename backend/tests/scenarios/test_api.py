from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.usefixtures("seeded_fact_sales_file_id")


def _generate_forecast(client: TestClient, metric: str, horizon_periods: int = 3) -> str:
    response = client.post(
        "/api/v1/forecasts/generate",
        json={"metric": metric, "horizon_periods": horizon_periods},
    )
    assert response.status_code == 200
    run_id = response.json()["id"]
    assert isinstance(run_id, str)
    return run_id


def _generate_scenario(client: TestClient, **body: Any) -> Any:
    response = client.post("/api/v1/scenarios", json=body)
    assert response.status_code == 200
    return response.json()


def test_generate_scenario_against_explicit_baseline_runs_returns_completed_with_results(
    client: TestClient,
) -> None:
    revenue_run_id = _generate_forecast(client, "revenue")
    cogs_run_id = _generate_forecast(client, "cogs")

    scenario = _generate_scenario(
        client,
        name="Faster revenue growth",
        revenue_growth_adjustment_pct=5.0,
        cogs_adjustment_pct=0.0,
        revenue_forecast_run_id=revenue_run_id,
        cogs_forecast_run_id=cogs_run_id,
    )
    assert scenario["status"] == "completed"
    assert scenario["horizon_periods"] == 3
    metrics = {r["metric"] for r in scenario["results"]}
    assert metrics == {"revenue", "cogs", "gross_profit", "gross_margin_pct"}
    revenue_results = [r for r in scenario["results"] if r["metric"] == "revenue"]
    for r in revenue_results:
        assert r["scenario_value"] == pytest.approx(r["baseline_value"] * 1.05)


def test_generate_rejects_an_unknown_forecast_run_id_with_400(client: TestClient) -> None:
    response = client.post(
        "/api/v1/scenarios",
        json={"name": "bad", "revenue_forecast_run_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert response.status_code == 400


def test_generate_rejects_an_out_of_range_adjustment_with_422(client: TestClient) -> None:
    response = client.post(
        "/api/v1/scenarios",
        json={"name": "too extreme", "revenue_growth_adjustment_pct": -500.0},
    )
    assert response.status_code == 422


def test_list_scenarios_and_get_one(client: TestClient) -> None:
    revenue_run_id = _generate_forecast(client, "revenue")
    scenario = _generate_scenario(client, name="list-and-get", revenue_forecast_run_id=revenue_run_id)

    listed = client.get("/api/v1/scenarios")
    assert listed.status_code == 200
    assert any(s["id"] == scenario["id"] for s in listed.json())

    fetched = client.get(f"/api/v1/scenarios/{scenario['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == scenario["id"]
    assert len(fetched.json()["results"]) == len(scenario["results"])


def test_get_unknown_scenario_returns_404(client: TestClient) -> None:
    response = client.get("/api/v1/scenarios/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
