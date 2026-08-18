"""
Ticket de service client (section 1 et 12 du cahier des charges).
Créé automatiquement quand un agent avec ticketing_enabled=True reçoit un
appel entrant, pour donner un suivi structuré (au-delà du simple transcript).
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey, Text

from app.core.database import Base
from app.models.distributor import GUID

VALID_PRIORITIES = {"basse", "normale", "haute", "urgente"}
VALID_STATUSES = {"ouvert", "en_cours", "résolu", "fermé"}


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    organization_id = Column(GUID(), ForeignKey("organizations.id"), nullable=False)
    agent_id = Column(GUID(), ForeignKey("agents.id"), nullable=False)
    call_id = Column(GUID(), ForeignKey("calls.id"), nullable=True)
    contact_id = Column(GUID(), ForeignKey("contacts.id"), nullable=True)

    subject = Column(String, nullable=False)
    category = Column(String, nullable=True)  # ex. "Réclamation", "Support technique"
    priority = Column(String, default="normale")
    status = Column(String, default="ouvert")
    description = Column(Text, nullable=True)
    resolution_notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
