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
from app.core.providers import get_messaging_provider

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
    confirmation_sms_sent: bool = False


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


def _send_confirmation_sms(db: Session, organization_id: uuid.UUID, phone: str, appointment: Appointment) -> bool:
    """
    Envoie la confirmation de réservation par SMS, en complément de l'email
    (section 12/16). Résilience (section 29) : un échec d'envoi ne doit
    JAMAIS faire échouer la réservation elle-même.
    """
    try:
        provider = get_messaging_provider(db, organization_id)
        body = (
            f"Réservation confirmée n°{appointment.pms_confirmation_number} — "
            f"{appointment.room_type}, du {appointment.scheduled_at:%d/%m} au {appointment.check_out_at:%d/%m}."
        )
        provider.send_sms(to_number=phone, body=body)
        return True
    except Exception:
        logger.exception("Échec de l'envoi du SMS de confirmation pour la réservation %s", appointment.pms_confirmation_number)
        return False


def _book_reservation(
    db: Session, organization_id: uuid.UUID, contact: Contact, check_in: date, check_out: date, room_type: str, guest_email: str | None = None
) -> tuple[Appointment, bool, bool]:
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
    sms_sent = _send_confirmation_sms(db, organization_id, contact.phone, appointment)

    return appointment, email_sent, sms_sent


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
        appointment, email_sent, sms_sent = _book_reservation(
            db, organization_id, contact, payload.check_in, payload.check_out, payload.room_type, payload.guest_email
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ReservationOut(
        id=appointment.id, contact_id=appointment.contact_id, room_type=appointment.room_type,
        check_in=appointment.scheduled_at, check_out=appointment.check_out_at,
        pms_confirmation_number=appointment.pms_confirmation_number, status=appointment.status,
        confirmation_email_sent=email_sent, confirmation_sms_sent=sms_sent,
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
    logger.info(
        "Outil check_room_availability appelé : org=%s check_in=%r check_out=%r room_type=%r",
        organization_id, payload.check_in, payload.check_out, payload.room_type,
    )
    try:
        check_in = date.fromisoformat(payload.check_in)
        check_out = date.fromisoformat(payload.check_out)
        offers = pms_provider.check_availability(check_in, check_out, payload.room_type)
    except ValueError as e:
        logger.warning("check_room_availability : ValueError -> %s", e)
        return {"available": False, "error": str(e)}
    except Exception:
        logger.exception("check_room_availability : erreur inattendue")
        return {"available": False, "error": "Erreur technique lors de la vérification."}

    if not offers:
        logger.info("check_room_availability : aucune offre disponible pour cette demande")
        return {"available": False, "message": "Aucune chambre disponible pour ces dates."}
    logger.info("check_room_availability : %d offre(s) trouvée(s)", len(offers))
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
    logger.info(
        "Outil create_room_reservation appelé : org=%s check_in=%r check_out=%r room_type=%r guest_phone=%r guest_email=%r",
        organization_id, payload.check_in, payload.check_out, payload.room_type, payload.guest_phone, payload.guest_email,
    )
    try:
        check_in = date.fromisoformat(payload.check_in)
        check_out = date.fromisoformat(payload.check_out)
    except ValueError:
        logger.warning("create_room_reservation : format de date invalide (%r, %r)", payload.check_in, payload.check_out)
        return {"success": False, "error": "Format de date invalide (attendu AAAA-MM-JJ)."}

    contact = db.query(Contact).filter(
        Contact.organization_id == organization_id, Contact.phone == payload.guest_phone
    ).first()
    if not contact:
        contact = Contact(organization_id=organization_id, phone=payload.guest_phone, first_name=payload.guest_name)
        db.add(contact)
        db.flush()

    try:
        appointment, email_sent, sms_sent = _book_reservation(
            db, organization_id, contact, check_in, check_out, payload.room_type, payload.guest_email
        )
    except ValueError as e:
        logger.warning("create_room_reservation : ValueError -> %s", e)
        return {"success": False, "error": str(e)}

    logger.info("create_room_reservation : succès, confirmation=%s", appointment.pms_confirmation_number)
    return {
        "success": True,
        "confirmation_number": appointment.pms_confirmation_number,
        "room_type": appointment.room_type,
        "check_in": payload.check_in,
        "check_out": payload.check_out,
        "confirmation_email_sent": email_sent,
        "confirmation_sms_sent": sms_sent,
    }


class ToolFindReservationRequest(BaseModel):
    guest_phone: str
    confirmation_number: str | None = None


class ToolModifyReservationRequest(BaseModel):
    confirmation_number: str
    new_check_in: str | None = None
    new_check_out: str | None = None
    new_room_type: str | None = None


class ToolCancelReservationRequest(BaseModel):
    confirmation_number: str


@router.post("/tools/find-reservation")
def tool_find_reservation(payload: ToolFindReservationRequest, organization_id: uuid.UUID = Query(...), db: Session = Depends(get_db)):
    """
    Retrouve les réservations actives d'un client, par téléphone (le contact
    n'a pas forcément le numéro de confirmation en tête) ou par numéro de
    confirmation direct. Utilisé avant une modification ou une annulation
    pendant l'appel (section 16).
    """
    query = db.query(Appointment).filter(
        Appointment.organization_id == organization_id,
        Appointment.room_type.isnot(None),  # uniquement les réservations hôtelières
        Appointment.status != "cancelled",
    )
    if payload.confirmation_number:
        query = query.filter(Appointment.pms_confirmation_number == payload.confirmation_number)
    else:
        query = query.join(Contact, Contact.id == Appointment.contact_id).filter(Contact.phone == payload.guest_phone)

    appointments = query.order_by(Appointment.scheduled_at.desc()).all()

    if not appointments:
        return {"found": False, "message": "Aucune réservation active trouvée pour ce numéro."}

    return {
        "found": True,
        "reservations": [
            {
                "confirmation_number": a.pms_confirmation_number,
                "room_type": a.room_type,
                "check_in": a.scheduled_at.date().isoformat(),
                "check_out": a.check_out_at.date().isoformat() if a.check_out_at else None,
                "status": a.status,
            }
            for a in appointments
        ],
    }


@router.post("/tools/modify-reservation")
def tool_modify_reservation(payload: ToolModifyReservationRequest, organization_id: uuid.UUID = Query(...), db: Session = Depends(get_db)):
    """
    Modifie les dates et/ou le type de chambre d'une réservation existante,
    EN DIRECT pendant l'appel — vérifie d'abord la disponibilité des
    nouvelles dates avant de confirmer le changement (section 16).
    """
    appointment = db.query(Appointment).filter(
        Appointment.organization_id == organization_id,
        Appointment.pms_confirmation_number == payload.confirmation_number,
    ).first()
    if not appointment or appointment.status == "cancelled":
        return {"success": False, "error": "Réservation introuvable ou déjà annulée."}

    new_check_in = date.fromisoformat(payload.new_check_in) if payload.new_check_in else appointment.scheduled_at.date()
    new_check_out = date.fromisoformat(payload.new_check_out) if payload.new_check_out else appointment.check_out_at.date()
    new_room_type = payload.new_room_type or appointment.room_type

    try:
        result = pms_provider.modify_reservation(payload.confirmation_number, new_check_in, new_check_out, new_room_type)
    except ValueError as e:
        return {"success": False, "error": str(e)}

    appointment.scheduled_at = datetime.combine(new_check_in, datetime.min.time())
    appointment.check_out_at = datetime.combine(new_check_out, datetime.min.time())
    appointment.room_type = new_room_type
    appointment.duration_minutes = (new_check_out - new_check_in).days * 24 * 60
    appointment.notes = f"Réservation modifiée — {result['total_price']} {result['currency']}."
    db.commit()

    return {
        "success": True,
        "confirmation_number": appointment.pms_confirmation_number,
        "room_type": new_room_type,
        "check_in": new_check_in.isoformat(),
        "check_out": new_check_out.isoformat(),
    }


@router.post("/tools/cancel-reservation")
def tool_cancel_reservation(payload: ToolCancelReservationRequest, organization_id: uuid.UUID = Query(...), db: Session = Depends(get_db)):
    """Annule une réservation EN DIRECT pendant l'appel (section 16)."""
    appointment = db.query(Appointment).filter(
        Appointment.organization_id == organization_id,
        Appointment.pms_confirmation_number == payload.confirmation_number,
    ).first()
    if not appointment:
        return {"success": False, "error": "Réservation introuvable."}
    if appointment.status == "cancelled":
        return {"success": True, "already_cancelled": True}

    try:
        pms_provider.cancel_reservation(payload.confirmation_number)
    except Exception:
        logger.exception("Échec de l'annulation PMS pour %s", payload.confirmation_number)

    appointment.status = "cancelled"
    db.commit()

    return {"success": True, "confirmation_number": payload.confirmation_number}
