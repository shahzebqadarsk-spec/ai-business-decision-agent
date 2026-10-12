from __future__ import annotations

from datetime import date

import pytest
from app.kpi.periods import InvalidPeriodError, resolve_comparison_period, resolve_period


def test_month_period_resolves_to_first_of_month() -> None:
    window = resolve_period("month", "2024-03")
    assert window.start_month == date(2024, 3, 1)
    assert window.end_month == date(2024, 3, 1)


def test_quarter_period_spans_three_months() -> None:
    window = resolve_period("quarter", "2024-Q1")
    assert window.start_month == date(2024, 1, 1)
    assert window.end_month == date(2024, 3, 1)


def test_quarter_4_spans_oct_to_dec() -> None:
    window = resolve_period("quarter", "2024-Q4")
    assert window.start_month == date(2024, 10, 1)
    assert window.end_month == date(2024, 12, 1)


def test_year_period_spans_twelve_months() -> None:
    window = resolve_period("year", "2024")
    assert window.start_month == date(2024, 1, 1)
    assert window.end_month == date(2024, 12, 1)


def test_invalid_month_key_rejected() -> None:
    with pytest.raises(InvalidPeriodError):
        resolve_period("month", "2024-13")


def test_invalid_quarter_key_rejected() -> None:
    with pytest.raises(InvalidPeriodError):
        resolve_period("quarter", "2024-Q5")


def test_unknown_granularity_rejected() -> None:
    with pytest.raises(InvalidPeriodError):
        resolve_period("week", "2024-W1")


def test_yoy_comparison_shifts_back_one_year() -> None:
    window = resolve_period("year", "2024")
    comparison = resolve_comparison_period(window, "YoY")
    assert comparison.period_key == "2023"
    assert comparison.start_month == date(2023, 1, 1)


def test_mom_comparison_crosses_year_boundary() -> None:
    window = resolve_period("month", "2024-01")
    comparison = resolve_comparison_period(window, "MoM")
    assert comparison.period_key == "2023-12"


def test_qoq_comparison_crosses_year_boundary() -> None:
    window = resolve_period("quarter", "2024-Q1")
    comparison = resolve_comparison_period(window, "QoQ")
    assert comparison.period_key == "2023-Q4"


def test_mom_rejected_for_year_granularity() -> None:
    window = resolve_period("year", "2024")
    with pytest.raises(InvalidPeriodError):
        resolve_comparison_period(window, "MoM")


def test_qoq_rejected_for_month_granularity() -> None:
    window = resolve_period("month", "2024-01")
    with pytest.raises(InvalidPeriodError):
        resolve_comparison_period(window, "QoQ")


def test_fiscal_year_start_month_shifts_year_window() -> None:
    window = resolve_period("year", "2024", fiscal_year_start_month=7)
    assert window.start_month == date(2024, 7, 1)
    assert window.end_month == date(2025, 6, 1)
