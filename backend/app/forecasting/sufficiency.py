"""Deterministic data-sufficiency gate for forecasting (Phase 5).

A forecast must never be produced from too little or gapped history -- mirrors Phase 3's own
KPI-sufficiency philosophy and Phase 4's "never manufacture a result" rule for RCA.
`check_history_sufficiency()` is the one gate every metric's forecast goes through before
`app/forecasting/model.py` ever sees the data; it always evaluates the *complete* available
canonical history (there is no caller-chosen window for forecasting -- unlike a KPI or an
issue, a forecast is not "for a period", it is "as of now, using everything available").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.kpi import aggregations as agg
from app.kpi.periods import PeriodWindow

MIN_HISTORY_PERIODS = 24  # 2 full annual cycles -- see app/forecasting/model.py


def _add_month(d: date) -> date:
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    return date(d.year, d.month + 1, 1)


@dataclass(frozen=True)
class HistorySufficiencyResult:
    status: str  # "sufficient" | "insufficient_data"
    reason: str | None = None
    history: tuple[tuple[str, float], ...] = field(default_factory=tuple)
    start_month: int = 1
    window: PeriodWindow | None = None


def check_history_sufficiency(session: Session, column: Any) -> HistorySufficiencyResult:
    month_range = agg.full_month_range(session)
    if month_range is None:
        return HistorySufficiencyResult(status="insufficient_data", reason="No fact_sales rows found at all.")
    start, end = month_range
    window = PeriodWindow(granularity="month", period_key="all", start_month=start, end_month=end)
    rows = agg.sum_by_month_bucket(session, column, window)

    expected_months = []
    cursor = start
    while cursor <= end:
        expected_months.append(f"{cursor.year:04d}-{cursor.month:02d}")
        cursor = _add_month(cursor)

    actual_months = [r[0] for r in rows]
    if actual_months != expected_months:
        missing = sorted(set(expected_months) - set(actual_months))
        shown = ", ".join(missing[:5])
        more = f" and {len(missing) - 5} more" if len(missing) > 5 else ""
        return HistorySufficiencyResult(
            status="insufficient_data",
            reason=f"Canonical history has gaps -- missing month(s): {shown}{more}.",
        )

    if len(rows) < MIN_HISTORY_PERIODS:
        return HistorySufficiencyResult(
            status="insufficient_data",
            reason=(
                f"Only {len(rows)} month(s) of history available; need at least "
                f"{MIN_HISTORY_PERIODS} (2 full annual cycles) to fit a seasonal model."
            ),
        )

    return HistorySufficiencyResult(
        status="sufficient", history=tuple(rows), start_month=start.month, window=window
    )


__all__ = ["MIN_HISTORY_PERIODS", "HistorySufficiencyResult", "check_history_sufficiency"]
