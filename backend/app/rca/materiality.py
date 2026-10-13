"""Deterministic, configuration-driven materiality rules (Phase 4 spec, section 2).

Every threshold below is a plain constant, not an LLM judgment call: `evaluate_materiality()`
is pure arithmetic against the numbers the caller hands it. A finding is material only if it
clears *every* threshold configured for its issue type (AND, not OR) -- e.g. a region with a
huge percentage decline but a negligible revenue share should not be flagged as a company-level
issue, and a region with a large absolute PKR drop but too few transactions to trust shouldn't
either. Thresholds live here, in one place, specifically so they can be tuned without touching
detection logic in `issues.py`.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.fx.convert import convert_amount


@dataclass(frozen=True)
class MaterialityThresholds:
    """Each field is `None` when that rule doesn't apply to a given issue type (e.g. a
    company-level issue has no "dimension share" to check)."""

    min_percentage_change_pct: float | None = None
    """Minimum |percentage_change| (in percentage points) to even consider flagging."""

    min_absolute_impact_pkr: float | None = None
    """Minimum |absolute_change| in PKR -- screens out a huge % change on a tiny base."""

    min_dimension_share_pct: float | None = None
    """For a per-entity (region/product/customer) finding: that entity's share of the
    *prior* period's company-wide total must be at least this, so a 90%-decline in a region
    that was 0.1% of revenue doesn't get flagged as a material company-level issue."""

    min_sample_size: int | None = None
    """Minimum row (transaction) count backing the finding, in the period being flagged."""

    min_contribution_share_pct: float | None = None
    """For concentration-style issues: minimum magnitude of the concentration metric's own
    change (e.g. top-5-customer revenue share moving by at least this many points)."""


# One entry per issue type in app.db.models.analysis.ISSUE_TYPES that has a detector in
# issues.py. Numbers are deliberately conservative defaults for a company this size (PakManufacture,
# ~PKR 900M/yr revenue, 300 customers, seed-42 dataset) -- tune per-deployment, not per-request.
MATERIALITY_CONFIG: dict[str, MaterialityThresholds] = {
    "revenue_decline": MaterialityThresholds(
        min_percentage_change_pct=10.0,
        min_absolute_impact_pkr=5_000_000.0,
    ),
    "revenue_growth_slowdown": MaterialityThresholds(
        # Threshold is on the *deceleration* (growth_pct_this_period - growth_pct_prior_period),
        # not on revenue's own change -- see issues.py::detect_revenue_growth_slowdown.
        min_percentage_change_pct=10.0,
    ),
    "margin_deterioration": MaterialityThresholds(
        min_percentage_change_pct=2.0,  # percentage-point drop in gross margin %
    ),
    "regional_performance_deterioration": MaterialityThresholds(
        min_percentage_change_pct=15.0,
        min_dimension_share_pct=2.0,
        min_sample_size=30,
    ),
    "product_margin_deterioration": MaterialityThresholds(
        min_percentage_change_pct=3.0,  # percentage-point drop in that product's margin %
        min_dimension_share_pct=1.0,
        min_sample_size=30,
    ),
    "unusual_cost_movement": MaterialityThresholds(
        # Threshold is on the *gap* between COGS growth % and revenue growth % -- see
        # issues.py::detect_unusual_cost_movement.
        min_percentage_change_pct=8.0,
    ),
    "unusual_volume_movement": MaterialityThresholds(
        min_percentage_change_pct=15.0,
    ),
    "customer_concentration_change": MaterialityThresholds(
        min_contribution_share_pct=5.0,  # points of top-5-customer revenue share
    ),
}

SEVERITY_BANDS = ("low", "medium", "high", "critical")


def get_thresholds(issue_type: str) -> MaterialityThresholds:
    thresholds = MATERIALITY_CONFIG.get(issue_type)
    if thresholds is None:
        raise ValueError(f"No materiality configuration for issue type '{issue_type}'.")
    return thresholds


@dataclass(frozen=True)
class MaterialityCheck:
    is_material: bool
    rules: dict[str, dict[str, float]]
    """Every rule that was *evaluated* (not just the ones that passed), each as
    {"threshold": ..., "actual": ...} -- persisted verbatim onto `Issue.materiality` so the
    full reasoning is visible, not just the pass/fail outcome."""


def evaluate_materiality(
    issue_type: str,
    *,
    percentage_change_pct: float | None = None,
    absolute_impact: float | None = None,
    currency: str | None = None,
    dimension_share_pct: float | None = None,
    sample_size: int | None = None,
    contribution_share_pct: float | None = None,
) -> MaterialityCheck:
    """A rule only fires if both its threshold is configured *and* the caller supplied the
    corresponding actual value; a configured-but-unsupplied rule is skipped, never silently
    passed. This keeps the function usable for every issue type without issue-type-specific
    branching here -- `issues.py` decides which actuals are meaningful for each type.

    `absolute_impact` is whatever currency the caller's own figures are actually in (a
    client's own resolved reporting currency, Phase 9) -- never assumed to be PKR just
    because `min_absolute_impact_pkr` is. `currency` says what that is, so the PKR-
    denominated threshold can be converted into the same units before comparing; omitting
    it (or passing "PKR") leaves the threshold as-is, a no-op conversion."""
    thresholds = get_thresholds(issue_type)
    rules: dict[str, dict[str, float]] = {}
    passed = True

    def _check(name: str, threshold: float | None, actual: float | None) -> None:
        nonlocal passed
        if threshold is None or actual is None:
            return
        rules[name] = {"threshold": threshold, "actual": actual}
        if actual < threshold:
            passed = False

    _check(
        "min_percentage_change_pct",
        thresholds.min_percentage_change_pct,
        None if percentage_change_pct is None else abs(percentage_change_pct),
    )
    threshold_in_currency = (
        None
        if thresholds.min_absolute_impact_pkr is None
        else convert_amount(
            thresholds.min_absolute_impact_pkr, from_currency="PKR", to_currency=currency or "PKR"
        )
    )
    _check(
        "min_absolute_impact_pkr",
        threshold_in_currency,
        None if absolute_impact is None else abs(absolute_impact),
    )
    _check("min_dimension_share_pct", thresholds.min_dimension_share_pct, dimension_share_pct)
    _check(
        "min_sample_size",
        None if thresholds.min_sample_size is None else float(thresholds.min_sample_size),
        None if sample_size is None else float(sample_size),
    )
    _check(
        "min_contribution_share_pct",
        thresholds.min_contribution_share_pct,
        None if contribution_share_pct is None else abs(contribution_share_pct),
    )

    return MaterialityCheck(is_material=passed and bool(rules), rules=rules)


def classify_severity(issue_type: str, *, percentage_change_pct: float | None) -> str:
    """Severity escalates in multiples of the issue type's own primary threshold, so a
    borderline-material finding is "low" and a multiple-of-threshold finding is "critical" --
    deterministic, and consistent across issue types without a second magic-number table."""
    thresholds = get_thresholds(issue_type)
    threshold = thresholds.min_percentage_change_pct
    if threshold is None or threshold <= 0 or percentage_change_pct is None:
        return "medium"
    ratio = abs(percentage_change_pct) / threshold
    if ratio >= 4.0:
        return "critical"
    if ratio >= 2.5:
        return "high"
    if ratio >= 1.5:
        return "medium"
    return "low"
