"""
Appel (sections 12 et 13 du cahier des charges).
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Text

from app.core.database import Base
from app.models.distributor import GUID


class Call(Base):
    __tablename__ = "calls"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    organization_id = Column(GUID(), ForeignKey("organizations.id"), nullable=False)
    agent_id = Column(GUID(), ForeignKey("agents.id"), nullable=False)
    contact_id = Column(GUID(), ForeignKey("contacts.id"), nullable=True)

    direction = Column(String, nullable=False)  # inbound | outbound
    status = Column(String, default="completed")
    provider = Column(String, default="mock")
    provider_call_id = Column(String, nullable=True)
    duration_seconds = Column(Integer, default=0)
    transcript = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)

    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
