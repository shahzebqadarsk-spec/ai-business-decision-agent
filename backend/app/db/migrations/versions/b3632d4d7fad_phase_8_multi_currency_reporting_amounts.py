"""phase 8: multi-currency reporting amounts on fact_sales

Adds, alongside the existing native-currency amounts (`unit_price_pkr`,
`net_amount_pkr`, `cogs_amount_pkr` -- kept as-is, holding whatever currency the row's
`currency` column says it's in, see docs/DECISIONS.md), the reporting-currency
equivalents every KPI/RCA/forecast calculation should actually aggregate on, plus the
exact rate used to get there so each converted number carries its own audit trail
(`fx_rate_to_reporting`, `fx_rate_as_of`). Purely additive: existing rows get NULL in
the new columns rather than a migration computing values it can't verify.

Revision ID: b3632d4d7fad
Revises: d5b2db704265
Create Date: 2026-10-12 08:05:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b3632d4d7fad"
down_revision: str | None = "d5b2db704265"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "fact_sales", sa.Column("unit_price_reporting", sa.Numeric(precision=18, scale=4), nullable=True)
    )
    op.add_column(
        "fact_sales", sa.Column("net_amount_reporting", sa.Numeric(precision=18, scale=4), nullable=True)
    )
    op.add_column(
        "fact_sales", sa.Column("cogs_amount_reporting", sa.Numeric(precision=18, scale=4), nullable=True)
    )
    op.add_column(
        "fact_sales", sa.Column("fx_rate_to_reporting", sa.Numeric(precision=18, scale=8), nullable=True)
    )
    op.add_column("fact_sales", sa.Column("fx_rate_as_of", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("fact_sales", "fx_rate_as_of")
    op.drop_column("fact_sales", "fx_rate_to_reporting")
    op.drop_column("fact_sales", "cogs_amount_reporting")
    op.drop_column("fact_sales", "net_amount_reporting")
    op.drop_column("fact_sales", "unit_price_reporting")
