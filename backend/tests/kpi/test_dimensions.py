from __future__ import annotations

import pandas as pd
import pytest
from app.kpi import calculators as calc
from app.kpi.periods import resolve_period
from sqlalchemy.orm import Session

pytestmark = pytest.mark.usefixtures("seeded_fact_sales_file_id")


def test_revenue_by_region_matches_independent_groupby(db_session: Session, sales_df: pd.DataFrame) -> None:
    subset = sales_df[sales_df["month"].dt.year == 2024]
    expected = subset.groupby("region_id")["net_amount"].sum().sort_values(ascending=False)

    window = resolve_period("year", "2024")
    rows = calc.breakdown_revenue(db_session, window, "region")

    assert len(rows) == len(expected)
    for row, (expected_region, expected_value) in zip(rows, expected.items(), strict=True):
        assert row.dimension_value == expected_region
        assert row.value == pytest.approx(expected_value, rel=1e-9)


def test_revenue_by_product_matches_independent_groupby(db_session: Session, sales_df: pd.DataFrame) -> None:
    subset = sales_df[sales_df["month"].dt.year == 2024]
    expected_total = subset.groupby("product_id")["net_amount"].sum().sum()

    window = resolve_period("year", "2024")
    rows = calc.breakdown_revenue(db_session, window, "product")
    assert sum(r.value or 0 for r in rows) == pytest.approx(expected_total, rel=1e-9)


def test_breakdown_rows_are_ranked_descending(db_session: Session) -> None:
    window = resolve_period("year", "2024")
    rows = calc.breakdown_revenue(db_session, window, "region")
    values = [v for r in rows if (v := r.value) is not None]
    assert len(values) == len(rows), "every available breakdown row should carry a numeric value"
    assert values == sorted(values, reverse=True)
    assert [r.rank for r in rows] == list(range(1, len(rows) + 1))


def test_breakdown_share_pct_sums_to_roughly_100(db_session: Session) -> None:
    window = resolve_period("year", "2024")
    rows = calc.breakdown_revenue(db_session, window, "region")
    total_share = sum(r.share_pct or 0 for r in rows)
    assert total_share == pytest.approx(100.0, rel=1e-6)


def test_time_dimension_breakdown_is_chronological_not_ranked(db_session: Session) -> None:
    window = resolve_period("year", "2024")
    rows = calc.breakdown_revenue(db_session, window, "month")
    keys = [k for r in rows if (k := r.dimension_value) is not None]
    assert len(keys) == len(rows), "every monthly bucket should carry a key"
    assert keys == sorted(keys)
    assert all(r.rank is None for r in rows)


def test_customer_breakdown_supports_top_and_bottom_ranking(db_session: Session) -> None:
    window = resolve_period("year", "2024")
    rows = calc.breakdown_revenue(db_session, window, "customer")
    top_5 = rows[:5]
    bottom_5 = rows[-5:]
    top_values = [v for r in top_5 if (v := r.value) is not None]
    assert all(top_values[i] >= top_values[i + 1] for i in range(len(top_values) - 1))
    all_values = [v for r in rows if (v := r.value) is not None]
    assert min(all_values) == bottom_5[-1].value


def test_deterministic_repeated_breakdown(db_session: Session) -> None:
    window = resolve_period("year", "2024")
    first = calc.breakdown_revenue(db_session, window, "region")
    second = calc.breakdown_revenue(db_session, window, "region")
    assert [(r.dimension_value, r.value) for r in first] == [(r.dimension_value, r.value) for r in second]
