"""Typed canonical fact table(s). Replaces the generic `CanonicalRecord` JSONB placeholder
from Phase 0 for the one canonical table Phase 2 actually materializes into (`fact_sales`) --
see docs/DECISIONS.md for why the scope is one fact table, not a full fact/dim warehouse.

Every row carries row-level lineage (`source_file_id`, `source_row_number`) back to the
exact raw upload and line it came from, in addition to the file-level lineage `datasets.py`
already has via `DatasetFile.dataset_id`.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class FactSales(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "fact_sales"

    # --- lineage: exactly which raw file and row this canonical row came from -----------
    source_file_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("dataset_files.id", ondelete="CASCADE"), index=True
    )
    source_row_number: Mapped[int] = mapped_column(Integer)

    # Phase 9: which client this row belongs to, denormalized here (not just reachable via
    # source_file_id -> dataset_id) because every KPI/RCA/forecast aggregation query filters
    # on this column directly -- see app/kpi/aggregations.py. Nullable only for backward
    # compatibility with pre-Phase-9 rows, which a client-scoped query simply never matches.
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("clients.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # --- canonical business fields -------------------------------------------------------
    sale_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    month: Mapped[date] = mapped_column(Date)
    order_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    invoice_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    customer_id: Mapped[str] = mapped_column(String(64), index=True)
    region_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    product_id: Mapped[str] = mapped_column(String(64), index=True)
    category_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    quantity: Mapped[float] = mapped_column(Numeric(18, 4))
    # Phase 9.1: these were named *_pkr back when the system only ever supported PKR;
    # renamed to drop that suffix now that multi-currency/multi-client is real (see
    # docs/DECISIONS.md) -- the value was never actually forced into PKR, only the label
    # implied it. `currency` below is what actually says what currency a row's raw amounts
    # are in.
    unit_price: Mapped[float] = mapped_column(Numeric(18, 4))
    gross_amount: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    net_amount: Mapped[float] = mapped_column(Numeric(18, 4))
    cogs_amount: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    gross_margin_pct: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    discount_pct: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    payment_terms: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # ISO 4217 code for the currency the raw amounts above are actually in for this row.
    # Populated by materialize.py for every new row: from a confirmed `currency` mapping,
    # else detected from the price text itself, else the deployment's configured default.
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)

    # --- reporting-currency equivalents (Phase 8: multi-currency support) ----------------
    # Every KPI/RCA/forecast calculation aggregates on these, never on the raw columns
    # above directly -- that's what makes mixing PKR and USD rows in one dataset safe to
    # sum. NULL on rows materialized before Phase 8 (purely additive migration).
    unit_price_reporting: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    net_amount_reporting: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    cogs_amount_reporting: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    # The multiplier actually used for this row's conversion (native -> reporting), and
    # the date the static rate table (app/fx/rates.py) was last reviewed when it was
    # used -- an audit trail, not a black box.
    fx_rate_to_reporting: Mapped[float | None] = mapped_column(Numeric(18, 8), nullable=True)
    fx_rate_as_of: Mapped[date | None] = mapped_column(Date, nullable=True)
