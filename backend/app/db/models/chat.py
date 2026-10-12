from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin, enum_column


class Conversation(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "conversations"

    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_id: Mapped[str | None] = mapped_column(Text, nullable=True)


class Message(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = enum_column(length=16, default="user")
    content: Mapped[str] = mapped_column(Text)
