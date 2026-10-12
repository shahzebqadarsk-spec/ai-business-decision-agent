from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin, enum_column


class Recommendation(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "recommendations"
    __table_args__ = (
        CheckConstraint(
            "(status != 'approved') OR (approved_by IS NOT NULL AND approved_at IS NOT NULL)",
            name="approved_requires_approver_and_timestamp",
        ),
    )

    title: Mapped[str] = mapped_column(String(255))
    narrative: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = enum_column(length=32, default="draft")
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evidence_refs: Mapped[list[object]] = mapped_column(JSON, default=list)


class VerificationReport(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "verification_reports"

    recommendation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    passed: Mapped[bool] = mapped_column(default=True)
    checks: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
