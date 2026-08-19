"""
Rendez-vous (section 30 du cahier des charges : POST /appointments).
Créé automatiquement quand un appel aboutit à "Rendez-vous pris" (section 19
et 41 — prospection commerciale), ou manuellement depuis le Dashboard.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Text

from app.core.database import Base
from app.models.distributor import GUID


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    organization_id = Column(GUID(), ForeignKey("organizations.id"), nullable=False)
    contact_id = Column(GUID(), ForeignKey("contacts.id"), nullable=False)
    agent_id = Column(GUID(), ForeignKey("agents.id"), nullable=True)
    call_id = Column(GUID(), ForeignKey("calls.id"), nullable=True)

    scheduled_at = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, default=30)
    status = Column(String, default="scheduled")  # scheduled | confirmed | cancelled | completed
    notes = Column(Text, nullable=True)

    # Réservation hôtelière (PMS, section 16 — intégration réelle) : quand
    # renseignés, ces champs indiquent que ce rendez-vous est en réalité une
    # réservation de chambre, avec sa confirmation côté PMS (Mock ou réel).
    # `scheduled_at` sert alors de date d'arrivée (check-in).
    room_type = Column(String, nullable=True)
    check_out_at = Column(DateTime, nullable=True)
    pms_confirmation_number = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
