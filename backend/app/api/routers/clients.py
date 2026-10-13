"""Phase 9: Client/Workspace API. A `Client` is the unit of per-tenant data isolation --
see `app.db.models.clients.Client` for the full rationale. This router only ever creates
and lists clients; a client's `reporting_currency` is never set here by hand -- it starts
NULL and is resolved automatically from that client's own first materialized upload
(`app.ingestion.materialize.detect_dominant_currency`, called from the ingestion router's
`/datasets/files/{file_id}/materialize` endpoint).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.api.schemas.clients import ClientCreate, ClientOut
from app.audit import record_audit
from app.db.models.clients import Client

router = APIRouter(prefix="/clients", tags=["clients"])


def get_client_or_404(session: Session, client_id: UUID) -> Client:
    client = session.get(Client, client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Client not found.")
    return client


@router.post("", response_model=ClientOut, status_code=status.HTTP_201_CREATED)
def create_client(body: ClientCreate, session: Session = Depends(get_db_session)) -> Client:
    client = Client(name=body.name)
    session.add(client)
    session.commit()
    record_audit(
        session, actor="api", action="create_client", entity_type="client", entity_id=str(client.id)
    )
    return client


@router.get("", response_model=list[ClientOut])
def list_clients(session: Session = Depends(get_db_session)) -> list[Client]:
    return list(session.query(Client).order_by(Client.created_at.desc()).all())


@router.get("/{client_id}", response_model=ClientOut)
def get_client(client_id: UUID, session: Session = Depends(get_db_session)) -> Client:
    return get_client_or_404(session, client_id)
