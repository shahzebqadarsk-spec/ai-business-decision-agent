"""Deterministic time-period resolution.

`fact_sales.month` is always a first-of-month date (see Phase 2's canonical schema), so a
period window is expressed as an inclusive [start_month, end_month] range of first-of-month
dates -- never a day-level range -- and filtering is a plain `BETWEEN` on that column.

Calendar year is currently locked to January-December (Phase 0 decision), but quarter/year
boundaries are derived from `settings.fiscal_year_start_month` rather than hard-coded to 1,
so a later change to that locked decision does not require touching this module.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

GRANULARITIES = ("month", "quarter", "year")
COMPARISON_TYPES = ("YoY", "QoQ", "MoM")

_MONTH_RE = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")
_QUARTER_RE = re.compile(r"^(\d{4})-Q([1-4])$")
_YEAR_RE = re.compile(r"^(\d{4})$")


class InvalidPeriodError(ValueError):
    """The period_key does not match its granularity, or the comparison_type does not
    apply to the given granularity (e.g. MoM requested for a year granularity)."""


@dataclass(frozen=True)
class PeriodWindow:
    granularity: str
    period_key: str
    start_month: date
    end_month: date  # inclusive, also a first-of-month date
    # Phase 9: which client this window's aggregations are scoped to (see
    # app/db/models/clients.py). `None` means "no client filter" -- every
    # `app/kpi/aggregations.py` query ANDs this in only when it is set, so existing
    # callers that never pass a client_id keep their pre-Phase-9 (unscoped) behavior.
    client_id: str | None = None


def _add_months(d: date, months: int) -> date:
    total = (d.year * 12 + (d.month - 1)) + months
    year, month0 = divmod(total, 12)
    return date(year, month0 + 1, 1)


def resolve_period(
    granularity: str,
    period_key: str,
    *,
    fiscal_year_start_month: int = 1,
    client_id: str | None = None,
) -> PeriodWindow:
    """`period_key`'s *year* always labels the fiscal year it falls in (the calendar year
    the fiscal year starts in), matching `resolve_period("year", "2024", ...)`'s own start."""
    if granularity not in GRANULARITIES:
        raise InvalidPeriodError(f"Unknown granularity '{granularity}'; expected one of {GRANULARITIES}.")

    if granularity == "month":
        m = _MONTH_RE.match(period_key)
        if not m:
            raise InvalidPeriodError(f"'{period_key}' is not a valid month period_key (expected YYYY-MM).")
        year, month = int(m.group(1)), int(m.group(2))
        start = date(year, month, 1)
        return PeriodWindow(granularity, period_key, start, start, client_id=client_id)

    if granularity == "quarter":
        m = _QUARTER_RE.match(period_key)
        if not m:
            raise InvalidPeriodError(f"'{period_key}' is not a valid quarter period_key (expected YYYY-Qn).")
        year, quarter = int(m.group(1)), int(m.group(2))
        fiscal_year_start = date(year, fiscal_year_start_month, 1)
        start = _add_months(fiscal_year_start, 3 * (quarter - 1))
        end = _add_months(start, 2)
        return PeriodWindow(granularity, period_key, start, end, client_id=client_id)

    m = _YEAR_RE.match(period_key)
    if not m:
        raise InvalidPeriodError(f"'{period_key}' is not a valid year period_key (expected YYYY).")
    year = int(m.group(1))
    start = date(year, fiscal_year_start_month, 1)
    end = _add_months(start, 11)
    return PeriodWindow(granularity, period_key, start, end, client_id=client_id)


def resolve_comparison_period(
    window: PeriodWindow, comparison_type: str, *, fiscal_year_start_month: int = 1
) -> PeriodWindow:
    if comparison_type not in COMPARISON_TYPES:
        raise InvalidPeriodError(f"Unknown comparison_type '{comparison_type}'.")

    if comparison_type == "YoY":
        shift = -12
    elif comparison_type == "MoM":
        if window.granularity != "month":
            raise InvalidPeriodError("MoM comparison only applies to the 'month' granularity.")
        shift = -1
    else:  # QoQ
        if window.granularity != "quarter":
            raise InvalidPeriodError("QoQ comparison only applies to the 'quarter' granularity.")
        shift = -3

    new_start = _add_months(window.start_month, shift)
    new_end = _add_months(window.end_month, shift)
    comparison_key = _period_key_for(window.granularity, new_start)
    # Inherits the source window's client_id -- a comparison period is always scoped to the
    # same client as the period it's compared against.
    return PeriodWindow(window.granularity, comparison_key, new_start, new_end, client_id=window.client_id)


def _period_key_for(granularity: str, start_month: date) -> str:
    if granularity == "month":
        return f"{start_month.year:04d}-{start_month.month:02d}"
    if granularity == "year":
        return f"{start_month.year:04d}"
    quarter = (start_month.month - 1) // 3 + 1
    return f"{start_month.year:04d}-Q{quarter}"
