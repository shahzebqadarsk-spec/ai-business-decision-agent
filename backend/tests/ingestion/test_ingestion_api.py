"""Integration tests for the full Phase 2 workflow:

    upload -> file validation -> dataset registration -> profiling -> data-quality checks
    -> semantic mapping proposal -> human confirmation -> canonical materialization

Exercised against real Phase 1 generator output (both the clean and the messy variant),
not hand-written fixtures, per the Phase 2 spec's explicit requirement to test against both.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

from app.db.models.canonical import FactSales
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def _upload(client: TestClient, dataset_id: object, csv_path: Path) -> dict[str, object]:
    with csv_path.open("rb") as fh:
        response = client.post(
            f"/api/v1/datasets/{dataset_id}/files",
            files={"file": (csv_path.name, fh, "text/csv")},
        )
    assert response.status_code == 200, response.text
    return cast(dict[str, object], response.json())


def _propose_and_confirm_all(client: TestClient, file_id: object) -> list[dict[str, object]]:
    response = client.post(f"/api/v1/datasets/files/{file_id}/mappings/propose")
    assert response.status_code == 200, response.text
    mappings = cast(list[dict[str, object]], response.json())
    for m in mappings:
        if m["status"] == "proposed":
            confirm = client.post(
                f"/api/v1/datasets/files/{file_id}/mappings/{m['id']}/confirm",
                json={"confirmed_canonical_field": m["proposed_canonical_field"], "confirmed_by": "qa"},
            )
            assert confirm.status_code == 200, confirm.text
    return mappings


def test_full_workflow_on_clean_dataset(
    client: TestClient, db_session: Session, clean_sales_csv: Path
) -> None:
    dataset = client.post("/api/v1/datasets", json={"name": "clean-workflow"}).json()
    file_ = _upload(client, dataset["id"], clean_sales_csv)
    assert file_["status"] == "validated"

    profile_resp = client.get(f"/api/v1/datasets/files/{file_['id']}/profile")
    assert profile_resp.status_code == 200
    assert len(profile_resp.json()) > 0

    quality_resp = client.get(f"/api/v1/datasets/files/{file_['id']}/quality-issues")
    assert quality_resp.status_code == 200
    # the clean dataset may still trip "suspicious_outliers" (whale customers are real,
    # not a defect) but should have no impossible-value or invalid-date issues
    assert not any(i["issue_type"] == "impossible_numeric_values" for i in quality_resp.json())
    assert not any(i["issue_type"] == "invalid_dates" for i in quality_resp.json())

    _propose_and_confirm_all(client, file_["id"])

    materialize_resp = client.post(
        f"/api/v1/datasets/files/{file_['id']}/materialize", json={"performed_by": "qa"}
    )
    assert materialize_resp.status_code == 200, materialize_resp.text
    result = materialize_resp.json()
    assert result["rows_written"] > 0
    assert result["rows_skipped"] == 0

    written = db_session.query(FactSales).filter(FactSales.source_file_id == file_["id"]).count()
    assert written == result["rows_written"]

    dataset_after = client.get(f"/api/v1/datasets/{dataset['id']}").json()
    assert dataset_after["status"] == "materialized"


def test_full_workflow_on_messy_dataset_produces_quality_warnings(
    client: TestClient, messy_sales_csv: Path
) -> None:
    dataset = client.post("/api/v1/datasets", json={"name": "messy-workflow"}).json()
    file_ = _upload(client, dataset["id"], messy_sales_csv)
    assert file_["status"] == "validated"

    quality_resp = client.get(f"/api/v1/datasets/files/{file_['id']}/quality-issues")
    issue_types = {i["issue_type"] for i in quality_resp.json()}
    assert "missing_values" in issue_types
    assert "invalid_dates" in issue_types
    assert "impossible_numeric_values" in issue_types
    assert "inconsistent_categorical_values" in issue_types
    assert "suspicious_outliers" in issue_types

    _propose_and_confirm_all(client, file_["id"])
    materialize_resp = client.post(
        f"/api/v1/datasets/files/{file_['id']}/materialize", json={"performed_by": "qa"}
    )
    assert materialize_resp.status_code == 200, materialize_resp.text
    # the messy variant's corrupted order_date rows should still materialize (order_date
    # is optional), but a non-numeric defect would be skipped -- either way the call
    # succeeds rather than crashing on bad data.
    assert materialize_resp.json()["rows_written"] > 0


def test_materialize_blocked_without_any_confirmed_mapping(client: TestClient, clean_sales_csv: Path) -> None:
    dataset = client.post("/api/v1/datasets", json={"name": "blocked-workflow"}).json()
    file_ = _upload(client, dataset["id"], clean_sales_csv)
    client.post(f"/api/v1/datasets/files/{file_['id']}/mappings/propose")

    response = client.post(f"/api/v1/datasets/files/{file_['id']}/materialize", json={"performed_by": "qa"})
    assert response.status_code == 422
    assert "month" in response.json()["detail"] or "customer_id" in response.json()["detail"]


def test_rejected_mapping_cannot_materialize_silently(client: TestClient, clean_sales_csv: Path) -> None:
    dataset = client.post("/api/v1/datasets", json={"name": "reject-workflow"}).json()
    file_ = _upload(client, dataset["id"], clean_sales_csv)
    mappings = client.post(f"/api/v1/datasets/files/{file_['id']}/mappings/propose").json()

    customer_mapping = next(m for m in mappings if m["source_column"] == "customer_id")
    client.post(
        f"/api/v1/datasets/files/{file_['id']}/mappings/{customer_mapping['id']}/reject",
        json={"rejected_by": "qa"},
    )
    for m in mappings:
        if m["source_column"] == "customer_id" or m["status"] != "proposed":
            continue
        client.post(
            f"/api/v1/datasets/files/{file_['id']}/mappings/{m['id']}/confirm",
            json={"confirmed_canonical_field": m["proposed_canonical_field"], "confirmed_by": "qa"},
        )

    response = client.post(f"/api/v1/datasets/files/{file_['id']}/materialize", json={"performed_by": "qa"})
    assert response.status_code == 422
    assert "customer_id" in response.json()["detail"]


def test_low_confidence_mapping_is_unresolved_not_auto_accepted(
    client: TestClient, clean_sales_csv: Path
) -> None:
    dataset = client.post("/api/v1/datasets", json={"name": "unresolved-workflow"}).json()
    file_ = _upload(client, dataset["id"], clean_sales_csv)
    mappings = client.post(f"/api/v1/datasets/files/{file_['id']}/mappings/propose").json()
    # unit_cost_pkr has no good canonical home and should land as unresolved, never confirmed
    unit_cost_mapping = next(m for m in mappings if m["source_column"] == "unit_cost_pkr")
    assert unit_cost_mapping["status"] == "unresolved"
    assert unit_cost_mapping["confirmed_canonical_field"] is None


def test_rule_based_mapping_proposals_are_deterministic_across_two_files(
    client: TestClient, clean_sales_csv: Path
) -> None:
    dataset = client.post("/api/v1/datasets", json={"name": "determinism-workflow"}).json()
    file_a = _upload(client, dataset["id"], clean_sales_csv)
    mappings_a = {
        m["source_column"]: (m["proposed_canonical_field"], m["confidence"])
        for m in client.post(f"/api/v1/datasets/files/{file_a['id']}/mappings/propose").json()
    }

    dataset_b = client.post("/api/v1/datasets", json={"name": "determinism-workflow-b"}).json()
    file_b = _upload(client, dataset_b["id"], clean_sales_csv)
    mappings_b = {
        m["source_column"]: (m["proposed_canonical_field"], m["confidence"])
        for m in client.post(f"/api/v1/datasets/files/{file_b['id']}/mappings/propose").json()
    }

    assert mappings_a == mappings_b


def test_invalid_file_is_rejected_and_recorded(client: TestClient) -> None:
    dataset = client.post("/api/v1/datasets", json={"name": "invalid-file-workflow"}).json()
    response = client.post(
        f"/api/v1/datasets/{dataset['id']}/files",
        files={
            "file": (
                "virus.exe",
                b"MZ\x90\x00not a real exe but wrong extension",
                "application/octet-stream",
            )
        },
    )
    assert response.status_code == 422

    files = client.get(f"/api/v1/datasets/{dataset['id']}/files").json()
    assert len(files) == 1
    assert files[0]["status"] == "rejected"
    assert files[0]["rejection_reason"] is not None


def test_canonical_materialization_preserves_lineage(
    client: TestClient, db_session: Session, clean_sales_csv: Path
) -> None:
    dataset = client.post("/api/v1/datasets", json={"name": "lineage-workflow"}).json()
    file_ = _upload(client, dataset["id"], clean_sales_csv)
    _propose_and_confirm_all(client, file_["id"])
    client.post(f"/api/v1/datasets/files/{file_['id']}/materialize", json={"performed_by": "qa"})

    first_row = (
        db_session.query(FactSales)
        .filter(FactSales.source_file_id == file_["id"])
        .order_by(FactSales.source_row_number.asc())
        .first()
    )
    assert first_row is not None
    assert str(first_row.source_file_id) == file_["id"]
    assert first_row.source_row_number == 0

    import pandas as pd

    raw_first_row = pd.read_csv(clean_sales_csv, dtype=str, nrows=1).iloc[0]
    assert first_row.customer_id == raw_first_row["customer_id"]
    assert first_row.product_id == raw_first_row["product_id"]


def test_referential_integrity_detected_against_sibling_file(client: TestClient, tmp_path: Path) -> None:
    dataset = client.post("/api/v1/datasets", json={"name": "referential-workflow"}).json()

    customers_csv = tmp_path / "customers.csv"
    customers_csv.write_text("customer_id,name\nCUST-0001,Alpha\nCUST-0002,Beta\n")
    _upload(client, dataset["id"], customers_csv)

    sales_csv = tmp_path / "sales.csv"
    sales_csv.write_text("customer_id,product_id\nCUST-0001,PROD-01\nCUST-9999,PROD-02\nCUST-0002,PROD-01\n")
    sales_file = _upload(client, dataset["id"], sales_csv)

    issues = client.get(f"/api/v1/datasets/files/{sales_file['id']}/quality-issues").json()
    assert any(
        i["issue_type"] == "referential_integrity" and i["column_name"] == "customer_id" for i in issues
    )


def test_canonical_fields_endpoint_lists_required_fields(client: TestClient) -> None:
    response = client.get("/api/v1/canonical-fields/fact_sales")
    assert response.status_code == 200
    fields = {f["name"]: f for f in response.json()}
    assert fields["customer_id"]["required"] is True
    assert fields["month"]["required"] is True
    assert fields["payment_terms"]["required"] is False


def test_canonical_fields_endpoint_404s_for_unknown_table(client: TestClient) -> None:
    response = client.get("/api/v1/canonical-fields/not_a_real_table")
    assert response.status_code == 404


def test_schema_inconsistency_detected_against_sibling_file(client: TestClient, tmp_path: Path) -> None:
    dataset = client.post("/api/v1/datasets", json={"name": "schema-workflow"}).json()

    first_csv = tmp_path / "first.csv"
    first_csv.write_text("a,b,c\n1,2,3\n4,5,6\n")
    _upload(client, dataset["id"], first_csv)

    second_csv = tmp_path / "second.csv"
    second_csv.write_text("a,b,d\n1,2,3\n4,5,6\n")
    second_file = _upload(client, dataset["id"], second_csv)

    issues = client.get(f"/api/v1/datasets/files/{second_file['id']}/quality-issues").json()
    assert any(i["issue_type"] == "schema_inconsistency" for i in issues)
