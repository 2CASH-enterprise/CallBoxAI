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

    created_at = Column(DateTime, default=datetime.utcnow)
