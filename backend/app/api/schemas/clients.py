from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ClientCreate(BaseModel):
    name: str


class ClientOut(BaseModel):
    id: UUID
    name: str
    reporting_currency: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
