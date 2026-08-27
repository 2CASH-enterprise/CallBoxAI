"""
Endpoints Tickets de service client (section 1 et 12 du cahier des charges).
Créés automatiquement pour les appels entrants d'un agent avec
ticketing_enabled=True — voir app.core.call_pipeline.
"""
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_organization_access
from app.core.providers import get_messaging_provider
from app.models.ticket import Ticket, VALID_PRIORITIES, VALID_STATUSES
from app.models.contact import Contact

logger = logging.getLogger(__name__)

router = APIRouter()


class TicketUpdate(BaseModel):
    status: str | None = None
    priority: str | None = None
    resolution_notes: str | None = None
    assigned_to: str | None = None


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
    assigned_to: str | None
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

        # Notifie le client par SMS dès que son ticket passe à "résolu"
        # (section 12) — jusqu'ici, aucun des quatre statuts ne redonnait
        # jamais de nouvelles au client une fois l'appel terminé, contrairement
        # à tous les autres cas d'usage (hôtel, télécom...) qui bouclent la
        # boucle par SMS/email/WhatsApp. Résilience (section 29) : un échec
        # d'envoi ne doit jamais empêcher la résolution du ticket.
        if payload.status == "résolu" and ticket.status != "résolu" and ticket.contact_id:
            contact = db.query(Contact).filter(Contact.id == ticket.contact_id).first()
            if contact and contact.phone:
                try:
                    provider = get_messaging_provider(db, organization_id)
                    body = f"Bonjour, votre demande \"{ticket.subject}\" a été traitée."
                    if payload.resolution_notes:
                        body += f" {payload.resolution_notes}"
                    body += " Merci de nous avoir contactés."
                    provider.send_sms(to_number=contact.phone, body=body)
                except Exception:
                    logger.exception("Échec de la notification SMS de résolution pour le ticket %s", ticket.id)

        ticket.status = payload.status
    if payload.priority is not None:
        if payload.priority not in VALID_PRIORITIES:
            raise HTTPException(status_code=400, detail="Priorité invalide")
        ticket.priority = payload.priority
    if payload.resolution_notes is not None:
        ticket.resolution_notes = payload.resolution_notes
    if payload.assigned_to is not None:
        ticket.assigned_to = payload.assigned_to

    db.commit()
    db.refresh(ticket)
    return ticket


# ---------- Outil en direct : consultation de ticket (section 12) ----------

class TicketLookupRequest(BaseModel):
    guest_phone: str


class TicketLookupResultOut(BaseModel):
    subject: str
    status: str
    priority: str
    created_at: datetime


@router.post("/tickets/tools/lookup")
def tool_lookup_tickets(
    payload: TicketLookupRequest,
    organization_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
):
    """
    Consulte les tickets existants d'un client, EN DIRECT pendant l'appel
    (section 12) — jusqu'ici, l'agent n'avait aucun moyen de répondre à un
    client qui rappelle pour connaître l'état d'une demande déjà ouverte.
    """
    logger.info("Outil lookup_tickets appelé : org=%s guest_phone=%r", organization_id, payload.guest_phone)
    contact = db.query(Contact).filter(
        Contact.organization_id == organization_id, Contact.phone == payload.guest_phone
    ).first()
    if not contact:
        return {"found": False, "tickets": []}

    tickets = (
        db.query(Ticket)
        .filter(Ticket.organization_id == organization_id, Ticket.contact_id == contact.id)
        .order_by(Ticket.created_at.desc())
        .limit(5)
        .all()
    )
    if not tickets:
        return {"found": False, "tickets": []}

    return {
        "found": True,
        "tickets": [
            {"subject": t.subject, "status": t.status, "priority": t.priority, "created_at": t.created_at.isoformat()}
            for t in tickets
        ],
    }
