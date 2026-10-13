"""Orchestration: turns `issues.py` detections and `decomposition.py` math into persisted
`AnalysisRun` / `Issue` / `Evidence` rows (Phase 4 spec, sections 1 and 12).

`detect_issues()` is the issue-detection run: resolves a period, runs every registered
detector, and persists one `Issue` plus one FACT `Evidence` row per material finding.

`analyze_issue()` is the RCA run: given an already-detected issue, dispatches to the
decomposition appropriate for its `issue_type` (section 3 -- revenue decomposes by
region/product/customer plus volume/price; gross-profit/margin issues decompose by
revenue-effect/COGS-effect, further by product/region; a region-specific issue decomposes
*within* that region; a product-margin issue reports that product's own components and its
contribution to the company-wide gross-profit change), persists CONTRIBUTION evidence for
every number it reports, and writes a `decomposition` summary onto the `Issue` row where every
figure carries the Evidence ID that backs it.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.db.models.analysis import AnalysisRun, Evidence, Issue
from app.db.models.canonical import FactSales
from app.kpi import aggregations as agg
from app.kpi.periods import PeriodWindow, resolve_comparison_period, resolve_period
from app.rca import decomposition, issues
from app.rca import evidence as ev
from app.rca.decomposition import ContributionRow

CUSTOMER_DISPLAY_TOP_K = 10

_METRIC_UNITS: dict[str, str] = {
    "revenue": "currency",
    "cogs": "currency",
    "gross_profit": "currency",
    "gross_margin_pct": "percentage",
    "sales_quantity": "quantity",
    "average_selling_price": "currency",
    "revenue_customer_concentration": "percentage",
}


class UnknownIssueError(ValueError):
    pass


class UnsupportedIssueTypeError(ValueError):
    pass


def detect_issues(
    session: Session,
    granularity: str,
    period_key: str,
    *,
    comparison_type: str = "YoY",
    dataset_id: uuid.UUID | None = None,
    persist: bool = True,
    client_id: str | None = None,
    client_currency: str | None = None,
) -> AnalysisRun:
    window = resolve_period(granularity, period_key, client_id=client_id)
    comparison_window = resolve_comparison_period(window, comparison_type)

    run = AnalysisRun(
        dataset_id=dataset_id,
        analysis_type="issue_detection",
        granularity=granularity,
        period_key=window.period_key,
        comparison_type=comparison_type,
        comparison_period_key=comparison_window.period_key,
        parameters={"granularity": granularity, "period_key": period_key, "comparison_type": comparison_type},
        status="running",
    )
    session.add(run)
    session.flush()

    candidates = issues.run_all_detectors(
        session, granularity, period_key, comparison_type, client_id, client_currency
    )
    created_issue_ids: list[str] = []
    for candidate in candidates:
        issue = Issue(
            detection_run_id=run.id,
            client_id=client_id,
            issue_type=candidate.issue_type,
            title=candidate.title,
            severity=candidate.severity,
            status="detected",
            granularity=candidate.granularity,
            period_key=candidate.period_key,
            comparison_period_key=candidate.comparison_period_key,
            metric=candidate.metric,
            current_value=candidate.current_value,
            prior_value=candidate.prior_value,
            absolute_change=candidate.absolute_change,
            percentage_change=candidate.percentage_change,
            affected_dimension=candidate.affected_dimension,
            affected_entity=candidate.affected_entity,
            materiality=candidate.materiality,
        )
        session.add(issue)
        session.flush()

        ev.record_fact(
            session,
            analysis_run_id=run.id,
            issue_id=issue.id,
            metric=candidate.metric,
            unit=_METRIC_UNITS.get(candidate.metric),
            granularity=candidate.granularity,
            period_key=candidate.period_key,
            value=candidate.current_value,
            comparison_period_key=candidate.comparison_period_key,
            comparison_value=candidate.prior_value,
            absolute_change=candidate.absolute_change,
            percentage_change=candidate.percentage_change,
            dimension=candidate.affected_dimension,
            dimension_value=candidate.affected_entity,
            calculation_name=f"issue_detection:{candidate.issue_type}",
            calculation_parameters={"materiality": candidate.materiality},
            source_file_ids=candidate.source_file_ids,
        )
        created_issue_ids.append(str(issue.id))

    run.mark_completed({"issues_detected": len(created_issue_ids), "issue_ids": created_issue_ids})
    if persist:
        session.commit()
    return run


def _row_payload(row: ContributionRow, evidence_id: uuid.UUID) -> dict[str, object]:
    return {
        "dimension_value": row.dimension_value,
        "current_value": row.current_value,
        "prior_value": row.prior_value,
        "absolute_contribution": row.absolute_contribution,
        "percentage_contribution": row.percentage_contribution,
        "direction": row.direction,
        "rank": row.rank,
        "current_share_pct": row.current_share_pct,
        "is_other_bucket": row.is_other_bucket,
        "other_bucket_count": row.other_bucket_count,
        "evidence_id": str(evidence_id),
    }


def _breakdown_payload(breakdown: decomposition.ContributionBreakdown) -> dict[str, object]:
    return {
        "total_change": breakdown.total_change,
        "current_total": breakdown.current_total,
        "prior_total": breakdown.prior_total,
        "coverage_pct": breakdown.coverage_pct,
        "residual_absolute": breakdown.residual_absolute,
        "residual_is_material": breakdown.residual_is_material,
    }


def _analyze_revenue_breakdowns(
    session: Session,
    run: AnalysisRun,
    issue: Issue,
    window: PeriodWindow,
    comparison_window: PeriodWindow,
    *,
    label_prefix: str = "",
) -> tuple[dict[str, object], list[Evidence]]:
    """Shared by every revenue-change issue type: region/product/customer contribution plus
    the company-wide volume/price effect. `label_prefix` namespaces the calculation_name for
    an entity-scoped call (see `_analyze_region`)."""
    assert issue.comparison_period_key is not None
    evidence_rows: list[Evidence] = []
    summary: dict[str, object] = {}

    for dim in ("region", "product", "customer"):
        breakdown = decomposition.decompose_by_dimension(
            session, FactSales.net_amount_reporting, window, comparison_window, dim
        )
        display = (
            decomposition.top_k_with_other(breakdown, CUSTOMER_DISPLAY_TOP_K)
            if dim == "customer"
            else breakdown
        )
        rows_payload = []
        for row in display.rows:
            e = ev.record_contribution(
                session,
                analysis_run_id=run.id,
                issue_id=issue.id,
                metric="revenue",
                unit="currency",
                granularity=issue.granularity,
                period_key=issue.period_key,
                comparison_period_key=issue.comparison_period_key,
                dimension=dim,
                row=row,
                calculation_name=f"{label_prefix}revenue_{dim}_contribution",
            )
            evidence_rows.append(e)
            rows_payload.append(_row_payload(row, e.id))
        payload = _breakdown_payload(breakdown)
        payload["rows"] = rows_payload
        summary[f"by_{dim}"] = payload

    current_qty = agg.sum_column(session, FactSales.quantity, window)
    prior_qty = agg.sum_column(session, FactSales.quantity, comparison_window)
    current_rev = agg.sum_column(session, FactSales.net_amount_reporting, window)
    prior_rev = agg.sum_column(session, FactSales.net_amount_reporting, comparison_window)
    vp = decomposition.decompose_volume_price(current_rev, prior_rev, current_qty, prior_qty)
    if vp is not None:
        vp_evidence = ev.record_volume_price_contribution(
            session,
            analysis_run_id=run.id,
            issue_id=issue.id,
            granularity=issue.granularity,
            period_key=issue.period_key,
            comparison_period_key=issue.comparison_period_key,
            effect=vp,
        )
        evidence_rows.extend(vp_evidence)
        summary["volume_price_effect"] = {
            "total_change": vp.total_change,
            "volume_effect": vp.volume_effect,
            "price_effect": vp.price_effect,
            "current_quantity": vp.current_quantity,
            "prior_quantity": vp.prior_quantity,
            "current_price": vp.current_price,
            "prior_price": vp.prior_price,
            "evidence_ids": [str(e.id) for e in vp_evidence],
        }
    return summary, evidence_rows


def _analyze_cogs_breakdowns(
    session: Session, run: AnalysisRun, issue: Issue, window: PeriodWindow, comparison_window: PeriodWindow
) -> tuple[dict[str, object], list[Evidence]]:
    assert issue.comparison_period_key is not None
    evidence_rows: list[Evidence] = []
    summary: dict[str, object] = {}
    for dim in ("product", "region"):
        breakdown = decomposition.decompose_by_dimension(
            session, FactSales.cogs_amount_reporting, window, comparison_window, dim
        )
        rows_payload = []
        for row in breakdown.rows:
            e = ev.record_contribution(
                session,
                analysis_run_id=run.id,
                issue_id=issue.id,
                metric="cogs",
                unit="currency",
                granularity=issue.granularity,
                period_key=issue.period_key,
                comparison_period_key=issue.comparison_period_key,
                dimension=dim,
                row=row,
                calculation_name=f"cogs_{dim}_contribution",
            )
            evidence_rows.append(e)
            rows_payload.append(_row_payload(row, e.id))
        payload = _breakdown_payload(breakdown)
        payload["rows"] = rows_payload
        summary[f"cogs_by_{dim}"] = payload
    return summary, evidence_rows


def _analyze_margin(
    session: Session, run: AnalysisRun, issue: Issue, window: PeriodWindow, comparison_window: PeriodWindow
) -> tuple[dict[str, object], list[Evidence]]:
    assert issue.comparison_period_key is not None
    current_rev = agg.sum_column(session, FactSales.net_amount_reporting, window)
    prior_rev = agg.sum_column(session, FactSales.net_amount_reporting, comparison_window)
    current_cogs = agg.sum_column(session, FactSales.cogs_amount_reporting, window)
    prior_cogs = agg.sum_column(session, FactSales.cogs_amount_reporting, comparison_window)
    gp = decomposition.decompose_gross_profit(current_rev, prior_rev, current_cogs, prior_cogs)
    gp_evidence = ev.record_gross_profit_components(
        session,
        analysis_run_id=run.id,
        issue_id=issue.id,
        granularity=issue.granularity,
        period_key=issue.period_key,
        comparison_period_key=issue.comparison_period_key,
        decomposition=gp,
    )
    summary: dict[str, object] = {
        "gross_profit": {
            "total_change": gp.total_change,
            "revenue_effect": gp.revenue_effect,
            "cogs_effect": gp.cogs_effect,
            "evidence_ids": [str(e.id) for e in gp_evidence],
        }
    }
    cost_summary, cost_evidence = _analyze_cogs_breakdowns(session, run, issue, window, comparison_window)
    summary.update(cost_summary)
    return summary, [*gp_evidence, *cost_evidence]


def _analyze_region(
    session: Session, run: AnalysisRun, issue: Issue, window: PeriodWindow, comparison_window: PeriodWindow
) -> tuple[dict[str, object], list[Evidence]]:
    assert issue.comparison_period_key is not None
    assert issue.affected_entity is not None
    region = issue.affected_entity
    evidence_rows: list[Evidence] = []
    summary: dict[str, object] = {"region": region}

    for dim in ("product", "customer"):
        breakdown = decomposition.decompose_by_dimension(
            session,
            FactSales.net_amount_reporting,
            window,
            comparison_window,
            dim,
            filter_dimension="region",
            filter_value=region,
        )
        display = (
            decomposition.top_k_with_other(breakdown, CUSTOMER_DISPLAY_TOP_K)
            if dim == "customer"
            else breakdown
        )
        rows_payload = []
        for row in display.rows:
            e = ev.record_contribution(
                session,
                analysis_run_id=run.id,
                issue_id=issue.id,
                metric="revenue",
                unit="currency",
                granularity=issue.granularity,
                period_key=issue.period_key,
                comparison_period_key=issue.comparison_period_key,
                dimension=dim,
                row=row,
                calculation_name=f"region_{region}_revenue_{dim}_contribution",
                calculation_parameters={"filter_dimension": "region", "filter_value": region},
            )
            evidence_rows.append(e)
            rows_payload.append(_row_payload(row, e.id))
        payload = _breakdown_payload(breakdown)
        payload["rows"] = rows_payload
        summary[f"by_{dim}_within_region"] = payload

    current_qty = agg.sum_column_filtered(session, FactSales.quantity, window, "region", region)
    prior_qty = agg.sum_column_filtered(session, FactSales.quantity, comparison_window, "region", region)
    current_rev = agg.sum_column_filtered(session, FactSales.net_amount_reporting, window, "region", region)
    prior_rev = agg.sum_column_filtered(
        session, FactSales.net_amount_reporting, comparison_window, "region", region
    )
    vp = decomposition.decompose_volume_price(current_rev, prior_rev, current_qty, prior_qty)
    if vp is not None:
        vp_evidence = ev.record_volume_price_contribution(
            session,
            analysis_run_id=run.id,
            issue_id=issue.id,
            granularity=issue.granularity,
            period_key=issue.period_key,
            comparison_period_key=issue.comparison_period_key,
            effect=vp,
        )
        evidence_rows.extend(vp_evidence)
        summary["volume_price_effect_within_region"] = {
            "total_change": vp.total_change,
            "volume_effect": vp.volume_effect,
            "price_effect": vp.price_effect,
            "evidence_ids": [str(e.id) for e in vp_evidence],
        }
    return summary, evidence_rows


def _analyze_product_margin(
    session: Session, run: AnalysisRun, issue: Issue, window: PeriodWindow, comparison_window: PeriodWindow
) -> tuple[dict[str, object], list[Evidence]]:
    assert issue.comparison_period_key is not None
    assert issue.affected_entity is not None
    product = issue.affected_entity
    evidence_rows: list[Evidence] = []

    cur_rev = agg.sum_column_filtered(session, FactSales.net_amount_reporting, window, "product", product)
    pri_rev = agg.sum_column_filtered(
        session, FactSales.net_amount_reporting, comparison_window, "product", product
    )
    cur_cogs = agg.sum_column_filtered(session, FactSales.cogs_amount_reporting, window, "product", product)
    pri_cogs = agg.sum_column_filtered(
        session, FactSales.cogs_amount_reporting, comparison_window, "product", product
    )
    cur_qty = agg.sum_column_filtered(session, FactSales.quantity, window, "product", product)
    pri_qty = agg.sum_column_filtered(session, FactSales.quantity, comparison_window, "product", product)
    cur_asp = (cur_rev / cur_qty) if cur_qty else None
    pri_asp = (pri_rev / pri_qty) if pri_qty else None
    cur_gp = cur_rev - cur_cogs
    pri_gp = pri_rev - pri_cogs

    def _fact(metric: str, unit: str, value: float | None, comparison_value: float | None) -> Evidence:
        absolute = (value - comparison_value) if value is not None and comparison_value is not None else None
        pct = (
            (absolute / abs(comparison_value) * 100)
            if absolute is not None and comparison_value not in (None, 0)
            else None
        )
        e = ev.record_fact(
            session,
            analysis_run_id=run.id,
            issue_id=issue.id,
            metric=metric,
            unit=unit,
            granularity=issue.granularity,
            period_key=issue.period_key,
            value=value,
            comparison_period_key=issue.comparison_period_key,
            comparison_value=comparison_value,
            absolute_change=absolute,
            percentage_change=pct,
            dimension="product",
            dimension_value=product,
            calculation_name=f"product_{product}_{metric}",
        )
        evidence_rows.append(e)
        return e

    revenue_e = _fact("revenue", "currency", cur_rev, pri_rev)
    cogs_e = _fact("cogs", "currency", cur_cogs, pri_cogs)
    quantity_e = _fact("sales_quantity", "quantity", cur_qty, pri_qty)
    asp_e = _fact("average_selling_price", "currency", cur_asp, pri_asp)
    gp_e = _fact("gross_profit", "currency", cur_gp, pri_gp)

    company_cur_rev = agg.sum_column(session, FactSales.net_amount_reporting, window)
    company_pri_rev = agg.sum_column(session, FactSales.net_amount_reporting, comparison_window)
    company_cur_cogs = agg.sum_column(session, FactSales.cogs_amount_reporting, window)
    company_pri_cogs = agg.sum_column(session, FactSales.cogs_amount_reporting, comparison_window)
    company_gp_change = (company_cur_rev - company_cur_cogs) - (company_pri_rev - company_pri_cogs)
    product_gp_change = cur_gp - pri_gp
    contribution_pct = (product_gp_change / company_gp_change * 100) if company_gp_change else None

    contribution_row = ContributionRow(
        dimension_value=product,
        current_value=cur_gp,
        prior_value=pri_gp,
        absolute_contribution=product_gp_change,
        percentage_contribution=contribution_pct,
        direction="negative" if product_gp_change < 0 else "positive",
    )
    contribution_e = ev.record_contribution(
        session,
        analysis_run_id=run.id,
        issue_id=issue.id,
        metric="gross_profit",
        unit="currency",
        granularity=issue.granularity,
        period_key=issue.period_key,
        comparison_period_key=issue.comparison_period_key,
        dimension="product",
        row=contribution_row,
        calculation_name=f"product_{product}_gross_profit_contribution_to_company",
    )
    evidence_rows.append(contribution_e)

    summary: dict[str, object] = {
        "product": product,
        # `Issue.current_value`/`.prior_value` are `Numeric` columns -- SQLAlchemy/psycopg3
        # hand back `Decimal` for those once the row has round-tripped through the DB, and
        # `Decimal` isn't JSON-serializable. Every other number in this summary already
        # originated as a plain Python `float` from `app/kpi/aggregations.py` (which casts
        # explicitly), so this is the one place that needs the same cast.
        "current_margin_pct": float(issue.current_value) if issue.current_value is not None else None,
        "prior_margin_pct": float(issue.prior_value) if issue.prior_value is not None else None,
        "revenue": {"current": cur_rev, "prior": pri_rev, "evidence_id": str(revenue_e.id)},
        "cogs": {"current": cur_cogs, "prior": pri_cogs, "evidence_id": str(cogs_e.id)},
        "sales_quantity": {"current": cur_qty, "prior": pri_qty, "evidence_id": str(quantity_e.id)},
        "average_selling_price": {"current": cur_asp, "prior": pri_asp, "evidence_id": str(asp_e.id)},
        "gross_profit": {"current": cur_gp, "prior": pri_gp, "evidence_id": str(gp_e.id)},
        "contribution_to_company_gross_profit_change_pct": contribution_pct,
        "contribution_evidence_id": str(contribution_e.id),
    }
    return summary, evidence_rows


def _analyze_customer_concentration(
    session: Session, run: AnalysisRun, issue: Issue, window: PeriodWindow, comparison_window: PeriodWindow
) -> tuple[dict[str, object], list[Evidence]]:
    assert issue.comparison_period_key is not None
    breakdown = decomposition.decompose_by_dimension(
        session, FactSales.net_amount_reporting, window, comparison_window, "customer"
    )
    display = decomposition.top_k_with_other(breakdown, CUSTOMER_DISPLAY_TOP_K)
    evidence_rows: list[Evidence] = []
    rows_payload = []
    for row in display.rows:
        e = ev.record_contribution(
            session,
            analysis_run_id=run.id,
            issue_id=issue.id,
            metric="revenue",
            unit="currency",
            granularity=issue.granularity,
            period_key=issue.period_key,
            comparison_period_key=issue.comparison_period_key,
            dimension="customer",
            row=row,
            calculation_name="revenue_customer_contribution",
        )
        evidence_rows.append(e)
        rows_payload.append(_row_payload(row, e.id))
    payload = _breakdown_payload(breakdown)
    payload["rows"] = rows_payload
    return {"by_customer": payload}, evidence_rows


_ANALYZERS = {
    "revenue_decline": _analyze_revenue_breakdowns,
    "revenue_growth_slowdown": _analyze_revenue_breakdowns,
    "unusual_volume_movement": _analyze_revenue_breakdowns,
    "unusual_cost_movement": _analyze_cogs_breakdowns,
    "margin_deterioration": _analyze_margin,
    "regional_performance_deterioration": _analyze_region,
    "product_margin_deterioration": _analyze_product_margin,
    "customer_concentration_change": _analyze_customer_concentration,
}


def analyze_issue(session: Session, issue_id: uuid.UUID, *, persist: bool = True) -> Issue:
    issue = session.get(Issue, issue_id)
    if issue is None:
        raise UnknownIssueError(f"Unknown issue id '{issue_id}'.")
    if issue.comparison_period_key is None:
        raise ValueError(f"Issue '{issue_id}' has no comparison period; cannot run driver analysis.")
    analyzer = _ANALYZERS.get(issue.issue_type)
    if analyzer is None:
        raise UnsupportedIssueTypeError(
            f"No driver-analysis decomposition registered for '{issue.issue_type}'."
        )

    # The issue already carries the client it was detected for (set in detect_issues above);
    # analyze_issue re-derives that scope from the issue itself rather than asking the caller
    # to pass it again, so POST /issues/{id}/analyze needs no client_id of its own.
    issue_client_id = str(issue.client_id) if issue.client_id is not None else None
    window = resolve_period(issue.granularity, issue.period_key, client_id=issue_client_id)
    comparison_window = resolve_period(
        issue.granularity, issue.comparison_period_key, client_id=issue_client_id
    )

    run = AnalysisRun(
        dataset_id=None,
        analysis_type="rca",
        granularity=issue.granularity,
        period_key=issue.period_key,
        comparison_type=None,
        comparison_period_key=issue.comparison_period_key,
        parameters={"issue_id": str(issue.id), "issue_type": issue.issue_type},
        status="running",
    )
    session.add(run)
    session.flush()

    summary, evidence_rows = analyzer(session, run, issue, window, comparison_window)

    issue.decomposition = summary
    issue.status = "analyzed"
    issue.analyzed_at = datetime.now(UTC)
    issue.latest_analysis_run_id = run.id

    run.mark_completed({"evidence_count": len(evidence_rows)})
    if persist:
        session.commit()
    return issue


__all__ = ["UnknownIssueError", "UnsupportedIssueTypeError", "analyze_issue", "detect_issues"]
