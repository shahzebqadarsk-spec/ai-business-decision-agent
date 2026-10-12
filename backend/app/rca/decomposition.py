"""Deterministic contribution math (Phase 4 spec, sections 3/8).

Terminology is deliberate throughout this module and everywhere its output is surfaced: a
"contribution" is a measured association between a dimension/entity and part of a total
change, never a causal claim (spec section 9 -- "change is not causation"). Nothing here uses
the words "caused", "root cause", or "because of".

Two decomposition shapes are implemented, both as *exact* algebraic partitions of the total
change (no forced-100% hack, no dropped cross-term):

1. **Dimensional partition** (`decompose_by_dimension`): revenue (or COGS) grouped by region /
   product / customer in both the current and prior period, matched by key. Because
   `sum(current) - sum(prior)` over the *same* set of keys equals the total change exactly,
   coverage is 100% and residual is 0 by construction, for any dimension that fully partitions
   the metric -- which every dimension on `fact_sales` does, since there is no "unallocated"
   row. The residual/coverage fields still exist and are checked, because a future phase's
   dimension might not partition perfectly (e.g. an overhead allocation that doesn't sum to
   the total); this phase's own output should simply always show residual ~= 0.

2. **Volume/price effect** (`decompose_volume_price`): splits a revenue change into a quantity
   effect and a price effect using the *midpoint* (average-rate) method -- effect_qty =
   delta_qty * (price_0 + price_1) / 2, effect_price = delta_price * (qty_0 + qty_1) / 2 -- which
   sums to the total change exactly, with no leftover interaction/cross term to explain away.
   (The simpler "anchor" method, effect_qty = delta_qty * price_0, effect_price = delta_price *
   qty_1, leaves a cross term delta_price * delta_qty unaccounted for; the spec names "volume
   effect" and "price/ASP effect" but not a method, so the midpoint method was chosen here as
   the one with no unexplained leftover -- see docs/DECISIONS.md.)

Gross profit's decomposition (`decompose_gross_profit`) is a third, even simpler case: ΔGP =
ΔRevenue - ΔCOGS is an exact identity with only two terms, so it is implemented directly
rather than through the dimensional-partition helper.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from sqlalchemy.orm import Session

from app.kpi import aggregations as agg
from app.kpi.periods import PeriodWindow

CALCULATION_VERSION = "1.0.0"

# A residual is "material" (worth an explicit "material unexplained residual" flag, spec
# section 8) only if it clears *both* a relative and an absolute floor -- mirrors
# app/rca/materiality.py's two-threshold pattern, applied to the decomposition's own honesty
# check rather than to whether an issue gets flagged in the first place.
RESIDUAL_MATERIALITY_RELATIVE_PCT = 1.0
RESIDUAL_MATERIALITY_FLOOR_PKR = 100_000.0


def is_residual_material(residual: float, total_change: float) -> bool:
    """A residual is "material" only if it clears *both* an absolute PKR floor and a
    percentage-of-total-change floor -- mirrors app/rca/materiality.py's two-threshold
    pattern, applied to a decomposition's own honesty check. Pulled out as its own function
    so it is unit-testable with contrived numbers, independent of any real decomposition
    query -- every decomposition this phase actually runs partitions `fact_sales` exactly, so
    `residual` is always ~0 there and this branch is otherwise untested by live data."""
    return abs(residual) > RESIDUAL_MATERIALITY_FLOOR_PKR and (
        total_change == 0 or abs(residual) / abs(total_change) * 100 > RESIDUAL_MATERIALITY_RELATIVE_PCT
    )


def _direction(value: float) -> str:
    if value > 0:
        return "positive"
    if value < 0:
        return "negative"
    return "flat"


@dataclass(frozen=True)
class ContributionRow:
    dimension_value: str | None
    current_value: float
    prior_value: float
    absolute_contribution: float
    percentage_contribution: float | None
    """Share of the *total change* this entity's own change represents, in percentage
    points -- `None` only when the total change is exactly zero (undefined, not zero)."""
    direction: str
    rank: int | None = None
    current_share_pct: float | None = None
    is_other_bucket: bool = False
    """True for a synthetic row merging every entity below the display cutoff -- see
    `top_k_with_other()`. Keeps API payloads small without breaking the exact partition."""
    other_bucket_count: int | None = None


@dataclass(frozen=True)
class ContributionBreakdown:
    dimension: str
    total_change: float
    current_total: float
    prior_total: float
    rows: tuple[ContributionRow, ...]
    coverage_pct: float | None
    """sum(explained contributions) / total_change * 100 -- `None` when total_change is 0
    (undefined, not 100% or 0%)."""
    residual_absolute: float
    residual_is_material: bool


def decompose_by_dimension(
    session: Session,
    column: object,
    current_window: PeriodWindow,
    prior_window: PeriodWindow,
    dimension: str,
    *,
    filter_dimension: str | None = None,
    filter_value: str | None = None,
) -> ContributionBreakdown:
    """`filter_dimension`/`filter_value` scope the partition to one entity of a *different*
    dimension -- e.g. `dimension="product", filter_dimension="region", filter_value="REG-05"`
    decomposes REG-05's own revenue change by product, rather than the whole company's."""
    if filter_dimension is not None and filter_value is not None:
        current_rows = dict(
            agg.sum_by_dimension_filtered(
                session, column, current_window, dimension, filter_dimension, filter_value
            )
        )
        prior_rows = dict(
            agg.sum_by_dimension_filtered(
                session, column, prior_window, dimension, filter_dimension, filter_value
            )
        )
    else:
        current_rows = dict(agg.sum_by_dimension(session, column, current_window, dimension))
        prior_rows = dict(agg.sum_by_dimension(session, column, prior_window, dimension))
    all_keys = set(current_rows) | set(prior_rows)

    current_total = sum(current_rows.values())
    prior_total = sum(prior_rows.values())
    total_change = current_total - prior_total

    rows: list[ContributionRow] = []
    for key in all_keys:
        current_value = current_rows.get(key, 0.0)
        prior_value = prior_rows.get(key, 0.0)
        contribution = current_value - prior_value
        pct_contribution = (contribution / total_change * 100) if total_change != 0 else None
        share = (current_value / current_total * 100) if current_total else None
        rows.append(
            ContributionRow(
                dimension_value=key,
                current_value=current_value,
                prior_value=prior_value,
                absolute_contribution=contribution,
                percentage_contribution=pct_contribution,
                direction=_direction(contribution),
                current_share_pct=share,
            )
        )
    rows.sort(key=lambda r: abs(r.absolute_contribution), reverse=True)
    ranked = tuple(replace(row, rank=i + 1) for i, row in enumerate(rows))

    explained = sum(r.absolute_contribution for r in ranked)
    residual = total_change - explained
    coverage_pct = (explained / total_change * 100) if total_change != 0 else None
    residual_material = is_residual_material(residual, total_change)

    return ContributionBreakdown(
        dimension=dimension,
        total_change=total_change,
        current_total=current_total,
        prior_total=prior_total,
        rows=ranked,
        coverage_pct=coverage_pct,
        residual_absolute=residual,
        residual_is_material=residual_material,
    )


def top_k_with_other(breakdown: ContributionBreakdown, k: int) -> ContributionBreakdown:
    """Display helper: keep the `k` largest-magnitude contributions, merge the remainder into
    one 'Other' row. The merged row's own contribution is the exact sum of what it replaces,
    so `rows` still sums to `total_change` exactly -- this is not a lossy summary."""
    if len(breakdown.rows) <= k:
        return breakdown
    kept = breakdown.rows[:k]
    rest = breakdown.rows[k:]
    other = ContributionRow(
        dimension_value=None,
        current_value=sum(r.current_value for r in rest),
        prior_value=sum(r.prior_value for r in rest),
        absolute_contribution=sum(r.absolute_contribution for r in rest),
        percentage_contribution=(
            sum(r.absolute_contribution for r in rest) / breakdown.total_change * 100
            if breakdown.total_change != 0
            else None
        ),
        direction=_direction(sum(r.absolute_contribution for r in rest)),
        rank=k + 1,
        current_share_pct=(
            sum(r.current_value for r in rest) / breakdown.current_total * 100
            if breakdown.current_total
            else None
        ),
        is_other_bucket=True,
        other_bucket_count=len(rest),
    )
    return ContributionBreakdown(
        dimension=breakdown.dimension,
        total_change=breakdown.total_change,
        current_total=breakdown.current_total,
        prior_total=breakdown.prior_total,
        rows=(*kept, other),
        coverage_pct=breakdown.coverage_pct,
        residual_absolute=breakdown.residual_absolute,
        residual_is_material=breakdown.residual_is_material,
    )


@dataclass(frozen=True)
class VolumePriceEffect:
    total_change: float
    volume_effect: float
    price_effect: float
    current_quantity: float
    prior_quantity: float
    current_price: float
    prior_price: float
    method: str = "midpoint"


def decompose_volume_price(
    current_revenue: float, prior_revenue: float, current_quantity: float, prior_quantity: float
) -> VolumePriceEffect | None:
    """Returns `None` (not a fabricated split) when either period's quantity is zero, since
    an average selling price is undefined in that case -- mirrors the KPI engine's
    `invalid_data` guard for the same reason (app/kpi/calculators.py::calculate_average_selling_price)."""
    if current_quantity == 0 or prior_quantity == 0:
        return None
    current_price = current_revenue / current_quantity
    prior_price = prior_revenue / prior_quantity
    delta_qty = current_quantity - prior_quantity
    delta_price = current_price - prior_price
    volume_effect = delta_qty * (prior_price + current_price) / 2
    price_effect = delta_price * (prior_quantity + current_quantity) / 2
    return VolumePriceEffect(
        total_change=current_revenue - prior_revenue,
        volume_effect=volume_effect,
        price_effect=price_effect,
        current_quantity=current_quantity,
        prior_quantity=prior_quantity,
        current_price=current_price,
        prior_price=prior_price,
    )


@dataclass(frozen=True)
class GrossProfitDecomposition:
    total_change: float
    revenue_effect: float
    cogs_effect: float
    current_revenue: float
    prior_revenue: float
    current_cogs: float
    prior_cogs: float


def decompose_gross_profit(
    current_revenue: float, prior_revenue: float, current_cogs: float, prior_cogs: float
) -> GrossProfitDecomposition:
    """ΔGrossProfit = ΔRevenue - ΔCOGS -- an exact two-term identity, not an approximation:
    GP = Revenue - COGS, so GP1 - GP0 = (Rev1 - Rev0) - (COGS1 - COGS0) always, with zero
    residual and no decomposition method to choose."""
    revenue_effect = current_revenue - prior_revenue
    cogs_effect = -(current_cogs - prior_cogs)
    return GrossProfitDecomposition(
        total_change=revenue_effect + cogs_effect,
        revenue_effect=revenue_effect,
        cogs_effect=cogs_effect,
        current_revenue=current_revenue,
        prior_revenue=prior_revenue,
        current_cogs=current_cogs,
        prior_cogs=prior_cogs,
    )


__all__ = [
    "CALCULATION_VERSION",
    "ContributionBreakdown",
    "ContributionRow",
    "GrossProfitDecomposition",
    "VolumePriceEffect",
    "decompose_by_dimension",
    "decompose_gross_profit",
    "decompose_volume_price",
    "is_residual_material",
    "top_k_with_other",
]
