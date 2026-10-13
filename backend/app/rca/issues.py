"""Deterministic issue detection (Phase 4 spec, section 1).

Every detector below is a plain function: resolve a period + comparison window, read the
already-tested Phase 3 KPI engine (company-level metrics) or `app/kpi/aggregations.py`
(per-dimension sums) for the numbers, run them through `app/rca/materiality.py`, and return
zero or more `IssueCandidate`s. Nothing here decides materiality by asking the LLM (spec
section 2) -- `evaluate_materiality()` is pure arithmetic.

Two issue types from the spec's initial list -- material inventory issues, overtime issues --
have **no detector function in this module**, on purpose: their canonical tables
(`fact_inventory`, `fact_workforce`) don't exist (Phase 2 materializes `fact_sales` only), and
the spec is explicit that issues must not be manufactured for unavailable data (section 1) --
unlike a KPI, which can return a `cannot_compute` *status* for a specific request, there is no
analogous "issue" to return here: `run_all_detectors()` simply never calls a detector for them.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.db.models.canonical import FactSales
from app.kpi import aggregations as agg
from app.kpi.engine import KPIResult, calculate_kpi
from app.kpi.models import KPIStatus
from app.kpi.periods import PeriodWindow, resolve_comparison_period, resolve_period
from app.rca.materiality import classify_severity, evaluate_materiality

TOP_N_FOR_CONCENTRATION = 5


@dataclass(frozen=True)
class IssueCandidate:
    issue_type: str
    title: str
    severity: str
    granularity: str
    period_key: str
    comparison_period_key: str | None
    metric: str
    current_value: float | None
    prior_value: float | None
    absolute_change: float | None
    percentage_change: float | None
    affected_dimension: str | None
    affected_entity: str | None
    materiality: dict[str, dict[str, float]]
    source_file_ids: tuple[str, ...] = field(default_factory=tuple)


def _kpi_change(
    session: Session,
    kpi_id: str,
    granularity: str,
    period_key: str,
    comparison_type: str,
    client_id: str | None = None,
) -> KPIResult | None:
    """`None` when either side of the comparison isn't `available` -- callers must treat a
    `None` result as "cannot evaluate this detector", never substitute a fabricated number."""
    result = calculate_kpi(
        session,
        kpi_id,
        granularity,
        period_key,
        comparison_type=comparison_type,
        persist=False,
        client_id=client_id,
    )
    if result.status is not KPIStatus.AVAILABLE or result.percentage_change_status != "ok":
        return None
    return result


def detect_revenue_decline(
    session: Session,
    granularity: str,
    period_key: str,
    comparison_type: str,
    client_id: str | None = None,
) -> list[IssueCandidate]:
    result = _kpi_change(session, "revenue", granularity, period_key, comparison_type, client_id)
    if result is None or result.percentage_change is None or result.percentage_change >= 0:
        return []
    check = evaluate_materiality(
        "revenue_decline",
        percentage_change_pct=result.percentage_change,
        absolute_impact_pkr=result.absolute_change,
    )
    if not check.is_material:
        return []
    severity = classify_severity("revenue_decline", percentage_change_pct=result.percentage_change)
    return [
        IssueCandidate(
            issue_type="revenue_decline",
            title=f"Revenue decline: {result.percentage_change:.1f}% {comparison_type} in {period_key}",
            severity=severity,
            granularity=granularity,
            period_key=period_key,
            comparison_period_key=result.comparison_period_key,
            metric="revenue",
            current_value=result.value,
            prior_value=result.comparison_value,
            absolute_change=result.absolute_change,
            percentage_change=result.percentage_change,
            affected_dimension=None,
            affected_entity=None,
            materiality=check.rules,
            source_file_ids=result.source_file_ids,
        )
    ]


def detect_revenue_growth_slowdown(
    session: Session,
    granularity: str,
    period_key: str,
    comparison_type: str,
    client_id: str | None = None,
) -> list[IssueCandidate]:
    current = _kpi_change(session, "revenue", granularity, period_key, comparison_type, client_id)
    if current is None or current.percentage_change is None or current.percentage_change <= 0:
        return []  # not growing this period -- that's revenue_decline's territory, not a slowdown
    assert current.comparison_period_key is not None
    prior = _kpi_change(
        session, "revenue", granularity, current.comparison_period_key, comparison_type, client_id
    )
    if prior is None or prior.percentage_change is None:
        return []
    deceleration = current.percentage_change - prior.percentage_change
    if deceleration >= 0:
        return []  # growth rate held or improved -- not a slowdown
    check = evaluate_materiality("revenue_growth_slowdown", percentage_change_pct=deceleration)
    if not check.is_material:
        return []
    severity = classify_severity("revenue_growth_slowdown", percentage_change_pct=deceleration)
    return [
        IssueCandidate(
            issue_type="revenue_growth_slowdown",
            title=(
                f"Revenue growth slowdown: {current.percentage_change:.1f}% {comparison_type} growth "
                f"in {period_key}, down from {prior.percentage_change:.1f}% the prior comparable period"
            ),
            severity=severity,
            granularity=granularity,
            period_key=period_key,
            comparison_period_key=current.comparison_period_key,
            metric="revenue",
            current_value=current.percentage_change,
            prior_value=prior.percentage_change,
            absolute_change=deceleration,
            percentage_change=deceleration,
            affected_dimension=None,
            affected_entity=None,
            materiality=check.rules,
            source_file_ids=current.source_file_ids,
        )
    ]


def detect_margin_deterioration(
    session: Session,
    granularity: str,
    period_key: str,
    comparison_type: str,
    client_id: str | None = None,
) -> list[IssueCandidate]:
    result = _kpi_change(session, "gross_margin_pct", granularity, period_key, comparison_type, client_id)
    # `absolute_change` here is a percentage-POINT change in a percentage metric -- the
    # business-meaningful threshold for margin deterioration (see materiality.py's comment),
    # not the KPI engine's relative `percentage_change` of that percentage.
    if result is None or result.absolute_change is None or result.absolute_change >= 0:
        return []
    check = evaluate_materiality("margin_deterioration", percentage_change_pct=result.absolute_change)
    if not check.is_material:
        return []
    severity = classify_severity("margin_deterioration", percentage_change_pct=result.absolute_change)
    return [
        IssueCandidate(
            issue_type="margin_deterioration",
            title=(
                f"Gross margin deterioration: {result.absolute_change:+.1f} points {comparison_type} "
                f"in {period_key}"
            ),
            severity=severity,
            granularity=granularity,
            period_key=period_key,
            comparison_period_key=result.comparison_period_key,
            metric="gross_margin_pct",
            current_value=result.value,
            prior_value=result.comparison_value,
            absolute_change=result.absolute_change,
            percentage_change=result.percentage_change,
            affected_dimension=None,
            affected_entity=None,
            materiality=check.rules,
            source_file_ids=result.source_file_ids,
        )
    ]


def detect_unusual_cost_movement(
    session: Session,
    granularity: str,
    period_key: str,
    comparison_type: str,
    client_id: str | None = None,
) -> list[IssueCandidate]:
    cogs = _kpi_change(session, "cogs", granularity, period_key, comparison_type, client_id)
    revenue = _kpi_change(session, "revenue", granularity, period_key, comparison_type, client_id)
    if cogs is None or revenue is None or cogs.percentage_change is None or revenue.percentage_change is None:
        return []
    gap = cogs.percentage_change - revenue.percentage_change
    if gap <= 0:
        return []  # cost is not growing faster than revenue -- not "unusual" in the cost direction
    check = evaluate_materiality("unusual_cost_movement", percentage_change_pct=gap)
    if not check.is_material:
        return []
    severity = classify_severity("unusual_cost_movement", percentage_change_pct=gap)
    return [
        IssueCandidate(
            issue_type="unusual_cost_movement",
            title=(
                f"Cost of goods sold grew {cogs.percentage_change:.1f}% {comparison_type} vs "
                f"revenue's {revenue.percentage_change:.1f}% in {period_key}"
            ),
            severity=severity,
            granularity=granularity,
            period_key=period_key,
            comparison_period_key=cogs.comparison_period_key,
            metric="cogs",
            current_value=cogs.value,
            prior_value=cogs.comparison_value,
            absolute_change=cogs.absolute_change,
            percentage_change=gap,
            affected_dimension=None,
            affected_entity=None,
            materiality=check.rules,
            source_file_ids=cogs.source_file_ids,
        )
    ]


def detect_unusual_volume_movement(
    session: Session,
    granularity: str,
    period_key: str,
    comparison_type: str,
    client_id: str | None = None,
) -> list[IssueCandidate]:
    result = _kpi_change(session, "sales_quantity", granularity, period_key, comparison_type, client_id)
    if result is None or result.percentage_change is None:
        return []
    check = evaluate_materiality("unusual_volume_movement", percentage_change_pct=result.percentage_change)
    if not check.is_material:
        return []
    severity = classify_severity("unusual_volume_movement", percentage_change_pct=result.percentage_change)
    direction = "increase" if result.percentage_change > 0 else "decline"
    return [
        IssueCandidate(
            issue_type="unusual_volume_movement",
            title=(
                f"Unusual sales volume {direction}: {result.percentage_change:+.1f}% {comparison_type} "
                f"in {period_key}"
            ),
            severity=severity,
            granularity=granularity,
            period_key=period_key,
            comparison_period_key=result.comparison_period_key,
            metric="sales_quantity",
            current_value=result.value,
            prior_value=result.comparison_value,
            absolute_change=result.absolute_change,
            percentage_change=result.percentage_change,
            affected_dimension=None,
            affected_entity=None,
            materiality=check.rules,
            source_file_ids=result.source_file_ids,
        )
    ]


def _dimension_windows(
    session: Session,
    granularity: str,
    period_key: str,
    comparison_type: str,
    client_id: str | None = None,
) -> tuple[PeriodWindow, PeriodWindow] | None:
    window = resolve_period(granularity, period_key, client_id=client_id)
    comparison_window = resolve_comparison_period(window, comparison_type)
    return window, comparison_window


def detect_regional_performance_deterioration(
    session: Session,
    granularity: str,
    period_key: str,
    comparison_type: str,
    client_id: str | None = None,
) -> list[IssueCandidate]:
    return _dimension_deterioration(
        session,
        granularity,
        period_key,
        comparison_type,
        dimension="region",
        issue_type="regional_performance_deterioration",
        metric="revenue",
        client_id=client_id,
    )


def detect_product_margin_deterioration(
    session: Session,
    granularity: str,
    period_key: str,
    comparison_type: str,
    client_id: str | None = None,
) -> list[IssueCandidate]:
    windows = _dimension_windows(session, granularity, period_key, comparison_type, client_id)
    if windows is None:
        return []
    window, comparison_window = windows

    current_rev = dict(agg.sum_by_dimension(session, FactSales.net_amount_reporting, window, "product"))
    prior_rev = dict(agg.sum_by_dimension(session, FactSales.net_amount_reporting, comparison_window, "product"))
    current_cogs = dict(agg.sum_by_dimension(session, FactSales.cogs_amount_reporting, window, "product"))
    prior_cogs = dict(agg.sum_by_dimension(session, FactSales.cogs_amount_reporting, comparison_window, "product"))
    counts = agg.count_by_dimension(session, window, "product")
    company_revenue = sum(current_rev.values()) or None

    candidates: list[IssueCandidate] = []
    for product_id in set(current_rev) & set(prior_rev):
        cur_r, pri_r = current_rev[product_id], prior_rev[product_id]
        cur_c, pri_c = current_cogs.get(product_id, 0.0), prior_cogs.get(product_id, 0.0)
        if cur_r == 0 or pri_r == 0:
            continue  # margin % undefined for a zero-revenue period, not a fabricated 0
        current_margin = (cur_r - cur_c) / cur_r * 100
        prior_margin = (pri_r - pri_c) / pri_r * 100
        point_change = current_margin - prior_margin
        if point_change >= 0:
            continue
        share = (cur_r / company_revenue * 100) if company_revenue else None
        check = evaluate_materiality(
            "product_margin_deterioration",
            percentage_change_pct=point_change,
            dimension_share_pct=share,
            sample_size=counts.get(product_id, 0),
        )
        if not check.is_material:
            continue
        severity = classify_severity("product_margin_deterioration", percentage_change_pct=point_change)
        candidates.append(
            IssueCandidate(
                issue_type="product_margin_deterioration",
                title=(
                    f"Product {product_id} margin deterioration: {point_change:+.1f} points "
                    f"{comparison_type} in {period_key}"
                ),
                severity=severity,
                granularity=granularity,
                period_key=period_key,
                comparison_period_key=comparison_window.period_key,
                metric="gross_margin_pct",
                current_value=current_margin,
                prior_value=prior_margin,
                absolute_change=point_change,
                percentage_change=point_change,
                affected_dimension="product",
                affected_entity=str(product_id),
                materiality=check.rules,
            )
        )
    return candidates


def _dimension_deterioration(
    session: Session,
    granularity: str,
    period_key: str,
    comparison_type: str,
    *,
    dimension: str,
    issue_type: str,
    metric: str,
    client_id: str | None = None,
) -> list[IssueCandidate]:
    windows = _dimension_windows(session, granularity, period_key, comparison_type, client_id)
    if windows is None:
        return []
    window, comparison_window = windows

    column = FactSales.net_amount_reporting
    current = dict(agg.sum_by_dimension(session, column, window, dimension))
    prior = dict(agg.sum_by_dimension(session, column, comparison_window, dimension))
    counts = agg.count_by_dimension(session, window, dimension)
    company_total = sum(current.values()) or None

    candidates: list[IssueCandidate] = []
    for entity in set(current) & set(prior):
        cur, pri = current[entity], prior[entity]
        if pri == 0:
            continue
        pct_change = (cur - pri) / abs(pri) * 100
        if pct_change >= 0:
            continue
        share = (cur / company_total * 100) if company_total else None
        check = evaluate_materiality(
            issue_type,
            percentage_change_pct=pct_change,
            absolute_impact_pkr=cur - pri,
            dimension_share_pct=share,
            sample_size=counts.get(entity, 0),
        )
        if not check.is_material:
            continue
        severity = classify_severity(issue_type, percentage_change_pct=pct_change)
        candidates.append(
            IssueCandidate(
                issue_type=issue_type,
                title=(
                    f"{dimension.capitalize()} {entity} {metric} decline: {pct_change:.1f}% "
                    f"{comparison_type} in {period_key}"
                ),
                severity=severity,
                granularity=granularity,
                period_key=period_key,
                comparison_period_key=comparison_window.period_key,
                metric=metric,
                current_value=cur,
                prior_value=pri,
                absolute_change=cur - pri,
                percentage_change=pct_change,
                affected_dimension=dimension,
                affected_entity=str(entity),
                materiality=check.rules,
            )
        )
    return candidates


def detect_customer_concentration_change(
    session: Session,
    granularity: str,
    period_key: str,
    comparison_type: str,
    client_id: str | None = None,
) -> list[IssueCandidate]:
    windows = _dimension_windows(session, granularity, period_key, comparison_type, client_id)
    if windows is None:
        return []
    window, comparison_window = windows

    current = agg.sum_by_dimension(session, FactSales.net_amount_reporting, window, "customer")
    prior = agg.sum_by_dimension(session, FactSales.net_amount_reporting, comparison_window, "customer")
    current_total = sum(v for _, v in current)
    prior_total = sum(v for _, v in prior)
    if current_total == 0 or prior_total == 0:
        return []

    current_top_share = sum(v for _, v in current[:TOP_N_FOR_CONCENTRATION]) / current_total * 100
    prior_top_share = sum(v for _, v in prior[:TOP_N_FOR_CONCENTRATION]) / prior_total * 100
    share_change = current_top_share - prior_top_share

    check = evaluate_materiality("customer_concentration_change", contribution_share_pct=share_change)
    if not check.is_material:
        return []
    severity = classify_severity("customer_concentration_change", percentage_change_pct=share_change)
    direction = "increased" if share_change > 0 else "decreased"
    return [
        IssueCandidate(
            issue_type="customer_concentration_change",
            title=(
                f"Top-{TOP_N_FOR_CONCENTRATION}-customer revenue concentration {direction} "
                f"{share_change:+.1f} points {comparison_type} in {period_key}"
            ),
            severity=severity,
            granularity=granularity,
            period_key=period_key,
            comparison_period_key=comparison_window.period_key,
            metric="revenue_customer_concentration",
            current_value=current_top_share,
            prior_value=prior_top_share,
            absolute_change=share_change,
            percentage_change=share_change,
            affected_dimension="customer",
            affected_entity=None,
            materiality=check.rules,
        )
    ]


# Registered detectors -- material_inventory_issue / overtime_issue deliberately absent
# (see module docstring).
DETECTORS = (
    detect_revenue_decline,
    detect_revenue_growth_slowdown,
    detect_margin_deterioration,
    detect_regional_performance_deterioration,
    detect_product_margin_deterioration,
    detect_unusual_cost_movement,
    detect_unusual_volume_movement,
    detect_customer_concentration_change,
)


def run_all_detectors(
    session: Session,
    granularity: str,
    period_key: str,
    comparison_type: str,
    client_id: str | None = None,
) -> list[IssueCandidate]:
    candidates: list[IssueCandidate] = []
    for detector in DETECTORS:
        candidates.extend(detector(session, granularity, period_key, comparison_type, client_id))
    return candidates


__all__ = ["DETECTORS", "IssueCandidate", "run_all_detectors"]
