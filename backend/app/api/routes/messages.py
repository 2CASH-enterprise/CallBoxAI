"""
Endpoints Messages (télé-secrétariat — section 12 du cahier des charges).
Créés automatiquement quand un appel entrant arrive hors des horaires
d'ouverture de l'agent (voir app.core.call_pipeline.is_within_business_hours).
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_organization_access
from app.models.message import Message

router = APIRouter()

VALID_STATUSES = {"new", "read", "handled"}


class MessageUpdate(BaseModel):
    status: str


class MessageOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    agent_id: uuid.UUID
    call_id: uuid.UUID | None
    contact_id: uuid.UUID | None
    caller_phone: str
    caller_name: str | None
    content: str
    urgent: bool
    callback_requested: bool
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/messages", response_model=list[MessageOut])
def list_messages(
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    return (
        db.query(Message)
        .filter(Message.organization_id == organization_id)
        .order_by(Message.created_at.desc())
        .all()
    )


@router.patch("/messages/{message_id}", response_model=MessageOut)
def update_message(
    message_id: uuid.UUID,
    payload: MessageUpdate,
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    if payload.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail="Statut invalide")

    message = db.query(Message).filter(
        Message.id == message_id, Message.organization_id == organization_id
    ).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message introuvable pour cette organisation")

    message.status = payload.status
    db.commit()
    db.refresh(message)
    return message
