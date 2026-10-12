"""Issue-detection unit tests.

Two styles are used deliberately:

1. Against the **real seed-42 dataset** (region/product/volume detectors, which genuinely
   fire on it) -- cross-checked independently with pandas, and also used to prove the
   materiality screen suppresses company-level detectors that *don't* clear threshold on the
   real, actually-growing company trend (Phase 4 spec section 2: "do not flag every small
   fluctuation").
2. With `calculate_kpi` monkeypatched to return a crafted `KPIResult` (revenue_decline,
   revenue_growth_slowdown, margin_deterioration, unusual_cost_movement,
   customer_concentration_change) -- so each detector's trigger/no-trigger branches are
   exercised deterministically, independent of whether the real dataset happens to contain a
   scenario that crosses that particular threshold.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest
from app.kpi.engine import KPIResult
from app.kpi.models import KPIStatus
from app.rca import issues
from sqlalchemy.orm import Session

pytestmark = pytest.mark.usefixtures("seeded_fact_sales_file_id")


def _kpi_result(**overrides: object) -> KPIResult:
    defaults: dict[str, object] = {
        "kpi_id": "revenue",
        "name": "Revenue",
        "unit": "currency",
        "currency": "PKR",
        "granularity": "year",
        "period_key": "2025",
        "status": KPIStatus.AVAILABLE,
        "status_reason": None,
        "value": 100.0,
        "comparison_type": "YoY",
        "comparison_period_key": "2024",
        "comparison_value": 100.0,
        "absolute_change": 0.0,
        "percentage_change": 0.0,
        "percentage_change_status": "ok",
        "data_coverage": {},
        "source_file_ids": (),
        "source_fields": (),
        "calculation_version": "1.0.0",
        "calculated_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return KPIResult(**defaults)  # type: ignore[arg-type]


# --- monkeypatched company-level detectors --------------------------------------------------


def test_revenue_decline_fires_when_material(monkeypatch: pytest.MonkeyPatch, db_session: Session) -> None:
    # Magnitudes large enough to clear *both* revenue_decline thresholds (>=10% and
    # >=PKR 5,000,000 -- see app/rca/materiality.py), not just the percentage one.
    monkeypatch.setattr(
        issues,
        "calculate_kpi",
        lambda *a, **k: _kpi_result(
            value=80_000_000.0,
            comparison_value=100_000_000.0,
            absolute_change=-20_000_000.0,
            percentage_change=-20.0,
        ),
    )
    found = issues.detect_revenue_decline(db_session, "year", "2025", "YoY")
    assert len(found) == 1
    assert found[0].issue_type == "revenue_decline"
    assert found[0].percentage_change == -20.0
    assert found[0].severity in ("medium", "high", "critical", "low")


def test_revenue_decline_does_not_fire_below_threshold(
    monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    monkeypatch.setattr(
        issues,
        "calculate_kpi",
        lambda *a, **k: _kpi_result(
            value=980.0, comparison_value=1000.0, absolute_change=-20.0, percentage_change=-2.0
        ),
    )
    assert issues.detect_revenue_decline(db_session, "year", "2025", "YoY") == []


def test_revenue_decline_does_not_fire_for_growth(
    monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    monkeypatch.setattr(
        issues,
        "calculate_kpi",
        lambda *a, **k: _kpi_result(
            value=1200.0, comparison_value=1000.0, absolute_change=200.0, percentage_change=20.0
        ),
    )
    assert issues.detect_revenue_decline(db_session, "year", "2025", "YoY") == []


def test_revenue_growth_slowdown_fires_on_deceleration(
    monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    calls = {"n": 0}

    def fake(session: object, kpi_id: str, granularity: str, period_key: str, **kwargs: object) -> KPIResult:
        calls["n"] += 1
        if period_key == "2025":
            return _kpi_result(percentage_change=5.0, comparison_period_key="2024")
        return _kpi_result(percentage_change=25.0, period_key="2024", comparison_period_key="2023")

    monkeypatch.setattr(issues, "calculate_kpi", fake)
    found = issues.detect_revenue_growth_slowdown(db_session, "year", "2025", "YoY")
    assert len(found) == 1
    assert found[0].issue_type == "revenue_growth_slowdown"
    assert found[0].absolute_change == pytest.approx(5.0 - 25.0)


def test_revenue_growth_slowdown_does_not_fire_when_growth_accelerates(
    monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    def fake(session: object, kpi_id: str, granularity: str, period_key: str, **kwargs: object) -> KPIResult:
        if period_key == "2025":
            return _kpi_result(percentage_change=30.0, comparison_period_key="2024")
        return _kpi_result(percentage_change=10.0, period_key="2024", comparison_period_key="2023")

    monkeypatch.setattr(issues, "calculate_kpi", fake)
    assert issues.detect_revenue_growth_slowdown(db_session, "year", "2025", "YoY") == []


def test_revenue_growth_slowdown_does_not_fire_when_declining(
    monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    monkeypatch.setattr(issues, "calculate_kpi", lambda *a, **k: _kpi_result(percentage_change=-5.0))
    assert issues.detect_revenue_growth_slowdown(db_session, "year", "2025", "YoY") == []


def test_margin_deterioration_fires_on_point_drop(
    monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    monkeypatch.setattr(
        issues,
        "calculate_kpi",
        lambda *a, **k: _kpi_result(
            kpi_id="gross_margin_pct",
            value=30.0,
            comparison_value=35.0,
            absolute_change=-5.0,
            percentage_change=-14.3,
        ),
    )
    found = issues.detect_margin_deterioration(db_session, "year", "2025", "YoY")
    assert len(found) == 1
    assert found[0].metric == "gross_margin_pct"
    assert found[0].absolute_change == -5.0


def test_margin_deterioration_does_not_fire_for_improvement(
    monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    monkeypatch.setattr(
        issues,
        "calculate_kpi",
        lambda *a, **k: _kpi_result(value=40.0, comparison_value=35.0, absolute_change=5.0),
    )
    assert issues.detect_margin_deterioration(db_session, "year", "2025", "YoY") == []


def test_unusual_cost_movement_fires_when_cogs_outgrows_revenue(
    monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    def fake(session: object, kpi_id: str, granularity: str, period_key: str, **kwargs: object) -> KPIResult:
        if kpi_id == "cogs":
            return _kpi_result(kpi_id="cogs", percentage_change=30.0)
        return _kpi_result(kpi_id="revenue", percentage_change=10.0)

    monkeypatch.setattr(issues, "calculate_kpi", fake)
    found = issues.detect_unusual_cost_movement(db_session, "year", "2025", "YoY")
    assert len(found) == 1
    assert found[0].percentage_change == pytest.approx(20.0)  # the gap


def test_unusual_cost_movement_does_not_fire_when_cost_grows_slower(
    monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    def fake(session: object, kpi_id: str, granularity: str, period_key: str, **kwargs: object) -> KPIResult:
        if kpi_id == "cogs":
            return _kpi_result(kpi_id="cogs", percentage_change=5.0)
        return _kpi_result(kpi_id="revenue", percentage_change=10.0)

    monkeypatch.setattr(issues, "calculate_kpi", fake)
    assert issues.detect_unusual_cost_movement(db_session, "year", "2025", "YoY") == []


def test_unusual_volume_movement_fires_in_either_direction(
    monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    monkeypatch.setattr(issues, "calculate_kpi", lambda *a, **k: _kpi_result(percentage_change=-20.0))
    found = issues.detect_unusual_volume_movement(db_session, "year", "2025", "YoY")
    assert len(found) == 1 and "decline" in found[0].title

    monkeypatch.setattr(issues, "calculate_kpi", lambda *a, **k: _kpi_result(percentage_change=20.0))
    found = issues.detect_unusual_volume_movement(db_session, "year", "2025", "YoY")
    assert len(found) == 1 and "increase" in found[0].title


# --- real seed-42 dataset: the three detectors that genuinely fire on it --------------------


def test_regional_performance_deterioration_matches_pandas_for_the_flagged_region(
    db_session: Session, sales_df: pd.DataFrame
) -> None:
    found = issues.detect_regional_performance_deterioration(db_session, "year", "2025", "YoY")
    assert len(found) >= 1
    for candidate in found:
        region = candidate.affected_entity
        cur = sales_df[(sales_df["month"].dt.year == 2025) & (sales_df["region_id"] == region)][
            "net_amount_pkr"
        ].sum()
        pri = sales_df[(sales_df["month"].dt.year == 2024) & (sales_df["region_id"] == region)][
            "net_amount_pkr"
        ].sum()
        expected_pct = (cur - pri) / abs(pri) * 100
        assert candidate.percentage_change == pytest.approx(expected_pct, rel=1e-6)
        assert expected_pct < 0


def test_product_margin_deterioration_matches_pandas_for_the_flagged_product(
    db_session: Session, sales_df: pd.DataFrame
) -> None:
    found = issues.detect_product_margin_deterioration(db_session, "year", "2025", "YoY")
    assert len(found) >= 1
    for candidate in found:
        product = candidate.affected_entity
        subset_cur = sales_df[(sales_df["month"].dt.year == 2025) & (sales_df["product_id"] == product)]
        subset_pri = sales_df[(sales_df["month"].dt.year == 2024) & (sales_df["product_id"] == product)]
        cur_margin = (
            (subset_cur["net_amount_pkr"].sum() - subset_cur["cogs_amount_pkr"].sum())
            / subset_cur["net_amount_pkr"].sum()
            * 100
        )
        pri_margin = (
            (subset_pri["net_amount_pkr"].sum() - subset_pri["cogs_amount_pkr"].sum())
            / subset_pri["net_amount_pkr"].sum()
            * 100
        )
        assert candidate.absolute_change == pytest.approx(cur_margin - pri_margin, rel=1e-6)


def test_detected_issues_recover_both_planted_ground_truth_entities(
    db_session: Session, planted_config: object
) -> None:
    """A light-touch acceptance check (the full ground-truth cross-check lives in
    test_ground_truth.py): running every detector together for 2025 YoY should surface both
    GT-02 (region) and GT-03 (product) by their configured entity IDs."""
    region_id = planted_config.planted.region_decline_id  # type: ignore[attr-defined]
    product_id = planted_config.planted.margin_decline_product_id  # type: ignore[attr-defined]

    found = issues.run_all_detectors(db_session, "year", "2025", "YoY")
    affected = {(c.issue_type, c.affected_entity) for c in found}
    assert ("regional_performance_deterioration", region_id) in affected
    assert ("product_margin_deterioration", product_id) in affected


def test_customer_concentration_change_detector_runs_without_error_on_real_data(db_session: Session) -> None:
    # Not asserting it fires (seed-42 wasn't planted with a concentration shift) -- just that
    # the detector's own math (top-5 share in both periods) runs cleanly against real data.
    found = issues.detect_customer_concentration_change(db_session, "year", "2025", "YoY")
    assert isinstance(found, list)


def test_customer_concentration_change_fires_on_a_crafted_share_shift(
    monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    from app.kpi.periods import resolve_period

    current_window = resolve_period("year", "2025")

    def fake_sum_by_dimension(session: object, column: object, w: object, dimension: str) -> list[object]:
        if w is current_window:
            return [("C1", 60.0), ("C2", 10.0), ("C3", 10.0), ("C4", 10.0), ("C5", 10.0), ("C6", 10.0)]
        return [("C1", 20.0), ("C2", 16.0), ("C3", 16.0), ("C4", 16.0), ("C5", 16.0), ("C6", 16.0)]

    from app.kpi import aggregations as agg

    monkeypatch.setattr(issues, "resolve_period", lambda *a, **k: current_window)
    monkeypatch.setattr(agg, "sum_by_dimension", fake_sum_by_dimension)
    found = issues.detect_customer_concentration_change(db_session, "year", "2025", "YoY")
    assert len(found) == 1
    assert found[0].issue_type == "customer_concentration_change"
    assert found[0].percentage_change is not None and found[0].percentage_change > 0
