"""Declarative base, naming convention, and small column-helper utilities.

IMPORTANT: SQLAlchemy 2.1's `mapped_column()` silently drops a positional
`CheckConstraint` passed the way legacy `Column()` accepted it. Enum-like
string columns therefore use `enum_column()` for the column itself and
`check_in()` to produce the matching `CheckConstraint` for `__table_args__`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, DateTime, MetaData, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def enum_column(*, length: int = 32, nullable: bool = False, default: str | None = None) -> Mapped[str]:
    """A plain VARCHAR column meant to hold one of a fixed set of string values.

    Use together with `check_in()` in `__table_args__` to actually enforce the set;
    `mapped_column(..., CheckConstraint(...))` does not work reliably in SQLAlchemy 2.1.
    """
    return mapped_column(String(length), nullable=nullable, default=default)


def check_in(column_name: str, values: tuple[str, ...], *, constraint_name: str) -> CheckConstraint:
    allowed = ", ".join(f"'{v}'" for v in values)
    return CheckConstraint(f"{column_name} IN ({allowed})", name=constraint_name)


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
