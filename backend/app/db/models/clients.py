"""Phase 9: per-client data isolation.

Before this phase, every uploaded dataset's rows pooled into one shared `fact_sales`
table forever -- there was no way to tell "this revenue figure is customer A's" from
"this revenue figure is everyone's, summed together" (see docs/DECISIONS.md). A
`Client` is the unit of isolation: every `Dataset`, and every `fact_sales` row
materialized from it, is tagged with exactly one `client_id`, and every KPI/RCA/
forecast/scenario query is scoped to one client at a time. `client_id=None` on those
queries means "no filter", kept only for backward compatibility with pre-Phase-9 rows
that have no client at all -- a fresh deployment should never produce new rows like that.

`reporting_currency` starts NULL and is resolved automatically from the client's own
first materialized upload (`app/ingestion/materialize.detect_dominant_currency`) --
never configured by hand, and never the old global `CURRENCY` env var, which stays only
as the deployment-wide fallback for a file that gives no currency signal at all.
"""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class Client(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "clients"

    name: Mapped[str] = mapped_column(String(255))
    # ISO 4217 code, resolved once from this client's first materialized upload (see
    # app/ingestion/materialize.py). NULL until then -- a client with no data yet has no
    # currency to report in.
    reporting_currency: Mapped[str | None] = mapped_column(String(8), nullable=True)


__all__ = ["Client"]
