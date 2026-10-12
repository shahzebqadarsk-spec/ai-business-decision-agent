"""Pure unit tests for the deterministic materiality config (no DB needed)."""

from __future__ import annotations

from app.rca.materiality import classify_severity, evaluate_materiality, get_thresholds


def test_a_configured_threshold_is_not_cleared_by_a_small_change() -> None:
    check = evaluate_materiality("revenue_decline", percentage_change_pct=-2.0, absolute_impact_pkr=-100.0)
    assert check.is_material is False
    assert "min_percentage_change_pct" in check.rules


def test_every_configured_threshold_must_pass_not_just_one() -> None:
    # Big % decline, but a tiny absolute impact -- both thresholds are configured for
    # revenue_decline, so both must clear.
    check = evaluate_materiality("revenue_decline", percentage_change_pct=-50.0, absolute_impact_pkr=-1.0)
    assert check.is_material is False
    assert check.rules["min_percentage_change_pct"]["actual"] == 50.0
    assert check.rules["min_absolute_impact_pkr"]["actual"] == 1.0


def test_clearing_every_configured_threshold_is_material() -> None:
    check = evaluate_materiality(
        "regional_performance_deterioration",
        percentage_change_pct=-20.0,
        absolute_impact_pkr=-10_000_000.0,
        dimension_share_pct=5.0,
        sample_size=100,
    )
    assert check.is_material is True
    assert set(check.rules) == {"min_percentage_change_pct", "min_dimension_share_pct", "min_sample_size"}


def test_a_rule_with_no_supplied_actual_is_skipped_not_silently_passed() -> None:
    # min_dimension_share_pct is configured for this issue type, but the caller doesn't supply
    # dimension_share_pct -- that rule must not appear in `rules` (it was never evaluated),
    # and must not cause a false "material".
    check = evaluate_materiality("regional_performance_deterioration", percentage_change_pct=-50.0)
    assert "min_dimension_share_pct" not in check.rules


def test_unconfigured_issue_type_raises() -> None:
    import pytest

    with pytest.raises(ValueError):
        get_thresholds("not_a_real_issue_type")


def test_severity_escalates_with_the_ratio_to_threshold() -> None:
    # revenue_decline's own min_percentage_change_pct threshold is 10.0.
    assert classify_severity("revenue_decline", percentage_change_pct=-11.0) == "low"
    assert classify_severity("revenue_decline", percentage_change_pct=-16.0) == "medium"
    assert classify_severity("revenue_decline", percentage_change_pct=-26.0) == "high"
    assert classify_severity("revenue_decline", percentage_change_pct=-41.0) == "critical"


def test_severity_uses_magnitude_not_sign() -> None:
    assert classify_severity("revenue_decline", percentage_change_pct=41.0) == "critical"
