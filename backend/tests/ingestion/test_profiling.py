from __future__ import annotations

import pandas as pd
from app.ingestion.profiling import profile_dataframe


def _df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "customer_id": ["CUST-0001", "CUST-0002", "CUST-0003", "CUST-0001", None],
            "quantity": ["10", "20", "30", "40", "50"],
            "order_date": ["2023-01-05", "2023-01-06", "2023-01-07", "2023-01-08", "2023-01-09"],
            "region_id": ["REG-01", "REG-02", "REG-01", "REG-01", "REG-02"],
        }
    )


def test_profiles_every_column() -> None:
    profiles = profile_dataframe(_df())
    assert {p.column_name for p in profiles} == {"customer_id", "quantity", "order_date", "region_id"}


def test_classifies_numeric_column_as_measure() -> None:
    profiles = {p.column_name: p for p in profile_dataframe(_df())}
    assert profiles["quantity"].inferred_dtype == "numeric"
    assert profiles["quantity"].classification == "measure"
    assert profiles["quantity"].mean_value == 30.0


def test_classifies_date_column_as_date() -> None:
    profiles = {p.column_name: p for p in profile_dataframe(_df())}
    assert profiles["order_date"].classification == "date"
    assert profiles["order_date"].date_min is not None
    assert profiles["order_date"].date_max is not None


def test_classifies_low_cardinality_string_as_category() -> None:
    profiles = {p.column_name: p for p in profile_dataframe(_df())}
    assert profiles["region_id"].classification == "category"


def test_null_percentage_and_count() -> None:
    profiles = {p.column_name: p for p in profile_dataframe(_df())}
    assert profiles["customer_id"].null_count == 1
    assert profiles["customer_id"].null_percentage == 20.0


def test_unique_count_and_samples() -> None:
    profiles = {p.column_name: p for p in profile_dataframe(_df())}
    assert profiles["customer_id"].unique_count == 3
    assert len(profiles["customer_id"].sample_values) <= 5


def test_classifies_mixed_currency_formatting_as_numeric_measure() -> None:
    # A real small-business export mixes "Rs 1,441.26" / "1,379.22" / "210.99" in one
    # column (different staff, copy-pasted rows). Without numeric_format.py cleaning
    # these first, pd.to_numeric fails on most of them and the column gets misread as
    # a string identifier instead of a measure -- this is the bug the fix closes.
    df = pd.DataFrame(
        {
            "unit_price_rs": ["Rs 1,441.26", "1,379.22", "210.99", "Rs. 500.00", "2,000"],
        }
    )
    profiles = {p.column_name: p for p in profile_dataframe(df)}
    assert profiles["unit_price_rs"].inferred_dtype == "numeric"
    assert profiles["unit_price_rs"].classification == "measure"
    assert profiles["unit_price_rs"].mean_value is not None
