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


def _compare(client: TestClient, **body: Any) -> Any:
    response = client.post("/api/v1/decisions", json=body)
    assert response.status_code == 200
    return response.json()


def test_compare_two_scenarios_returns_ranked_options(client: TestClient) -> None:
    revenue_run_id = _generate_forecast(client, "revenue")
    cogs_run_id = _generate_forecast(client, "cogs")

    growth = _generate_scenario(
        client,
        name="Faster growth",
        revenue_growth_adjustment_pct=10.0,
        revenue_forecast_run_id=revenue_run_id,
        cogs_forecast_run_id=cogs_run_id,
    )
    cost = _generate_scenario(
        client,
        name="Cheaper cogs",
        cogs_adjustment_pct=-10.0,
        revenue_forecast_run_id=revenue_run_id,
        cogs_forecast_run_id=cogs_run_id,
    )

    run = _compare(client, name="growth vs cost", scenario_ids=[growth["id"], cost["id"]])
    assert run["status"] == "completed"
    assert len(run["options"]) == 2
    ranks = sorted(o["rank"] for o in run["options"])
    assert ranks == [1, 2]
    for option in run["options"]:
        assert option["score"] is not None
        assert option["rationale"]


def test_compare_with_custom_weights(client: TestClient) -> None:
    revenue_run_id = _generate_forecast(client, "revenue")
    growth = _generate_scenario(
        client, name="A", revenue_growth_adjustment_pct=5.0, revenue_forecast_run_id=revenue_run_id
    )
    other = _generate_scenario(
        client, name="B", revenue_growth_adjustment_pct=1.0, revenue_forecast_run_id=revenue_run_id
    )

    run = _compare(
        client,
        name="weighted",
        scenario_ids=[growth["id"], other["id"]],
        criteria_weights={"growth": 1.0},
    )
    assert run["criteria_weights"] == {"growth": 1.0}


def test_weights_not_summing_to_one_returns_400(client: TestClient) -> None:
    revenue_run_id = _generate_forecast(client, "revenue")
    a = _generate_scenario(client, name="A", revenue_forecast_run_id=revenue_run_id)
    b = _generate_scenario(client, name="B", revenue_forecast_run_id=revenue_run_id)
    response = client.post(
        "/api/v1/decisions",
        json={"name": "bad", "scenario_ids": [a["id"], b["id"]], "criteria_weights": {"growth": 0.5}},
    )
    assert response.status_code == 400


def test_fewer_than_two_scenario_ids_returns_422(client: TestClient) -> None:
    revenue_run_id = _generate_forecast(client, "revenue")
    a = _generate_scenario(client, name="A", revenue_forecast_run_id=revenue_run_id)
    response = client.post("/api/v1/decisions", json={"name": "too few", "scenario_ids": [a["id"]]})
    assert response.status_code == 422


def test_unknown_scenario_id_returns_400(client: TestClient) -> None:
    revenue_run_id = _generate_forecast(client, "revenue")
    a = _generate_scenario(client, name="A", revenue_forecast_run_id=revenue_run_id)
    response = client.post(
        "/api/v1/decisions",
        json={
            "name": "bad",
            "scenario_ids": [a["id"], "00000000-0000-0000-0000-000000000000"],
        },
    )
    assert response.status_code == 400


def test_list_decisions_and_get_one(client: TestClient) -> None:
    revenue_run_id = _generate_forecast(client, "revenue")
    a = _generate_scenario(client, name="A", revenue_forecast_run_id=revenue_run_id)
    b = _generate_scenario(
        client, name="B", revenue_growth_adjustment_pct=2.0, revenue_forecast_run_id=revenue_run_id
    )
    run = _compare(client, name="list-and-get", scenario_ids=[a["id"], b["id"]])

    listed = client.get("/api/v1/decisions")
    assert listed.status_code == 200
    assert any(r["id"] == run["id"] for r in listed.json())

    fetched = client.get(f"/api/v1/decisions/{run['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == run["id"]
    assert len(fetched.json()["options"]) == len(run["options"])


def test_get_unknown_decision_returns_404(client: TestClient) -> None:
    response = client.get("/api/v1/decisions/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_evidence_endpoint_exposes_decision_fact_and_recommendation(client: TestClient) -> None:
    revenue_run_id = _generate_forecast(client, "revenue")
    a = _generate_scenario(client, name="A", revenue_forecast_run_id=revenue_run_id)
    b = _generate_scenario(
        client, name="B", revenue_growth_adjustment_pct=3.0, revenue_forecast_run_id=revenue_run_id
    )
    run = _compare(client, name="evidence check", scenario_ids=[a["id"], b["id"]])

    assert run["fact_evidence_id"] is not None
    fact_response = client.get(f"/api/v1/evidence/{run['fact_evidence_id']}")
    assert fact_response.status_code == 200
    assert fact_response.json()["claim_type"] == "fact"
    assert fact_response.json()["decision_run_id"] == run["id"]

    scored_option = next(o for o in run["options"] if o["score"] is not None)
    assert scored_option["evidence_id"] is not None
    rec_response = client.get(f"/api/v1/evidence/{scored_option['evidence_id']}")
    assert rec_response.status_code == 200
    assert rec_response.json()["claim_type"] == "recommendation"
    assert rec_response.json()["decision_option_id"] == scored_option["id"]
