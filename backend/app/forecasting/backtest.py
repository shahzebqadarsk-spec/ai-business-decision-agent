"""Holdout backtest diagnostic for the trend+seasonal model (Phase 5).

Purely diagnostic: refits the model on history minus the last `holdout_periods` observations,
"forecasts" those held-out periods, and reports MAE/MAPE against what actually happened. This
is stored on the `ForecastRun` so a person using a forecast can see how the model performed on
data it never got to see, rather than taking "the fit looks good" on faith -- mirrors Phase
4's "independent validation" principle (test against independently-computed expectations),
applied here as a live, persisted diagnostic rather than only a test-time check.

This never changes which fit produces the delivered forecast -- that one (`engine.py`) is
always refit on the *complete* history after this diagnostic has already been computed.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.forecasting.model import MIN_HISTORY_FOR_FIT, fit_trend_seasonal, predict_point

DEFAULT_HOLDOUT_PERIODS = 6


@dataclass(frozen=True)
class BacktestResult:
    holdout_periods: int
    mae: float
    mape_pct: float | None
    """`None` -- not a fabricated 0% -- when every held-out actual is exactly 0, which makes a
    percentage error undefined rather than infinite or zero."""


def run_backtest(
    values: list[float], start_month: int, *, holdout_periods: int = DEFAULT_HOLDOUT_PERIODS
) -> BacktestResult | None:
    """Returns `None` when there isn't enough history to both hold out `holdout_periods`
    observations *and* still have >= `MIN_HISTORY_FOR_FIT` left to fit the holdout model on --
    never a backtest computed on too little data just to produce a number."""
    n = len(values)
    train_size = n - holdout_periods
    if holdout_periods <= 0 or train_size < MIN_HISTORY_FOR_FIT:
        return None

    train = values[:train_size]
    actual_holdout = values[train_size:]
    fit = fit_trend_seasonal(train, start_month)

    errors: list[float] = []
    pct_errors: list[float] = []
    for i, actual in enumerate(actual_holdout):
        predicted = predict_point(fit, train_size + i)
        errors.append(abs(actual - predicted))
        if actual != 0:
            pct_errors.append(abs(actual - predicted) / abs(actual) * 100)

    mae = sum(errors) / len(errors)
    mape = sum(pct_errors) / len(pct_errors) if pct_errors else None
    return BacktestResult(holdout_periods=holdout_periods, mae=mae, mape_pct=mape)


__all__ = ["DEFAULT_HOLDOUT_PERIODS", "BacktestResult", "run_backtest"]
