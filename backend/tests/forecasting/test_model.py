"""Pure-math unit tests for app/forecasting/model.py, cross-checked against an independent
numpy computation wherever possible -- same bar as Phase 3/4's own calculators."""

from __future__ import annotations

import math

import numpy as np
import pytest
from app.forecasting import model as fm

# A noise-free trend+seasonal series: 3 exact annual cycles. The seasonal pattern is chosen
# symmetric (season[m] == season[13-m]) with sum(season[1..6]) == 0, which makes it provably
# orthogonal to a linear trend over this exact 3-cycle, start_month=1 window -- so stage-1 OLS
# recovers the trend with zero confounding bias and the fit should match the planted
# parameters essentially exactly. (Classical two-stage decomposition is *not* an exact-
# reconstruction method in general -- an arbitrary seasonal pattern sampled over a finite
# window is not guaranteed to be orthogonal to a linear trend, which biases the recovered
# trend by a small, deterministic amount. That is a documented property of this simple method,
# not a numerical bug -- see docs/PHASE_5_FORECASTING_ENGINE.md. This test's pattern is
# deliberately chosen to sidestep that bias so it can assert exact recovery; the noisy,
# arbitrary-pattern cross-check tests below are the ones that matter for general inputs.)
TRUE_INTERCEPT = 100.0
TRUE_SLOPE = 2.0
TRUE_SEASONAL = {
    1: 10.0,
    2: -5.0,
    3: -10.0,
    4: 5.0,
    5: 5.0,
    6: -5.0,
    7: -5.0,
    8: 5.0,
    9: 5.0,
    10: -10.0,
    11: -5.0,
    12: 10.0,
}
assert sum(TRUE_SEASONAL.values()) == 0.0
assert all(TRUE_SEASONAL[m] == TRUE_SEASONAL[13 - m] for m in range(1, 13))


def _month_at(t: int) -> int:
    return (t % 12) + 1


def _make_series(n: int = 36) -> list[float]:
    return [TRUE_INTERCEPT + TRUE_SLOPE * t + TRUE_SEASONAL[_month_at(t)] for t in range(n)]


def test_fit_recovers_exact_trend_and_seasonal_pattern_with_no_noise() -> None:
    fit = fm.fit_trend_seasonal(_make_series(), start_month=1)
    assert fit.intercept == pytest.approx(TRUE_INTERCEPT, abs=1e-6)
    assert fit.slope == pytest.approx(TRUE_SLOPE, abs=1e-6)
    for month, expected in TRUE_SEASONAL.items():
        assert fit.seasonal_indices[month] == pytest.approx(expected, abs=1e-6)
    assert fit.residual_std == pytest.approx(0.0, abs=1e-6)
    assert all(abs(r) < 1e-6 for r in fit.residuals)


def test_trend_cross_checked_against_independent_numpy_ols() -> None:
    """The returned intercept/slope are the stage-1 OLS fit -- verify against numpy's own
    polyfit on the same (noisy) data, computed independently of model.py."""
    rng = np.random.default_rng(42)
    noise = rng.normal(0, 3.0, size=36)
    values = [v + n for v, n in zip(_make_series(), noise, strict=True)]

    fit = fm.fit_trend_seasonal(values, start_month=1)

    ts = np.arange(36)
    np_slope, np_intercept = np.polyfit(ts, np.array(values), 1)
    assert fit.slope == pytest.approx(float(np_slope), abs=1e-9)
    assert fit.intercept == pytest.approx(float(np_intercept), abs=1e-9)

    # Cross-check the seasonal indices too: stage-1 residuals grouped by month, centered.
    stage1_resid = np.array(values) - (np_intercept + np_slope * ts)
    raw_seasonal = {m: float(np.mean(stage1_resid[ts % 12 == (m - 1)])) for m in range(1, 13)}
    center = sum(raw_seasonal.values()) / 12
    expected_seasonal = {m: v - center for m, v in raw_seasonal.items()}
    for month in range(1, 13):
        assert fit.seasonal_indices[month] == pytest.approx(expected_seasonal[month], abs=1e-9)


def test_seasonal_indices_sum_to_zero() -> None:
    fit = fm.fit_trend_seasonal(_make_series(), start_month=1)
    assert sum(fit.seasonal_indices.values()) == pytest.approx(0.0, abs=1e-9)


def test_degrees_of_freedom_is_observations_minus_thirteen() -> None:
    fit = fm.fit_trend_seasonal(_make_series(36), start_month=1)
    assert fit.degrees_of_freedom == 36 - 13


def test_start_month_other_than_january_maps_months_correctly() -> None:
    """start_month=7 means t=0 is July; cross-checked against an independent numpy
    computation using the same (t+6)%12+1 month mapping, rather than against the
    orthogonal-safe TRUE_SEASONAL pattern above (whose exact-recovery property is specific to
    start_month=1 -- see that pattern's own comment)."""
    rng = np.random.default_rng(11)
    arbitrary_seasonal = {m: v * 1.3 for m, v in TRUE_SEASONAL.items()}  # any pattern will do
    base = [TRUE_INTERCEPT + TRUE_SLOPE * t + arbitrary_seasonal[((t + 6) % 12) + 1] for t in range(36)]
    values = [v + n for v, n in zip(base, rng.normal(0, 4.0, size=36), strict=True)]

    fit = fm.fit_trend_seasonal(values, start_month=7)

    ts = np.arange(36)
    np_slope, np_intercept = np.polyfit(ts, np.array(values), 1)
    stage1_resid = np.array(values) - (np_intercept + np_slope * ts)
    # Month for index t when start_month=7 is ((t + 6) % 12) + 1 -- same mapping as above.
    calendar_month = ((ts + 6) % 12) + 1
    raw_seasonal = {m: float(np.mean(stage1_resid[calendar_month == m])) for m in range(1, 13)}
    center = sum(raw_seasonal.values()) / 12
    expected_seasonal = {m: v - center for m, v in raw_seasonal.items()}

    assert fit.slope == pytest.approx(float(np_slope), abs=1e-9)
    assert fit.intercept == pytest.approx(float(np_intercept), abs=1e-9)
    for month in range(1, 13):
        assert fit.seasonal_indices[month] == pytest.approx(expected_seasonal[month], abs=1e-9)


def test_fit_raises_below_minimum_history() -> None:
    with pytest.raises(ValueError, match="at least"):
        fm.fit_trend_seasonal(_make_series(fm.MIN_HISTORY_FOR_FIT - 1), start_month=1)


def test_predict_point_matches_the_fit_formula_directly() -> None:
    fit = fm.fit_trend_seasonal(_make_series(), start_month=1)
    t = 40  # a future period, past the 36 observed
    expected = fit.intercept + fit.slope * t + fit.seasonal_indices[_month_at(t)]
    assert fm.predict_point(fit, t) == pytest.approx(expected)


def test_prediction_interval_is_symmetric_about_the_point_estimate() -> None:
    fit = fm.fit_trend_seasonal(_make_series(), start_month=1)
    point = fm.predict_point(fit, 40)
    lower, upper = fm.predict_interval(fit, 40, confidence_level=0.8)
    assert (point - lower) == pytest.approx(upper - point, abs=1e-9)


def test_prediction_interval_widens_further_from_the_historical_window() -> None:
    """A forecast further into the future should have a wider interval -- the whole point of
    using the leverage-based OLS prediction-interval formula instead of a fixed +/-X% band."""
    # Use noisy data so residual_std > 0 and the leverage term is actually visible.
    rng = np.random.default_rng(7)
    values = [v + n for v, n in zip(_make_series(), rng.normal(0, 5.0, size=36), strict=True)]
    fit = fm.fit_trend_seasonal(values, start_month=1)

    near_lower, near_upper = fm.predict_interval(fit, 36, confidence_level=0.8)
    far_lower, far_upper = fm.predict_interval(fit, 60, confidence_level=0.8)
    assert (far_upper - far_lower) > (near_upper - near_lower)


def test_higher_confidence_level_widens_the_interval() -> None:
    rng = np.random.default_rng(7)
    values = [v + n for v, n in zip(_make_series(), rng.normal(0, 5.0, size=36), strict=True)]
    fit = fm.fit_trend_seasonal(values, start_month=1)

    low_lower, low_upper = fm.predict_interval(fit, 40, confidence_level=0.80)
    high_lower, high_upper = fm.predict_interval(fit, 40, confidence_level=0.99)
    assert (high_upper - high_lower) > (low_upper - low_lower)


def test_predict_interval_rejects_unsupported_confidence_level() -> None:
    fit = fm.fit_trend_seasonal(_make_series(), start_month=1)
    with pytest.raises(ValueError, match="Unsupported confidence_level"):
        fm.predict_interval(fit, 40, confidence_level=0.5)


def test_degenerate_degrees_of_freedom_returns_zero_width_interval() -> None:
    """Constructed directly (bypassing fit_trend_seasonal's MIN_HISTORY_FOR_FIT guard) to
    exercise the defensive branch that model.py's real callers never hit."""
    degenerate = fm.TrendSeasonalFit(
        n_observations=13,
        start_month=1,
        intercept=100.0,
        slope=1.0,
        seasonal_indices=dict.fromkeys(range(1, 13), 0.0),
        residuals=tuple([0.0] * 13),
        residual_std=float("nan"),
        degrees_of_freedom=0,
    )
    point = fm.predict_point(degenerate, 20)
    lower, upper = fm.predict_interval(degenerate, 20, confidence_level=0.8)
    assert lower == pytest.approx(point)
    assert upper == pytest.approx(point)
    assert math.isnan(degenerate.residual_std)
