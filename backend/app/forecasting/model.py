"""Deterministic trend + seasonal forecasting model (Phase 5).

Classical two-stage decomposition, entirely closed-form (ordinary least squares + grouped
residual means) -- no ARIMA/Prophet/ML library, so every number here is checkable by hand or
against an independent numpy/pandas computation in tests, the same bar every other engine in
this project is held to (Phase 3's KPI formulas, Phase 4's contribution math).

Stage 1: fit `y_t = intercept + slope*t` by OLS (closed-form normal equations), ignoring
seasonality.
Stage 2: average the stage-1 residuals by calendar month (1-12) to get a seasonal index per
month, then center the 12 indices to sum to zero so they don't shift the trend's own
intercept (otherwise the seasonal indices and the intercept are not separately identified).
Final fitted value: `intercept + slope*t + seasonal_index[month(t)]`.

Prediction intervals use the standard OLS prediction-interval formula --
`point +/- z * residual_std * sqrt(1 + leverage(t))` -- so the band widens the further a
forecasted period is from the historical mean time index, which is the statistically honest
behavior for an extrapolation (not a fixed +/-X% guess). This is a documented simplification:
the leverage term is derived from the *trend* regression alone and does not fully propagate
the seasonal indices' own estimation uncertainty into the band -- see
docs/PHASE_5_FORECASTING_ENGINE.md.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Two full annual cycles -- with fewer than this, a given calendar month's seasonal index
# would be estimated from a single observation, indistinguishable from noise. Also guarantees
# `degrees_of_freedom` (n - 13, see below) stays comfortably positive.
MIN_HISTORY_FOR_FIT = 24

# Two-sided normal-distribution critical values for the confidence levels this system offers.
# Hardcoded rather than computed via scipy.stats.norm.ppf (scipy is not a project dependency)
# -- deterministic, auditable at a glance, and the only four levels the API/UI actually expose.
Z_SCORES: dict[float, float] = {
    0.80: 1.2816,
    0.90: 1.6449,
    0.95: 1.9600,
    0.99: 2.5758,
}


@dataclass(frozen=True)
class TrendSeasonalFit:
    n_observations: int
    start_month: int
    """Calendar month (1-12) of time index t=0 -- needed to map any t back to a month."""
    intercept: float
    slope: float
    seasonal_indices: dict[int, float]
    """Calendar month (1-12) -> additive seasonal index. Sums to (approximately) zero."""
    residuals: tuple[float, ...]
    """Final (trend+season) residual for each input observation, same order as the input."""
    residual_std: float
    degrees_of_freedom: int
    """n - 13: 2 trend parameters + 11 free seasonal parameters (the 12th is fixed by the
    sum-to-zero constraint). `NaN`-guarded by MIN_HISTORY_FOR_FIT, which keeps this positive."""


def _month_at(start_month: int, t: int) -> int:
    return ((start_month - 1 + t) % 12) + 1


def fit_trend_seasonal(values: list[float], start_month: int) -> TrendSeasonalFit:
    """`values` must be a chronologically ordered, gap-free monthly series (callers verify
    this via `app/forecasting/sufficiency.py` before calling here); `start_month` is the
    calendar month of `values[0]`."""
    n = len(values)
    if n < MIN_HISTORY_FOR_FIT:
        raise ValueError(f"Need at least {MIN_HISTORY_FOR_FIT} observations to fit, got {n}.")

    ts = list(range(n))
    t_mean = sum(ts) / n
    y_mean = sum(values) / n
    ss_t = sum((t - t_mean) ** 2 for t in ts)
    if ss_t == 0:
        raise ValueError("Cannot fit a trend with fewer than 2 distinct time points.")
    slope = sum((ts[i] - t_mean) * (values[i] - y_mean) for i in range(n)) / ss_t
    intercept = y_mean - slope * t_mean

    stage1_residuals = [values[i] - (intercept + slope * ts[i]) for i in range(n)]

    by_month: dict[int, list[float]] = {m: [] for m in range(1, 13)}
    for i in range(n):
        by_month[_month_at(start_month, i)].append(stage1_residuals[i])
    raw_seasonal = {m: (sum(r) / len(r) if r else 0.0) for m, r in by_month.items()}
    center = sum(raw_seasonal.values()) / 12
    seasonal_indices = {m: v - center for m, v in raw_seasonal.items()}

    final_residuals = tuple(
        values[i] - (intercept + slope * ts[i] + seasonal_indices[_month_at(start_month, i)])
        for i in range(n)
    )
    degrees_of_freedom = n - 13
    sse = sum(r * r for r in final_residuals)
    residual_std = math.sqrt(sse / degrees_of_freedom) if degrees_of_freedom > 0 else float("nan")

    return TrendSeasonalFit(
        n_observations=n,
        start_month=start_month,
        intercept=intercept,
        slope=slope,
        seasonal_indices=seasonal_indices,
        residuals=final_residuals,
        residual_std=residual_std,
        degrees_of_freedom=degrees_of_freedom,
    )


def predict_point(fit: TrendSeasonalFit, t: int) -> float:
    month = _month_at(fit.start_month, t)
    return fit.intercept + fit.slope * t + fit.seasonal_indices[month]


def predict_interval(fit: TrendSeasonalFit, t: int, confidence_level: float) -> tuple[float, float]:
    """Returns `(point, point)` -- a visibly zero-width interval, not a silently wrong one --
    when the fit has no usable residual degrees of freedom. `MIN_HISTORY_FOR_FIT` keeps this
    from ever happening through the real engine; it exists so `model.py` stays safe to call
    directly with contrived small inputs in tests."""
    if confidence_level not in Z_SCORES:
        raise ValueError(
            f"Unsupported confidence_level {confidence_level}; expected one of {sorted(Z_SCORES)}."
        )
    point = predict_point(fit, t)
    if fit.degrees_of_freedom <= 0 or math.isnan(fit.residual_std):
        return point, point

    n = fit.n_observations
    t_mean = (n - 1) / 2
    ss_t = sum((i - t_mean) ** 2 for i in range(n))
    leverage = 1.0 / n + ((t - t_mean) ** 2) / ss_t
    se_pred = fit.residual_std * math.sqrt(1 + leverage)
    margin = Z_SCORES[confidence_level] * se_pred
    return point - margin, point + margin


__all__ = [
    "MIN_HISTORY_FOR_FIT",
    "Z_SCORES",
    "TrendSeasonalFit",
    "fit_trend_seasonal",
    "predict_interval",
    "predict_point",
]
