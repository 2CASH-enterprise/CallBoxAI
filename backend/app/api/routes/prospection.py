"""
Prospection commerciale B2C/B2B (section 42 du cahier des charges) :
- Consultation du journal WhatsApp (mode Mock, comme pour les SMS).
- Outils en direct appelés par Retell pendant l'appel : envoi d'une
  brochure/offre par WhatsApp, et réservation d'un rendez-vous (B2B
  uniquement — l'IA réserve elle-même, contrairement au B2C où l'intérêt
  est simplement transmis à un commercial humain).
"""
import logging
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_organization_access
from app.core.providers import get_messaging_provider
from app.models.appointment import Appointment
from app.models.contact import Contact
from app.models.whatsapp_log import WhatsAppLog

logger = logging.getLogger(__name__)

router = APIRouter(tags=["prospection"])


# ---------- Journal WhatsApp (consultation dashboard) ----------

class WhatsAppLogOut(BaseModel):
    id: uuid.UUID
    to_number: str
    body: str
    provider: str
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/whatsapp", response_model=list[WhatsAppLogOut])
def list_whatsapp(
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    return (
        db.query(WhatsAppLog)
        .filter(WhatsAppLog.organization_id == organization_id)
        .order_by(WhatsAppLog.created_at.desc())
        .all()
    )


# ---------- Outil en direct : envoi WhatsApp ----------

class SendWhatsAppRequest(BaseModel):
    guest_phone: str
    content_summary: str  # ce que l'agent veut transmettre (offre, brochure, cas client...)
    guest_name: str | None = None


@router.post("/prospection/tools/send-whatsapp")
def tool_send_whatsapp(
    payload: SendWhatsAppRequest,
    organization_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
):
    """
    Envoie par WhatsApp un résumé/brochure/offre au prospect intéressé, EN
    DIRECT pendant l'appel. Le contact est retrouvé (ou créé) par téléphone
    — même logique que les outils PMS/KYC (section 18).
    """
    logger.info("Outil send_whatsapp appelé : org=%s guest_phone=%r", organization_id, payload.guest_phone)

    contact = db.query(Contact).filter(
        Contact.organization_id == organization_id, Contact.phone == payload.guest_phone
    ).first()
    if not contact:
        contact = Contact(organization_id=organization_id, phone=payload.guest_phone, first_name=payload.guest_name)
        db.add(contact)
        db.flush()

    try:
        from app.providers.whatsapp.mock import MockWhatsAppProvider

        provider = MockWhatsAppProvider(db, organization_id)
        body = f"Bonjour{f' {payload.guest_name}' if payload.guest_name else ''}, voici l'information demandée suite à notre appel : {payload.content_summary}"
        provider.send_message(to_number=payload.guest_phone, body=body)
        sent = True
    except Exception:
        logger.exception("send_whatsapp : échec de l'envoi")
        sent = False

    db.commit()
    if not sent:
        return {"success": False, "error": "Échec de l'envoi WhatsApp. Réessayez ou transférez à un opérateur."}
    return {"success": True, "message": "Message WhatsApp envoyé."}


# ---------- Outil en direct : réservation de rendez-vous (B2B) ----------

class BookMeetingRequest(BaseModel):
    guest_phone: str
    guest_name: str | None = None
    scheduled_at: str  # ISO datetime
    duration_minutes: int = 30
    notes: str | None = None


@router.post("/prospection/tools/book-meeting")
def tool_book_meeting(
    payload: BookMeetingRequest,
    organization_id: uuid.UUID = Query(...),
    agent_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
):
    """
    Réserve directement un rendez-vous commercial (B2B, section 42) dans le
    calendrier de l'équipe — contrairement au B2C, où l'IA ne réserve jamais
    rien elle-même. Rejette les créneaux déjà pris (calendrier partagé par
    toute l'organisation, pas par agent) pour éviter un double-booking.
    """
    logger.info(
        "Outil book_meeting appelé : org=%s guest_phone=%r scheduled_at=%r",
        organization_id, payload.guest_phone, payload.scheduled_at,
    )

    try:
        scheduled_at = datetime.fromisoformat(payload.scheduled_at)
    except ValueError:
        return {"success": False, "error": "Format de date invalide (attendu ISO 8601)."}

    if scheduled_at < datetime.utcnow():
        return {"success": False, "error": "Ce créneau est déjà passé."}

    new_end = scheduled_at + timedelta(minutes=payload.duration_minutes)
    existing = (
        db.query(Appointment)
        .filter(Appointment.organization_id == organization_id, Appointment.status != "cancelled")
        .all()
    )
    for appt in existing:
        appt_end = appt.scheduled_at + timedelta(minutes=appt.duration_minutes or 30)
        if scheduled_at < appt_end and appt.scheduled_at < new_end:
            return {"success": False, "error": "Ce créneau est déjà pris. Proposez un autre horaire."}

    contact = db.query(Contact).filter(
        Contact.organization_id == organization_id, Contact.phone == payload.guest_phone
    ).first()
    if not contact:
        contact = Contact(organization_id=organization_id, phone=payload.guest_phone, first_name=payload.guest_name)
        db.add(contact)
        db.flush()

    appointment = Appointment(
        organization_id=organization_id,
        agent_id=agent_id,
        contact_id=contact.id,
        scheduled_at=scheduled_at,
        duration_minutes=payload.duration_minutes,
        status="scheduled",
        notes=payload.notes,
    )
    db.add(appointment)
    db.commit()
    db.refresh(appointment)

    return {"success": True, "appointment_id": str(appointment.id), "scheduled_at": payload.scheduled_at}
