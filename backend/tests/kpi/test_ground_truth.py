"""Uses the hidden ground-truth measurement functions ONLY here, in a test, to independently
confirm the KPI engine reproduces the planted regional revenue decline (GT-02) -- never as
the KPI engine's runtime input (see tests/synthetic/test_isolation.py's static source-grep,
which would fail this whole suite if app/ ever imported `generator.measure`).
"""

from __future__ import annotations

import pandas as pd
import pytest
from app.kpi import calculators as calc
from app.kpi.periods import resolve_period
from generator.config import GeneratorConfig
from generator.measure import measure_region_decline
from sqlalchemy.orm import Session

pytestmark = pytest.mark.usefixtures("seeded_fact_sales_file_id")


def test_declining_region_shows_negative_revenue_change_matching_ground_truth(
    db_session: Session, sales_df: pd.DataFrame, planted_config: GeneratorConfig
) -> None:
    region_id = planted_config.planted.region_decline_id
    # `measure_region_decline` (generator-side) compares `month` against plain ISO date
    # *strings*, matching the generator's own in-memory table shape; our `sales_df` fixture
    # parses `month` as a real date for the rest of this suite's `.dt.year` filtering, so it
    # needs converting back to strings for this one cross-check against the generator.
    string_month_df = sales_df.assign(month=sales_df["month"].dt.strftime("%Y-%m-%d"))
    expected_ratio = measure_region_decline(string_month_df, region_id=region_id)
    assert expected_ratio < 0, "sanity check: the planted region is supposed to be declining"

    first_quarter = calc.breakdown_revenue(db_session, resolve_period("quarter", "2023-Q1"), "region")
    final_quarter = calc.breakdown_revenue(db_session, resolve_period("quarter", "2025-Q4"), "region")

    first_value = next(r.value for r in first_quarter if r.dimension_value == region_id)
    final_value = next(r.value for r in final_quarter if r.dimension_value == region_id)
    assert first_value is not None and final_value is not None
    engine_ratio = (final_value - first_value) / first_value

    assert engine_ratio < 0
    assert engine_ratio == pytest.approx(expected_ratio, rel=1e-9)


def test_non_declining_regions_do_not_all_show_the_same_decline(
    db_session: Session, planted_config: GeneratorConfig
) -> None:
    """The decline is concentrated in one region, not a company-wide trend -- at least one
    other region should *not* be down over the same window."""
    region_id = planted_config.planted.region_decline_id
    first_quarter = {
        r.dimension_value: r.value
        for r in calc.breakdown_revenue(db_session, resolve_period("quarter", "2023-Q1"), "region")
    }
    final_quarter = {
        r.dimension_value: r.value
        for r in calc.breakdown_revenue(db_session, resolve_period("quarter", "2025-Q4"), "region")
    }
    other_regions = [r for r in first_quarter if r != region_id and r in final_quarter]
    ratios = [
        (fv - iv) / iv
        for r in other_regions
        if (iv := first_quarter[r]) is not None and (fv := final_quarter[r]) is not None
    ]
    assert any(ratio > 0 for ratio in ratios), "expected at least one region to be growing, not declining"


def test_overall_company_revenue_trend_is_not_simply_the_declining_regions_trend(
    db_session: Session, planted_config: GeneratorConfig
) -> None:
    """Company-wide revenue for 2025 should still exceed 2023 -- the regional decline (GT-02)
    is a concentrated, diagnosable problem, not the dominant company-wide signal."""
    from app.kpi import engine

    revenue_2023 = engine.calculate_kpi(db_session, "revenue", "year", "2023").value
    revenue_2025 = engine.calculate_kpi(db_session, "revenue", "year", "2025").value
    assert revenue_2025 is not None and revenue_2023 is not None
    assert revenue_2025 > revenue_2023
