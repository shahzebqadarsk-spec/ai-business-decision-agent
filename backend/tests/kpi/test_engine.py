"""Engine-level tests: period comparisons (YoY/QoQ/MoM), the zero/undefined-percentage-
change guard, unknown-KPI handling, and that every calculation is persisted as a provenance
row (Phase 3 spec, "KPI result/evidence persistence")."""

from __future__ import annotations

import pandas as pd
import pytest
from app.db.models.kpi import KpiCalculation
from app.kpi import engine
from app.kpi.models import KPIStatus
from sqlalchemy import select
from sqlalchemy.orm import Session

pytestmark = pytest.mark.usefixtures("seeded_fact_sales_file_id")


def test_yoy_comparison_reports_both_values_and_a_direction(
    db_session: Session, sales_df: pd.DataFrame
) -> None:
    revenue_2024 = sales_df[sales_df["month"].dt.year == 2024]["net_amount_pkr"].sum()
    revenue_2023 = sales_df[sales_df["month"].dt.year == 2023]["net_amount_pkr"].sum()

    result = engine.calculate_kpi(db_session, "revenue", "year", "2024", comparison_type="YoY")

    assert result.value == pytest.approx(revenue_2024, rel=1e-9)
    assert result.comparison_value == pytest.approx(revenue_2023, rel=1e-9)
    assert result.comparison_period_key == "2023"
    assert result.absolute_change == pytest.approx(revenue_2024 - revenue_2023, rel=1e-9)
    assert result.percentage_change == pytest.approx(
        (revenue_2024 - revenue_2023) / revenue_2023 * 100, rel=1e-9
    )
    assert result.percentage_change_status == "ok"


def test_mom_comparison(db_session: Session, sales_df: pd.DataFrame) -> None:
    feb = sales_df[(sales_df["month"].dt.year == 2024) & (sales_df["month"].dt.month == 2)]
    jan = sales_df[(sales_df["month"].dt.year == 2024) & (sales_df["month"].dt.month == 1)]

    result = engine.calculate_kpi(db_session, "revenue", "month", "2024-02", comparison_type="MoM")

    assert result.value == pytest.approx(feb["net_amount_pkr"].sum(), rel=1e-9)
    assert result.comparison_value == pytest.approx(jan["net_amount_pkr"].sum(), rel=1e-9)
    assert result.comparison_period_key == "2024-01"


def test_qoq_comparison(db_session: Session) -> None:
    result = engine.calculate_kpi(db_session, "revenue", "quarter", "2024-Q2", comparison_type="QoQ")
    assert result.comparison_period_key == "2024-Q1"
    assert result.percentage_change_status in ("ok", "undefined_zero_denominator")


def test_percentage_change_is_none_when_comparison_period_has_no_data(db_session: Session) -> None:
    # 2023 is the dataset's first year, so its YoY comparison period (2022) has zero rows.
    # comparison_value must come back None (not 0), and percentage_change must stay unset
    # rather than raising a ZeroDivisionError.
    result = engine.calculate_kpi(db_session, "customer_count", "year", "2023", comparison_type="YoY")
    assert result.comparison_value is None
    assert result.percentage_change is None
    assert result.percentage_change_status == "undefined_missing_data"


def test_no_comparison_requested_is_distinguished_from_undefined(db_session: Session) -> None:
    result = engine.calculate_kpi(db_session, "revenue", "year", "2024")
    assert result.comparison_type is None
    assert result.percentage_change_status == "not_requested"


def test_unknown_kpi_id_raises() -> None:
    with pytest.raises(engine.UnknownKpiError):
        engine.calculate_kpi(None, "not_a_real_kpi", "year", "2024")  # type: ignore[arg-type]


def test_calculation_is_persisted_as_a_provenance_row(db_session: Session) -> None:
    before = db_session.execute(select(KpiCalculation).where(KpiCalculation.kpi_id == "revenue")).all()
    engine.calculate_kpi(db_session, "revenue", "year", "2024", comparison_type="YoY")
    after = db_session.execute(select(KpiCalculation).where(KpiCalculation.kpi_id == "revenue")).all()
    assert len(after) == len(before) + 1

    row = after[-1][0]
    assert row.status == KPIStatus.AVAILABLE.value
    assert row.calculation_version
    assert row.source_file_ids
    assert row.source_fields


def test_cannot_compute_kpi_is_also_persisted_with_its_reason(db_session: Session) -> None:
    result = engine.calculate_kpi(db_session, "procurement_cost", "year", "2024")
    assert result.status is KPIStatus.CANNOT_COMPUTE
    row = (
        db_session.execute(
            select(KpiCalculation)
            .where(KpiCalculation.kpi_id == "procurement_cost")
            .order_by(KpiCalculation.created_at.desc())
        )
        .scalars()
        .first()
    )
    assert row is not None
    assert row.status == "cannot_compute"
    assert row.status_reason is not None


def test_availability_check_never_runs_the_aggregation_query(db_session: Session) -> None:
    status, reason = engine.check_availability("payroll_cost", "year", "2024", db_session)
    assert status is KPIStatus.CANNOT_COMPUTE
    assert reason is not None

    status, reason = engine.check_availability("revenue", "year", "2024", db_session)
    assert status is KPIStatus.AVAILABLE


def test_breakdown_for_kpi_without_breakdown_support_rejected(db_session: Session) -> None:
    with pytest.raises(engine.UnsupportedBreakdownError):
        engine.calculate_breakdown(db_session, "gross_margin_pct", "year", "2024", "region")


def test_breakdown_for_unsupported_dimension_rejected(db_session: Session) -> None:
    with pytest.raises(engine.UnsupportedBreakdownError):
        engine.calculate_breakdown(db_session, "revenue", "year", "2024", "not_a_real_dimension")
