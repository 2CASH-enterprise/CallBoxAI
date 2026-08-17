"""
Agent IA (section 8 du cahier des charges).
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Boolean

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

    # Règles de transfert vers un opérateur humain (section 8 et 11 du cahier
    # des charges) : numéro/poste à joindre, et instructions optionnelles
    # décrivant dans quels cas transférer (ex. "demande hors compétence").
    transfer_enabled = Column(Boolean, default=False)
    transfer_number = Column(String, nullable=True)
    transfer_instructions = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
