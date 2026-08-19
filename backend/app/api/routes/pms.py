"""
Endpoints PMS (Property Management System — section 5/16 du cahier des
charges). Vérification de disponibilité et création de réservation pour
l'agent réceptionniste hôtelier, via l'abstraction PMSProvider.
"""
import logging
import uuid
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_organization_access
from app.models.appointment import Appointment
from app.models.contact import Contact
from app.providers.pms.mock import MockPMSProvider

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


class ReservationOut(BaseModel):
    id: uuid.UUID
    contact_id: uuid.UUID
    room_type: str
    check_in: datetime
    check_out: datetime
    pms_confirmation_number: str | None
    status: str


@router.post("/availability", response_model=list[AvailabilityOffer])
def check_availability(
    payload: AvailabilityRequest,
    _organization_id: uuid.UUID = Depends(require_organization_access),
):
    try:
        offers = pms_provider.check_availability(payload.check_in, payload.check_out, payload.room_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return offers


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

    guest_name = f"{contact.first_name or ''} {contact.last_name or ''}".strip() or contact.phone

    try:
        result = pms_provider.create_reservation(
            check_in=payload.check_in,
            check_out=payload.check_out,
            room_type=payload.room_type,
            guest_name=guest_name,
            guest_phone=contact.phone,
            num_guests=payload.num_guests,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    appointment = Appointment(
        organization_id=organization_id,
        contact_id=contact.id,
        scheduled_at=datetime.combine(payload.check_in, datetime.min.time()),
        check_out_at=datetime.combine(payload.check_out, datetime.min.time()),
        duration_minutes=(payload.check_out - payload.check_in).days * 24 * 60,
        status="confirmed",
        room_type=payload.room_type,
        pms_confirmation_number=result["confirmation_number"],
        notes=f"Réservation PMS {result['confirmation_number']} — {result['total_price']} {result['currency']}.",
    )
    db.add(appointment)
    contact.status = "RDV"
    db.commit()
    db.refresh(appointment)

    return ReservationOut(
        id=appointment.id,
        contact_id=appointment.contact_id,
        room_type=appointment.room_type,
        check_in=appointment.scheduled_at,
        check_out=appointment.check_out_at,
        pms_confirmation_number=appointment.pms_confirmation_number,
        status=appointment.status,
    )
