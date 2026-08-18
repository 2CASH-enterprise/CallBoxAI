"""
Endpoints Tickets de service client (section 1 et 12 du cahier des charges).
Créés automatiquement pour les appels entrants d'un agent avec
ticketing_enabled=True — voir app.core.call_pipeline.
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_organization_access
from app.models.ticket import Ticket, VALID_PRIORITIES, VALID_STATUSES

router = APIRouter()


class TicketUpdate(BaseModel):
    status: str | None = None
    priority: str | None = None
    resolution_notes: str | None = None


class TicketOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    agent_id: uuid.UUID
    call_id: uuid.UUID | None
    contact_id: uuid.UUID | None
    subject: str
    category: str | None
    priority: str
    status: str
    description: str | None
    resolution_notes: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


@router.get("/tickets", response_model=list[TicketOut])
def list_tickets(
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    return (
        db.query(Ticket)
        .filter(Ticket.organization_id == organization_id)
        .order_by(Ticket.created_at.desc())
        .all()
    )


@router.patch("/tickets/{ticket_id}", response_model=TicketOut)
def update_ticket(
    ticket_id: uuid.UUID,
    payload: TicketUpdate,
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.organization_id == organization_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket introuvable pour cette organisation")

    if payload.status is not None:
        if payload.status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail="Statut invalide")
        ticket.status = payload.status
    if payload.priority is not None:
        if payload.priority not in VALID_PRIORITIES:
            raise HTTPException(status_code=400, detail="Priorité invalide")
        ticket.priority = payload.priority
    if payload.resolution_notes is not None:
        ticket.resolution_notes = payload.resolution_notes

    db.commit()
    db.refresh(ticket)
    return ticket
