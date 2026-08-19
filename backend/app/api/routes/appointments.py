"""
Endpoints Rendez-vous (section 30 du cahier des charges : POST /appointments).
Créés automatiquement par le pipeline d'appel (section 19/41 — prospection
commerciale) quand un appel aboutit à "Rendez-vous pris", manuellement, ou
via une réservation PMS (section 16 — voir app.api.routes.pms).
"""
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_organization_access
from app.models.appointment import Appointment
from app.models.contact import Contact
from app.providers.pms.mock import MockPMSProvider

logger = logging.getLogger(__name__)

router = APIRouter()

VALID_STATUSES = {"scheduled", "confirmed", "cancelled", "completed"}

pms_provider = MockPMSProvider()


class AppointmentCreate(BaseModel):
    contact_id: uuid.UUID
    scheduled_at: datetime
    duration_minutes: int = 30
    notes: str | None = None


class AppointmentUpdate(BaseModel):
    status: str | None = None
    scheduled_at: datetime | None = None
    notes: str | None = None


class AppointmentOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    contact_id: uuid.UUID
    agent_id: uuid.UUID | None
    call_id: uuid.UUID | None
    scheduled_at: datetime
    duration_minutes: int
    status: str
    notes: str | None
    room_type: str | None
    check_out_at: datetime | None
    pms_confirmation_number: str | None
    created_at: datetime

    class Config:
        from_attributes = True


@router.post("/appointments", response_model=AppointmentOut)
def create_appointment(
    payload: AppointmentCreate,
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    contact = db.query(Contact).filter(
        Contact.id == payload.contact_id, Contact.organization_id == organization_id
    ).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact introuvable pour cette organisation")

    appointment = Appointment(organization_id=organization_id, **payload.model_dump())
    db.add(appointment)
    contact.status = "RDV"
    db.commit()
    db.refresh(appointment)
    return appointment


@router.get("/appointments", response_model=list[AppointmentOut])
def list_appointments(
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    return (
        db.query(Appointment)
        .filter(Appointment.organization_id == organization_id)
        .order_by(Appointment.scheduled_at.asc())
        .all()
    )


@router.patch("/appointments/{appointment_id}", response_model=AppointmentOut)
def update_appointment(
    appointment_id: uuid.UUID,
    payload: AppointmentUpdate,
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    appointment = db.query(Appointment).filter(
        Appointment.id == appointment_id, Appointment.organization_id == organization_id
    ).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable pour cette organisation")

    if payload.status is not None:
        if payload.status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail="Statut invalide")

        # Répercute l'annulation vers le PMS si c'est une réservation
        # hôtelière (section 16). Résilience (section 29) : un échec côté
        # PMS ne doit jamais empêcher l'annulation locale.
        if payload.status == "cancelled" and appointment.pms_confirmation_number:
            try:
                pms_provider.cancel_reservation(appointment.pms_confirmation_number)
            except Exception:
                logger.exception(
                    "Échec de l'annulation PMS pour la réservation %s", appointment.pms_confirmation_number
                )

        appointment.status = payload.status
    if payload.scheduled_at is not None:
        appointment.scheduled_at = payload.scheduled_at
    if payload.notes is not None:
        appointment.notes = payload.notes

    db.commit()
    db.refresh(appointment)
    return appointment
