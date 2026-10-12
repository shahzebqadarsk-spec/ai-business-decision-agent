from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.usefixtures("seeded_fact_sales_file_id")


def test_catalog_lists_all_registered_kpis(client: TestClient) -> None:
    response = client.get("/api/v1/kpis")
    assert response.status_code == 200
    kpis = response.json()
    ids = {k["kpi_id"] for k in kpis}
    assert "revenue" in ids
    assert "procurement_cost" in ids
    # every KPI named in the Phase 3 spec's minimum set is present (collapsing "revenue by
    # region/product/customer" into revenue's dimensional breakdown -- see registry.py).
    assert len(kpis) == 21


def test_catalog_marks_unimplemented_kpis(client: TestClient) -> None:
    response = client.get("/api/v1/kpis")
    by_id = {k["kpi_id"]: k for k in response.json()}
    assert by_id["revenue"]["implemented"] is True
    assert by_id["payroll_cost"]["implemented"] is False


def test_get_single_kpi_definition(client: TestClient) -> None:
    response = client.get("/api/v1/kpis/revenue")
    assert response.status_code == 200
    assert response.json()["name"] == "Revenue"


def test_get_unknown_kpi_definition_404s(client: TestClient) -> None:
    response = client.get("/api/v1/kpis/not_a_real_kpi")
    assert response.status_code == 404


def test_availability_endpoint_for_available_kpi(client: TestClient) -> None:
    response = client.get(
        "/api/v1/kpis/revenue/availability", params={"granularity": "year", "period_key": "2024"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "available"


def test_availability_endpoint_for_unimplemented_kpi(client: TestClient) -> None:
    response = client.get(
        "/api/v1/kpis/inventory_value/availability", params={"granularity": "year", "period_key": "2024"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "cannot_compute"
    assert body["status_reason"] is not None


def test_calculate_endpoint_returns_a_full_result(client: TestClient) -> None:
    response = client.post(
        "/api/v1/kpis/revenue/calculate",
        json={"granularity": "year", "period_key": "2024", "comparison_type": "YoY"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "available"
    assert body["value"] > 0
    assert body["comparison_period_key"] == "2023"
    assert body["calculation_version"]
    assert body["source_file_ids"]


def test_calculate_endpoint_rejects_invalid_period(client: TestClient) -> None:
    response = client.post(
        "/api/v1/kpis/revenue/calculate", json={"granularity": "month", "period_key": "2024-99"}
    )
    assert response.status_code == 400


def test_calculate_endpoint_404s_for_unknown_kpi(client: TestClient) -> None:
    response = client.post(
        "/api/v1/kpis/not_a_real_kpi/calculate", json={"granularity": "year", "period_key": "2024"}
    )
    assert response.status_code == 404


def test_breakdown_endpoint_returns_ranked_rows(client: TestClient) -> None:
    response = client.post(
        "/api/v1/kpis/revenue/breakdown",
        json={"granularity": "year", "period_key": "2024", "dimension": "region"},
    )
    assert response.status_code == 200
    rows = response.json()["rows"]
    assert len(rows) > 0
    assert rows[0]["rank"] == 1
    values = [r["value"] for r in rows]
    assert values == sorted(values, reverse=True)


def test_breakdown_endpoint_rejects_unsupported_dimension(client: TestClient) -> None:
    response = client.post(
        "/api/v1/kpis/revenue/breakdown",
        json={"granularity": "year", "period_key": "2024", "dimension": "not_a_real_dimension"},
    )
    assert response.status_code == 400


def test_dashboard_endpoint_returns_headline_cards_and_breakdowns(client: TestClient) -> None:
    response = client.get("/api/v1/dashboard", params={"period_key": "2024"})
    assert response.status_code == 200
    body = response.json()
    card_ids = {c["kpi_id"] for c in body["cards"]}
    assert card_ids == {
        "revenue",
        "sales_quantity",
        "average_selling_price",
        "customer_count",
        "transaction_count",
    }
    assert len(body["revenue_by_region"]) > 0
    assert len(body["revenue_trend"]) > 0
    assert len(body["top_customers"]) == 5
    assert len(body["bottom_customers"]) == 5


def test_dashboard_defaults_to_latest_available_year(client: TestClient) -> None:
    response = client.get("/api/v1/dashboard")
    assert response.status_code == 200
    assert response.json()["period_key"] == "2025"


def test_cannot_compute_kpi_never_shows_a_fabricated_zero(client: TestClient) -> None:
    response = client.post(
        "/api/v1/kpis/operating_expenses/calculate", json={"granularity": "year", "period_key": "2024"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "cannot_compute"
    assert body["value"] is None
    assert body["status_reason"] is not None
