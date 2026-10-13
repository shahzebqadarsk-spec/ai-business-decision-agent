from __future__ import annotations

import pandas as pd
from app.ingestion.quality import run_quality_checks


def test_detects_missing_values() -> None:
    df = pd.DataFrame({"quantity": ["10", None, "30"], "unit_price": ["5", "6", "7"]})
    issues = run_quality_checks(df)
    assert any(i.issue_type == "missing_values" and i.column_name == "quantity" for i in issues)


def test_detects_duplicate_records() -> None:
    df = pd.DataFrame({"quantity": ["10", "10"], "unit_price": ["5", "5"]})
    issues = run_quality_checks(df)
    assert any(i.issue_type == "duplicate_records" for i in issues)


def test_detects_invalid_dates() -> None:
    df = pd.DataFrame({"order_date": ["2023-01-01", "2025-13-45", "2023-01-03"]})
    issues = run_quality_checks(df, date_columns=("order_date",), measure_columns=())
    assert any(i.issue_type == "invalid_dates" and i.column_name == "order_date" for i in issues)


def test_detects_impossible_numeric_values() -> None:
    df = pd.DataFrame({"quantity": ["10", "-5", "20"], "unit_price": ["5", "6", "0"]})
    issues = run_quality_checks(df, date_columns=(), measure_columns=())
    types_by_column = {i.column_name for i in issues if i.issue_type == "impossible_numeric_values"}
    assert "quantity" in types_by_column
    assert "unit_price" in types_by_column


def test_detects_inconsistent_categorical_values() -> None:
    df = pd.DataFrame({"payment_terms": ["NET30", "net30", "NET-30", "NET60"] * 5})
    issues = run_quality_checks(df, date_columns=(), measure_columns=())
    assert any(i.issue_type == "inconsistent_categorical_values" for i in issues)


def test_detects_suspicious_outliers_without_flagging_legitimate_spread() -> None:
    # A Zipf-like spread of "legitimate" large values plus one genuine extreme outlier.
    normal_values = [str(v) for v in range(1, 40)]
    df = pd.DataFrame({"quantity": [*normal_values, "500000"]})
    issues = run_quality_checks(df, date_columns=(), measure_columns=("quantity",))
    outlier_issues = [i for i in issues if i.issue_type == "suspicious_outliers"]
    assert outlier_issues
    assert outlier_issues[0].affected_row_count == 1


def test_detects_referential_integrity_violation() -> None:
    df = pd.DataFrame({"customer_id": ["CUST-0001", "CUST-9999", "CUST-0002"]})
    issues = run_quality_checks(
        df,
        date_columns=(),
        measure_columns=(),
        known_ids_by_column={"customer_id": {"CUST-0001", "CUST-0002"}},
    )
    assert any(i.issue_type == "referential_integrity" for i in issues)


def test_no_referential_integrity_issue_when_all_known() -> None:
    df = pd.DataFrame({"customer_id": ["CUST-0001", "CUST-0002"]})
    issues = run_quality_checks(
        df,
        date_columns=(),
        measure_columns=(),
        known_ids_by_column={"customer_id": {"CUST-0001", "CUST-0002"}},
    )
    assert not any(i.issue_type == "referential_integrity" for i in issues)


def test_detects_schema_inconsistency_against_reference_columns() -> None:
    df = pd.DataFrame({"a": ["1"], "b": ["2"]})
    issues = run_quality_checks(df, date_columns=(), measure_columns=(), reference_columns=("a", "c"))
    schema_issues = [i for i in issues if i.issue_type == "schema_inconsistency"]
    assert schema_issues
    assert "c" in schema_issues[0].details["missing"]
    assert "b" in schema_issues[0].details["extra"]


def test_no_schema_inconsistency_without_a_reference() -> None:
    df = pd.DataFrame({"a": ["1"]})
    issues = run_quality_checks(df, date_columns=(), measure_columns=(), reference_columns=None)
    assert not any(i.issue_type == "schema_inconsistency" for i in issues)


def test_clean_dataframe_has_no_issues() -> None:
    df = pd.DataFrame(
        {
            "quantity": [str(v) for v in range(1, 21)],
            "unit_price": [str(v) for v in range(10, 30)],
            "order_date": [f"2023-01-{d:02d}" for d in range(1, 21)],
        }
    )
    issues = run_quality_checks(df)
    assert issues == []
