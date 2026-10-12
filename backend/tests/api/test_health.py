from __future__ import annotations

from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_ready(client: TestClient) -> None:
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_system_config(client: TestClient) -> None:
    response = client.get("/api/v1/system/config")
    body = response.json()
    assert body["currency"] == "PKR"
    assert body["synthetic_data_only"] is True


def test_llm_status(client: TestClient) -> None:
    response = client.get("/api/v1/llm/status")
    assert response.status_code == 200
    assert response.json()["use_mock"] is True


def test_response_has_request_id_header(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert "x-request-id" in response.headers
