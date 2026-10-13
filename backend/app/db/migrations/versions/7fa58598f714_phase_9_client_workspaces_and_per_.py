"""phase 9: client workspaces and per-client data isolation

Adds `clients` (see app/db/models/clients.py) and a nullable, indexed `client_id` FK on
every table a KPI/RCA/forecast/scenario query filters by client: `datasets`,
`fact_sales`, `issues`, `forecast_runs`, `scenarios`. Purely additive, same as Phase 8:
existing rows get NULL (meaning "no client"), which a client-scoped query simply never
matches rather than needing a backfill this migration can't verify.

Revision ID: 7fa58598f714
Revises: b3632d4d7fad
Create Date: 2026-10-13 08:44:28.896731
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7fa58598f714"
down_revision: str | None = "b3632d4d7fad"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_CLIENT_SCOPED_TABLES = ("datasets", "fact_sales", "forecast_runs", "issues", "scenarios")


def upgrade() -> None:
    op.create_table(
        "clients",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("reporting_currency", sa.String(length=8), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_clients")),
    )
    for table in _CLIENT_SCOPED_TABLES:
        op.add_column(table, sa.Column("client_id", sa.Uuid(), nullable=True))
        op.create_index(op.f(f"ix_{table}_client_id"), table, ["client_id"], unique=False)
        op.create_foreign_key(
            op.f(f"fk_{table}_client_id_clients"),
            table,
            "clients",
            ["client_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    for table in reversed(_CLIENT_SCOPED_TABLES):
        op.drop_constraint(op.f(f"fk_{table}_client_id_clients"), table, type_="foreignkey")
        op.drop_index(op.f(f"ix_{table}_client_id"), table_name=table)
        op.drop_column(table, "client_id")
    op.drop_table("clients")
