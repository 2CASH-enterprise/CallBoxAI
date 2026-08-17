"""
Agent IA (section 8 du cahier des charges).
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey, Text

from app.core.database import Base
from app.models.distributor import GUID


class Agent(Base):
    __tablename__ = "agents"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    organization_id = Column(GUID(), ForeignKey("organizations.id"), nullable=False)

    name = Column(String, nullable=False)
    objective = Column(String, nullable=True)
    language = Column(String, default="fr")
    system_prompt = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
