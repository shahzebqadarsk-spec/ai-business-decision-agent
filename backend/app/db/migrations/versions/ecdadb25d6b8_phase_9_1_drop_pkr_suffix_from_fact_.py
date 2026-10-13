"""phase 9.1: drop "_pkr" suffix from fact_sales money columns

These columns (`unit_price_pkr`, `gross_amount_pkr`, `net_amount_pkr`, `cogs_amount_pkr`)
were named back when the system only ever supported PKR. The value stored was never
actually forced into PKR -- `currency` (Phase 8) always said what currency a row's raw
amounts were really in, and `*_reporting` holds the converted figure every KPI/RCA/
forecast calculation actually aggregates on. Only the label was stale and confusing once
multi-currency/multi-client (Phase 8/9) became real. A plain column rename (not a
drop+add), so every existing row's data is preserved exactly as-is.

Revision ID: ecdadb25d6b8
Revises: 7fa58598f714
Create Date: 2026-10-13 09:37:17.439682
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "ecdadb25d6b8"
down_revision: str | None = "7fa58598f714"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_RENAMES = (
    ("unit_price_pkr", "unit_price"),
    ("gross_amount_pkr", "gross_amount"),
    ("net_amount_pkr", "net_amount"),
    ("cogs_amount_pkr", "cogs_amount"),
)


def upgrade() -> None:
    for old_name, new_name in _RENAMES:
        op.alter_column("fact_sales", old_name, new_column_name=new_name)


def downgrade() -> None:
    for old_name, new_name in _RENAMES:
        op.alter_column("fact_sales", new_name, new_column_name=old_name)
