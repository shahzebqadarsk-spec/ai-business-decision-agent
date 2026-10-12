"""Calculator-level tests against the real seed-42 dataset. Where practical, the expected
value is computed independently with pandas directly from the generator's own CSV, rather
than only comparing the KPI engine against itself (Phase 3 spec, section 12).
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest
from app.db.models.canonical import FactSales
from app.kpi import calculators as calc
from app.kpi.models import KPIStatus
from app.kpi.periods import resolve_period
from sqlalchemy import insert
from sqlalchemy.orm import Session

pytestmark = pytest.mark.usefixtures("seeded_fact_sales_file_id")


def _year_2024(sales_df: pd.DataFrame) -> pd.DataFrame:
    mask: pd.Series = sales_df["month"].dt.year == 2024
    return sales_df.loc[mask]


def test_revenue_matches_independent_pandas_sum(db_session: Session, sales_df: pd.DataFrame) -> None:
    expected = _year_2024(sales_df)["net_amount_pkr"].sum()
    window = resolve_period("year", "2024")
    result = calc.calculate_revenue(db_session, window)
    assert result.status is KPIStatus.AVAILABLE
    assert result.value is not None
    assert result.value == pytest.approx(expected, rel=1e-9)


def test_sales_quantity_matches_independent_pandas_sum(db_session: Session, sales_df: pd.DataFrame) -> None:
    expected = _year_2024(sales_df)["quantity"].sum()
    window = resolve_period("year", "2024")
    result = calc.calculate_sales_quantity(db_session, window)
    assert result.value == pytest.approx(expected, rel=1e-9)


def test_average_selling_price_matches_independent_calculation(
    db_session: Session, sales_df: pd.DataFrame
) -> None:
    subset = _year_2024(sales_df)
    expected = subset["net_amount_pkr"].sum() / subset["quantity"].sum()
    window = resolve_period("year", "2024")
    result = calc.calculate_average_selling_price(db_session, window)
    assert result.value == pytest.approx(expected, rel=1e-9)


def test_customer_count_matches_independent_nunique(db_session: Session, sales_df: pd.DataFrame) -> None:
    expected = _year_2024(sales_df)["customer_id"].nunique()
    window = resolve_period("year", "2024")
    result = calc.calculate_customer_count(db_session, window)
    assert result.value == expected


def test_transaction_count_matches_independent_nunique(db_session: Session, sales_df: pd.DataFrame) -> None:
    expected = _year_2024(sales_df)["sale_id"].nunique()
    window = resolve_period("year", "2024")
    result = calc.calculate_transaction_count(db_session, window)
    assert result.value == expected


def test_cogs_matches_independent_pandas_sum(db_session: Session, sales_df: pd.DataFrame) -> None:
    expected = _year_2024(sales_df)["cogs_amount_pkr"].sum()
    window = resolve_period("year", "2024")
    result = calc.calculate_cogs(db_session, window)
    assert result.value == pytest.approx(expected, rel=1e-9)


def test_gross_profit_matches_independent_calculation(db_session: Session, sales_df: pd.DataFrame) -> None:
    subset = _year_2024(sales_df)
    expected = subset["net_amount_pkr"].sum() - subset["cogs_amount_pkr"].sum()
    window = resolve_period("year", "2024")
    result = calc.calculate_gross_profit(db_session, window)
    assert result.value == pytest.approx(expected, rel=1e-9)


def test_gross_margin_pct_matches_independent_calculation(
    db_session: Session, sales_df: pd.DataFrame
) -> None:
    subset = _year_2024(sales_df)
    revenue = subset["net_amount_pkr"].sum()
    cogs = subset["cogs_amount_pkr"].sum()
    expected = (revenue - cogs) / revenue * 100
    window = resolve_period("year", "2024")
    result = calc.calculate_gross_margin_pct(db_session, window)
    assert result.value == pytest.approx(expected, rel=1e-9)


def test_monthly_annual_and_quarterly_aggregation_are_consistent(
    db_session: Session, sales_df: pd.DataFrame
) -> None:
    """Independently verify (via pandas) that summing the 12 months of 2024 equals the
    year-2024 total, and that summing Q1-Q4 2024 also equals it -- same invariant the KPI
    engine itself must satisfy no matter which granularity is requested."""
    months_2024 = [f"2024-{m:02d}" for m in range(1, 13)]
    monthly_total = sum(
        calc.calculate_revenue(db_session, resolve_period("month", m)).value or 0.0 for m in months_2024
    )
    quarters_2024 = [f"2024-Q{q}" for q in range(1, 5)]
    quarterly_total = sum(
        calc.calculate_revenue(db_session, resolve_period("quarter", q)).value or 0.0 for q in quarters_2024
    )
    annual = calc.calculate_revenue(db_session, resolve_period("year", "2024")).value

    assert monthly_total == pytest.approx(annual, rel=1e-9)
    assert quarterly_total == pytest.approx(annual, rel=1e-9)


def test_lineage_includes_the_source_file(db_session: Session, seeded_fact_sales_file_id: str) -> None:
    window = resolve_period("year", "2024")
    result = calc.calculate_revenue(db_session, window)
    assert seeded_fact_sales_file_id in result.source_file_ids


def test_deterministic_repeated_calculation(db_session: Session) -> None:
    window = resolve_period("year", "2024")
    first = calc.calculate_revenue(db_session, window)
    second = calc.calculate_revenue(db_session, window)
    assert first.value == second.value
    assert first.status == second.status


def test_cannot_compute_for_unimplemented_canonical_table(db_session: Session) -> None:
    calculator = calc.make_cannot_compute_calculator(("fact_procurement",))
    result = calculator(db_session, resolve_period("year", "2024"))
    assert result.status is KPIStatus.CANNOT_COMPUTE
    assert result.value is None
    assert "fact_procurement" in (result.status_reason or "")


def test_insufficient_data_for_a_period_with_no_rows(db_session: Session) -> None:
    window = resolve_period("year", "2099")
    result = calc.calculate_revenue(db_session, window)
    assert result.status is KPIStatus.INSUFFICIENT_DATA
    assert result.value is None
    assert "2099" in (result.status_reason or "")


@pytest.fixture
def sparse_cogs_period(db_session: Session, seeded_fact_sales_file_id: str) -> None:
    """10 rows in a dedicated, otherwise-untouched period where only 1 of 10 has COGS
    populated -- below the sufficiency threshold -- to exercise the "missing required field"
    gate independently of the "no rows at all" gate above.

    Deliberately `flush()`, never `commit()`: the test below reads this through the same
    `db_session` object (autoflush makes the uncommitted insert visible to it), and leaving it
    uncommitted means the shared `session.rollback()` in the `db_session` fixture's teardown
    discards it. A `commit()` here used to leave these far-future (2098-06) rows permanently in
    the shared test database, silently widening `fact_sales`'s whole-table min/max month range
    for every test that ran afterward -- invisible to every Phase 0-4 test, since none of them
    ever queried that whole-table range, until Phase 5's `check_history_sufficiency()` did."""
    rows = []
    for i in range(10):
        rows.append(
            {
                "source_file_id": seeded_fact_sales_file_id,
                "source_row_number": 900_000 + i,
                "sale_id": f"EDGE-{i}",
                "month": date(2098, 6, 1),
                "customer_id": "CUST-EDGE",
                "product_id": "PROD-EDGE",
                "quantity": 1,
                "unit_price_pkr": 100,
                "net_amount_pkr": 100,
                "cogs_amount_pkr": 60 if i == 0 else None,
                # Calculators now read the *_reporting columns (Phase 8); this fixture
                # bypasses materialize_fact_sales, so it has to set them itself, same as
                # the shared seeded_fact_sales_file_id fixture does for the main dataset.
                "currency": "PKR",
                "net_amount_reporting": 100,
                "cogs_amount_reporting": 60 if i == 0 else None,
            }
        )
    db_session.execute(insert(FactSales), rows)
    db_session.flush()


def test_insufficient_data_for_low_field_coverage(db_session: Session, sparse_cogs_period: None) -> None:
    window = resolve_period("year", "2098")
    result = calc.calculate_cogs(db_session, window)
    assert result.status is KPIStatus.INSUFFICIENT_DATA
    assert "cogs_amount_reporting" in (result.status_reason or "")


@pytest.fixture
def zero_quantity_period(db_session: Session, seeded_fact_sales_file_id: str) -> None:
    """A period with real rows but zero total quantity, to exercise the zero-denominator
    guard on average selling price without it ever being confused for "no data at all".

    `flush()`, not `commit()` -- see `sparse_cogs_period`'s own comment just above; the same
    permanent-pollution risk applies to this fixture's 2097-01 row."""
    rows = [
        {
            "source_file_id": seeded_fact_sales_file_id,
            "source_row_number": 950_000,
            "sale_id": "ZERO-1",
            "month": date(2097, 1, 1),
            "customer_id": "CUST-ZERO",
            "product_id": "PROD-ZERO",
            "quantity": 0,
            "unit_price_pkr": 0,
            "net_amount_pkr": 0,
            "currency": "PKR",
            "net_amount_reporting": 0,
        }
    ]
    db_session.execute(insert(FactSales), rows)
    db_session.flush()


def test_zero_denominator_returns_invalid_data_not_a_crash(
    db_session: Session, zero_quantity_period: None
) -> None:
    window = resolve_period("year", "2097")
    result = calc.calculate_average_selling_price(db_session, window)
    assert result.status is KPIStatus.INVALID_DATA
    assert result.value is None
    assert "zero" in (result.status_reason or "").lower()
