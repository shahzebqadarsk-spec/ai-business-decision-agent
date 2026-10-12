"""Builds and persists `Evidence` rows (Phase 4 spec, sections 10/11).

Every function here does exactly one thing: take numbers the issue-detection or decomposition
engine already computed, and write down a self-contained, typed record of the claim those
numbers support. Nothing in this module queries the database itself or performs a calculation
-- it is pure persistence/formatting, which is what keeps the "LLM must never modify evidence"
and "evidence must originate from deterministic analytics" rules (section 11) structurally
true: there is no code path into this table except from `app/rca/engine.py`, which only ever
passes in output from `issues.py` / `decomposition.py`.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.db.models.analysis import Evidence
from app.rca.decomposition import ContributionRow, GrossProfitDecomposition, VolumePriceEffect

RCA_CALCULATION_VERSION = "1.0.0"


def _fmt(value: float | None, unit: str | None) -> str:
    if value is None:
        return "unavailable"
    if unit == "currency":
        return f"PKR {value:,.2f}"
    if unit == "percentage":
        return f"{value:.2f}%"
    return f"{value:,.2f}"


def record_fact(
    session: Session,
    *,
    analysis_run_id: uuid.UUID,
    issue_id: uuid.UUID | None,
    metric: str,
    unit: str | None,
    granularity: str,
    period_key: str,
    value: float | None,
    comparison_period_key: str | None = None,
    comparison_value: float | None = None,
    absolute_change: float | None = None,
    percentage_change: float | None = None,
    dimension: str | None = None,
    dimension_value: str | None = None,
    calculation_name: str,
    calculation_parameters: dict[str, object] | None = None,
    source_file_ids: tuple[str, ...] = (),
    source_fields: tuple[str, ...] = (),
    quality_metadata: dict[str, object] | None = None,
) -> Evidence:
    """A FACT claim: "metric X was Y for period P (vs Z for the comparison period)." --
    no interpretation, just what a deterministic query against canonical data returned."""
    where = f" for {dimension} {dimension_value}" if dimension and dimension_value else ""
    claim = f"{metric}{where} was {_fmt(value, unit)} for {period_key}"
    if comparison_period_key is not None:
        claim += f" (vs {_fmt(comparison_value, unit)} for {comparison_period_key})"
    claim += "."

    evidence = Evidence(
        analysis_run_id=analysis_run_id,
        issue_id=issue_id,
        claim_type="fact",
        claim=claim,
        metric=metric,
        unit=unit,
        granularity=granularity,
        period_key=period_key,
        comparison_period_key=comparison_period_key,
        dimension=dimension,
        dimension_value=dimension_value,
        value=value,
        comparison_value=comparison_value,
        absolute_change=absolute_change,
        percentage_change=percentage_change,
        source_file_ids=list(source_file_ids),
        source_fields=list(source_fields),
        calculation_name=calculation_name,
        calculation_version=RCA_CALCULATION_VERSION,
        calculation_parameters=calculation_parameters or {},
        quality_metadata=quality_metadata or {},
    )
    session.add(evidence)
    session.flush()
    return evidence


def record_contribution(
    session: Session,
    *,
    analysis_run_id: uuid.UUID,
    issue_id: uuid.UUID | None,
    metric: str,
    unit: str | None,
    granularity: str,
    period_key: str,
    comparison_period_key: str,
    dimension: str,
    row: ContributionRow,
    calculation_name: str,
    calculation_parameters: dict[str, object] | None = None,
    quality_metadata: dict[str, object] | None = None,
) -> Evidence:
    """A CONTRIBUTION claim about one dimensional-partition row: "entity E's own change was A
    (P% of the total change) between the comparison period and the period." Deliberately uses
    "contributed"/"associated" phrasing, never "caused" -- see module docstring and
    app/rca/decomposition.py's own docstring on why this is an association, not a causal claim."""
    entity_label = "Other" if row.is_other_bucket else str(row.dimension_value)
    pct_text = (
        f"{row.percentage_contribution:.1f}% of the total change"
        if row.percentage_contribution is not None
        else "an undefined share of the total change (total change was zero)"
    )
    claim = (
        f"{dimension.capitalize()} '{entity_label}' moved from {_fmt(row.prior_value, unit)} to "
        f"{_fmt(row.current_value, unit)} for {metric} between {comparison_period_key} and "
        f"{period_key} -- an absolute contribution of {_fmt(row.absolute_contribution, unit)} "
        f"({pct_text}). This is a measured association, not a causal claim."
    )

    evidence = Evidence(
        analysis_run_id=analysis_run_id,
        issue_id=issue_id,
        claim_type="contribution",
        claim=claim,
        metric=metric,
        unit=unit,
        granularity=granularity,
        period_key=period_key,
        comparison_period_key=comparison_period_key,
        dimension=dimension,
        dimension_value=None if row.is_other_bucket else row.dimension_value,
        value=row.current_value,
        comparison_value=row.prior_value,
        absolute_change=row.absolute_contribution,
        percentage_change=None,
        contribution_to_total_pct=row.percentage_contribution,
        calculation_name=calculation_name,
        calculation_version=RCA_CALCULATION_VERSION,
        calculation_parameters=calculation_parameters or {},
        quality_metadata=quality_metadata or {},
    )
    session.add(evidence)
    session.flush()
    return evidence


def record_volume_price_contribution(
    session: Session,
    *,
    analysis_run_id: uuid.UUID,
    issue_id: uuid.UUID | None,
    granularity: str,
    period_key: str,
    comparison_period_key: str,
    effect: VolumePriceEffect,
) -> list[Evidence]:
    """Two CONTRIBUTION rows (volume effect, price effect) that together sum exactly to the
    revenue change -- see decomposition.py's module docstring for why the midpoint method
    leaves no cross-term residual to explain."""
    params = {
        "method": effect.method,
        "current_quantity": effect.current_quantity,
        "prior_quantity": effect.prior_quantity,
        "current_price": effect.current_price,
        "prior_price": effect.prior_price,
    }
    pct_volume = (effect.volume_effect / effect.total_change * 100) if effect.total_change else None
    pct_price = (effect.price_effect / effect.total_change * 100) if effect.total_change else None

    volume_evidence = Evidence(
        analysis_run_id=analysis_run_id,
        issue_id=issue_id,
        claim_type="contribution",
        claim=(
            f"Sales volume moved from {effect.prior_quantity:,.1f} to {effect.current_quantity:,.1f} "
            f"units between {comparison_period_key} and {period_key}; valued at the average selling "
            f"price across both periods, this volume change is associated with a revenue effect of "
            f"{_fmt(effect.volume_effect, 'currency')}. This is a measured association, not a causal claim."
        ),
        metric="revenue",
        unit="currency",
        granularity=granularity,
        period_key=period_key,
        comparison_period_key=comparison_period_key,
        dimension="volume_price_effect",
        dimension_value="volume",
        value=effect.current_quantity,
        comparison_value=effect.prior_quantity,
        absolute_change=effect.volume_effect,
        contribution_to_total_pct=pct_volume,
        calculation_name="revenue_volume_price_decomposition",
        calculation_version=RCA_CALCULATION_VERSION,
        calculation_parameters=params,
    )
    price_evidence = Evidence(
        analysis_run_id=analysis_run_id,
        issue_id=issue_id,
        claim_type="contribution",
        claim=(
            f"Average selling price moved from PKR {effect.prior_price:,.2f} to "
            f"PKR {effect.current_price:,.2f} between {comparison_period_key} and {period_key}; "
            f"valued at the volume in both periods, this price change is associated with a revenue "
            f"effect of {_fmt(effect.price_effect, 'currency')}. This is a measured association, "
            f"not a causal claim."
        ),
        metric="revenue",
        unit="currency",
        granularity=granularity,
        period_key=period_key,
        comparison_period_key=comparison_period_key,
        dimension="volume_price_effect",
        dimension_value="price",
        value=effect.current_price,
        comparison_value=effect.prior_price,
        absolute_change=effect.price_effect,
        contribution_to_total_pct=pct_price,
        calculation_name="revenue_volume_price_decomposition",
        calculation_version=RCA_CALCULATION_VERSION,
        calculation_parameters=params,
    )
    session.add_all([volume_evidence, price_evidence])
    session.flush()
    return [volume_evidence, price_evidence]


def record_gross_profit_components(
    session: Session,
    *,
    analysis_run_id: uuid.UUID,
    issue_id: uuid.UUID | None,
    granularity: str,
    period_key: str,
    comparison_period_key: str,
    decomposition: GrossProfitDecomposition,
) -> list[Evidence]:
    """Two CONTRIBUTION rows (revenue effect, COGS effect) that sum exactly to the gross
    profit change -- an algebraic identity (GP = Revenue - COGS), not a modeling choice."""
    revenue_evidence = Evidence(
        analysis_run_id=analysis_run_id,
        issue_id=issue_id,
        claim_type="contribution",
        claim=(
            f"Revenue moved from {_fmt(decomposition.prior_revenue, 'currency')} to "
            f"{_fmt(decomposition.current_revenue, 'currency')} between {comparison_period_key} and "
            f"{period_key}, associated with a gross-profit effect of "
            f"{_fmt(decomposition.revenue_effect, 'currency')} (GP = Revenue - COGS). "
            f"This is a measured association, not a causal claim."
        ),
        metric="gross_profit",
        unit="currency",
        granularity=granularity,
        period_key=period_key,
        comparison_period_key=comparison_period_key,
        dimension="gross_profit_component",
        dimension_value="revenue_effect",
        value=decomposition.current_revenue,
        comparison_value=decomposition.prior_revenue,
        absolute_change=decomposition.revenue_effect,
        contribution_to_total_pct=(
            decomposition.revenue_effect / decomposition.total_change * 100
            if decomposition.total_change
            else None
        ),
        calculation_name="gross_profit_decomposition",
        calculation_version=RCA_CALCULATION_VERSION,
        calculation_parameters={},
    )
    cogs_evidence = Evidence(
        analysis_run_id=analysis_run_id,
        issue_id=issue_id,
        claim_type="contribution",
        claim=(
            f"COGS moved from {_fmt(decomposition.prior_cogs, 'currency')} to "
            f"{_fmt(decomposition.current_cogs, 'currency')} between {comparison_period_key} and "
            f"{period_key}, associated with a gross-profit effect of "
            f"{_fmt(decomposition.cogs_effect, 'currency')} (GP = Revenue - COGS). "
            f"This is a measured association, not a causal claim."
        ),
        metric="gross_profit",
        unit="currency",
        granularity=granularity,
        period_key=period_key,
        comparison_period_key=comparison_period_key,
        dimension="gross_profit_component",
        dimension_value="cogs_effect",
        value=decomposition.current_cogs,
        comparison_value=decomposition.prior_cogs,
        absolute_change=decomposition.cogs_effect,
        contribution_to_total_pct=(
            decomposition.cogs_effect / decomposition.total_change * 100
            if decomposition.total_change
            else None
        ),
        calculation_name="gross_profit_decomposition",
        calculation_version=RCA_CALCULATION_VERSION,
        calculation_parameters={},
    )
    session.add_all([revenue_evidence, cogs_evidence])
    session.flush()
    return [revenue_evidence, cogs_evidence]


__all__ = [
    "RCA_CALCULATION_VERSION",
    "record_contribution",
    "record_fact",
    "record_gross_profit_components",
    "record_volume_price_contribution",
]
