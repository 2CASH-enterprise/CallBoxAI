"""
Endpoints PMS (Property Management System — section 5/16 du cahier des
charges), via l'abstraction PMSProvider. Deux familles d'endpoints :

- /pms/availability, /pms/reservations : utilisés par le DASHBOARD (staff de
  l'hôtel), protégés par JWT comme le reste de la plateforme.
- /pms/tools/... : utilisés par RETELL PENDANT UN VRAI APPEL (function
  calling, section 16), donc SANS JWT — Retell ne peut pas s'authentifier
  comme un utilisateur du dashboard. Scopés par organization_id en query
  param (configuré une fois pour toutes au provisionnement de l'agent, voir
  app.api.routes.agents et app.providers.voice.retell_provider).
"""
import logging
import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import require_organization_access
from app.models.appointment import Appointment
from app.models.contact import Contact
from app.providers.pms.mock import MockPMSProvider
from app.providers.email.mock import MockEmailProvider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pms", tags=["pms"])

# Toujours Mock pour l'instant (section 40) — aucun connecteur réel (Mews,
# Cloudbeds...) n'est encore branché ; voir app.providers.pms.base pour
# l'abstraction prête à les recevoir.
pms_provider = MockPMSProvider()


class AvailabilityRequest(BaseModel):
    check_in: date
    check_out: date
    room_type: str | None = None


class AvailabilityOffer(BaseModel):
    room_type: str
    rate_per_night: float
    total_price: float
    rooms_available: int
    currency: str


class ReservationRequest(BaseModel):
    contact_id: uuid.UUID
    check_in: date
    check_out: date
    room_type: str
    num_guests: int = 1
    guest_email: str | None = None


class ReservationOut(BaseModel):
    id: uuid.UUID
    contact_id: uuid.UUID
    room_type: str
    check_in: datetime
    check_out: datetime
    pms_confirmation_number: str | None
    status: str
    confirmation_email_sent: bool = False


def _send_confirmation_email(email: str, appointment: Appointment) -> bool:
    """
    Envoie la confirmation de réservation par email (section 12/16).
    Résilience (section 29) : un échec d'envoi ne doit JAMAIS faire échouer
    la réservation elle-même — elle est déjà actée dans le PMS et le CRM.
    """
    try:
        provider = MockEmailProvider(host=settings.smtp_host, port=settings.smtp_port, from_email=settings.smtp_from_email)
        nights = (appointment.check_out_at - appointment.scheduled_at).days
        body = (
            f"Votre réservation est confirmée.\n\n"
            f"Numéro de confirmation : {appointment.pms_confirmation_number}\n"
            f"Type de chambre : {appointment.room_type}\n"
            f"Arrivée : {appointment.scheduled_at:%d/%m/%Y}\n"
            f"Départ : {appointment.check_out_at:%d/%m/%Y}\n"
            f"Nombre de nuits : {nights}\n\n"
            f"{appointment.notes or ''}\n\n"
            f"À très bientôt !"
        )
        provider.send(
            to_email=email,
            subject=f"Confirmation de réservation — {appointment.pms_confirmation_number}",
            body=body,
        )
        return True
    except Exception:
        logger.exception("Échec de l'envoi de l'email de confirmation pour la réservation %s", appointment.pms_confirmation_number)
        return False


def _book_reservation(
    db: Session, organization_id: uuid.UUID, contact: Contact, check_in: date, check_out: date, room_type: str, guest_email: str | None = None
) -> tuple[Appointment, bool]:
    """Logique de réservation partagée entre le dashboard et les outils Retell."""
    result = pms_provider.create_reservation(
        check_in=check_in,
        check_out=check_out,
        room_type=room_type,
        guest_name=f"{contact.first_name or ''} {contact.last_name or ''}".strip() or contact.phone,
        guest_phone=contact.phone,
    )

    appointment = Appointment(
        organization_id=organization_id,
        contact_id=contact.id,
        scheduled_at=datetime.combine(check_in, datetime.min.time()),
        check_out_at=datetime.combine(check_out, datetime.min.time()),
        duration_minutes=(check_out - check_in).days * 24 * 60,
        status="confirmed",
        room_type=room_type,
        pms_confirmation_number=result["confirmation_number"],
        notes=f"Réservation PMS {result['confirmation_number']} — {result['total_price']} {result['currency']}.",
    )
    db.add(appointment)
    contact.status = "RDV"

    # Mémorise l'email sur le contact s'il n'en avait pas encore, sans
    # écraser une valeur déjà connue (même logique que l'import CSV).
    if guest_email and not contact.email:
        contact.email = guest_email

    db.commit()
    db.refresh(appointment)

    email_to_use = guest_email or contact.email
    email_sent = _send_confirmation_email(email_to_use, appointment) if email_to_use else False

    return appointment, email_sent


# ---------- Endpoints Dashboard (JWT) ----------

@router.post("/availability", response_model=list[AvailabilityOffer])
def check_availability(
    payload: AvailabilityRequest,
    _organization_id: uuid.UUID = Depends(require_organization_access),
):
    try:
        return pms_provider.check_availability(payload.check_in, payload.check_out, payload.room_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/reservations", response_model=ReservationOut)
def create_reservation(
    payload: ReservationRequest,
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    contact = db.query(Contact).filter(
        Contact.id == payload.contact_id, Contact.organization_id == organization_id
    ).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact introuvable pour cette organisation")

    try:
        appointment, email_sent = _book_reservation(
            db, organization_id, contact, payload.check_in, payload.check_out, payload.room_type, payload.guest_email
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ReservationOut(
        id=appointment.id, contact_id=appointment.contact_id, room_type=appointment.room_type,
        check_in=appointment.scheduled_at, check_out=appointment.check_out_at,
        pms_confirmation_number=appointment.pms_confirmation_number, status=appointment.status,
        confirmation_email_sent=email_sent,
    )


# ---------- Endpoints "outils" appelés par Retell PENDANT un vrai appel ----------

class ToolAvailabilityRequest(BaseModel):
    check_in: str
    check_out: str
    room_type: str | None = None


class ToolReservationRequest(BaseModel):
    check_in: str
    check_out: str
    room_type: str
    guest_name: str
    guest_phone: str
    guest_email: str | None = None


@router.post("/tools/availability")
def tool_check_availability(payload: ToolAvailabilityRequest, organization_id: uuid.UUID = Query(...)):
    """
    Appelé par Retell EN DIRECT pendant l'appel (function calling, section
    16) — pas de JWT (Retell ne peut pas s'authentifier comme un
    utilisateur), scopé par organization_id fixé une fois pour toutes au
    provisionnement de l'agent. Réponse pensée pour être lue par le LLM.
    """
    try:
        check_in = date.fromisoformat(payload.check_in)
        check_out = date.fromisoformat(payload.check_out)
        offers = pms_provider.check_availability(check_in, check_out, payload.room_type)
    except ValueError as e:
        return {"available": False, "error": str(e)}

    if not offers:
        return {"available": False, "message": "Aucune chambre disponible pour ces dates."}
    return {"available": True, "offers": offers}


@router.post("/tools/reservations")
def tool_create_reservation(
    payload: ToolReservationRequest,
    organization_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
):
    """
    Crée réellement la réservation pendant l'appel, et envoie la
    confirmation par email si le client l'a donné. Le contact est retrouvé
    (ou créé) par numéro de téléphone — l'agent n'a pas de contact_id du CRM
    à ce stade, seulement ce que dit l'appelant (section 18 : réutilisation
    par numéro, même logique que l'import CSV).
    """
    try:
        check_in = date.fromisoformat(payload.check_in)
        check_out = date.fromisoformat(payload.check_out)
    except ValueError:
        return {"success": False, "error": "Format de date invalide (attendu AAAA-MM-JJ)."}

    contact = db.query(Contact).filter(
        Contact.organization_id == organization_id, Contact.phone == payload.guest_phone
    ).first()
    if not contact:
        contact = Contact(organization_id=organization_id, phone=payload.guest_phone, first_name=payload.guest_name)
        db.add(contact)
        db.flush()

    try:
        appointment, email_sent = _book_reservation(
            db, organization_id, contact, check_in, check_out, payload.room_type, payload.guest_email
        )
    except ValueError as e:
        return {"success": False, "error": str(e)}

    return {
        "success": True,
        "confirmation_number": appointment.pms_confirmation_number,
        "room_type": appointment.room_type,
        "check_in": payload.check_in,
        "check_out": payload.check_out,
        "confirmation_email_sent": email_sent,
    }
