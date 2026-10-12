"""Pure unit tests for app/forecasting/backtest.py -- no DB needed."""

from __future__ import annotations

import numpy as np
import pytest
from app.forecasting import backtest as bt
from app.forecasting import model as fm


def _series(n: int, *, noise_seed: int | None = None, noise_std: float = 0.0) -> list[float]:
    base = [100.0 + 2.0 * t + (10.0 if t % 12 in (5, 6) else -5.0) for t in range(n)]
    if noise_seed is None or noise_std == 0.0:
        return base
    rng = np.random.default_rng(noise_seed)
    return [v + n for v, n in zip(base, rng.normal(0, noise_std, size=len(base)), strict=True)]


def test_run_backtest_returns_none_when_too_little_history_to_hold_out() -> None:
    # 24 (MIN_HISTORY_FOR_FIT) + default 6 holdout - 1, so train_size would fall just short.
    values = _series(fm.MIN_HISTORY_FOR_FIT + bt.DEFAULT_HOLDOUT_PERIODS - 1)
    assert bt.run_backtest(values, start_month=1) is None


def test_run_backtest_returns_a_result_once_there_is_exactly_enough_history() -> None:
    values = _series(fm.MIN_HISTORY_FOR_FIT + bt.DEFAULT_HOLDOUT_PERIODS)
    result = bt.run_backtest(values, start_month=1)
    assert result is not None
    assert result.holdout_periods == bt.DEFAULT_HOLDOUT_PERIODS
    assert result.mae >= 0


def test_run_backtest_mae_is_small_for_a_noise_free_series() -> None:
    """Not exactly 0: this helper's seasonal pattern is not the orthogonal-safe one
    test_model.py uses, so the classical two-stage fit carries a small, deterministic
    trend/seasonal confound bias even with no noise (see test_model.py's TRUE_SEASONAL
    comment) -- the bound here is generous precisely because exactness isn't the property
    being tested, boundedness is."""
    values = _series(36)
    result = bt.run_backtest(values, start_month=1)
    assert result is not None
    assert result.mae < 2.0
    assert result.mape_pct is not None
    assert result.mape_pct < 5.0


def test_run_backtest_mae_cross_checked_against_independent_computation() -> None:
    values = _series(36, noise_seed=3, noise_std=5.0)
    result = bt.run_backtest(values, start_month=1, holdout_periods=6)
    assert result is not None

    train = values[:30]
    actual = values[30:]
    fit = fm.fit_trend_seasonal(train, start_month=1)
    expected_errors = [abs(actual[i] - fm.predict_point(fit, 30 + i)) for i in range(6)]
    expected_mae = sum(expected_errors) / len(expected_errors)
    expected_mape = sum(e / abs(a) * 100 for e, a in zip(expected_errors, actual, strict=True)) / 6

    assert result.mae == pytest.approx(expected_mae, abs=1e-9)
    assert result.mape_pct == pytest.approx(expected_mape, abs=1e-9)


def test_run_backtest_zero_holdout_periods_returns_none() -> None:
    assert bt.run_backtest(_series(36), start_month=1, holdout_periods=0) is None


def test_run_backtest_mape_is_none_when_every_held_out_actual_is_zero() -> None:
    values = [0.0] * 30 + [100.0 * t for t in range(6)]  # train is all-zero revenue, degenerate
    # Use a flat non-zero train so fit_trend_seasonal doesn't choke, but all-zero actuals.
    values = [10.0] * 30 + [0.0] * 6
    result = bt.run_backtest(values, start_month=1, holdout_periods=6)
    assert result is not None
    assert result.mape_pct is None
    assert result.mae >= 0
