"""Contribution math: exact-partition decomposition, the volume/price midpoint method, the
gross-profit identity, and independent pandas cross-checks against the real seed-42 dataset
(Phase 4 spec section 16)."""

from __future__ import annotations

import pandas as pd
import pytest
from app.db.models.canonical import FactSales
from app.kpi.periods import resolve_period
from app.rca import decomposition as dec
from sqlalchemy.orm import Session

pytestmark = pytest.mark.usefixtures("seeded_fact_sales_file_id")


# --- pure unit tests: no DB needed ----------------------------------------------------------


def test_gross_profit_decomposition_is_an_exact_identity() -> None:
    gp = dec.decompose_gross_profit(
        current_revenue=1_200.0, prior_revenue=1_000.0, current_cogs=800.0, prior_cogs=600.0
    )
    assert gp.revenue_effect == pytest.approx(200.0)
    assert gp.cogs_effect == pytest.approx(-200.0)
    assert gp.total_change == pytest.approx(0.0)  # GP unchanged: revenue +200, COGS +200


def test_gross_profit_decomposition_matches_hand_computed_gp_change() -> None:
    gp = dec.decompose_gross_profit(
        current_revenue=1_200.0, prior_revenue=1_000.0, current_cogs=700.0, prior_cogs=600.0
    )
    expected = (1_200.0 - 700.0) - (1_000.0 - 600.0)
    assert gp.total_change == pytest.approx(expected)
    assert gp.revenue_effect + gp.cogs_effect == pytest.approx(expected)


def test_volume_price_decomposition_sums_exactly_to_total_change() -> None:
    effect = dec.decompose_volume_price(
        current_revenue=1_300.0, prior_revenue=1_000.0, current_quantity=110.0, prior_quantity=100.0
    )
    assert effect is not None
    assert effect.volume_effect + effect.price_effect == pytest.approx(effect.total_change)
    assert effect.total_change == pytest.approx(300.0)


def test_volume_price_decomposition_matches_hand_computed_midpoint_formula() -> None:
    cur_rev, pri_rev, cur_qty, pri_qty = 1_300.0, 1_000.0, 110.0, 100.0
    effect = dec.decompose_volume_price(cur_rev, pri_rev, cur_qty, pri_qty)
    assert effect is not None
    cur_price, pri_price = cur_rev / cur_qty, pri_rev / pri_qty
    expected_volume = (cur_qty - pri_qty) * (pri_price + cur_price) / 2
    expected_price = (cur_price - pri_price) * (pri_qty + cur_qty) / 2
    assert effect.volume_effect == pytest.approx(expected_volume)
    assert effect.price_effect == pytest.approx(expected_price)


def test_volume_price_decomposition_is_undefined_not_zero_when_quantity_is_zero() -> None:
    assert dec.decompose_volume_price(100.0, 0.0, 10.0, 0.0) is None
    assert dec.decompose_volume_price(0.0, 100.0, 0.0, 10.0) is None


def test_residual_materiality_requires_both_relative_and_absolute_floors() -> None:
    # Big relative % but tiny absolute PKR -- not material.
    assert dec.is_residual_material(residual=50.0, total_change=100.0) is False
    # Big absolute PKR but tiny relative % of a huge total change -- not material.
    assert dec.is_residual_material(residual=200_000.0, total_change=1_000_000_000.0) is False
    # Clears both floors -- material.
    assert dec.is_residual_material(residual=500_000.0, total_change=1_000_000.0) is True


def test_top_k_with_other_preserves_the_exact_total() -> None:
    rows = tuple(
        dec.ContributionRow(
            dimension_value=f"E{i}",
            current_value=float(i),
            prior_value=0.0,
            absolute_contribution=float(i),
            percentage_contribution=None,
            direction="positive",
            rank=i + 1,
        )
        for i in range(5)
    )
    breakdown = dec.ContributionBreakdown(
        dimension="x",
        total_change=10.0,
        current_total=10.0,
        prior_total=0.0,
        rows=rows,
        coverage_pct=100.0,
        residual_absolute=0.0,
        residual_is_material=False,
    )
    display = dec.top_k_with_other(breakdown, k=2)
    assert len(display.rows) == 3  # top 2 + 1 "Other"
    other = display.rows[-1]
    assert other.is_other_bucket is True
    assert other.other_bucket_count == 3
    assert sum(r.absolute_contribution for r in display.rows) == pytest.approx(breakdown.total_change)


def test_top_k_with_other_is_a_no_op_when_under_the_limit() -> None:
    rows = (
        dec.ContributionRow(
            dimension_value="E0",
            current_value=1.0,
            prior_value=0.0,
            absolute_contribution=1.0,
            percentage_contribution=None,
            direction="positive",
            rank=1,
        ),
    )
    breakdown = dec.ContributionBreakdown(
        dimension="x",
        total_change=1.0,
        current_total=1.0,
        prior_total=0.0,
        rows=rows,
        coverage_pct=100.0,
        residual_absolute=0.0,
        residual_is_material=False,
    )
    assert dec.top_k_with_other(breakdown, k=5) is breakdown


# --- DB-backed tests against the real seed-42 dataset ---------------------------------------


def test_region_decomposition_partitions_revenue_exactly(db_session: Session) -> None:
    current = resolve_period("year", "2025")
    prior = resolve_period("year", "2024")
    breakdown = dec.decompose_by_dimension(db_session, FactSales.net_amount_pkr, current, prior, "region")
    assert breakdown.coverage_pct == pytest.approx(100.0, abs=0.01)
    assert breakdown.residual_is_material is False
    assert sum(r.absolute_contribution for r in breakdown.rows) == pytest.approx(breakdown.total_change)


def test_region_decomposition_matches_independent_pandas_computation(
    db_session: Session, sales_df: pd.DataFrame
) -> None:
    current = resolve_period("year", "2025")
    prior = resolve_period("year", "2024")
    breakdown = dec.decompose_by_dimension(db_session, FactSales.net_amount_pkr, current, prior, "region")

    expected_current = (
        sales_df[sales_df["month"].dt.year == 2025].groupby("region_id")["net_amount_pkr"].sum()
    )
    expected_prior = sales_df[sales_df["month"].dt.year == 2024].groupby("region_id")["net_amount_pkr"].sum()
    for row in breakdown.rows:
        region = row.dimension_value
        assert row.current_value == pytest.approx(float(expected_current.get(region, 0.0)), rel=1e-6)
        assert row.prior_value == pytest.approx(float(expected_prior.get(region, 0.0)), rel=1e-6)
        assert row.direction == ("positive" if row.absolute_contribution > 0 else "negative")


def test_region_decomposition_ranks_by_magnitude_of_contribution_descending(db_session: Session) -> None:
    current = resolve_period("year", "2025")
    prior = resolve_period("year", "2024")
    breakdown = dec.decompose_by_dimension(db_session, FactSales.net_amount_pkr, current, prior, "region")
    magnitudes = [abs(r.absolute_contribution) for r in breakdown.rows]
    assert magnitudes == sorted(magnitudes, reverse=True)
    assert [r.rank for r in breakdown.rows] == list(range(1, len(breakdown.rows) + 1))


def test_region_filtered_product_decomposition_sums_to_that_regions_own_change(
    db_session: Session, planted_config: object
) -> None:
    region_id = planted_config.planted.region_decline_id  # type: ignore[attr-defined]
    current = resolve_period("year", "2025")
    prior = resolve_period("year", "2024")

    region_only = dec.decompose_by_dimension(db_session, FactSales.net_amount_pkr, current, prior, "region")
    region_total_change = next(
        r.absolute_contribution for r in region_only.rows if r.dimension_value == region_id
    )

    within_region_by_product = dec.decompose_by_dimension(
        db_session,
        FactSales.net_amount_pkr,
        current,
        prior,
        "product",
        filter_dimension="region",
        filter_value=region_id,
    )
    assert within_region_by_product.total_change == pytest.approx(region_total_change)
    assert sum(r.absolute_contribution for r in within_region_by_product.rows) == pytest.approx(
        region_total_change
    )


def test_company_wide_volume_price_effect_sums_to_revenue_change(db_session: Session) -> None:
    from app.kpi import aggregations as agg

    current = resolve_period("year", "2025")
    prior = resolve_period("year", "2024")
    cur_rev = agg.sum_column(db_session, FactSales.net_amount_pkr, current)
    pri_rev = agg.sum_column(db_session, FactSales.net_amount_pkr, prior)
    cur_qty = agg.sum_column(db_session, FactSales.quantity, current)
    pri_qty = agg.sum_column(db_session, FactSales.quantity, prior)

    effect = dec.decompose_volume_price(cur_rev, pri_rev, cur_qty, pri_qty)
    assert effect is not None
    assert effect.volume_effect + effect.price_effect == pytest.approx(cur_rev - pri_rev, rel=1e-9)
