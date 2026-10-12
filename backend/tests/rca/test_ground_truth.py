"""Seed-42 acceptance tests (Phase 4 spec, section 15): confirm the deterministic issue
detection + RCA engine independently recovers GT-02 (Karachi-area region decline, entity
REG-05) and GT-03 (product margin deterioration, entity PROD-12) from canonical data alone.

Uses `generator.measure` (the hidden ground-truth measurement module) ONLY here, in a test,
exactly like Phase 3's `tests/kpi/test_ground_truth.py` -- never as engine runtime input. See
`tests/synthetic/test_isolation.py`'s static source-grep, which scans `app/` only, never
`tests/`, and which would fail this whole suite if that import ever leaked into production code.

**Deviation from the spec's literal text, by design (standing instruction: use independent
judgment where the spec is factually wrong for *this* seed-42 dataset):** the spec's section 4
says "GT-02: Karachi / R02" and section 15 says "GT-03: P14 margin deterioration". The actual
`_hidden/ground_truth.yaml` for seed 42 names GT-02's entity as region **REG-05** (not R02) and
GT-03's entity as product **PROD-12** (not P14) -- confirmed via `planted_config.planted.
region_decline_id` / `.margin_decline_product_id`, the same generator config object Phase 3's
ground-truth test already relies on. These tests assert against the actual configured IDs,
not the spec's (apparently mistaken, possibly carried over from a different seed or an earlier
draft) literal strings -- asserting against "R02"/"P14" would simply never pass against the
real seed-42 data, defeating the point of a ground-truth acceptance test.
"""

from __future__ import annotations

from typing import Any, cast

import pandas as pd
import pytest
from app.rca import engine, issues
from generator.config import GeneratorConfig
from generator.measure import measure_margin_decline, measure_region_decline
from sqlalchemy.orm import Session

pytestmark = pytest.mark.usefixtures("seeded_fact_sales_file_id")

GRANULARITY = "year"
PERIOD_KEY = "2025"
COMPARISON_TYPE = "YoY"


def test_gt02_region_decline_is_detected_from_canonical_data_alone(
    db_session: Session, sales_df: pd.DataFrame, planted_config: GeneratorConfig
) -> None:
    region_id = planted_config.planted.region_decline_id
    string_month_df = sales_df.assign(month=sales_df["month"].dt.strftime("%Y-%m-%d"))
    expected_ratio = measure_region_decline(string_month_df, region_id=region_id)
    assert expected_ratio < 0, "sanity check: the planted region is supposed to be declining"

    found = issues.detect_regional_performance_deterioration(
        db_session, GRANULARITY, PERIOD_KEY, COMPARISON_TYPE
    )
    matching = [c for c in found if c.affected_entity == region_id]
    assert len(matching) == 1, f"expected REG-05-equivalent ({region_id}) in {found}"
    assert matching[0].percentage_change is not None and matching[0].percentage_change < 0


def test_gt02_region_decline_has_a_traceable_driver_analysis(
    db_session: Session, planted_config: GeneratorConfig
) -> None:
    region_id = planted_config.planted.region_decline_id
    run = engine.detect_issues(db_session, GRANULARITY, PERIOD_KEY, comparison_type=COMPARISON_TYPE)
    from app.db.models.analysis import Issue
    from sqlalchemy import select

    issue = db_session.execute(
        select(Issue).where(Issue.detection_run_id == run.id, Issue.affected_entity == region_id)
    ).scalar_one()

    analyzed = engine.analyze_issue(db_session, issue.id)
    assert analyzed.decomposition is not None
    decomposition = cast(dict[str, Any], analyzed.decomposition)

    # Spec section 4: region's revenue change, volume change, ASP change, customer
    # contribution, product contribution, relevant time periods -- all present.
    assert "by_product_within_region" in decomposition
    assert "by_customer_within_region" in decomposition
    vp = decomposition["volume_price_effect_within_region"]
    assert vp["volume_effect"] + vp["price_effect"] == pytest.approx(vp["total_change"], rel=1e-6)

    # The claim text must describe an association, never a causal claim (spec section 9).
    import uuid as _uuid

    from app.db.models.analysis import Evidence

    evidence_id = decomposition["by_product_within_region"]["rows"][0]["evidence_id"]
    ev = db_session.get(Evidence, _uuid.UUID(evidence_id))
    assert ev is not None
    lowered = ev.claim.lower()
    for forbidden in ("caused", "root cause", "because of"):
        assert forbidden not in lowered


def test_gt03_product_margin_deterioration_is_detected_from_canonical_data_alone(
    db_session: Session, sales_df: pd.DataFrame, planted_config: GeneratorConfig
) -> None:
    product_id = planted_config.planted.margin_decline_product_id
    # `measure_margin_decline` (generator-side) compares `month` against plain ISO date
    # *strings*; our `sales_df` fixture parses `month` as a real date for the rest of this
    # suite's `.dt.year` filtering, so it needs converting back to strings for this one
    # cross-check -- identical issue to Phase 3's GT-02 test (tests/kpi/test_ground_truth.py).
    string_month_df = sales_df.assign(month=sales_df["month"].dt.strftime("%Y-%m-%d"))
    # `gross_margin_pct` (the canonical column `measure_margin_decline` reads) is stored as a
    # 0-1 *fraction*; the engine's own margin KPI is a 0-100 *percentage* (see
    # app/kpi/calculators.py::calculate_gross_margin_pct) -- x100 puts both on the same scale.
    expected_point_drop = measure_margin_decline(string_month_df, product_id=product_id) * 100
    assert expected_point_drop > 0, "sanity check: the planted product's margin is supposed to deteriorate"

    found = issues.detect_product_margin_deterioration(db_session, GRANULARITY, PERIOD_KEY, COMPARISON_TYPE)
    matching = [c for c in found if c.affected_entity == product_id]
    assert len(matching) == 1, f"expected PROD-12-equivalent ({product_id}) in {found}"
    assert matching[0].absolute_change is not None and matching[0].absolute_change < 0

    # Not an exact-equality cross-check, and not expected to be close in *magnitude*:
    # `measure_margin_decline` measures the full 3-year planted deterioration (2023-Q1 vs
    # 2025-Q4 mean per-row margin), while the engine's `detect_product_margin_deterioration`
    # reports one YoY *slice* of it (2024 vs 2025) -- there is no 2022 data to make 2023's own
    # YoY contribution measurable at all, so the single-year figure is necessarily smaller
    # than the full multi-year figure. Only direction is asserted here; magnitude plausibility
    # (the YoY slice is a fraction of the 3-year total, not wildly larger or oppositely signed)
    # is covered by the loose bound below.
    engine_point_drop = -matching[0].absolute_change
    assert engine_point_drop > 0
    assert 0 < engine_point_drop < expected_point_drop


def test_gt03_product_margin_has_a_traceable_driver_analysis(
    db_session: Session, planted_config: GeneratorConfig
) -> None:
    product_id = planted_config.planted.margin_decline_product_id
    run = engine.detect_issues(db_session, GRANULARITY, PERIOD_KEY, comparison_type=COMPARISON_TYPE)
    from app.db.models.analysis import Issue
    from sqlalchemy import select

    issue = db_session.execute(
        select(Issue).where(Issue.detection_run_id == run.id, Issue.affected_entity == product_id)
    ).scalar_one()

    analyzed = engine.analyze_issue(db_session, issue.id)
    assert analyzed.decomposition is not None
    decomposition = cast(dict[str, Any], analyzed.decomposition)

    # Spec section 5: product, prior margin, current margin, revenue, quantity, ASP, COGS,
    # gross profit, contribution to overall margin/profit change -- all present.
    for key in ("revenue", "cogs", "sales_quantity", "average_selling_price", "gross_profit"):
        assert key in decomposition
        assert decomposition[key]["current"] is not None
        assert decomposition[key]["prior"] is not None
    assert issue.current_value is not None and issue.prior_value is not None
    assert decomposition["current_margin_pct"] == pytest.approx(float(issue.current_value), rel=1e-6)
    assert decomposition["prior_margin_pct"] == pytest.approx(float(issue.prior_value), rel=1e-6)
    assert decomposition["contribution_to_company_gross_profit_change_pct"] is not None


def test_gt01_gt04_gt05_are_not_tested_against_raw_synthetic_files() -> None:
    """Explicit acknowledgement of the spec's own instruction (section 15): GT-01
    (procurement), GT-04 (overtime), GT-05 (inventory) require canonical procurement/
    payroll/inventory tables that Phase 2 does not materialize, and must remain untested here
    -- they are correctly `unavailable` because their detectors don't exist (see
    app/rca/issues.py's module docstring), not because of a bug. This test exists only to make
    that omission a documented, deliberate fact rather than a silent gap."""
    from app.db.models.analysis import ISSUE_TYPES

    assert "material_inventory_issue" in ISSUE_TYPES  # reserved vocabulary
    assert "overtime_issue" in ISSUE_TYPES  # reserved vocabulary
    registered = {d.__name__ for d in issues.DETECTORS}
    assert "detect_material_inventory_issue" not in registered
    assert "detect_overtime_issue" not in registered
