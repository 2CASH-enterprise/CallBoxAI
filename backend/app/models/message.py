"""
Message pris par l'agent en dehors des horaires d'ouverture, ou quand
personne n'est disponible pour répondre (télé-secrétariat — section 12).
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Boolean

from app.core.database import Base
from app.models.distributor import GUID


class Message(Base):
    __tablename__ = "messages"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    organization_id = Column(GUID(), ForeignKey("organizations.id"), nullable=False)
    agent_id = Column(GUID(), ForeignKey("agents.id"), nullable=False)
    call_id = Column(GUID(), ForeignKey("calls.id"), nullable=True)
    contact_id = Column(GUID(), ForeignKey("contacts.id"), nullable=True)

    caller_phone = Column(String, nullable=False)
    caller_name = Column(String, nullable=True)
    content = Column(Text, nullable=False)
    urgent = Column(Boolean, default=False)
    callback_requested = Column(Boolean, default=True)
    status = Column(String, default="new")  # new | read | handled

    created_at = Column(DateTime, default=datetime.utcnow)
