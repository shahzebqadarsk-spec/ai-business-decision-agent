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
    unit_price_pkr: Mapped[float] = mapped_column(Numeric(18, 4))
    gross_amount_pkr: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    net_amount_pkr: Mapped[float] = mapped_column(Numeric(18, 4))
    cogs_amount_pkr: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    gross_margin_pct: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    discount_pct: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    payment_terms: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # ISO 4217 code for the currency the _pkr-suffixed amounts above are actually in for
    # this row (despite the column names -- see docs/DECISIONS.md phase 8). Populated by
    # materialize.py for every new row: from a confirmed `currency` mapping, else detected
    # from the price text itself, else the deployment's configured default currency.
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)

    # --- reporting-currency equivalents (Phase 8: multi-currency support) ----------------
    # Every KPI/RCA/forecast calculation aggregates on these, never on the _pkr fields
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
