"""Proves ground_truth.yaml is never reachable through the HTTP API -- not by any declared
route, and not leaked into any response body during an ordinary pipeline run. Complements
tests/synthetic/test_isolation.py's static source-grep with a runtime check.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_no_route_mentions_ground_truth_or_hidden_fixtures(client: TestClient) -> None:
    for route in client.app.routes:  # type: ignore[attr-defined]
        path = getattr(route, "path", "")
        assert "ground_truth" not in path
        assert "hidden" not in path
        assert "messy_defects" not in path


def test_openapi_schema_never_mentions_ground_truth(client: TestClient) -> None:
    response = client.get("/api/openapi.json")
    assert response.status_code == 200
    assert "ground_truth" not in response.text
    assert "messy_defects" not in response.text


def test_dataset_and_file_responses_never_contain_ground_truth(client: TestClient) -> None:
    response = client.post("/api/v1/datasets", json={"name": "isolation-check"})
    assert response.status_code == 201
    assert "ground_truth" not in response.text

    dataset_id = response.json()["id"]
    response = client.get(f"/api/v1/datasets/{dataset_id}")
    assert "ground_truth" not in response.text
