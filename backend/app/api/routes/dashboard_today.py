"""
Tableau de bord "Aujourd'hui" (section 12/16 du cahier des charges) — brief
opérationnel pour le personnel qui reprend la main chaque matin après une
nuit gérée entièrement par l'agent IA (24h/24). Regroupe en une seule vue
ce qui, autrement, serait éparpillé entre Rendez-vous, Messages et Tickets.
"""
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_organization_access
from app.models.appointment import Appointment
from app.models.contact import Contact
from app.models.message import Message
from app.models.ticket import Ticket
from app.models.call import Call

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Fenêtre considérée comme "la nuit" pour le résumé d'activité (section 12).
OVERNIGHT_WINDOW_HOURS = 12


def _contact_label(contact: Contact | None) -> str:
    if not contact:
        return "Contact inconnu"
    return f"{contact.first_name or ''} {contact.last_name or ''}".strip() or contact.phone


class ReservationBrief(BaseModel):
    appointment_id: uuid.UUID
    contact_name: str
    contact_phone: str
    room_type: str | None
    check_in: datetime
    check_out: datetime | None
    status: str


class MessageBrief(BaseModel):
    message_id: uuid.UUID
    caller_name: str | None
    caller_phone: str
    content: str
    urgent: bool
    created_at: datetime


class TicketBrief(BaseModel):
    ticket_id: uuid.UUID
    subject: str
    category: str | None
    priority: str
    status: str


class OvernightSummary(BaseModel):
    since: datetime
    total_calls: int
    reservations_made: int


class TodayDashboardOut(BaseModel):
    arrivals_today: list[ReservationBrief]
    departures_today: list[ReservationBrief]
    pending_messages: list[MessageBrief]
    open_tickets: list[TicketBrief]
    overnight_summary: OvernightSummary


@router.get("/today", response_model=TodayDashboardOut)
def get_today_dashboard(
    db: Session = Depends(get_db),
    organization_id: uuid.UUID = Depends(require_organization_access),
):
    now = datetime.utcnow()
    today_start = datetime.combine(now.date(), datetime.min.time())
    today_end = today_start + timedelta(days=1)
    since = now - timedelta(hours=OVERNIGHT_WINDOW_HOURS)

    # Arrivées / départs du jour (uniquement les réservations hôtelières,
    # identifiées par room_type non nul — section 16).
    reservations = (
        db.query(Appointment)
        .filter(Appointment.organization_id == organization_id, Appointment.room_type.isnot(None))
        .all()
    )
    contacts_by_id = {c.id: c for c in db.query(Contact).filter(Contact.organization_id == organization_id).all()}

    arrivals = [
        ReservationBrief(
            appointment_id=a.id,
            contact_name=_contact_label(contacts_by_id.get(a.contact_id)),
            contact_phone=contacts_by_id.get(a.contact_id).phone if contacts_by_id.get(a.contact_id) else "",
            room_type=a.room_type,
            check_in=a.scheduled_at,
            check_out=a.check_out_at,
            status=a.status,
        )
        for a in reservations
        if a.status != "cancelled" and today_start <= a.scheduled_at < today_end
    ]
    departures = [
        ReservationBrief(
            appointment_id=a.id,
            contact_name=_contact_label(contacts_by_id.get(a.contact_id)),
            contact_phone=contacts_by_id.get(a.contact_id).phone if contacts_by_id.get(a.contact_id) else "",
            room_type=a.room_type,
            check_in=a.scheduled_at,
            check_out=a.check_out_at,
            status=a.status,
        )
        for a in reservations
        if a.status != "cancelled" and a.check_out_at and today_start <= a.check_out_at < today_end
    ]

    # Messages non encore traités (télé-secrétariat, section 12)
    pending_messages = (
        db.query(Message)
        .filter(Message.organization_id == organization_id, Message.status != "handled")
        .order_by(Message.urgent.desc(), Message.created_at.desc())
        .limit(20)
        .all()
    )

    # Tickets encore ouverts (service client, section 1)
    open_tickets = (
        db.query(Ticket)
        .filter(Ticket.organization_id == organization_id, Ticket.status.in_(["ouvert", "en_cours"]))
        .order_by(Ticket.priority.desc(), Ticket.created_at.desc())
        .limit(20)
        .all()
    )

    # Résumé de l'activité de la nuit (calls + réservations créées)
    overnight_calls = (
        db.query(Call)
        .filter(Call.organization_id == organization_id, Call.started_at >= since)
        .count()
    )
    overnight_reservations = (
        db.query(Appointment)
        .filter(
            Appointment.organization_id == organization_id,
            Appointment.room_type.isnot(None),
            Appointment.created_at >= since,
        )
        .count()
    )

    return TodayDashboardOut(
        arrivals_today=arrivals,
        departures_today=departures,
        pending_messages=[
            MessageBrief(
                message_id=m.id, caller_name=m.caller_name, caller_phone=m.caller_phone,
                content=m.content, urgent=m.urgent, created_at=m.created_at,
            )
            for m in pending_messages
        ],
        open_tickets=[
            TicketBrief(ticket_id=t.id, subject=t.subject, category=t.category, priority=t.priority, status=t.status)
            for t in open_tickets
        ],
        overnight_summary=OvernightSummary(
            since=since, total_calls=overnight_calls, reservations_made=overnight_reservations
        ),
    )
