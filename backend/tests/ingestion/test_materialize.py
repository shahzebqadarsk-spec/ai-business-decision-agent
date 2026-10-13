from __future__ import annotations

import uuid

import pandas as pd
import pytest
from app.fx.rates import RATES_AS_OF
from app.ingestion.materialize import MissingRequiredFieldMappingError, materialize_fact_sales


def _df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "mo": ["2023-01-01", "2023-02-01"],
            "cust": ["CUST-0001", "CUST-0002"],
            "prod": ["PROD-01", "PROD-02"],
            "qty": ["10", "-3"],
            "price": ["100", "200"],
            "net": ["1000", "not-a-number"],
        }
    )


_FULL_MAPPING = {
    "mo": "month",
    "cust": "customer_id",
    "prod": "product_id",
    "qty": "quantity",
    "price": "unit_price",
    "net": "net_amount",
}


def test_materialize_requires_all_required_fields_confirmed() -> None:
    incomplete_mapping = {"mo": "month", "cust": "customer_id"}
    with pytest.raises(MissingRequiredFieldMappingError) as exc_info:
        materialize_fact_sales(_df(), confirmed_mapping=incomplete_mapping, source_file_id=uuid.uuid4())
    assert "product_id" in exc_info.value.missing_fields


def test_materialize_writes_lineage() -> None:
    file_id = uuid.uuid4()
    rows, _result = materialize_fact_sales(_df(), confirmed_mapping=_FULL_MAPPING, source_file_id=file_id)
    assert all(row.source_file_id == file_id for row in rows)
    assert [row.source_row_number for row in rows[:1]] == [0]


def test_materialize_skips_rows_that_fail_to_coerce() -> None:
    rows, result = materialize_fact_sales(_df(), confirmed_mapping=_FULL_MAPPING, source_file_id=uuid.uuid4())
    # row 1 has a non-numeric net_amount and should be skipped, row 0 should succeed
    assert result.rows_written == 1
    assert result.rows_skipped == 1
    assert len(rows) == 1
    assert rows[0].customer_id == "CUST-0001"


def test_materialize_preserves_negative_quantity_as_a_quality_concern_not_a_block() -> None:
    # Materialization only blocks on type-coercion failure, not business-rule violations
    # (those are surfaced separately as data-quality issues) -- row 0 has qty=10 (fine);
    # confirm that a *valid-but-business-questionable* value elsewhere doesn't get silently
    # dropped by materialize.
    df = pd.DataFrame(
        {
            "mo": ["2023-01-01"],
            "cust": ["CUST-0001"],
            "prod": ["PROD-01"],
            "qty": ["-5"],
            "price": ["100"],
            "net": ["1000"],
        }
    )
    rows, result = materialize_fact_sales(df, confirmed_mapping=_FULL_MAPPING, source_file_id=uuid.uuid4())
    assert result.rows_written == 1
    assert float(rows[0].quantity) == -5.0


def test_materialize_coerces_mixed_currency_formatted_values() -> None:
    # Mirrors the profiling-side fix: a price/amount column mixing "Rs 1,441.26",
    # "1,379.22" and "210.99" must still materialize as a correct float, not just
    # profile as numeric -- a column that passes profiling but fails here would
    # silently drop every row at the materialize step instead.
    df = pd.DataFrame(
        {
            "mo": ["2023-01-01", "2023-02-01"],
            "cust": ["CUST-0001", "CUST-0002"],
            "prod": ["PROD-01", "PROD-02"],
            "qty": ["10", "20"],
            "price": ["Rs 1,441.26", "210.99"],
            "net": ["Rs. 14,412.60", "4,219.80"],
        }
    )
    rows, result = materialize_fact_sales(df, confirmed_mapping=_FULL_MAPPING, source_file_id=uuid.uuid4())
    assert result.rows_written == 2
    assert result.rows_skipped == 0
    assert rows[0].unit_price == 1441.26
    assert rows[0].net_amount == 14412.60
    assert rows[1].unit_price == 210.99
    assert rows[1].net_amount == 4219.80


# --- Phase 8: multi-currency support -----------------------------------------------------


def test_materialize_defaults_to_reporting_currency_when_no_currency_signal() -> None:
    # No currency column mapped, no symbol in the price text -- same implicit
    # single-currency assumption every upload made before Phase 8 existed.
    rows, _result = materialize_fact_sales(_df(), confirmed_mapping=_FULL_MAPPING, source_file_id=uuid.uuid4())
    assert rows[0].currency == "PKR"
    assert float(rows[0].fx_rate_to_reporting) == pytest.approx(1.0)
    assert rows[0].fx_rate_as_of == RATES_AS_OF
    assert float(rows[0].unit_price_reporting) == pytest.approx(float(rows[0].unit_price))
    assert float(rows[0].net_amount_reporting) == pytest.approx(float(rows[0].net_amount))


def test_materialize_detects_unambiguous_currency_from_price_text() -> None:
    # No explicit currency column, but "US$" in the price cell is unambiguous.
    df = pd.DataFrame(
        {
            "mo": ["2023-01-01"],
            "cust": ["CUST-0001"],
            "prod": ["PROD-01"],
            "qty": ["10"],
            "price": ["US$100.00"],
            "net": ["US$1000.00"],
        }
    )
    rows, result = materialize_fact_sales(df, confirmed_mapping=_FULL_MAPPING, source_file_id=uuid.uuid4())
    assert result.rows_written == 1
    assert rows[0].currency == "USD"
    assert float(rows[0].unit_price) == 100.0  # native amount, column name notwithstanding
    assert float(rows[0].fx_rate_to_reporting) != pytest.approx(1.0)
    assert float(rows[0].net_amount_reporting) == pytest.approx(
        1000.0 * float(rows[0].fx_rate_to_reporting)
    )


def test_materialize_an_explicit_currency_column_wins_over_detection() -> None:
    mapping = {**_FULL_MAPPING, "cur": "currency"}
    df = pd.DataFrame(
        {
            "mo": ["2023-01-01"],
            "cust": ["CUST-0001"],
            "prod": ["PROD-01"],
            "qty": ["10"],
            "price": ["100"],  # no symbol -- would default to reporting currency otherwise
            "net": ["1000"],
            "cur": ["EUR"],
        }
    )
    rows, result = materialize_fact_sales(df, confirmed_mapping=mapping, source_file_id=uuid.uuid4())
    assert result.rows_written == 1
    assert rows[0].currency == "EUR"


def test_materialize_mixed_currencies_within_one_file_convert_independently() -> None:
    # The actual point of Phase 8: one upload, different rows, different native
    # currencies -- each row's reporting amount uses its own rate, not a shared one.
    mapping = {**_FULL_MAPPING, "cur": "currency"}
    df = pd.DataFrame(
        {
            "mo": ["2023-01-01", "2023-02-01"],
            "cust": ["CUST-0001", "CUST-0002"],
            "prod": ["PROD-01", "PROD-02"],
            "qty": ["10", "10"],
            "price": ["100", "100"],
            "net": ["1000", "1000"],
            "cur": ["PKR", "USD"],
        }
    )
    rows, result = materialize_fact_sales(df, confirmed_mapping=mapping, source_file_id=uuid.uuid4())
    assert result.rows_written == 2
    pkr_row = next(r for r in rows if r.currency == "PKR")
    usd_row = next(r for r in rows if r.currency == "USD")
    assert float(pkr_row.fx_rate_to_reporting) == pytest.approx(1.0)
    assert float(usd_row.fx_rate_to_reporting) != pytest.approx(1.0)
    assert float(pkr_row.net_amount_reporting) == pytest.approx(1000.0)
    assert float(usd_row.net_amount_reporting) != pytest.approx(float(usd_row.net_amount))


def test_materialize_skips_rows_with_an_unsupported_explicit_currency() -> None:
    # A confirmed currency mapping with a code we have no rate for must not silently
    # fall back to the deployment default -- the user explicitly said what it is.
    mapping = {**_FULL_MAPPING, "cur": "currency"}
    df = pd.DataFrame(
        {
            "mo": ["2023-01-01"],
            "cust": ["CUST-0001"],
            "prod": ["PROD-01"],
            "qty": ["10"],
            "price": ["100"],
            "net": ["1000"],
            "cur": ["ZZZ"],
        }
    )
    rows, result = materialize_fact_sales(df, confirmed_mapping=mapping, source_file_id=uuid.uuid4())
    assert result.rows_written == 0
    assert result.rows_skipped == 1
    assert "ZZZ" in result.skipped_reasons[0]
