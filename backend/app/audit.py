from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models.operations import AuditLog


def record_audit(
    session: Session,
    *,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: str,
    details: dict[str, object] | None = None,
) -> None:
    session.add(
        AuditLog(
            actor=actor, action=action, entity_type=entity_type, entity_id=entity_id, details=details or {}
        )
    )
    session.commit()
