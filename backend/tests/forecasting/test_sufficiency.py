"""DB-backed tests for app/forecasting/sufficiency.py against the real seed-42 dataset
(36 contiguous months), plus pure gap-detection tests against a throwaway table-free check."""

from __future__ import annotations

from datetime import date

import pytest
from app.db.models.canonical import FactSales
from app.forecasting import sufficiency as suf
from sqlalchemy import delete
from sqlalchemy.orm import Session

pytestmark = pytest.mark.usefixtures("seeded_fact_sales_file_id")


def test_full_seed42_history_is_sufficient(db_session: Session) -> None:
    result = suf.check_history_sufficiency(db_session, FactSales.net_amount_pkr)
    assert result.status == "sufficient"
    assert len(result.history) == 36
    assert result.history[0][0] == "2023-01"
    assert result.history[-1][0] == "2025-12"
    assert result.start_month == 1


def test_empty_table_is_insufficient(db_session: Session) -> None:
    db_session.execute(delete(FactSales))
    db_session.flush()
    result = suf.check_history_sufficiency(db_session, FactSales.net_amount_pkr)
    assert result.status == "insufficient_data"
    assert "No fact_sales rows" in (result.reason or "")
    db_session.rollback()  # never commit the delete -- other tests in this session need the data


def test_a_gap_in_the_middle_of_history_is_detected(db_session: Session) -> None:
    """Deletes one real calendar month's worth of rows from the middle of the seed-42 range
    (contiguous, no gaps by construction) to prove the gap check actually fires, then rolls
    back so the shared session-scoped fixture is untouched for later tests."""
    db_session.execute(delete(FactSales).where(FactSales.month == date(2024, 6, 1)))
    db_session.flush()
    result = suf.check_history_sufficiency(db_session, FactSales.net_amount_pkr)
    assert result.status == "insufficient_data"
    assert "gaps" in (result.reason or "")
    assert "2024-06" in (result.reason or "")
    db_session.rollback()


def test_insufficient_total_history_below_minimum(db_session: Session) -> None:
    """Keeps only the first 12 months (well under MIN_HISTORY_PERIODS=24)."""
    db_session.execute(delete(FactSales).where(FactSales.month >= date(2024, 1, 1)))
    db_session.flush()
    result = suf.check_history_sufficiency(db_session, FactSales.net_amount_pkr)
    assert result.status == "insufficient_data"
    assert "Only 12 month" in (result.reason or "")
    db_session.rollback()
